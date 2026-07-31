"""Server-side authentication primitives for the operations console.

The console never treats a frontend route or a hidden element as an access
control. Sessions are signed by the backend, carried in an HttpOnly cookie,
and paired with a per-session CSRF token for state-changing requests.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

PASSWORD_SCHEME = "pbkdf2_sha256"
MIN_PASSWORD_ITERATIONS = 200_000
MAX_PASSWORD_ITERATIONS = 2_000_000

# Signing-key purposes. Every token class is signed with a distinct subkey
# derived from the session secret, so a token minted for one purpose can never
# validate as another even if a caller passes it to the wrong verifier.
SANDBOX_KEY_PURPOSE = "safeops.sandbox-session.v1"
ENTRY_GATE_KEY_PURPOSE = "safeops.entry-gate.v1"

CONSOLE_SCOPE = "console"
SANDBOX_SCOPE = "sandbox"


class AuthConfigurationError(RuntimeError):
    """Authentication was enabled without a complete secure configuration."""


@dataclass(frozen=True)
class ConsoleIdentity:
    username: str
    expires_at: int
    csrf_token: str


@dataclass(frozen=True)
class SandboxIdentity:
    """A deception session. Carries no privilege on the real console.

    ``session_id`` seeds the synthetic data plane so a sandboxed client sees a
    coherent, stable fake environment across requests.
    """

    session_id: str
    expires_at: int
    csrf_token: str
    opened_at: int


def generate_password_hash(
    password: str,
    *,
    iterations: int = 600_000,
    salt: bytes | None = None,
) -> str:
    """Return a portable PBKDF2-SHA256 password verifier string."""
    if not password:
        raise ValueError("password must not be empty")
    if not MIN_PASSWORD_ITERATIONS <= iterations <= MAX_PASSWORD_ITERATIONS:
        raise ValueError("password hash iterations are outside the allowed range")
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        actual_salt,
        iterations,
    )
    return "$".join(
        [
            PASSWORD_SCHEME,
            str(iterations),
            _b64encode(actual_salt),
            _b64encode(digest),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password without exposing parsing failures to the caller."""
    try:
        scheme, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        iterations = int(iterations_text)
        if scheme != PASSWORD_SCHEME:
            return False
        if not MIN_PASSWORD_ITERATIONS <= iterations <= MAX_PASSWORD_ITERATIONS:
            return False
        salt = _b64decode(salt_text)
        expected = _b64decode(digest_text)
        if not 8 <= len(salt) <= 64 or len(expected) != hashlib.sha256().digest_size:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


