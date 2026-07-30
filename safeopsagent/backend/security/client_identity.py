"""Trusted-proxy-aware client identification for rate limiting and attribution.

Per-source throttling and incident attribution are only as trustworthy as the
address they key on. Any client can set ``X-Forwarded-For`` freely, so a naive
reader lets an attacker rotate a header value to reset every counter and to
pollute the evidence trail with forged origins. Forwarded headers are therefore
honoured only when the immediate peer is a configured reverse proxy, and the
chain is walked from right to left so only the hop closest to the proxy is
trusted.

The fingerprint here is deliberately passive: it is derived from headers the
client already sent. No client-side probing is performed, so observation is
invisible to the source and adds no request latency.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Iterable, Mapping, Sequence

UNKNOWN_SOURCE = "unknown"
MAX_FORWARDED_HOPS = 16
MAX_HEADER_VALUE_CHARS = 256

# Headers retained for attribution. Chosen because they are stable across a
# single client's requests yet vary between tools, which is what makes an
# automated client distinguishable from a browser.
FORENSIC_HEADERS = (
    "user-agent",
    "accept",
    "accept-language",
    "accept-encoding",
    "referer",
    "origin",
    "sec-ch-ua",
    "sec-ch-ua-platform",
    "sec-fetch-mode",
    "sec-fetch-site",
    "x-requested-with",
)

# Substrings that identify a non-browser client by self-declaration. Absence
# proves nothing (a user agent is trivially forged), so this only raises
# confidence in a classification and never gates a security decision.
AUTOMATION_AGENT_TOKENS = (
    "curl",
    "wget",
    "python-requests",
    "httpx",
    "aiohttp",
    "go-http-client",
    "java/",
    "okhttp",
    "libwww",
    "nmap",
    "nikto",
    "sqlmap",
    "hydra",
    "medusa",
    "ffuf",
    "gobuster",
    "dirbuster",
    "wpscan",
    "masscan",
    "zgrab",
    "burp",
    "nuclei",
    "postman",
    "insomnia",
    "scrapy",
    "httpie",
)


def parse_networks(values: Iterable[str]) -> tuple:
    """Parse CIDR/address strings, silently dropping malformed entries.

    Configuration mistakes must not crash request handling; an unparsable entry
    simply grants no trust.
    """
    networks = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        try:
            networks.append(ip_network(text, strict=False))
        except ValueError:
            continue
    return tuple(networks)


@dataclass(frozen=True)
class ClientIdentity:
    """Resolved origin of a request plus the evidence used to resolve it."""

    source_ip: str
    peer_ip: str
    forwarded_chain: tuple[str, ...]
    proxy_trusted: bool
    user_agent: str
    fingerprint: str
    headers: tuple[tuple[str, str], ...]
    automated_agent: bool

    @property
    def rate_limit_key(self) -> str:
        return self.source_ip or UNKNOWN_SOURCE

    def to_dict(self) -> dict:
        return {
            "source_ip": self.source_ip,
            "peer_ip": self.peer_ip,
            "forwarded_chain": list(self.forwarded_chain),
            "proxy_trusted": self.proxy_trusted,
            "user_agent": self.user_agent,
            "fingerprint": self.fingerprint,
            "headers": {name: value for name, value in self.headers},
            "automated_agent": self.automated_agent,
        }


def _normalize_ip(value: str) -> str:
    """Return a canonical address, unwrapping ``[v6]:port`` and ``v4:port``."""
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith("["):
        closing = text.find("]")
        if closing > 0:
            text = text[1:closing]
    elif text.count(":") == 1:
        # An IPv4 literal with a port. A bare IPv6 address also contains
        # colons, which is why this only strips when exactly one is present.
        text = text.split(":", 1)[0]
    try:
        return str(ip_address(text))
    except ValueError:
        return ""


def _is_trusted(candidate: str, trusted_networks: Sequence) -> bool:
    if not candidate or not trusted_networks:
        return False
    try:
        address = ip_address(candidate)
    except ValueError:
        return False
    return any(address in network for network in trusted_networks)


def _forwarded_candidates(headers: Mapping[str, str]) -> tuple[str, ...]:
    """Collect the forwarded chain, left to right, as the proxy reported it."""
    raw = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
    parts = str(raw).rsplit(",", MAX_FORWARDED_HOPS)
    hops = [_normalize_ip(part) for part in parts[-MAX_FORWARDED_HOPS:]]
    chain = tuple(hop for hop in hops if hop)
    if chain:
        return chain

    # RFC 7239 form: for=192.0.2.1;proto=https
    forwarded = headers.get("forwarded") or headers.get("Forwarded") or ""
    collected: list[str] = []
    elements = str(forwarded).rsplit(",", MAX_FORWARDED_HOPS)
    for element in elements[-MAX_FORWARDED_HOPS:]:
        for directive in element.split(";"):
            key, _, value = directive.partition("=")
            if key.strip().lower() == "for":
                candidate = _normalize_ip(value.strip().strip('"'))
                if candidate:
                    collected.append(candidate)
    return tuple(collected)


def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(name).lower(): str(value) for name, value in headers.items()}


def resolve_client(
    peer_host: str,
    headers: Mapping[str, str],
    trusted_proxies: Iterable[str] = (),
) -> ClientIdentity:
    """Resolve the effective source of a request.

    ``peer_host`` is the transport-level address, which cannot be forged by the
    client. Forwarded headers are consulted only when that peer is a trusted
    proxy.
    """
    lowered = _lower_headers(headers)
    peer_ip = _normalize_ip(peer_host)
    trusted_networks = parse_networks(trusted_proxies)
    chain = _forwarded_candidates(lowered)
    proxy_trusted = _is_trusted(peer_ip, trusted_networks)

    source_ip = peer_ip or UNKNOWN_SOURCE
    if proxy_trusted and chain:
        # Walk right to left and accept the first hop that is not itself a
        # trusted proxy: everything further left was supplied by the client.
        for candidate in reversed(chain):
            if not _is_trusted(candidate, trusted_networks):
                source_ip = candidate
                break

    retained = tuple(
        (name, lowered[name][:MAX_HEADER_VALUE_CHARS])
        for name in FORENSIC_HEADERS
        if lowered.get(name)
    )
    user_agent = lowered.get("user-agent", "")[:MAX_HEADER_VALUE_CHARS]
    return ClientIdentity(
        source_ip=source_ip,
        peer_ip=peer_ip or UNKNOWN_SOURCE,
        forwarded_chain=chain,
        proxy_trusted=proxy_trusted,
        user_agent=user_agent,
        fingerprint=_fingerprint(lowered),
        headers=retained,
        automated_agent=is_automated_agent(user_agent),
    )


def _fingerprint(lowered: Mapping[str, str]) -> str:
    """Stable digest of client-declared capabilities.

    Two requests from the same tool share a fingerprint even when the source
    address rotates, which is what links a distributed attempt back together.
    """
    material = "\n".join(
        f"{name}={lowered.get(name, '')[:MAX_HEADER_VALUE_CHARS]}"
        for name in (
            "user-agent",
            "accept",
            "accept-language",
            "accept-encoding",
            "sec-ch-ua",
            "sec-ch-ua-platform",
        )
    )
    header_order = ",".join(name for name in lowered if not name.startswith("cookie"))
    digest = hashlib.sha256(f"{material}\n#{header_order}".encode("utf-8", "replace"))
    return digest.hexdigest()[:16]


def is_automated_agent(user_agent: str) -> bool:
    text = str(user_agent).lower()
    if not text.strip():
        # A browser always sends one; omission is itself a signal.
        return True
    return any(token in text for token in AUTOMATION_AGENT_TOKENS)


def credential_digest(secret: str, key: bytes) -> str:
    """Return a short, keyed digest of a submitted password.

    Attempted passwords are valuable evidence (they reveal which wordlist is in
    use) but storing them in cleartext would create a fresh liability: they are
    frequently real credentials reused from elsewhere. Only a keyed digest
    prefix is retained, which supports "same password retried" correlation
    without ever recording a usable secret or enabling offline guessing.
    """
    digest = hmac.new(
        key,
        str(secret).encode("utf-8", "replace"),
        hashlib.sha256,
    )
    return digest.hexdigest()[:16]
