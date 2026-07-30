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
from dataclasses import dataclass
from typing import Callable, Optional


PASSWORD_SCHEME = "pbkdf2_sha256"
MIN_PASSWORD_ITERATIONS = 200_000
MAX_PASSWORD_ITERATIONS = 2_000_000


class AuthConfigurationError(RuntimeError):
    """Authentication was enabled without a complete secure configuration."""


@dataclass(frozen=True)
class ConsoleIdentity:
    username: str
    expires_at: int
    csrf_token: str


def generate_password_hash(
    password: str,
    *,
    iterations: int = 600_000,
    salt: Optional[bytes] = None,
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
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = bool(enabled)
        self.username = str(username)
        self.password_hash = str(password_hash)
        self._session_secret = str(session_secret).encode("utf-8")
        self.session_ttl_seconds = max(60, min(int(session_ttl_seconds), 86_400))
        self.login_attempt_limit = max(1, min(int(login_attempt_limit), 50))
        self.login_window_seconds = max(10, min(int(login_window_seconds), 3600))
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
            recent = self._recent_attempts(client_key, now)
            self._attempts[client_key] = recent
            return len(recent) < self.login_attempt_limit

    def record_failed_attempt(self, client_key: str) -> None:
        now = self._clock()
        with self._attempt_lock:
            recent = self._recent_attempts(client_key, now)
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

    def authenticate(self, token: str) -> Optional[ConsoleIdentity]:
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

    def verify_csrf(self, identity: ConsoleIdentity, csrf_token: str) -> bool:
        return bool(csrf_token) and hmac.compare_digest(identity.csrf_token, str(csrf_token))

    def _recent_attempts(self, client_key: str, now: float) -> list[float]:
        cutoff = now - self.login_window_seconds
        return [attempt for attempt in self._attempts.get(client_key, []) if attempt > cutoff]


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        f"{value}{padding}".encode("ascii"),
        altchars=b"-_",
        validate=True,
    )