class ConsoleAuth:
    """Stateless signed-session authentication with bounded login attempts."""

    def __init__(
        self,
        *,
        enabled: bool,
        username: str,
        password_hash: str,
        session_secret: str,
        session_ttl_seconds: int = 3600,
        login_attempt_limit: int = 5,
        login_window_seconds: int = 60,
        login_attempt_key_limit: int = 4096,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = bool(enabled)
        self.username = str(username)
        self.password_hash = str(password_hash)
        self._session_secret = str(session_secret).encode("utf-8")
        self.session_ttl_seconds = max(60, min(int(session_ttl_seconds), 86_400))
        self.login_attempt_limit = max(1, min(int(login_attempt_limit), 50))
        self.login_window_seconds = max(10, min(int(login_window_seconds), 3600))
        self.login_attempt_key_limit = max(1, min(int(login_attempt_key_limit), 100_000))
        self._clock = clock
        self._attempts: dict[str, list[float]] = {}
        self._attempt_lock = threading.RLock()

    @property
    def configured(self) -> bool:
        return (
            bool(self.username)
            and bool(self.password_hash)
            and len(self._session_secret) >= 32
            and self.password_hash.startswith(f"{PASSWORD_SCHEME}$")
        )

    def require_configuration(self) -> None:
        if self.enabled and not self.configured:
            raise AuthConfigurationError(
                "Console authentication is enabled but its username, password hash, "
                "or 32-character session secret is missing."
            )

    def attempts_allowed(self, client_key: str) -> bool:
        now = self._clock()
        with self._attempt_lock:
            self._prune_attempt_keys(now)
            recent = self._recent_attempts(client_key, now)
            if client_key not in self._attempts and len(self._attempts) >= self.login_attempt_key_limit:
                return False
            if recent:
                self._attempts[client_key] = recent
            else:
                self._attempts.pop(client_key, None)
            return len(recent) < self.login_attempt_limit

    def reserve_attempt(self, client_key: str) -> bool:
        """Atomically consume one login-attempt slot before password hashing."""
        now = self._clock()
        with self._attempt_lock:
            self._prune_attempt_keys(now)
            recent = self._recent_attempts(client_key, now)
            if client_key not in self._attempts and len(self._attempts) >= self.login_attempt_key_limit:
                return False
            if len(recent) >= self.login_attempt_limit:
                self._attempts[client_key] = recent
                return False
            recent.append(now)
            self._attempts[client_key] = recent
            return True

    def record_failed_attempt(self, client_key: str) -> None:
        now = self._clock()
        with self._attempt_lock:
            self._prune_attempt_keys(now)
            recent = self._recent_attempts(client_key, now)
            if client_key not in self._attempts and len(self._attempts) >= self.login_attempt_key_limit:
                return
            recent.append(now)
            self._attempts[client_key] = recent

    def clear_attempts(self, client_key: str) -> None:
        with self._attempt_lock:
            self._attempts.pop(client_key, None)

    def verify_credentials(self, username: str, password: str) -> bool:
        self.require_configuration()
        username_ok = hmac.compare_digest(str(username), self.username)
        # Always evaluate the password verifier to reduce username timing leaks.
        password_ok = verify_password(str(password), self.password_hash)
        return username_ok and password_ok

    def issue_session(self) -> tuple[str, ConsoleIdentity]:
        self.require_configuration()
        now = int(self._clock())
        identity = ConsoleIdentity(
            username=self.username,
            expires_at=now + self.session_ttl_seconds,
            csrf_token=secrets.token_urlsafe(24),
        )
        payload = {
            "v": 1,
            "s": CONSOLE_SCOPE,
            "u": identity.username,
            "exp": identity.expires_at,
            "csrf": identity.csrf_token,
            "nonce": secrets.token_urlsafe(12),
        }
        encoded_payload = _b64encode(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = hmac.new(
            self._session_secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{encoded_payload}.{_b64encode(signature)}", identity

    def authenticate(self, token: str) -> ConsoleIdentity | None:
        if not self.enabled:
            return ConsoleIdentity("local", 0, "")
        if not self.configured or not token:
            return None
        try:
            payload_text, signature_text = token.split(".", 1)
            expected = hmac.new(
                self._session_secret,
                payload_text.encode("ascii"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(expected, _b64decode(signature_text)):
                return None
            payload = json.loads(_b64decode(payload_text).decode("utf-8"))
            if payload.get("v") != 1:
                return None
            # Scope is checked in addition to the distinct signing subkey used by
            # deception sessions: two independent barriers guard the boundary
            # between a sandboxed client and the real console.
            if payload.get("s") != CONSOLE_SCOPE:
                return None
            username = payload.get("u")
            expires_at = payload.get("exp")
            csrf_token = payload.get("csrf")
            if not isinstance(username, str) or not hmac.compare_digest(username, self.username):
                return None
            if not isinstance(expires_at, int) or expires_at <= int(self._clock()):
                return None
            if not isinstance(csrf_token, str) or len(csrf_token) < 24:
                return None
            return ConsoleIdentity(username, expires_at, csrf_token)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            return None

    @property
    def sandbox_capable(self) -> bool:
        """Deception sessions only need signing material, not operator credentials."""
        return len(self._session_secret) >= 32

    def _subkey(self, purpose: str) -> bytes:
        return hmac.new(self._session_secret, purpose.encode("ascii"), hashlib.sha256).digest()

    def issue_sandbox_session(self, ttl_seconds: int) -> tuple[str, SandboxIdentity]:
        """Mint a deception session that grants no access to real data.

        Signed with a dedicated subkey so it is cryptographically incapable of
        passing :meth:`authenticate`.
        """
        if not self.sandbox_capable:
            raise AuthConfigurationError(
                "A 32-character session secret is required to issue deception sessions."
            )
        now = int(self._clock())
        bounded_ttl = max(60, min(int(ttl_seconds), 86_400))
        identity = SandboxIdentity(
            session_id=secrets.token_hex(8),
            expires_at=now + bounded_ttl,
            csrf_token=secrets.token_urlsafe(24),
            opened_at=now,
        )
        payload = {
            "v": 1,
            "s": SANDBOX_SCOPE,
            "sid": identity.session_id,
            "exp": identity.expires_at,
            "iat": identity.opened_at,
            "csrf": identity.csrf_token,
            "nonce": secrets.token_urlsafe(12),
        }
        encoded_payload = _b64encode(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = hmac.new(
            self._subkey(SANDBOX_KEY_PURPOSE),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{encoded_payload}.{_b64encode(signature)}", identity

    def authenticate_sandbox(self, token: str) -> SandboxIdentity | None:
        if not self.sandbox_capable or not token:
            return None
        try:
            payload_text, signature_text = token.split(".", 1)
            expected = hmac.new(
                self._subkey(SANDBOX_KEY_PURPOSE),
                payload_text.encode("ascii"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(expected, _b64decode(signature_text)):
                return None
            payload = json.loads(_b64decode(payload_text).decode("utf-8"))
            if payload.get("v") != 1 or payload.get("s") != SANDBOX_SCOPE:
                return None
            session_id = payload.get("sid")
            expires_at = payload.get("exp")
            opened_at = payload.get("iat")
            csrf_token = payload.get("csrf")
            if not isinstance(session_id, str) or not 4 <= len(session_id) <= 64:
                return None
            if not isinstance(expires_at, int) or expires_at <= int(self._clock()):
                return None
            if not isinstance(opened_at, int):
                return None
            if not isinstance(csrf_token, str) or len(csrf_token) < 24:
                return None
            return SandboxIdentity(session_id, expires_at, csrf_token, opened_at)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            return None

    def entry_gate_subkey(self) -> bytes:
        """Expose the gate signing subkey so the gate stays domain-separated."""
        return self._subkey(ENTRY_GATE_KEY_PURPOSE)

    def verify_csrf(self, identity: ConsoleIdentity, csrf_token: str) -> bool:
        return bool(csrf_token) and hmac.compare_digest(identity.csrf_token, str(csrf_token))

    def _recent_attempts(self, client_key: str, now: float) -> list[float]:
        cutoff = now - self.login_window_seconds
        return [attempt for attempt in self._attempts.get(client_key, []) if attempt > cutoff]

    def _prune_attempt_keys(self, now: float) -> None:
        """Drop globally expired client keys before enforcing the capacity bound."""
        cutoff = now - self.login_window_seconds
        expired = [
            client_key
            for client_key, attempts in self._attempts.items()
            if not attempts or attempts[-1] <= cutoff
        ]
        for client_key in expired:
            self._attempts.pop(client_key, None)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        f"{value}{padding}".encode("ascii"),
        altchars=b"-_",
        validate=True,
    )


class AttemptLimiter:
    """Sliding-window attempt counter with a bound on tracked keys.

    Deliberately separate from :class:`ConsoleAuth`'s own counters: the gate and
    the credential login must not share a budget, or failed gate probes would
    lock out a legitimate operator's password attempts.
    """

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        key_limit: int = 4096,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.limit = max(1, min(int(limit), 100))
        self.window_seconds = max(10, min(int(window_seconds), 86_400))
        self.key_limit = max(1, min(int(key_limit), 100_000))
        self._clock = clock
        self._events: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def reserve(self, key: str) -> bool:
        """Consume one slot. Returns False when the caller is over budget."""
        now = self._clock()
        with self._lock:
            self._prune(now)
            recent = self._recent(key, now)
            if key not in self._events and len(self._events) >= self.key_limit:
                return False
            if len(recent) >= self.limit:
                self._events[key] = recent
                return False
            recent.append(now)
            self._events[key] = recent
            return True

    def count(self, key: str) -> int:
        now = self._clock()
        with self._lock:
            return len(self._recent(key, now))

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def _recent(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        return [event for event in self._events.get(key, []) if event > cutoff]

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale = [
            key
            for key, events in self._events.items()
            if not events or events[-1] <= cutoff
        ]
        for key in stale:
            self._events.pop(key, None)


class EntryGate:
    """Server-side gate that must be passed before the operator login is served.

    This is the second factor that makes the credential login unreachable by
    brute force: without a valid gate token the login endpoint rejects the
    request before the password verifier is ever consulted. The passphrase is
    stored only as a PBKDF2 verifier, exactly like the operator password, and is
    never sent to the browser in any form.
    """

    def __init__(
        self,
        *,
        passphrase_hash: str,
        signing_key: bytes,
        ttl_seconds: int = 300,
        attempt_limit: int = 5,
        window_seconds: int = 300,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.passphrase_hash = str(passphrase_hash).strip()
        self._signing_key = bytes(signing_key)
        self.ttl_seconds = max(30, min(int(ttl_seconds), 3600))
        self._clock = clock
        self._limiter = AttemptLimiter(
            limit=attempt_limit,
            window_seconds=window_seconds,
            clock=clock,
        )

    @property
    def enabled(self) -> bool:
        """A gate without a configured verifier is inert, keeping login single-factor."""
        return (
            self.passphrase_hash.startswith(f"{PASSWORD_SCHEME}$")
            and len(self._signing_key) >= 32
        )

    def reserve_attempt(self, client_key: str) -> bool:
        return self._limiter.reserve(client_key)

    def clear_attempts(self, client_key: str) -> None:
        self._limiter.clear(client_key)

    def verify_passphrase(self, passphrase: str) -> bool:
        if not self.enabled:
            return False
        return verify_password(str(passphrase), self.passphrase_hash)

    def issue_token(self) -> str:
        if not self.enabled:
            raise AuthConfigurationError("The entry gate is not configured.")
        payload = {
            "v": 1,
            "s": "gate",
            "exp": int(self._clock()) + self.ttl_seconds,
            "nonce": secrets.token_urlsafe(12),
        }
        encoded_payload = _b64encode(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = hmac.new(self._signing_key, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        return f"{encoded_payload}.{_b64encode(signature)}"

    def verify_token(self, token: str) -> bool:
        if not self.enabled or not token:
            return False
        try:
            payload_text, signature_text = token.split(".", 1)
            expected = hmac.new(
                self._signing_key,
                payload_text.encode("ascii"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(expected, _b64decode(signature_text)):
                return False
            payload = json.loads(_b64decode(payload_text).decode("utf-8"))
            if payload.get("v") != 1 or payload.get("s") != "gate":
                return False
            expires_at = payload.get("exp")
            return isinstance(expires_at, int) and expires_at > int(self._clock())
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            return False
