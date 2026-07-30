"""Authentication contract tests for the legacy Streamlit console."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def streamlit_app(monkeypatch):
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.session_state = _SessionState()
    fake_streamlit.set_page_config = lambda **kwargs: None
    fake_streamlit.markdown = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    module_path = Path(__file__).parents[2] / "frontend" / "streamlit_app.py"
    spec = importlib.util.spec_from_file_location("safeops_streamlit_auth_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.init_state()
    return module


def _install_transport(monkeypatch, module, handler):
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(*args, **kwargs):
        assert kwargs.get("trust_env") is False
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "Client", client_factory)


def _session_payload(*, authenticated: bool, csrf_token: str | None = None):
    return {
        "enabled": True,
        "authenticated": authenticated,
        "username": "operator" if authenticated else None,
        "expires_at": 1_900_000_000 if authenticated else None,
        "csrf_token": csrf_token,
    }


def test_gate_login_cookie_csrf_and_logout_round_trip(monkeypatch, streamlit_app):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        cookie = request.headers.get("cookie", "")
        if request.url.path == "/auth/session":
            return httpx.Response(200, json=_session_payload(authenticated=False))
        if request.url.path == "/auth/gate":
            assert json.loads(request.content) == {"passphrase": "entry phrase"}
            return httpx.Response(
                200,
                json={"unlocked": True},
                headers={"set-cookie": "safeops_stage=gate-token; Path=/; Secure; HttpOnly; SameSite=Strict"},
            )
        if request.url.path == "/auth/login":
            assert "safeops_stage=gate-token" in cookie
            assert json.loads(request.content) == {"username": "operator", "password": "correct"}
            return httpx.Response(
                200,
                json=_session_payload(authenticated=True, csrf_token="csrf-123"),
                headers={"set-cookie": "safeops_session=session-token; Path=/; Secure; HttpOnly; SameSite=Strict"},
            )
        if request.url.path == "/chat":
            assert "safeops_stage=gate-token" in cookie
            assert "safeops_session=session-token" in cookie
            assert request.headers["x-csrf-token"] == "csrf-123"
            return httpx.Response(200, json={"success": True})
        if request.url.path == "/auth/logout":
            assert "safeops_session=session-token" in cookie
            assert request.headers["x-csrf-token"] == "csrf-123"
            return httpx.Response(
                200,
                json=_session_payload(authenticated=False),
                headers=[
                    ("set-cookie", "safeops_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"),
                    ("set-cookie", "safeops_stage=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"),
                ],
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    _install_transport(monkeypatch, streamlit_app, handler)

    ok, session, error = streamlit_app.fetch_auth_session()
    assert ok is True and error == "" and session["authenticated"] is False

    unlocked, error = streamlit_app.submit_entry_passphrase("entry phrase")
    assert unlocked is True and error == ""
    assert streamlit_app.st.session_state.backend_cookies[0]["secure"] is True

    authenticated, error = streamlit_app.sign_in("operator", "correct")
    assert authenticated is True and error == ""
    assert streamlit_app.st.session_state.backend_csrf_token == "csrf-123"
    assert {record["name"] for record in streamlit_app.st.session_state.backend_cookies} == {
        "safeops_session",
        "safeops_stage",
    }
    assert all(record["secure"] is True for record in streamlit_app.st.session_state.backend_cookies)

    ok, payload, error = streamlit_app.api_request(
        "POST",
        "/chat",
        json_body={"session_id": "test", "message": "status"},
    )
    assert ok is True and error == "" and payload == {"success": True}

    logged_out, error = streamlit_app.sign_out()
    assert logged_out is True and error == ""
    assert streamlit_app.st.session_state.backend_cookies == []
    assert streamlit_app.st.session_state.backend_csrf_token == ""
    assert streamlit_app.st.session_state.backend_auth_session is None
    assert seen_paths == ["/auth/session", "/auth/gate", "/auth/login", "/chat", "/auth/logout"]


def test_gate_failure_never_falls_through_to_login(monkeypatch, streamlit_app):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/auth/gate":
            return httpx.Response(404, json={"detail": "Not Found"})
        raise AssertionError("login must not run after a failed entry gate")

    _install_transport(monkeypatch, streamlit_app, handler)

    unlocked, error = streamlit_app.submit_entry_passphrase("wrong phrase")

    assert unlocked is False
    assert error
    assert seen_paths == ["/auth/gate"]


def test_optional_gate_is_skipped_but_backend_still_decides_login(monkeypatch, streamlit_app):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.url.path == "/auth/login"
        return httpx.Response(401, json={"detail": "Invalid username or password"})

    _install_transport(monkeypatch, streamlit_app, handler)

    authenticated, error = streamlit_app.sign_in("operator", "correct")

    assert authenticated is False
    assert error
    assert seen_paths == ["/auth/login"]


def test_secure_cookie_is_not_downgraded_for_non_loopback_http(monkeypatch, streamlit_app):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/auth/gate":
            return httpx.Response(
                200,
                json={"unlocked": True},
                headers={"set-cookie": "safeops_stage=gate-token; Path=/; Secure; HttpOnly"},
            )
        if request.url.path == "/auth/login":
            assert "safeops_stage" not in request.headers.get("cookie", "")
            return httpx.Response(401, json={"detail": "Invalid username or password"})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    monkeypatch.setattr(streamlit_app, "API_BASE", "http://backend.internal:8000")
    _install_transport(monkeypatch, streamlit_app, handler)

    unlocked, error = streamlit_app.submit_entry_passphrase("entry phrase")
    assert unlocked is True and error == ""
    authenticated, error = streamlit_app.sign_in("operator", "correct")

    assert authenticated is False
    assert error
    assert seen_paths == ["/auth/gate", "/auth/login"]


def test_unauthenticated_session_reopens_an_expired_entry_gate(monkeypatch, streamlit_app):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/session"
        return httpx.Response(200, json=_session_payload(authenticated=False))

    _install_transport(monkeypatch, streamlit_app, handler)
    streamlit_app.st.session_state.backend_entry_unlocked = True
    streamlit_app.st.session_state.backend_entry_prompt_open = False
    streamlit_app.st.session_state.backend_cookies = []

    ok, session, error = streamlit_app.fetch_auth_session()

    assert ok is True and error == "" and session["authenticated"] is False
    assert streamlit_app.st.session_state.backend_entry_unlocked is False
    assert streamlit_app.st.session_state.backend_entry_prompt_open is False


def test_pending_entry_form_survives_session_refresh_and_processes_submission(
    monkeypatch,
    streamlit_app,
):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/auth/session":
            return httpx.Response(200, json=_session_payload(authenticated=False))
        if request.url.path == "/auth/gate":
            assert json.loads(request.content) == {"passphrase": "entry phrase"}
            return httpx.Response(
                200,
                json={"unlocked": True},
                headers={"set-cookie": "safeops_stage=gate-token; Path=/; Secure; HttpOnly"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    _install_transport(monkeypatch, streamlit_app, handler)
    streamlit_app.st.session_state.backend_entry_unlocked = False
    streamlit_app.st.session_state.backend_entry_prompt_open = True

    ok, session, error = streamlit_app.fetch_auth_session()

    assert ok is True and error == "" and session["authenticated"] is False
    assert streamlit_app.st.session_state.backend_entry_unlocked is False
    assert streamlit_app.st.session_state.backend_entry_prompt_open is True

    unlocked, error = streamlit_app.submit_entry_passphrase("entry phrase")

    assert unlocked is True and error == ""
    assert seen_paths == ["/auth/session", "/auth/gate"]


def test_valid_entry_ticket_keeps_streamlit_gate_unlocked(monkeypatch, streamlit_app):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/gate":
            return httpx.Response(
                200,
                json={"unlocked": True},
                headers={"set-cookie": "safeops_stage=gate-token; Path=/; Secure; HttpOnly"},
            )
        if request.url.path == "/auth/session":
            assert "safeops_stage=gate-token" in request.headers.get("cookie", "")
            return httpx.Response(200, json=_session_payload(authenticated=False))
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    _install_transport(monkeypatch, streamlit_app, handler)
    unlocked, error = streamlit_app.submit_entry_passphrase("entry phrase")
    assert unlocked is True and error == ""
    streamlit_app.st.session_state.backend_entry_unlocked = True

    ok, session, error = streamlit_app.fetch_auth_session()

    assert ok is True and error == "" and session["authenticated"] is False
    assert streamlit_app.st.session_state.backend_entry_unlocked is True


def test_entry_affordance_requires_three_clicks(streamlit_app):
    assert streamlit_app.st.session_state.backend_entry_prompt_open is False

    streamlit_app._register_entry_affordance_click()
    streamlit_app._register_entry_affordance_click()
    assert streamlit_app.st.session_state.backend_entry_prompt_open is False

    streamlit_app._register_entry_affordance_click()
    assert streamlit_app.st.session_state.backend_entry_prompt_open is True
    assert streamlit_app.st.session_state.backend_entry_affordance_count == 0


def test_main_does_not_render_protected_ui_without_backend_session(monkeypatch, streamlit_app):
    rendered = []
    monkeypatch.setattr(streamlit_app, "require_backend_session", lambda: False)
    monkeypatch.setattr(streamlit_app, "render_sidebar", lambda: rendered.append("sidebar"))
    monkeypatch.setattr(streamlit_app, "render_current_page", lambda: rendered.append("page"))

    streamlit_app.main()

    assert rendered == []


def test_disabled_auth_allows_loopback_streamlit_session(monkeypatch, streamlit_app):
    streamlit_app.st.session_state.last_chat_result = {"answer": "keep me"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/session"
        return httpx.Response(
            200,
            json={
                "enabled": False,
                "authenticated": False,
                "username": None,
                "expires_at": None,
                "csrf_token": None,
            },
        )

    _install_transport(monkeypatch, streamlit_app, handler)

    assert streamlit_app.require_backend_session() is True
    assert streamlit_app.st.session_state.last_chat_result == {"answer": "keep me"}
