"""Deception and attribution for the console front door.

The publicly reachable login is a decoy. Credentials submitted there never
authenticate anything; after a configurable number of failures the client is
handed a *sandbox* session instead, and the console it then sees is rendered
entirely from synthetic data. That buys two things: an intruder spends their
time on fabricated infrastructure, and every action they take becomes evidence.

Attribution here is deliberately passive. Everything recorded is derived from
what the client already sent, so observation costs no extra round trip and is
invisible to the source. The engine performs no scanning, no callbacks, and no
active identification of the observed host: those would be unreliable against a
proxied attacker and are not the operator's to perform. Optional reverse-DNS
enrichment is the single outbound lookup available, and it is off by default.

Submitted passwords are never stored. Only a salted digest prefix is kept, which
is enough to correlate "the same password was retried" without turning the
evidence file into a credential dump — attempted passwords are frequently real
secrets reused from elsewhere.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import statistics
import threading
import time
from dataclasses import dataclass, field
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Callable, Optional

from backend.security.client_identity import ClientIdentity, credential_digest

EVIDENCE_FILE_NAME = "incidents.jsonl"
MAX_TRACKED_VALUES = 24
MAX_TRACKED_INTERVALS = 64
MAX_ACTIVITY_ENTRIES = 40
EVIDENCE_LINE_LIMIT = 8000

# Ordered by increasing severity so a numeric comparison stays readable.
SEVERITY_ORDER = ("info", "low", "medium", "high", "critical")


def _now_iso(timestamp: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp))


def _network_scope(value: str) -> str:
    """Classify an address offline, with no lookup of any kind."""
    try:
        address = ip_address(value)
    except ValueError:
        return "unknown"
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link_local"
    if address.is_private:
        return "private"
    if address.is_reserved or address.is_multicast:
        return "reserved"
    return "global"


@dataclass
class SourceDossier:
    """Accumulated observations for one source address."""

    source: str
    first_seen: float
    last_seen: float
    login_failures: int = 0
    gate_failures: int = 0
    login_successes: int = 0
    sandbox_sessions: int = 0
    sandbox_requests: int = 0
    usernames: list[str] = field(default_factory=list)
    credential_digests: list[str] = field(default_factory=list)
    user_agents: list[str] = field(default_factory=list)
    fingerprints: list[str] = field(default_factory=list)
    intervals: list[float] = field(default_factory=list)
    activity: list[dict[str, Any]] = field(default_factory=list)
    forwarded_chain: tuple[str, ...] = ()
    proxy_trusted: bool = False
    automated_agent: bool = False
    reverse_dns: str = ""
    sandbox_active: bool = False

    @property
    def total_attempts(self) -> int:
        return self.login_failures + self.gate_failures

    @property
    def median_interval(self) -> Optional[float]:
        if len(self.intervals) < 2:
            return None
        return round(statistics.median(self.intervals), 3)

    def classification(self) -> str:
        """Best-effort label for how the source is behaving.

        Heuristic and advisory only: it annotates evidence for a human reviewer
        and never gates a security decision.
        """
        if self.total_attempts == 0:
            return "observed"
        interval = self.median_interval
        machine_paced = interval is not None and interval < 1.5
        if len(self.usernames) >= 4:
            return "credential_stuffing"
        if len(self.credential_digests) >= 5 and len(self.usernames) <= 2:
            return "password_brute_force"
        if machine_paced and self.total_attempts >= 5:
            return "automated_bruteforce"
        if self.automated_agent and self.total_attempts >= 2:
            return "automated_tooling"
        return "manual_probing"

    def severity(self) -> str:
        attempts = self.total_attempts
        if self.sandbox_requests >= 5 or attempts >= 25:
            return "critical"
        if self.sandbox_active or attempts >= 10:
            return "high"
        # Aligned with the default sandbox trigger: by the time a source has
        # burned this many attempts it is no longer a plausible typo.
        if attempts >= 3:
            return "medium"
        if attempts >= 1:
            return "low"
        return "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "network_scope": _network_scope(self.source),
            "first_seen": _now_iso(self.first_seen),
            "last_seen": _now_iso(self.last_seen),
            "observed_seconds": round(max(0.0, self.last_seen - self.first_seen), 3),
            "login_failures": self.login_failures,
            "gate_failures": self.gate_failures,
            "login_successes": self.login_successes,
            "sandbox_sessions": self.sandbox_sessions,
            "sandbox_requests": self.sandbox_requests,
            "total_attempts": self.total_attempts,
            "usernames_tried": list(self.usernames),
            "distinct_passwords": len(self.credential_digests),
            "credential_digests": list(self.credential_digests),
            "user_agents": list(self.user_agents),
            "fingerprints": list(self.fingerprints),
            "median_interval_seconds": self.median_interval,
            "forwarded_chain": list(self.forwarded_chain),
            "proxy_trusted": self.proxy_trusted,
            "automated_agent": self.automated_agent,
            "reverse_dns": self.reverse_dns,
            "sandbox_active": self.sandbox_active,
            "classification": self.classification(),
            "severity": self.severity(),
            "recent_activity": list(self.activity[-MAX_ACTIVITY_ENTRIES:]),
        }


class DeceptionEngine:
    """Records front-door activity and decides when to open a sandbox."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        evidence_dir: Path | str = "",
        trigger_attempts: int = 3,
        max_evidence_bytes: int = 32 * 1024 * 1024,
        max_sources: int = 4096,
        reverse_dns: bool = False,
        reverse_dns_timeout: float = 1.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = bool(enabled)
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        self.trigger_attempts = max(1, min(int(trigger_attempts), 100))
        self.max_evidence_bytes = max(64 * 1024, int(max_evidence_bytes))
        self.max_sources = max(16, min(int(max_sources), 100_000))
        self.reverse_dns = bool(reverse_dns)
        self.reverse_dns_timeout = max(0.1, min(float(reverse_dns_timeout), 5.0))
        self._clock = clock
        self._lock = threading.RLock()
        self._sources: dict[str, SourceDossier] = {}
        self._sandbox_owner: dict[str, str] = {}
        self._credential_salt = secrets.token_bytes(16)
        self._reverse_dns_cache: dict[str, str] = {}
        self._evidence_error = ""

    # ---------------------------------------------------------------- observe

    def record_login_failure(
        self,
        client: ClientIdentity,
        username: str,
        password: str,
        *,
        reason: str = "invalid_credentials",
    ) -> dict[str, Any]:
        with self._lock:
            dossier = self._touch(client)
            dossier.login_failures += 1
            self._track(dossier.usernames, str(username)[:128])
            self._track(
                dossier.credential_digests,
                credential_digest(password, self._credential_salt),
            )
            self._append_activity(dossier, "login_failure", {"username": str(username)[:128]})
            snapshot = dossier.to_dict()
        self._write_evidence("login_failure", client, snapshot, {"reason": reason})
        return snapshot

    def record_gate_failure(self, client: ClientIdentity, *, reason: str = "invalid_passphrase") -> dict[str, Any]:
        with self._lock:
            dossier = self._touch(client)
            dossier.gate_failures += 1
            self._append_activity(dossier, "gate_failure", {"reason": reason})
            snapshot = dossier.to_dict()
        self._write_evidence("gate_failure", client, snapshot, {"reason": reason})
        return snapshot

    def record_login_success(self, client: ClientIdentity, username: str) -> dict[str, Any]:
        with self._lock:
            dossier = self._touch(client)
            dossier.login_successes += 1
            dossier.login_failures = 0
            dossier.gate_failures = 0
            self._append_activity(dossier, "login_success", {"username": str(username)[:128]})
            snapshot = dossier.to_dict()
        self._write_evidence("login_success", client, snapshot, {"reason": "authenticated"})
        return snapshot

    def record_sandbox_opened(self, client: ClientIdentity, sandbox_id: str) -> dict[str, Any]:
        with self._lock:
            dossier = self._touch(client)
            dossier.sandbox_sessions += 1
            dossier.sandbox_active = True
            self._sandbox_owner[str(sandbox_id)] = dossier.source
            self._append_activity(dossier, "sandbox_opened", {"sandbox_id": str(sandbox_id)})
            snapshot = dossier.to_dict()
        self._write_evidence(
            "sandbox_opened",
            client,
            snapshot,
            {"reason": "credential_attempts_exceeded", "sandbox_id": str(sandbox_id)},
        )
        return snapshot

    def record_sandbox_activity(
        self,
        client: ClientIdentity,
        sandbox_id: str,
        method: str,
        path: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        with self._lock:
            dossier = self._touch(client)
            dossier.sandbox_requests += 1
            dossier.sandbox_active = True
            self._sandbox_owner.setdefault(str(sandbox_id), dossier.source)
            self._append_activity(
                dossier,
                "sandbox_request",
                {
                    "method": str(method).upper()[:8],
                    "path": str(path)[:256],
                    **(detail or {}),
                },
            )
            snapshot = dossier.to_dict()
        self._write_evidence(
            "sandbox_request",
            client,
            snapshot,
            {
                "sandbox_id": str(sandbox_id),
                "method": str(method).upper()[:8],
                "path": str(path)[:256],
                **(detail or {}),
            },
        )
        return snapshot

    # --------------------------------------------------------------- decision

    def should_open_sandbox(self, client: ClientIdentity) -> bool:
        """True once a source has burned through its credible attempt budget."""
        if not self.enabled:
            return False
        with self._lock:
            dossier = self._sources.get(client.rate_limit_key)
            if dossier is None:
                return False
            return dossier.login_failures >= self.trigger_attempts

    # -------------------------------------------------------------- reporting

    def dossier(self, source: str) -> Optional[dict[str, Any]]:
        with self._lock:
            found = self._sources.get(str(source))
            return found.to_dict() if found else None

    def dossiers(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        with self._lock:
            ordered = sorted(
                self._sources.values(),
                key=lambda item: item.last_seen,
                reverse=True,
            )
            return [item.to_dict() for item in ordered[:bounded]]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            dossiers = list(self._sources.values())
            active = [item for item in dossiers if item.sandbox_active]
            return {
                "enabled": self.enabled,
                "trigger_attempts": self.trigger_attempts,
                "tracked_sources": len(dossiers),
                "sandbox_sessions_open": len(active),
                "total_login_failures": sum(item.login_failures for item in dossiers),
                "total_gate_failures": sum(item.gate_failures for item in dossiers),
                "total_sandbox_requests": sum(item.sandbox_requests for item in dossiers),
                "highest_severity": self._highest_severity(dossiers),
                "evidence_path": str(self._evidence_path()) if self.evidence_dir else "",
                "evidence_error": self._evidence_error,
                "reverse_dns_enabled": self.reverse_dns,
            }

    def sandbox_owner(self, sandbox_id: str) -> str:
        with self._lock:
            return self._sandbox_owner.get(str(sandbox_id), "")

    def reset(self) -> None:
        """Clear in-memory state. Evidence already written stays on disk."""
        with self._lock:
            self._sources.clear()
            self._sandbox_owner.clear()
            self._evidence_error = ""

    # ---------------------------------------------------------------- private

    @staticmethod
    def _highest_severity(dossiers: list[SourceDossier]) -> str:
        highest = "info"
        for item in dossiers:
            candidate = item.severity()
            if SEVERITY_ORDER.index(candidate) > SEVERITY_ORDER.index(highest):
                highest = candidate
        return highest

    def _touch(self, client: ClientIdentity) -> SourceDossier:
        """Fetch or create the dossier for a source, bounding total memory."""
        now = self._clock()
        key = client.rate_limit_key
        dossier = self._sources.get(key)
        if dossier is None:
            if len(self._sources) >= self.max_sources:
                self._evict_oldest()
            dossier = SourceDossier(source=key, first_seen=now, last_seen=now)
            self._sources[key] = dossier
        else:
            interval = now - dossier.last_seen
            if 0 <= interval <= 3600:
                dossier.intervals.append(round(interval, 3))
                del dossier.intervals[:-MAX_TRACKED_INTERVALS]
            dossier.last_seen = now

        dossier.forwarded_chain = client.forwarded_chain
        dossier.proxy_trusted = client.proxy_trusted
        dossier.automated_agent = dossier.automated_agent or client.automated_agent
        self._track(dossier.user_agents, client.user_agent or "(absent)")
        self._track(dossier.fingerprints, client.fingerprint)
        if self.reverse_dns and not dossier.reverse_dns:
            dossier.reverse_dns = self._resolve_reverse_dns(key)
        return dossier

    def _evict_oldest(self) -> None:
        oldest = min(self._sources.items(), key=lambda item: item[1].last_seen, default=None)
        if oldest is None:
            return
        source = oldest[0]
        self._sources.pop(source, None)
        for sandbox_id, owner in list(self._sandbox_owner.items()):
            if owner == source:
                self._sandbox_owner.pop(sandbox_id, None)

    @staticmethod
    def _track(values: list[str], candidate: str) -> None:
        text = str(candidate)
        if text and text not in values:
            values.append(text)
            del values[:-MAX_TRACKED_VALUES]

    def _append_activity(self, dossier: SourceDossier, event: str, detail: dict[str, Any]) -> None:
        dossier.activity.append(
            {"at": _now_iso(self._clock()), "event": event, **detail}
        )
        del dossier.activity[:-MAX_ACTIVITY_ENTRIES]

    def _resolve_reverse_dns(self, source: str) -> str:
        """Opt-in PTR lookup. Never raises; a failure simply yields no name."""
        cached = self._reverse_dns_cache.get(source)
        if cached is not None:
            return cached
        name = ""
        previous = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(self.reverse_dns_timeout)
            name = socket.gethostbyaddr(source)[0]
        except (OSError, UnicodeError, IndexError):
            name = ""
        finally:
            try:
                socket.setdefaulttimeout(previous)
            except Exception:
                pass
        self._reverse_dns_cache[source] = name
        return name

    def _evidence_path(self) -> Path:
        assert self.evidence_dir is not None
        return self.evidence_dir / EVIDENCE_FILE_NAME

    def _write_evidence(
        self,
        event: str,
        client: ClientIdentity,
        dossier: dict[str, Any],
        detail: dict[str, Any],
    ) -> None:
        """Append one evidence record. Never raises into the request path."""
        if not self.evidence_dir:
            return
        record = {
            "at": _now_iso(self._clock()),
            "event": event,
            "severity": dossier.get("severity", "info"),
            "classification": dossier.get("classification", "observed"),
            "client": client.to_dict(),
            "detail": detail,
            "dossier": {
                key: dossier.get(key)
                for key in (
                    "source",
                    "network_scope",
                    "first_seen",
                    "last_seen",
                    "login_failures",
                    "gate_failures",
                    "sandbox_sessions",
                    "sandbox_requests",
                    "usernames_tried",
                    "distinct_passwords",
                    "median_interval_seconds",
                    "automated_agent",
                    "reverse_dns",
                )
            },
        }
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            path = self._evidence_path()
            self._rotate_if_needed(path)
            line = json.dumps(record, ensure_ascii=False, default=str)
            if len(line) > EVIDENCE_LINE_LIMIT:
                line = json.dumps(
                    {
                        "at": record["at"],
                        "event": event,
                        "severity": record["severity"],
                        "source": dossier.get("source"),
                        "truncated": True,
                    },
                    ensure_ascii=False,
                )
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            self._evidence_error = ""
        except OSError as error:
            # Evidence is best-effort: losing a record must never take the
            # console offline or leak a write failure to the observed client.
            self._evidence_error = str(error)[:200]

    def _rotate_if_needed(self, path: Path) -> None:
        try:
            if path.exists() and path.stat().st_size >= self.max_evidence_bytes:
                archive = path.with_suffix(path.suffix + ".1")
                if archive.exists():
                    archive.unlink()
                os.replace(path, archive)
        except OSError:
            pass

    def read_evidence(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent evidence records, newest first."""
        if not self.evidence_dir:
            return []
        bounded = max(1, min(int(limit), 1000))
        path = self._evidence_path()
        try:
            if not path.is_file():
                return []
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()[-bounded:]
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in reversed(lines):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError:
                continue
        return records


_engine: Optional[DeceptionEngine] = None
_engine_lock = threading.RLock()


def get_deception_engine() -> DeceptionEngine:
    """Process-wide engine built from configuration on first use."""
    global _engine
    with _engine_lock:
        if _engine is None:
            from backend import config

            _engine = DeceptionEngine(
                enabled=config.HONEYPOT_ENABLED,
                evidence_dir=config.DECEPTION_EVIDENCE_DIR,
                trigger_attempts=config.HONEYPOT_TRIGGER_ATTEMPTS,
                max_evidence_bytes=config.DECEPTION_MAX_EVIDENCE_BYTES,
                max_sources=config.DECEPTION_MAX_TRACKED_SOURCES,
                reverse_dns=config.DECEPTION_REVERSE_DNS,
                reverse_dns_timeout=config.DECEPTION_REVERSE_DNS_TIMEOUT_SECONDS,
            )
        return _engine


def set_deception_engine(engine: Optional[DeceptionEngine]) -> None:
    """Replace the process-wide engine. Used by tests."""
    global _engine
    with _engine_lock:
        _engine = engine
