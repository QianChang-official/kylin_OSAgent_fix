import base64
from concurrent.futures import ThreadPoolExecutor
import json
import sys

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.security.console_auth import (
    AuthConfigurationError,
    ConsoleAuth,
    generate_password_hash,
    verify_password,
)
from scripts import hash_console_password


def _auth(clock, *, enabled=True, secret="s" * 48):
    return ConsoleAuth(
        enabled=enabled,
        username="operator",
        password_hash=generate_password_hash(
            "correct horse battery staple",
            iterations=200_000,
            salt=b"fixed-test-salt",
        ),
        session_secret=secret,
        session_ttl_seconds=120,
        login_attempt_limit=2,
        login_window_seconds=60,
        clock=clock,
    )


def test_password_hash_round_trip_and_rejects_wrong_password():
    encoded = generate_password_hash(
        "safe password",
        iterations=200_000,
        salt=b"0123456789abcdef",
    )

    assert encoded.startswith("pbkdf2_sha256$200000$")
    assert verify_password("safe password", encoded) is True
    assert verify_password("wrong password", encoded) is False
    assert verify_password("safe password", "not-a-valid-hash") is False


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], "CONSOLE_AUTH_PASSWORD_HASH=pbkdf2_sha256$600000$salt$digest"),
        (["--entry-gate"], "CONSOLE_ENTRY_GATE_HASH=pbkdf2_sha256$600000$salt$digest"),
        (["--value-only"], "pbkdf2_sha256$600000$salt$digest"),
    ],
)
def test_hash_console_password_output_modes(monkeypatch, capsys, arguments, expected):
    answers = iter(["secret", "secret"])
    monkeypatch.setattr(hash_console_password.getpass, "getpass", lambda _prompt: next(answers))
    monkeypatch.setattr(
        hash_console_password,
        "generate_password_hash",
        lambda _secret: "pbkdf2_sha256$600000$salt$digest",
    )
    monkeypatch.setattr(sys, "argv", ["hash_console_password.py", *arguments])

    assert hash_console_password.main() == 0
    assert capsys.readouterr().out.strip() == expected


def test_session_round_trip_csrf_tamper_and_expiry():
    now = [1_700_000_000.0]
    auth = _auth(lambda: now[0])

    token, issued = auth.issue_session()
    identity = auth.authenticate(token)

    assert identity == issued
    assert auth.verify_csrf(identity, issued.csrf_token) is True
    assert auth.verify_csrf(identity, "wrong") is False

    payload, signature = token.split(".", 1)
    changed = ("A" if payload[0] != "A" else "B") + payload[1:]
    assert auth.authenticate(f"{changed}.{signature}") is None

    raw_signature = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    forged_signature = bytes([raw_signature[0] ^ 1]) + raw_signature[1:]
    forged_text = base64.urlsafe_b64encode(forged_signature).rstrip(b"=").decode("ascii")
    assert auth.authenticate(f"{payload}.{forged_text}") is None

    now[0] += 121
    assert auth.authenticate(token) is None


def test_login_attempt_window_is_bounded():
    now = [10_000.0]
    auth = _auth(lambda: now[0])

    assert auth.attempts_allowed("127.0.0.1") is True
    auth.record_failed_attempt("127.0.0.1")
    assert auth.attempts_allowed("127.0.0.1") is True
    auth.record_failed_attempt("127.0.0.1")
    assert auth.attempts_allowed("127.0.0.1") is False

    now[0] += 61
    assert auth.attempts_allowed("127.0.0.1") is True


def test_login_attempt_reservation_is_atomic_under_concurrency():
    auth = _auth(lambda: 10_000.0)

    with ThreadPoolExecutor(max_workers=16) as pool:
        reservations = list(pool.map(lambda _: auth.reserve_attempt("127.0.0.1"), range(32)))

    assert sum(reservations) == auth.login_attempt_limit
    assert auth.reserve_attempt("127.0.0.1") is False


def test_login_attempt_key_capacity_fails_closed_and_prunes_expired_keys():
    now = [10_000.0]
    auth = ConsoleAuth(
        enabled=True,
        username="operator",
        password_hash=generate_password_hash(
            "correct horse battery staple",
            iterations=200_000,
            salt=b"fixed-test-salt",
        ),
        session_secret="s" * 48,
        login_attempt_limit=2,
        login_window_seconds=60,
        login_attempt_key_limit=2,
        clock=lambda: now[0],
    )

    assert auth.reserve_attempt("client-a") is True
    assert auth.reserve_attempt("client-b") is True
    assert auth.reserve_attempt("client-c") is False
    assert len(auth._attempts) == 2

    now[0] += 61
    assert auth.reserve_attempt("client-c") is True
    assert set(auth._attempts) == {"client-c"}


def test_enabled_auth_requires_complete_configuration():
    auth = ConsoleAuth(
        enabled=True,
        username="operator",
        password_hash="",
        session_secret="short",
    )

    with pytest.raises(AuthConfigurationError):
        auth.require_configuration()


def test_disabled_auth_reports_local_identity_without_a_cookie():
    auth = ConsoleAuth(
        enabled=False,
        username="",
        password_hash="",
        session_secret="",
    )

    identity = auth.authenticate("")
    assert identity is not None
    assert identity.username == "local"


