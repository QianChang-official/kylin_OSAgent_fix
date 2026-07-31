"""Front-door deception: decoy login, concealed entry gate, sandbox isolation."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import config
from backend.security.client_identity import credential_digest, resolve_client
from backend.security.console_auth import (
    AttemptLimiter,
    ConsoleAuth,
    EntryGate,
    generate_password_hash,
)
from backend.security.deception import DeceptionEngine, set_deception_engine

OPERATOR_PASSWORD = "correct horse battery staple"
GATE_PASSPHRASE = "kylin-hatch"


def _auth(*, secret="s" * 48, attempt_limit=20):
    return ConsoleAuth(
        enabled=True,
        username="operator",
        password_hash=generate_password_hash(
            OPERATOR_PASSWORD,
            iterations=200_000,
            salt=b"fixed-test-salt",
        ),
        session_secret=secret,
        session_ttl_seconds=600,
        login_attempt_limit=attempt_limit,
        login_window_seconds=60,
    )


def _gate(auth, *, configured=True, attempt_limit=5):
    return EntryGate(
        passphrase_hash=generate_password_hash(
            GATE_PASSPHRASE,
            iterations=200_000,
            salt=b"fixed-gate-salt",
        )
        if configured
        else "",
        signing_key=auth.entry_gate_subkey(),
        ttl_seconds=300,
        attempt_limit=attempt_limit,
        window_seconds=300,
    )


@pytest.fixture
def engine(tmp_path):
    built = DeceptionEngine(
        enabled=True,
        evidence_dir=tmp_path / "deception",
        trigger_attempts=3,
    )
    set_deception_engine(built)
    yield built
    set_deception_engine(None)


@pytest.fixture
def gated_client(monkeypatch, engine):
    auth = _auth()
    monkeypatch.setattr(app_module, "_console_auth", auth)
    monkeypatch.setattr(app_module, "_entry_gate", _gate(auth))
    return TestClient(app_module.app)


def _login(client, password=OPERATOR_PASSWORD, username="operator"):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_gate_disabled_keeps_single_factor_login(monkeypatch, engine):
    auth = _auth()
    monkeypatch.setattr(app_module, "_console_auth", auth)
    monkeypatch.setattr(app_module, "_entry_gate", _gate(auth, configured=False))
    client = TestClient(app_module.app)

    assert client.post("/auth/gate", json={"passphrase": GATE_PASSPHRASE}).status_code == 404
    assert _login(client, "wrong").status_code == 401
    assert _login(client).status_code == 200
    assert client.get("/tools/list").status_code == 200


def test_correct_credentials_are_rejected_without_the_gate(gated_client):
    """The concealed gate is what makes the credential login unreachable."""
    response = _login(gated_client)

    assert response.status_code == 401
    assert gated_client.get("/tools/list").status_code == 401


def test_gate_then_credentials_grants_a_real_session(gated_client):
    unlocked = gated_client.post("/auth/gate", json={"passphrase": GATE_PASSPHRASE})
    assert unlocked.status_code == 200
    assert unlocked.json() == {"unlocked": True}

    login = _login(gated_client)
    body = login.json()

    assert login.status_code == 200
    assert body["authenticated"] is True
    assert body["username"] == "operator"
    assert gated_client.get("/tools/list").status_code == 200


def test_wrong_passphrase_is_indistinguishable_from_a_missing_route(gated_client):
    response = gated_client.post("/auth/gate", json={"passphrase": "not-the-phrase"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_gate_probing_is_rate_limited_and_recorded(monkeypatch, engine):
    auth = _auth()
    monkeypatch.setattr(app_module, "_console_auth", auth)
    monkeypatch.setattr(app_module, "_entry_gate", _gate(auth, attempt_limit=3))
    client = TestClient(app_module.app)

    statuses = [
        client.post("/auth/gate", json={"passphrase": f"guess-{index}"}).status_code
        for index in range(5)
    ]

    assert statuses[:3] == [404, 404, 404]
    assert statuses[3:] == [429, 429]
    assert engine.summary()["total_gate_failures"] >= 3


def test_brute_force_lands_in_a_sandbox_that_holds_no_real_data(gated_client, engine):
    for index in range(3):
        response = _login(gated_client, f"guess-{index}", username=f"admin{index}")

    # The third attempt is answered as a successful login.
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True

    summary = engine.summary()
    assert summary["sandbox_sessions_open"] == 1

    # The console now renders, but every value is fabricated.
    status = gated_client.get("/agent/status")
    assert status.status_code == 200
    assert status.json()["model_name"] == "offline-safe-planner"

    overview = gated_client.get("/monitor/overview").json()
    assert overview["host"]["hostname"] == config.HONEYPOT_HOSTNAME
    assert overview["health"] == "healthy"

    logs = gated_client.get("/audit/logs?limit=5").json()["logs"]
    assert len(logs) == 5
    assert all("request_id" in row for row in logs)


def test_sandbox_session_never_reaches_a_real_handler(gated_client, monkeypatch):
    for index in range(3):
        _login(gated_client, f"guess-{index}")

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("a sandbox request reached a real handler")

    monkeypatch.setattr(app_module, "get_orch", explode)
    monkeypatch.setattr(app_module, "get_registry", explode)
    monkeypatch.setattr(app_module, "get_logger", explode)
    monkeypatch.setattr(app_module, "get_monitoring_service", explode)
    monkeypatch.setattr(app_module, "run_probe", explode)

    session = gated_client.get("/auth/session").json()
    csrf = session["csrf_token"]

    assert gated_client.get("/tools/list").status_code == 200
    assert gated_client.get("/system/probe").status_code == 200
    assert gated_client.get("/monitor/metrics?points=6").status_code == 200
    chat = gated_client.post(
        "/chat",
        json={"message": "df -h 看看磁盘", "session_id": "s1"},
        headers={"X-CSRF-Token": csrf},
    )
    assert chat.status_code == 200
    assert chat.json()["security_decision"] == "allow"

    resources = gated_client.get("/security/resources").json()
    assert resources["codex_security"]["title"] == "Codex Security"
    assert resources["policy"]["restricted_category_count"] == 0

    intel = gated_client.get("/security/intel/aisecurity").json()
    assert intel["source"]["name"] == "AI Security feed"
    assert intel["items"] == []
    assert intel["automatic_model_ingestion"] is False


def test_sandbox_cannot_clear_the_real_audit_trail(gated_client):
    for index in range(3):
        _login(gated_client, f"guess-{index}")
    csrf = gated_client.get("/auth/session").json()["csrf_token"]

    response = gated_client.post("/audit/clear", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 200
    assert response.json()["cleared"] == 0


def test_sandbox_enforces_csrf_like_the_real_console(gated_client):
    for index in range(3):
        _login(gated_client, f"guess-{index}")

    missing = gated_client.post("/chat", json={"message": "hi", "session_id": "s"})

    assert missing.status_code == 403


def test_sandbox_token_is_rejected_by_the_real_verifier(gated_client):
    for index in range(3):
        _login(gated_client, f"guess-{index}")
    token = gated_client.cookies.get(config.CONSOLE_AUTH_COOKIE_NAME)

    assert token
    assert app_module._console_auth.authenticate(token) is None
    assert app_module._console_auth.authenticate_sandbox(token) is not None


def test_operator_typing_a_wrong_password_behind_the_gate_is_not_sandboxed(gated_client, engine):
    gated_client.post("/auth/gate", json={"passphrase": GATE_PASSPHRASE})

    for _ in range(4):
        response = _login(gated_client, "fat fingered")

    assert response.status_code == 401
    assert engine.summary()["sandbox_sessions_open"] == 0
    assert _login(gated_client).status_code == 200


def test_leaked_credentials_without_the_gate_are_flagged(gated_client, engine):
    _login(gated_client)

    records = engine.read_evidence(10)
    reasons = [record["detail"].get("reason") for record in records]

    assert "valid_credentials_without_gate" in reasons


def test_evidence_records_attribution_without_storing_passwords(gated_client, engine):
    for index in range(3):
        _login(gated_client, f"hunter{index}", username=f"admin{index}")

    dossiers = engine.dossiers()
    assert len(dossiers) == 1
    dossier = dossiers[0]

    assert dossier["login_failures"] >= 3
    assert dossier["usernames_tried"] == ["admin0", "admin1", "admin2"]
    assert dossier["distinct_passwords"] == 3
    assert dossier["sandbox_sessions"] == 1
    assert dossier["severity"] in {"medium", "high", "critical"}

    evidence_dir = Path(engine.evidence_dir)
    raw = (evidence_dir / "incidents.jsonl").read_text(encoding="utf-8")
    for index in range(3):
        assert f"hunter{index}" not in raw
    assert "admin0" in raw


def test_incident_api_requires_a_real_session(gated_client):
    for index in range(3):
        _login(gated_client, f"guess-{index}")

    # A sandboxed client sees the synthetic 404, not the incident report.
    assert gated_client.get("/security/deception/incidents").status_code == 404

    gated_client.cookies.clear()
    gated_client.post("/auth/gate", json={"passphrase": GATE_PASSPHRASE})
    _login(gated_client)
    report = gated_client.get("/security/deception/incidents")

    assert report.status_code == 200
    body = report.json()
    assert body["gate_enabled"] is True
    assert body["summary"]["tracked_sources"] >= 1
    assert isinstance(body["sources"], list)


def test_forwarded_headers_are_ignored_from_an_untrusted_peer():
    spoofed = resolve_client("198.51.100.9", {"x-forwarded-for": "10.9.9.9"})
    proxied = resolve_client(
        "10.0.0.5",
        {"x-forwarded-for": "203.0.113.44, 10.0.0.5"},
        ["10.0.0.0/8"],
    )

    assert spoofed.source_ip == "198.51.100.9"
    assert spoofed.proxy_trusted is False
    assert proxied.source_ip == "203.0.113.44"
    assert proxied.proxy_trusted is True


def test_long_forwarded_chain_retains_hops_closest_to_trusted_proxy():
    forged = [f"198.51.100.{index}" for index in range(1, 21)]
    actual = "203.0.113.44"
    trusted = "10.0.0.5"
    x_forwarded_for = ", ".join([*forged, actual, trusted])
    forwarded = ", ".join(
        [*(f"for={candidate}" for candidate in forged), f"for={actual}", f"for={trusted}"]
    )

    from_xff = resolve_client(
        trusted,
        {"x-forwarded-for": x_forwarded_for},
        ["10.0.0.0/8"],
    )
    from_forwarded = resolve_client(
        trusted,
        {"forwarded": forwarded},
        ["10.0.0.0/8"],
    )

    assert from_xff.source_ip == actual
    assert from_forwarded.source_ip == actual
    assert len(from_xff.forwarded_chain) <= 16
    assert len(from_forwarded.forwarded_chain) <= 16


def test_credential_digest_is_keyed_and_does_not_reveal_secret():
    secret = "reused-real-password"
    first = credential_digest(secret, b"a" * 32)
    repeated = credential_digest(secret, b"a" * 32)
    other_key = credential_digest(secret, b"b" * 32)

    assert first == repeated
    assert first != other_key
    assert secret not in first
    assert len(first) == 16


def test_evidence_survives_an_unwritable_directory(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    built = DeceptionEngine(enabled=True, evidence_dir=blocked, trigger_attempts=2)
    client = resolve_client("203.0.113.7", {"user-agent": "curl/8.4.0"})

    snapshot = built.record_login_failure(client, "admin", "pw")

    assert snapshot["login_failures"] == 1
    assert built.summary()["evidence_error"]


def test_decoy_flooding_does_not_lock_the_operator_out(monkeypatch, engine):
    """An intruder hammering the public form must not deny the operator entry.

    Regression: the decoy once shared the credential login's attempt budget, so
    sustained brute force at the front door exhausted the allowance the operator
    needed behind the gate.
    """
    auth = _auth(attempt_limit=5)
    monkeypatch.setattr(app_module, "_console_auth", auth)
    monkeypatch.setattr(app_module, "_entry_gate", _gate(auth))
    intruder = TestClient(app_module.app)

    # 401 while guessing, 200 once the sandbox opens, 429 if they outrun the
    # decoy's own budget — none of which may touch the operator's allowance.
    for index in range(40):
        assert _login(intruder, f"guess-{index}", f"admin{index}").status_code in {200, 401, 429}

    # The operator, arriving from the same address in their own browser, still
    # gets in.
    operator = TestClient(app_module.app)
    assert operator.post("/auth/gate", json={"passphrase": GATE_PASSPHRASE}).status_code == 200
    assert _login(operator).status_code == 200
    assert operator.get("/tools/list").status_code == 200


def test_decoy_flooding_is_still_bounded(monkeypatch, engine):
    """Separate budget is not an unlimited budget."""
    auth = _auth()
    monkeypatch.setattr(app_module, "_console_auth", auth)
    monkeypatch.setattr(app_module, "_entry_gate", _gate(auth))
    monkeypatch.setattr(
        app_module,
        "_decoy_limiter",
        AttemptLimiter(limit=3, window_seconds=60),
    )
    client = TestClient(app_module.app)

    statuses = [_login(client, f"guess-{index}").status_code for index in range(6)]

    assert 429 in statuses, "the decoy must still bound abuse"
