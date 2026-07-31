"""FastAPI backend — REST API for SafeOpsAgent."""
from contextlib import asynccontextmanager
from ipaddress import ip_address

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Any
import hmac
import json
import threading
import time
import uuid
from pathlib import Path

from backend import config
from backend.agent.orchestrator import CHAT_READONLY_TOOLS, AgentOrchestrator
from backend.tools.registry import get_registry, ToolResult
from backend.audit.logger import AuditWriteError, get_logger
from backend.monitoring import get_monitoring_service
from backend.osprobe.probe import run_probe
from backend.security.codex_results import CodexResultError, CodexResultStore
from backend.security.client_identity import ClientIdentity, resolve_client
from backend.security.console_auth import (
    AttemptLimiter,
    AuthConfigurationError,
    ConsoleAuth,
    ConsoleIdentity,
    EntryGate,
    SandboxIdentity,
)
from backend.security.deception import get_deception_engine
from backend.security.sandbox_plane import SANDBOX_USERNAME, synthetic_response
from backend.security.guardrail import Guardrail
from backend.security.ai_resources import security_resources_payload
from backend.security.rule_labels import flatten_rule_hits, label_rules
from backend.security_intel import load_aisecurity_feed, load_integration_catalog
from backend.security_intel.rss import load_aisecurity_snapshot
from backend.llm.domestic_model_gateway import resolve_model_config

# Register all tools
from backend.tools import (
    disk_usage,
    process_list,
    network_status,
    large_file_scan,
    journal_query,
    port_tool,
    memory_tool,
    service_tool,
    cpu_tool,
    cleanup_tools,
    config_drift_tool,
    zombie_process_tool,
    disk_io_tool,
    impact_tool,
)

disk_usage.register()
process_list.register()
network_status.register()
large_file_scan.register()
journal_query.register()
port_tool.register()
memory_tool.register()
service_tool.register()
cpu_tool.register()
cleanup_tools.register()
config_drift_tool.register()
zombie_process_tool.register()
disk_io_tool.register()
impact_tool.register()

APP_VERSION = "1.3.0"
SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}
TOOL_EXECUTION_ERROR = "Tool execution failed"


def _build_console_auth() -> ConsoleAuth:
    return ConsoleAuth(
        enabled=config.CONSOLE_AUTH_ENABLED,
        username=config.CONSOLE_AUTH_USERNAME,
        password_hash=config.CONSOLE_AUTH_PASSWORD_HASH,
        session_secret=config.CONSOLE_AUTH_SESSION_SECRET,
        session_ttl_seconds=config.CONSOLE_AUTH_SESSION_TTL_SECONDS,
        login_attempt_limit=config.CONSOLE_LOGIN_ATTEMPT_LIMIT,
        login_window_seconds=config.CONSOLE_LOGIN_WINDOW_SECONDS,
        login_attempt_key_limit=config.CONSOLE_LOGIN_ATTEMPT_KEY_LIMIT,
    )


_console_auth = _build_console_auth()


def _build_entry_gate(auth: ConsoleAuth) -> EntryGate:
    """Build the concealed entry gate, signed with a dedicated subkey.

    The gate is inert unless a passphrase verifier is configured, which keeps a
    default deployment on the familiar single-factor login.
    """
    return EntryGate(
        passphrase_hash=config.CONSOLE_ENTRY_GATE_HASH,
        signing_key=auth.entry_gate_subkey() if auth.sandbox_capable else b"",
        ttl_seconds=config.CONSOLE_ENTRY_GATE_TTL_SECONDS,
        attempt_limit=config.CONSOLE_ENTRY_GATE_ATTEMPT_LIMIT,
        window_seconds=config.CONSOLE_ENTRY_GATE_WINDOW_SECONDS,
    )


_entry_gate = _build_entry_gate(_console_auth)