def test_auth_routes_issue_cookie_and_enforce_csrf(monkeypatch):
    now = [1_700_000_000.0]
    monkeypatch.setattr(app_module, "_console_auth", _auth(lambda: now[0]))
    client = TestClient(app_module.app)

    unauthenticated = client.get("/tools/list")
    session = client.get("/auth/session")
    failed_login = client.post(
        "/auth/login",
        json={"username": "operator", "password": "wrong"},
    )

    assert unauthenticated.status_code == 401
    assert session.json() == {
        "enabled": True,
        "authenticated": False,
        "username": None,
        "expires_at": None,
        "csrf_token": None,
    }
    assert failed_login.status_code == 401

    login = client.post(
        "/auth/login",
        json={"username": "operator", "password": "correct horse battery staple"},
    )
    body = login.json()

    assert login.status_code == 200
    assert body["enabled"] is True
    assert body["authenticated"] is True
    assert body["username"] == "operator"
    assert isinstance(body["csrf_token"], str) and len(body["csrf_token"]) >= 24
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=strict" in login.headers["set-cookie"].lower()
    assert client.get("/tools/list").status_code == 200

    missing_csrf = client.post(
        "/tools/call",
        json={"tool_name": "get_memory_status", "arguments": {}},
    )
    with_csrf = client.post(
        "/tools/call",
        json={"tool_name": "get_memory_status", "arguments": {}},
        headers={"X-CSRF-Token": body["csrf_token"]},
    )

    assert missing_csrf.status_code == 403
    assert with_csrf.status_code == 200

    logout = client.post("/auth/logout", headers={"X-CSRF-Token": body["csrf_token"]})
    assert logout.status_code == 200
    assert client.get("/tools/list").status_code == 401


def test_auth_boundary_covers_openapi_mcp_and_unknown_auth_routes(monkeypatch):
    monkeypatch.setattr(app_module, "_console_auth", _auth(lambda: 1_700_000_000.0))
    client = TestClient(app_module.app)

    assert client.get("/openapi.json").status_code == 401
    assert client.get("/docs").status_code == 401
    assert client.get("/mcp/sse").status_code == 401
    assert client.get("/auth/not-a-public-route").status_code == 401
    assert client.get("/console/").status_code == 200
    assert client.get("/health").status_code == 200


def test_cors_allows_only_configured_credentialed_origin(monkeypatch):
    monkeypatch.setattr(app_module, "_console_auth", _auth(lambda: 1_700_000_000.0))
    client = TestClient(app_module.app)
    allowed_origin = "http://localhost:5173"

    unauthorized = client.get("/tools/list", headers={"Origin": allowed_origin})
    preflight = client.options(
        "/tools/call",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token",
        },
    )
    rejected = client.options(
        "/tools/call",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert unauthorized.status_code == 401
    assert unauthorized.headers["access-control-allow-origin"] == allowed_origin
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == allowed_origin
    assert preflight.headers["access-control-allow-credentials"] == "true"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_login_rate_limit_and_audit_never_record_password(monkeypatch):
    captured = []

    class CaptureLogger:
        def log(self, entry):
            captured.append(entry)
            return True

    monkeypatch.setattr(app_module, "_console_auth", _auth(lambda: 1_700_000_000.0))
    monkeypatch.setattr(app_module, "get_logger", lambda: CaptureLogger())
    client = TestClient(app_module.app)
    password = "do-not-store-this-password"

    for _ in range(2):
        response = client.post(
            "/auth/login",
            json={"username": "operator", "password": password},
        )
        assert response.status_code == 401
    limited = client.post(
        "/auth/login",
        json={"username": "operator", "password": password},
    )

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert [entry["security_reason"] for entry in captured] == [
        "invalid_credentials",
        "invalid_credentials",
        "login_rate_limited",
    ]
    assert password not in json.dumps(captured)


def test_expired_cookie_and_missing_logout_csrf_are_rejected(monkeypatch):
    now = [1_700_000_000.0]
    monkeypatch.setattr(app_module, "_console_auth", _auth(lambda: now[0]))
    client = TestClient(app_module.app)
    login = client.post(
        "/auth/login",
        json={"username": "operator", "password": "correct horse battery staple"},
    )

    assert login.status_code == 200
    assert client.post("/auth/logout").status_code == 403
    now[0] += 121
    assert client.get("/tools/list").status_code == 401
    assert client.get("/auth/session").json()["authenticated"] is False


def test_misconfigured_enabled_auth_fails_closed(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_console_auth",
        ConsoleAuth(
            enabled=True,
            username="operator",
            password_hash="",
            session_secret="short",
        ),
    )
    client = TestClient(app_module.app)

    assert client.get("/auth/session").status_code == 503
    assert client.get("/tools/list").status_code == 503
    assert client.get("/health").status_code == 200
    assert client.get("/console/").status_code == 200


def test_disabled_auth_is_restricted_to_loopback_clients(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_console_auth",
        ConsoleAuth(enabled=False, username="", password_hash="", session_secret=""),
    )
    monkeypatch.setattr(app_module.config, "CONSOLE_AUTH_ALLOW_INSECURE_NON_LOOPBACK", False)
    client = TestClient(app_module.app)

    assert app_module._is_loopback_address("127.0.0.1") is True
    assert app_module._is_loopback_address("::1") is True
    assert app_module._is_loopback_address("192.0.2.10") is False
    assert client.get("/tools/list").status_code == 403
    assert client.get("/health").status_code == 200