# Flood budget for the public decoy form. Separate from both the entry gate and
# the credential login so that hammering the decoy can never exhaust the
# operator's allowance at the real entrance.
_decoy_limiter = AttemptLimiter(
    limit=config.HONEYPOT_DECOY_ATTEMPT_LIMIT,
    window_seconds=config.HONEYPOT_DECOY_WINDOW_SECONDS,
    key_limit=config.CONSOLE_LOGIN_ATTEMPT_KEY_LIMIT,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start metric sampling only when the server actually runs.

    Importing the app (tests, tooling) must not spawn background threads,
    so this deliberately lives in lifespan rather than at module scope.
    """
    _console_auth.require_configuration()
    get_monitoring_service().start()
    yield
    get_monitoring_service().stop()


app = FastAPI(title="SafeOpsAgent", version=APP_VERSION, lifespan=lifespan)
CONSOLE_DIST_DIR = Path(__file__).resolve().parent / "static" / "console"


@app.middleware("http")
async def enforce_console_auth(request: Request, call_next):
    if _is_public_route(request.url.path) or request.method == "OPTIONS":
        return await call_next(request)

    try:
        _console_auth.require_configuration()
    except AuthConfigurationError:
        return _auth_error(503, "Console authentication is not configured")

    client = _resolve_client(request)
    if (
        not _console_auth.enabled
        and not config.CONSOLE_AUTH_ALLOW_INSECURE_NON_LOOPBACK
        and not _is_loopback_address(client.peer_ip)
    ):
        # Deliberately keyed on the transport peer: a trusted proxy forwarding a
        # loopback address must not unlock an unauthenticated console.
        return _auth_error(403, "Disabled authentication is restricted to loopback clients")

    identity = _request_identity(request)
    if identity is None:
        # A deception session never reaches a real handler. It is answered here,
        # from fabricated data, and the attempt is recorded as evidence.
        sandbox = _sandbox_identity(request)
        if sandbox is not None:
            return await _sandbox_reply(request, client, sandbox)
        return _auth_error(401, "Authentication required")
    if (
        _console_auth.enabled
        and request.method.upper() not in SAFE_HTTP_METHODS
        and not _console_auth.verify_csrf(identity, request.headers.get("X-CSRF-Token", ""))
    ):
        return _auth_error(403, "CSRF validation failed")
    request.state.console_identity = identity
    request.scope["safeops.console_auth_enforced"] = True
    return await call_next(request)


# CORS remains outside the authentication middleware so browser clients also
# receive policy headers on 401/403 responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.CORS_ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

# Optional MCP SSE transport (requires mcp SDK, see backend/requirements-mcp.txt).
# When the SDK is installed, MCP clients connect via /mcp/sse + /mcp/messages/.
# When not installed, stdio transport still works and the FastAPI service is unaffected.
try:
    from backend.mcp_server import mount_sse_server
    mount_sse_server(app)
except Exception:
    # MCP SDK not installed; SSE transport unavailable, stdio still works
    pass

# Shared state
_orchestrator: Optional[AgentOrchestrator] = None
_confirmations: dict[str, dict] = {}
_confirmation_lock = threading.RLock()


def get_orch() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    session_id: str = ""


class ToolConfirmRequest(BaseModel):
    confirmation_token: str
    session_id: str = ""


class AuthCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class EntryPassphrase(BaseModel):
    passphrase: str = Field(min_length=1, max_length=512)


@app.get("/health")
def health():
    return {"status": "ok", "agent": "SafeOpsAgent", "version": APP_VERSION}


def _is_public_route(path: str) -> bool:
    return (
        path == "/health"
        or path == "/favicon.ico"
        or path in {"/auth/session", "/auth/login", "/auth/gate"}
        or path == "/console"
        or path.startswith("/console/")
    )


def _auth_error(status_code: int, detail: str) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if status_code == 401:
        headers["WWW-Authenticate"] = "Cookie"
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


def _request_identity(request: Request) -> ConsoleIdentity | None:
    token = request.cookies.get(config.CONSOLE_AUTH_COOKIE_NAME, "")
    return _console_auth.authenticate(token)


def _sandbox_identity(request: Request) -> SandboxIdentity | None:
    """Resolve a deception session from the same cookie name as a real session.

    Sharing the cookie name denies a client any local signal about which kind of
    session it holds; the two are separated cryptographically instead.
    """
    token = request.cookies.get(config.CONSOLE_AUTH_COOKIE_NAME, "")
    return _console_auth.authenticate_sandbox(token)


def _resolve_client(request: Request) -> ClientIdentity:
    peer = request.client.host if request.client and request.client.host else ""
    return resolve_client(peer, request.headers, config.CONSOLE_TRUSTED_PROXIES)


def _client_key(request: Request) -> str:
    return _resolve_client(request).rate_limit_key


def _is_loopback_address(value: str) -> bool:
    try:
        return ip_address(value).is_loopback
    except ValueError:
        return value.casefold() == "localhost"


async def _sandbox_reply(
    request: Request,
    client: ClientIdentity,
    sandbox: SandboxIdentity,
) -> JSONResponse:
    """Answer a sandboxed request from fabricated data and record the attempt."""
    method = request.method.upper()
    path = request.url.path

    if method not in SAFE_HTTP_METHODS and not hmac.compare_digest(
        sandbox.csrf_token,
        request.headers.get("X-CSRF-Token", ""),
    ):
        # Mirrors the real console so the sandbox behaves identically.
        return _auth_error(403, "CSRF validation failed")

    body: dict[str, Any] = {}
    if method == "POST":
        try:
            parsed = await request.json()
            if isinstance(parsed, dict):
                body = parsed
        except Exception:
            body = {}

    engine = get_deception_engine()
    detail: dict[str, Any] = {}
    if body.get("tool_name"):
        detail["tool_name"] = str(body["tool_name"])[:64]
    if body.get("message"):
        detail["message"] = str(body["message"])[:200]
    engine.record_sandbox_activity(client, sandbox.session_id, method, path, detail)

    if path == "/auth/logout":
        response = JSONResponse(
            {
                "enabled": True,
                "authenticated": False,
                "username": None,
                "expires_at": None,
                "csrf_token": None,
            },
            headers={"Cache-Control": "no-store"},
        )
        _clear_auth_cookie(response)
        return response

    status_code, payload = synthetic_response(
        sandbox.session_id,
        method,
        path,
        dict(request.query_params),
        body,
    )
    return JSONResponse(status_code=status_code, content=payload, headers={"Cache-Control": "no-store"})


def _sandbox_session_payload(sandbox: SandboxIdentity) -> dict[str, Any]:
    """Present a deception session as an ordinary authenticated session."""
    return {
        "enabled": True,
        "authenticated": True,
        "username": SANDBOX_USERNAME,
        "expires_at": sandbox.expires_at,
        "csrf_token": sandbox.csrf_token,
    }


def _auth_session_payload(identity: ConsoleIdentity | None = None) -> dict[str, Any]:
    authenticated = identity is not None
    return {
        "enabled": _console_auth.enabled,
        "authenticated": authenticated,
        "username": identity.username if identity else None,
        "expires_at": identity.expires_at if identity and identity.expires_at else None,
        "csrf_token": identity.csrf_token if identity and identity.csrf_token else None,
    }


def _clear_auth_cookie(response: JSONResponse) -> None:
    for cookie_name in (
        config.CONSOLE_AUTH_COOKIE_NAME,
        config.CONSOLE_ENTRY_GATE_COOKIE_NAME,
    ):
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=config.CONSOLE_AUTH_SECURE_COOKIE,
            httponly=True,
            samesite="strict",
        )


def _audit_auth_event(request: Request, event: str, decision: str, reason: str) -> None:
    """Record authentication decisions without storing submitted credentials."""
    rejected = decision != "allow"
    get_logger().log({
        "request_id": str(uuid.uuid4())[:8],
        "user_input": event,
        "intent": "console_auth",
        "tool_arguments": {"client": _client_key(request)},
        "risk_level": 3 if rejected else 1,
        "risk_score": 100 if rejected else 10,
        "risk_level_text": "high" if rejected else "low",
        "legacy_risk_level": 3 if rejected else 1,
        "security_decision": decision,
        "security_reason": reason,
        "confirmation_required": False,
        "executed": False,
        "execution_success": False,
        "final_response": reason,
    })


@app.get("/auth/session", include_in_schema=False)
def auth_session(request: Request):
    try:
        _console_auth.require_configuration()
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Console authentication is not configured") from exc

    identity = _request_identity(request)
    if identity is None:
        sandbox = _sandbox_identity(request)
        if sandbox is not None:
            response = JSONResponse(_sandbox_session_payload(sandbox))
            response.headers["Cache-Control"] = "no-store"
            return response

    response = JSONResponse(_auth_session_payload(identity))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/auth/gate", include_in_schema=False)
def auth_gate(request: Request, submission: EntryPassphrase):
    """Verify the concealed entry passphrase and open the operator login.

    Passing the gate grants no console access on its own: it only makes the
    credential login reachable. Failures are rate limited and recorded, so
    probing the gate is itself evidence.
    """
    client = _resolve_client(request)
    engine = get_deception_engine()

    if not _entry_gate.enabled:
        # Nothing to pass. Reported as a plain rejection so an unconfigured
        # deployment does not advertise that a gate exists.
        return _auth_error(404, "Not Found")

    if not _entry_gate.reserve_attempt(client.rate_limit_key):
        engine.record_gate_failure(client, reason="gate_rate_limited")
        _audit_auth_event(request, "console_entry_gate", "reject", "gate_rate_limited")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many attempts"},
            headers={
                "Cache-Control": "no-store",
                "Retry-After": str(config.CONSOLE_ENTRY_GATE_WINDOW_SECONDS),
            },
        )

    if not _entry_gate.verify_passphrase(submission.passphrase):
        engine.record_gate_failure(client, reason="invalid_passphrase")
        _audit_auth_event(request, "console_entry_gate", "reject", "invalid_passphrase")
        return _auth_error(404, "Not Found")

    _entry_gate.clear_attempts(client.rate_limit_key)
    _audit_auth_event(request, "console_entry_gate", "allow", "gate_passed")
    response = JSONResponse({"unlocked": True}, headers={"Cache-Control": "no-store"})
    response.set_cookie(
        config.CONSOLE_ENTRY_GATE_COOKIE_NAME,
        _entry_gate.issue_token(),
        max_age=_entry_gate.ttl_seconds,
        path="/",
        secure=config.CONSOLE_AUTH_SECURE_COOKIE,
        httponly=True,
        samesite="strict",
    )
    return response


def _open_sandbox_session(request: Request, client: ClientIdentity) -> JSONResponse:
    """Hand a persistent guesser a deception session that looks like success."""
    engine = get_deception_engine()
    token, sandbox = _console_auth.issue_sandbox_session(config.HONEYPOT_SESSION_TTL_SECONDS)
    engine.record_sandbox_opened(client, sandbox.session_id)
    _audit_auth_event(request, "console_login", "reject", "deception_session_opened")
    response = JSONResponse(
        _sandbox_session_payload(sandbox),
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        config.CONSOLE_AUTH_COOKIE_NAME,
        token,
        max_age=_console_auth.session_ttl_seconds,
        path="/",
        secure=config.CONSOLE_AUTH_SECURE_COOKIE,
        httponly=True,
        samesite="strict",
    )
    return response


@app.post("/auth/login", include_in_schema=False)
def auth_login(request: Request, credentials: AuthCredentials):
    try:
        _console_auth.require_configuration()
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Console authentication is not configured") from exc

    if not _console_auth.enabled:
        return JSONResponse(
            _auth_session_payload(_console_auth.authenticate("")),
            headers={"Cache-Control": "no-store"},
        )

    client = _resolve_client(request)
    client_key = client.rate_limit_key
    engine = get_deception_engine()
    gate_token = request.cookies.get(config.CONSOLE_ENTRY_GATE_COOKIE_NAME, "")
    gate_passed = _entry_gate.verify_token(gate_token) if _entry_gate.enabled else True

    if not gate_passed:
        # Decoy path, metered against its own budget. Flooding the public form
        # must not consume the operator's allowance at the real entrance, so the
        # limits below only bound abuse — reaching the honeypot is the intended
        # outcome, not an error.
        if not _decoy_limiter.reserve(client_key):
            engine.record_login_failure(
                client,
                credentials.username,
                credentials.password,
                reason="decoy_rate_limited",
            )
            _audit_auth_event(request, "console_login", "reject", "decoy_rate_limited")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts"},
                headers={
                    "Cache-Control": "no-store",
                    "Retry-After": str(_decoy_limiter.window_seconds),
                },
            )
        # The credential verifier is still executed and its result discarded, so
        # the decoy is indistinguishable from the real login by response timing.
        # Correct credentials presented here cannot grant access, and are
        # flagged: they imply the operator password leaked.
        credentials_matched = _console_auth.verify_credentials(
            credentials.username,
            credentials.password,
        )
        reason = "valid_credentials_without_gate" if credentials_matched else "decoy_login_failure"
        engine.record_login_failure(client, credentials.username, credentials.password, reason=reason)
        _audit_auth_event(request, "console_login", "reject", reason)
        if engine.should_open_sandbox(client) and _console_auth.sandbox_capable:
            return _open_sandbox_session(request, client)
        return _auth_error(401, "Invalid username or password")

    if not _console_auth.reserve_attempt(client_key):
        engine.record_login_failure(
            client,
            credentials.username,
            credentials.password,
            reason="login_rate_limited",
        )
        _audit_auth_event(request, "console_login", "reject", "login_rate_limited")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many login attempts"},
            headers={
                "Cache-Control": "no-store",
                "Retry-After": str(_console_auth.login_window_seconds),
            },
        )

    if not _console_auth.verify_credentials(credentials.username, credentials.password):
        engine.record_login_failure(client, credentials.username, credentials.password)
        _audit_auth_event(request, "console_login", "reject", "invalid_credentials")
        return _auth_error(401, "Invalid username or password")

    _console_auth.clear_attempts(client_key)
    engine.record_login_success(client, credentials.username)
    token, identity = _console_auth.issue_session()
    response = JSONResponse(
        _auth_session_payload(identity),
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        config.CONSOLE_AUTH_COOKIE_NAME,
        token,
        max_age=_console_auth.session_ttl_seconds,
        path="/",
        secure=config.CONSOLE_AUTH_SECURE_COOKIE,
        httponly=True,
        samesite="strict",
    )
    _audit_auth_event(request, "console_login", "allow", "authenticated")
    return response


@app.post("/auth/logout", include_in_schema=False)
def auth_logout(request: Request):
    identity = getattr(request.state, "console_identity", None)
    _audit_auth_event(request, "console_logout", "allow", "session_terminated")
    response = JSONResponse(
        _auth_session_payload(None if _console_auth.enabled else identity),
        headers={"Cache-Control": "no-store"},
    )
    _clear_auth_cookie(response)
    return response


@app.get("/security/deception/incidents", include_in_schema=False)
def deception_incidents(limit: int = 50):
    """Attribution dossiers for front-door activity. Requires a real session."""
    engine = get_deception_engine()
    bounded = _safe_limit(limit, default=50, maximum=500)
    return {
        "summary": engine.summary(),
        "gate_enabled": _entry_gate.enabled,
        "sources": engine.dossiers(bounded),
        "recent_evidence": engine.read_evidence(bounded),
    }


def _console_response(asset_path: str = "") -> FileResponse:
    """Serve the built Vue console with a fallback scoped to /console only."""
    console_root = CONSOLE_DIST_DIR.resolve()
    # CodeQL does not model the resolve + relative_to containment check below.
    requested = (console_root / asset_path).resolve()  # lgtm[py/path-injection]
    try:
        requested.relative_to(console_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Console asset not found") from exc

    if asset_path and requested.is_file():  # lgtm[py/path-injection]
        return FileResponse(  # lgtm[py/path-injection]
            requested,  # lgtm[py/path-injection]
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    index_file = console_root / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=503,
            detail="Operations console has not been built",
        )
    return FileResponse(index_file, headers={"Cache-Control": "no-cache"})


def _favicon_response() -> FileResponse:
    favicon_file = CONSOLE_DIST_DIR / "favicon.svg"
    if not favicon_file.is_file():
        raise HTTPException(status_code=404, detail="Favicon has not been built")
    return FileResponse(
        favicon_file,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/favicon.ico", include_in_schema=False)
@app.head("/favicon.ico", include_in_schema=False)
def favicon_root():
    return _favicon_response()


@app.get("/console/favicon.ico", include_in_schema=False)
@app.head("/console/favicon.ico", include_in_schema=False)
def favicon_console():
    return _favicon_response()


@app.get("/console", include_in_schema=False)
def console_root():
    return _console_response()


@app.get("/console/{asset_path:path}", include_in_schema=False)
def console_spa(asset_path: str):
    return _console_response(asset_path)


@app.get("/agent/status")
def agent_status():
    tools = get_registry().list_tools()
    tool_names = {tool["name"] for tool in tools}
    model_config = resolve_model_config()
    model_metadata = model_config.public_metadata()
    return {
        "status": "online",
        **model_metadata,
        "configured_provider": model_metadata["model_provider"],
        "guardrail_enabled": True,
        "risk_scoring_enabled": True,
        "audit_enabled": True,
        "tools_count": len(tools),
        "readonly_tools_count": len(tool_names.intersection(CHAT_READONLY_TOOLS)),
        "security_summary": "安全护栏已启用，模型不能直接执行系统命令。",
        "deployment_hint": "当前为用户态安全 Agent，不修改系统内核；无 API Key 时自动使用离线安全模式。",
    }


@app.get("/security/resources")
def security_resources():
    return security_resources_payload()


@app.get("/security/integrations")
def security_integrations():
    """Expose the reviewed local registry; this endpoint never installs tools."""
    return load_integration_catalog()


@app.get("/security/intel/aisecurity")
def aisecurity_intel(limit: int = 20, refresh: bool = False):
    """Return sanitized, untrusted RSS metadata with deterministic mappings."""
    feed = load_aisecurity_feed(timeout_seconds=3.0) if refresh else load_aisecurity_snapshot()
    bounded_limit = _safe_limit(limit, default=20, maximum=40)
    feed["items"] = feed.get("items", [])[:bounded_limit]
    return feed


def _codex_result_store() -> CodexResultStore | None:
    if not config.CODEX_SECURITY_RESULTS_DIR:
        return None
    try:
        return CodexResultStore(
            Path(config.CODEX_SECURITY_RESULTS_DIR),
            config.PROJECT_DIR,
        )
    except (CodexResultError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Codex Security result directory is unavailable",
        ) from exc


@app.get("/security/codex/scans")
def codex_security_scans(limit: int = 20):
    store = _codex_result_store()
    if store is None:
        return {
            "configured": False,
            "scans": [],
            "discovery_limited": False,
            "discovery_limit_reasons": [],
            "entries_examined": 0,
        }
    page = store.list_scans_page(limit=_safe_limit(limit, default=20, maximum=100))
    return {
        "configured": True,
        **page,
    }


@app.get("/security/codex/scans/{scan_id}")
def codex_security_scan(scan_id: str, finding_limit: int = 100):
    store = _codex_result_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Codex Security result directory is not configured")
    try:
        return store.load(
            scan_id,
            finding_limit=_safe_limit(finding_limit, default=100, maximum=200),
        )
    except CodexResultError as exc:
        raise HTTPException(
            status_code=422,
            detail="Codex Security scan failed containment or integrity validation",
        ) from exc


@app.get("/tools/list")
def list_tools():
    return {"tools": get_registry().list_tools()}


@app.post("/tools/call")
def call_tool(req: ToolCallRequest):
    request_id = str(uuid.uuid4())[:8]
    started = int(time.time() * 1000)
    registry = get_registry()
    guardrail = Guardrail()
    available_tool_names = [tool["name"] for tool in registry.list_tools()]
    rule_hits = {
        "input": [],
        "tool_selection": [],
        "tool_args": [],
        "tool_output": [],
    }
    risk_score = 10
    risk_level = "low"
    legacy_risk_level = 1
    risk_factors = []
    matched_rules = []
    executed = False
    execution_result: Any = None
    tool_audit: dict = {}
    security_decision = "allow"
    security_reason = ""
    error = ""
    confirmation_token = None
    dry_run_result = None
    confirmation_events = []

    def apply_risk(risk_assessment):
        nonlocal risk_score, risk_level, legacy_risk_level
        nonlocal risk_factors, matched_rules, security_decision
        risk_score = risk_assessment.score
        risk_level = risk_assessment.risk_level
        legacy_risk_level = risk_assessment.legacy_risk_level
        risk_factors = risk_assessment.factors
        matched_rules = risk_assessment.matched_rules
        security_decision = risk_assessment.security_decision

    def finish(success: bool, result: Any = None):
        nonlocal execution_result
        duration = int(time.time() * 1000) - started
        execution_result = result if result is not None else execution_result
        readable_rule_labels = _rule_labels_for(matched_rules, rule_hits)
        get_logger().log({
            "session_id": req.session_id,
            "request_id": request_id,
            "user_input": _tool_call_text(req.tool_name, req.arguments),
            "intent": "direct_tool_call",
            "selected_tool": req.tool_name,
            "tool_arguments": req.arguments,
            "risk_level": legacy_risk_level,
            "risk_score": risk_score,
            "risk_level_text": risk_level,
            "legacy_risk_level": legacy_risk_level,
            "security_decision": security_decision,
            "security_reason": security_reason,
            "matched_rules": matched_rules,
            "confirmation_required": security_decision == "confirm",
            "executed": executed,
            "actual_command": tool_audit.get("actual_command", []),
            "executor_user": tool_audit.get("executor_user", ""),
            "execution_success": tool_audit.get("execution_success", False),
            "execution_result": execution_result or {},
            "stdout_summary": tool_audit.get("stdout_summary", ""),
            "stderr_summary": tool_audit.get("stderr_summary", ""),
            "final_response": security_reason or security_decision if success else error,
            "rule_hits": rule_hits,
            "confirmation_events": confirmation_events,
            "duration_ms": duration,
        })
        return {
            "success": success,
            "request_id": request_id,
            "tool_name": req.tool_name,
            "arguments": req.arguments,
            "risk_level": risk_level,
            "legacy_risk_level": legacy_risk_level,
            "risk_score": risk_score,
            "risk_band": risk_level,
            "risk_factors": risk_factors,
            "matched_rules": matched_rules,
            "rule_labels": readable_rule_labels,
            "security_decision": security_decision,
            "security_reason": security_reason,
            "confirmation_required": security_decision == "confirm",
            "executed": executed,
            "confirmation_token": confirmation_token,
            "dry_run_result": dry_run_result,
            "result": result,
            "error": error,
            "rule_hits": rule_hits,
            "rule_labels": readable_rule_labels,
        }

    if not registry.get_schema(req.tool_name):
        risk_assessment = guardrail.score_100(extra_factors=[f"tool_not_found:{req.tool_name}"])
        apply_risk(risk_assessment)
        security_reason = "blocked_tool_not_found"
        error = f"Tool '{req.tool_name}' not found"
        rule_hits["tool_selection"].append(f"tool_not_found:{req.tool_name}")
        return finish(False)

    valid, validation_error = registry.validate_args(req.tool_name, req.arguments)
    if not valid:
        risk_assessment = guardrail.score_100(
            tool_name=req.tool_name,
            arguments=req.arguments,
            extra_factors=[f"schema_validation:{validation_error}"],
        )
        apply_risk(risk_assessment)
        security_reason = "blocked_invalid_arguments"
        error = validation_error
        rule_hits["tool_args"].append(f"schema_validation:{validation_error}")
        return finish(False)

    input_check = guardrail.check_input(_tool_call_text(req.tool_name, req.arguments))
    tool_check = guardrail.validate_tool_selection(req.tool_name, available_tool_names)
    arg_check = guardrail.validate_tool_args(req.tool_name, req.arguments)
    risk_assessment = guardrail.score_100(
        input_check=input_check,
        tool_check=tool_check,
        arg_check=arg_check,
        tool_name=req.tool_name,
        arguments=req.arguments,
    )
    apply_risk(risk_assessment)
    rule_hits["input"].extend(input_check.rule_hits)
    rule_hits["tool_selection"].extend(tool_check.rule_hits)
    rule_hits["tool_args"].extend(arg_check.rule_hits)

    if security_decision != "allow":
        security_reason = "confirmation_required" if security_decision == "confirm" else "blocked_by_guardrail"
        if security_decision == "confirm":
            dry_run_result = _build_dry_run_result(
                req.tool_name,
                req.arguments,
                risk_score,
                risk_level,
                legacy_risk_level,
                security_decision,
                security_reason,
                matched_rules,
                risk_factors,
            )
            error = dry_run_result["message"]
            confirmation_token = _create_confirmation(
                request_id,
                req.session_id,
                req.tool_name,
                req.arguments,
                risk_score,
                risk_level,
                legacy_risk_level,
                security_decision,
                security_reason,
                matched_rules,
                risk_factors,
                rule_hits,
            )
            confirmation_events.append("confirmation_requested")
            return finish(False, dry_run_result)
        error = "Tool call blocked by security guardrail"
        return finish(False)

    try:
        tool_result = registry.call(req.tool_name, req.arguments)
        executed = tool_result.status == "success"
    except Exception as exc:
        exception_type = type(exc).__name__
        tool_audit.update({
            "execution_success": False,
            "stderr_summary": f"{exception_type}: internal tool failure",
        })
        security_decision = "reject"
        security_reason = "tool_exception"
        error = TOOL_EXECUTION_ERROR
        execution_result = {"tool": req.tool_name, "status": "exception", "error": error}
        return finish(False, execution_result)

    result_payload = _tool_result_payload(tool_result)
    tool_audit.update(_tool_audit_metadata(tool_result))
    execution_result = result_payload
    output_text = _tool_output_text(tool_result, result_payload)
    output_check = guardrail.check_tool_output(output_text)
    rule_hits["tool_output"].extend(output_check.rule_hits)
    risk_assessment = guardrail.score_100(
        input_check=input_check,
        tool_check=tool_check,
        arg_check=arg_check,
        output_check=output_check,
        tool_name=req.tool_name,
        arguments=req.arguments,
    )
    apply_risk(risk_assessment)

    if not output_check.passed:
        security_decision = "reject"
        security_reason = "blocked_tool_output"
        error = "Tool output blocked by security guardrail"
        return finish(False, result_payload)

    security_decision = "allow"
    security_reason = "executed"
    success = tool_result.status == "success"
    if not success:
        error = tool_result.error or tool_result.status
    return finish(success, result_payload)


@app.post("/tools/confirm")
def confirm_tool(req: ToolConfirmRequest):
    request_id = str(uuid.uuid4())[:8]
    started = int(time.time() * 1000)
    registry = get_registry()
    guardrail = Guardrail()
    token_record, token_error = _consume_confirmation(req.confirmation_token)
    confirmation_events = []
    rule_hits = {
        "input": [],
        "tool_selection": [],
        "tool_args": [],
        "tool_output": [],
    }
    tool_audit: dict = {}
    executed = False
    execution_result: Any = {}
    error = ""
    security_reason = ""
    original_request_id = token_record.get("original_request_id") if token_record else ""
    tool_name = token_record.get("tool_name", "") if token_record else ""
    arguments = token_record.get("arguments", {}) if token_record else {}
    risk_score = token_record.get("risk_score", 100) if token_record else 100
    risk_level = token_record.get("risk_level", "forbidden") if token_record else "forbidden"
    legacy_risk_level = token_record.get("legacy_risk_level", 5) if token_record else 5
    risk_factors = token_record.get("risk_factors", []) if token_record else []
    matched_rules = token_record.get("matched_rules", []) if token_record else []
    security_decision = "reject"

    def finish(success: bool, result: Any = None):
        nonlocal execution_result
        duration = int(time.time() * 1000) - started
        execution_result = result if result is not None else execution_result
        readable_rule_labels = _rule_labels_for(matched_rules, rule_hits)
        get_logger().log({
            "session_id": req.session_id or (token_record or {}).get("session_id", ""),
            "request_id": request_id,
            "user_input": json.dumps(
                {
                    "confirmation_token_present": bool(req.confirmation_token),
                    "original_request_id": original_request_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            "intent": "confirm_tool_call",
            "selected_tool": tool_name,
            "tool_arguments": arguments,
            "risk_level": legacy_risk_level,
            "risk_score": risk_score,
            "risk_level_text": risk_level,
            "legacy_risk_level": legacy_risk_level,
            "security_decision": security_decision,
            "security_reason": security_reason,
            "matched_rules": matched_rules,
            "confirmation_required": False,
            "executed": executed,
            "actual_command": tool_audit.get("actual_command", []),
            "executor_user": tool_audit.get("executor_user", ""),
            "execution_success": tool_audit.get("execution_success", False),
            "execution_result": execution_result or {},
            "stdout_summary": tool_audit.get("stdout_summary", ""),
            "stderr_summary": tool_audit.get("stderr_summary", ""),
            "final_response": security_reason if success else error,
            "rule_hits": rule_hits,
            "confirmation_events": confirmation_events,
            "original_request_id": original_request_id,
            "duration_ms": duration,
        })
        return {
            "success": success,
            "request_id": request_id,
            "original_request_id": original_request_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "risk_level": risk_level,
            "legacy_risk_level": legacy_risk_level,
            "risk_score": risk_score,
            "risk_band": risk_level,
            "risk_factors": risk_factors,
            "matched_rules": matched_rules,
            "rule_labels": readable_rule_labels,
            "security_decision": security_decision,
            "security_reason": security_reason,
            "confirmation_required": False,
            "executed": executed,
            "result": result,
            "error": error,
            "rule_hits": rule_hits,
            "rule_labels": readable_rule_labels,
        }

    if token_error:
        security_reason = token_error
        error = {
            "confirmation_token_invalid": "Confirmation token not found or expired",
            "confirmation_token_used": "Confirmation token has already been used",
            "confirmation_token_expired": "Confirmation token has expired",
            "confirmation_token_not_confirmable": "Confirmation token is not confirmable",
        }[token_error]
        return finish(False)

    available_tool_names = [tool["name"] for tool in registry.list_tools()]
    valid, validation_error = registry.validate_args(tool_name, arguments)
    if not valid:
        security_reason = "blocked_invalid_arguments"
        error = validation_error
        matched_rules = [*matched_rules, f"schema_validation:{validation_error}"]
        rule_hits["tool_args"].append(f"schema_validation:{validation_error}")
        return finish(False)

    input_check = guardrail.check_input(_tool_call_text(tool_name, arguments))
    tool_check = guardrail.validate_tool_selection(tool_name, available_tool_names)
    arg_check = guardrail.validate_tool_args(tool_name, arguments)
    reassessment = guardrail.score_100(
        input_check=input_check,
        tool_check=tool_check,
        arg_check=arg_check,
        tool_name=tool_name,
        arguments=arguments,
    )
    risk_score = reassessment.score
    risk_level = reassessment.risk_level
    legacy_risk_level = reassessment.legacy_risk_level
    risk_factors = reassessment.factors
    matched_rules = reassessment.matched_rules
    security_decision = reassessment.security_decision
    rule_hits["input"].extend(input_check.rule_hits)
    rule_hits["tool_selection"].extend(tool_check.rule_hits)
    rule_hits["tool_args"].extend(arg_check.rule_hits)

    if security_decision == "reject" or risk_level == "forbidden":
        security_reason = "blocked_by_guardrail"
        error = "Confirmed tool call became forbidden during revalidation"
        return finish(False)

    try:
        tool_result = registry.call(tool_name, arguments)
        executed = tool_result.status == "success"
    except Exception as exc:
        exception_type = type(exc).__name__
        security_decision = "reject"
        security_reason = "tool_exception"
        error = TOOL_EXECUTION_ERROR
        tool_audit.update({
            "execution_success": False,
            "stderr_summary": f"{exception_type}: internal tool failure",
        })
        return finish(False, {"tool": tool_name, "status": "exception", "error": error})

    result_payload = _tool_result_payload(tool_result)
    tool_audit.update(_tool_audit_metadata(tool_result))
    output_text = _tool_output_text(tool_result, result_payload)
    output_check = guardrail.check_tool_output(output_text)
    rule_hits["tool_output"].extend(output_check.rule_hits)
    reassessment = guardrail.score_100(
        input_check=input_check,
        tool_check=tool_check,
        arg_check=arg_check,
        output_check=output_check,
        tool_name=tool_name,
        arguments=arguments,
    )
    risk_score = reassessment.score
    risk_level = reassessment.risk_level
    legacy_risk_level = reassessment.legacy_risk_level
    risk_factors = reassessment.factors
    matched_rules = reassessment.matched_rules

    if not output_check.passed:
        security_decision = "reject"
        security_reason = "blocked_tool_output"
        error = "Tool output blocked by security guardrail"
        return finish(False, result_payload)

    confirmation_events.append("confirmation_approved")
    security_decision = "allow"
    security_reason = "confirmed_executed"
    success = tool_result.status == "success"
    if not success:
        error = tool_result.error or tool_result.status
    return finish(success, result_payload)


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.session_id:
        req.session_id = str(uuid.uuid4())
    if not req.message or len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="Invalid message")
    try:
        result = get_orch().run(req.session_id, req.message)
    except AuditWriteError as exc:
        # Refusing is the correct answer: the audit log is the only record
        # that the guardrail ran, so an unrecordable request is not served.
        raise HTTPException(
            status_code=503,
            detail="Audit log is unavailable; the request was refused without executing anything",
        ) from exc
    result["session_id"] = req.session_id
    return result


def _tool_call_text(tool_name: str, arguments: dict) -> str:
    return json.dumps(
        {"tool_name": tool_name, "arguments": arguments},
        ensure_ascii=False,
        sort_keys=True,
    )


def _cleanup_confirmations(now: float | None = None, exclude_token: str = "") -> None:
    with _confirmation_lock:
        current = time.time() if now is None else now
        expired_tokens = [
            token
            for token, record in _confirmations.items()
            if token != exclude_token and record.get("expires_at", 0) < current
        ]
        for token in expired_tokens:
            _confirmations.pop(token, None)


def _consume_confirmation(token: str) -> tuple[dict | None, str]:
    """Atomically validate and consume a one-time confirmation token."""
    with _confirmation_lock:
        now = time.time()
        _cleanup_confirmations(now=now, exclude_token=token)
        record = _confirmations.get(token)
        if not record:
            return None, "confirmation_token_invalid"
        if record.get("used"):
            return dict(record), "confirmation_token_used"
        if record.get("expires_at", 0) < now:
            _confirmations.pop(token, None)
            return dict(record), "confirmation_token_expired"
        if (
            record.get("security_decision") != "confirm"
            or record.get("risk_level") == "forbidden"
            or record.get("risk_score", 0) >= 100
        ):
            record["used"] = True
            record["used_at"] = now
            return dict(record), "confirmation_token_not_confirmable"
        record["used"] = True
        record["used_at"] = now
        return dict(record), ""


def _create_confirmation(
    original_request_id: str,
    session_id: str,
    tool_name: str,
    arguments: dict,
    risk_score: int,
    risk_level: str,
    legacy_risk_level: int,
    security_decision: str,
    security_reason: str,
    matched_rules: list,
    risk_factors: list,
    rule_hits: dict,
) -> str:
    with _confirmation_lock:
        _cleanup_confirmations()
        token = uuid.uuid4().hex
        now = time.time()
        _confirmations[token] = {
            "original_request_id": original_request_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": dict(arguments or {}),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "legacy_risk_level": legacy_risk_level,
            "security_decision": security_decision,
            "security_reason": security_reason,
            "matched_rules": list(matched_rules or []),
            "risk_factors": list(risk_factors or []),
            "rule_hits": dict(rule_hits or {}),
            "created_at": now,
            "expires_at": now + config.CONFIRMATION_TTL_SECONDS,
            "used": False,
        }
        return token


def _build_dry_run_result(
    tool_name: str,
    arguments: dict,
    risk_score: int,
    risk_level: str,
    legacy_risk_level: int,
    security_decision: str,
    security_reason: str,
    matched_rules: list,
    risk_factors: list,
) -> dict:
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "legacy_risk_level": legacy_risk_level,
        "security_decision": security_decision,
        "security_reason": security_reason,
        "matched_rules": matched_rules,
        "risk_factors": risk_factors,
        "message": "该操作需要人工确认，尚未执行。",
    }


def _tool_result_payload(tool_result: ToolResult) -> dict:
    return {
        "tool": tool_result.tool,
        "status": tool_result.status,
        "data": tool_result.data,
        "raw_output": tool_result.raw_output,
        "error": tool_result.error,
    }


def _tool_output_text(tool_result: ToolResult, payload: dict) -> str:
    if tool_result.raw_output:
        return tool_result.raw_output
    return json.dumps(payload, ensure_ascii=False, default=str)


def _tool_audit_metadata(tool_result: ToolResult) -> dict:
    audit = dict(tool_result.audit or {})
    if "execution_success" not in audit:
        audit["execution_success"] = tool_result.status == "success"
    if not audit.get("stdout_summary") and tool_result.raw_output:
        audit["stdout_summary"] = tool_result.raw_output[:500]
    if not audit.get("stderr_summary") and tool_result.error:
        audit["stderr_summary"] = tool_result.error[:500]
    return audit


def _safe_limit(limit: int, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(maximum, value))


def _rule_labels_for(*sources: Any) -> list[str]:
    return label_rules(*sources)


def _risk_band_from_row(row: dict) -> str:
    if row.get("risk_level_text"):
        return str(row.get("risk_level_text"))
    score = row.get("risk_score")
    try:
        numeric = int(score)
    except (TypeError, ValueError):
        numeric = 0
    if numeric >= 100:
        return "forbidden"
    if numeric >= 70:
        return "high"
    if numeric >= 40:
        return "medium"
    return "low"


def _summary_from_row(row: dict) -> str:
    final_response = row.get("final_response") or ""
    if final_response:
        return str(final_response)[:500]
    result = row.get("execution_result") or {}
    if isinstance(result, dict):
        error = result.get("error")
        status = result.get("status")
        if error:
            return str(error)[:500]
        if status:
            return str(status)[:500]
    if isinstance(result, list) and result:
        return json.dumps(result[:3], ensure_ascii=False, default=str)[:500]
    return ""


def _execution_status_from_row(row: dict) -> str:
    trace = row.get("full_trace_json") or {}
    if isinstance(trace, dict):
        for event in trace.get("events", []):
            if event.get("stage") == "security_decision" and event.get("execution_status"):
                return str(event.get("execution_status"))
            if event.get("stage") == "tool_executed" and event.get("execution_status"):
                return str(event.get("execution_status"))
    if row.get("security_decision") == "reject":
        return "blocked"
    if row.get("executed"):
        return "success" if row.get("execution_success") else "failed"
    return "not_executed"


def _friendly_audit_row(row: dict) -> dict:
    friendly = dict(row)
    friendly["created_at"] = row.get("timestamp", "")
    friendly["agent_mode"] = _agent_mode_from_trace(row)
    friendly["risk_band"] = _risk_band_from_row(row)
    friendly["execution_status"] = _execution_status_from_row(row)
    friendly["summary"] = _summary_from_row(row)
    friendly["rule_labels"] = _rule_labels_for(
        row.get("matched_rules", []),
        flatten_rule_hits(row.get("rule_hits", [])),
    )
    friendly.setdefault("request_id", row.get("request_id", ""))
    friendly.setdefault("user_input", row.get("user_input", ""))
    friendly.setdefault("selected_tool", row.get("selected_tool", ""))
    friendly.setdefault("security_decision", row.get("security_decision", ""))
    return friendly


def _agent_mode_from_trace(row: dict) -> str:
    trace = row.get("full_trace_json") or {}
    if isinstance(trace, dict):
        for event in trace.get("events", []):
            if event.get("stage") == "agent_planning" and event.get("agent_mode"):
                return str(event.get("agent_mode"))
    return "offline_safe"


def _trace_timeline(payload: dict) -> list[dict]:
    trace = payload.get("trace") if isinstance(payload, dict) else {}
    audit = payload.get("audit") if isinstance(payload, dict) else {}
    events = trace.get("events", []) if isinstance(trace, dict) else []
    stages = {event.get("stage"): event for event in events if isinstance(event, dict)}
    decision = (audit or {}).get("security_decision") or stages.get("security_decision", {}).get("security_decision")
    execution_status = _execution_status_from_row(audit or {}) if audit else "not_returned"
    return [
        _timeline_item("接收请求", "completed" if "receive_input" in stages else "not_returned", "系统接收用户输入。"),
        _timeline_item("安全检查", "blocked" if decision == "reject" else _stage_status(stages, "precheck"), "安全护栏完成风险预检。"),
        _timeline_item("智能理解", _stage_status(stages, "agent_planning", skipped_if=decision == "reject"), "Agent 识别用户意图与模型规划来源。"),
        _timeline_item("工具规划", _stage_status(stages, "tool_plan_created", skipped_if=decision == "reject"), "系统生成受控工具计划。"),
        _timeline_item("执行状态", execution_status or "not_returned", "只读工具执行状态或阻断结果。"),
        _timeline_item("保存记录", "completed" if "audit_saved" in stages else "not_returned", "审计记录已保存并可追溯。"),
    ]


def _timeline_item(title: str, status: str, description: str) -> dict:
    return {"title": title, "status": status, "description": description}


def _stage_status(stages: dict, name: str, skipped_if: bool = False) -> str:
    if skipped_if:
        return "skipped"
    return "completed" if name in stages else "not_returned"


@app.get("/audit/logs")
def audit_logs(session_id: str = "", limit: int = 20):
    logger = get_logger()
    rows = logger.query(session_id=session_id, limit=_safe_limit(limit))
    return {"logs": [_friendly_audit_row(row) for row in rows]}


@app.get("/audit/trace/{request_id}")
def audit_trace(request_id: str):
    payload = get_logger().trace(request_id)
    payload["timeline"] = _trace_timeline(payload)
    return payload


@app.post("/audit/clear")
def audit_clear():
    """Clear all audit data — use before demo."""
    return get_logger().clear_all()


@app.get("/system/probe")
def system_probe():
    cap = run_probe()
    return {
        "kernel": cap.kernel,
        "os_release": cap.os_release,
        "python_version": cap.python_version,
        "available_commands": list(cap.cmd_paths.keys()),
        "missing_commands": cap.unavailable,
    }


@app.get("/monitor/overview")
def monitor_overview():
    """Host facts, health verdict and sampler state for the dashboard header."""
    return get_monitoring_service().overview()


@app.get("/monitor/metrics")
def monitor_metrics(points: int = 120):
    """Metric time series with each metric's learned baseline."""
    return get_monitoring_service().metrics_payload(points=_safe_limit(points, default=120, maximum=1000))


@app.get("/monitor/anomalies")
def monitor_anomalies():
    """Current baseline deviations — learned per host, not fixed thresholds."""
    return {"anomalies": get_monitoring_service().anomalies()}


@app.post("/monitor/sample")
def monitor_sample():
    """Force an immediate sample. Read-only collection; no system mutation."""
    return get_monitoring_service().sample_once()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
