import type {
  AgentStatus,
  AuthCredentials,
  AuthSession,
  AuditLog,
  ChatResponse,
  CodexScansResponse,
  DeceptionIncidents,
  HealthResponse,
  AiSecurityIntelResponse,
  MetricAnomaly,
  MonitorMetrics,
  MonitorOverview,
  SecurityResources,
  SystemProbe,
  ToolCallResponse,
  ToolDefinition,
  TraceResponse,
} from '@/types/api'

const API_BASE = String(import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')
const DEFAULT_TIMEOUT_MS = 15_000
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
let csrfToken = ''
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  unauthorizedHandler = handler
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
  const method = String(init.method || 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json; charset=utf-8')
  }
  if (!SAFE_METHODS.has(method) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: 'include',
      headers,
      signal: controller.signal,
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      if (response.status === 401) {
        csrfToken = ''
        unauthorizedHandler?.()
      }
      const detail = payload?.detail
      throw new ApiError(typeof detail === 'string' ? detail : `请求失败 (${response.status})`, response.status)
    }
    if (payload && typeof payload === 'object' && 'csrf_token' in payload) {
      const nextToken = (payload as { csrf_token?: unknown }).csrf_token
      csrfToken = typeof nextToken === 'string' ? nextToken : ''
    }
    return payload as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('请求超时，请检查后端服务状态。')
    }
    throw new ApiError('无法连接 SafeOpsAgent 后端。')
  } finally {
    window.clearTimeout(timeout)
  }
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

function parseAuthSession(payload: unknown): AuthSession {
  if (
    !payload
    || typeof payload !== 'object'
    || typeof (payload as { enabled?: unknown }).enabled !== 'boolean'
    || typeof (payload as { authenticated?: unknown }).authenticated !== 'boolean'
  ) {
    throw new ApiError('后端返回了无效的认证状态。')
  }

  const session = payload as Partial<AuthSession>
  return {
    enabled: session.enabled as boolean,
    authenticated: session.authenticated as boolean,
    username: typeof session.username === 'string' ? session.username : null,
    expires_at: typeof session.expires_at === 'number' ? session.expires_at : null,
    csrf_token: typeof session.csrf_token === 'string' ? session.csrf_token : null,
  }
}

export const api = {
  authSession: async () => parseAuthSession(await request<unknown>('/auth/session')),
  authLogin: async (credentials: AuthCredentials) => (
    parseAuthSession(await post<unknown>('/auth/login', credentials))
  ),
  // Resolved entirely by the backend: the passphrase is verified against a
  // PBKDF2 record server-side and never exists in this bundle in any form.
  // A wrong passphrase is answered as a plain 404, so failure reveals nothing.
  authGate: async (passphrase: string) => {
    try {
      await post<unknown>('/auth/gate', { passphrase })
      return true
    } catch {
      return false
    }
  },
  authLogout: async () => {
    await post<unknown>('/auth/logout', {})
    csrfToken = ''
  },
  health: () => request<HealthResponse>('/health'),
  agentStatus: () => request<AgentStatus>('/agent/status'),
  systemProbe: () => request<SystemProbe>('/system/probe'),
  securityResources: () => request<SecurityResources>('/security/resources'),
  aiSecurityIntel: (limit = 8) =>
    request<AiSecurityIntelResponse>(`/security/intel/aisecurity?limit=${Math.max(1, Math.min(limit, 50))}`),
  codexScans: (limit = 20) =>
    request<CodexScansResponse>(`/security/codex/scans?limit=${Math.max(1, Math.min(limit, 100))}`),
  chat: (message: string, sessionId: string) =>
    post<ChatResponse>('/chat', { message, session_id: sessionId }),
  tools: async () => (await request<{ tools: ToolDefinition[] }>('/tools/list')).tools,
  callTool: (toolName: string, argumentsValue: Record<string, unknown>, sessionId = '') =>
    post<ToolCallResponse>('/tools/call', {
      tool_name: toolName,
      arguments: argumentsValue,
      session_id: sessionId,
    }),
  confirmTool: (confirmationToken: string, sessionId = '') =>
    post<ToolCallResponse>('/tools/confirm', {
      confirmation_token: confirmationToken,
      session_id: sessionId,
    }),
  auditLogs: async (limit = 20) =>
    (await request<{ logs: AuditLog[] }>(`/audit/logs?limit=${Math.max(1, Math.min(limit, 100))}`)).logs,
  auditTrace: (requestId: string) => request<TraceResponse>(`/audit/trace/${encodeURIComponent(requestId)}`),
  monitorOverview: () => request<MonitorOverview>('/monitor/overview'),
  monitorMetrics: (points = 120) => request<MonitorMetrics>(`/monitor/metrics?points=${Math.max(1, Math.min(points, 1000))}`),
  monitorAnomalies: async () =>
    (await request<{ anomalies: MetricAnomaly[] }>('/monitor/anomalies')).anomalies,
  monitorSample: () => post<{ sample: Record<string, unknown>; stored_metrics: number }>('/monitor/sample', {}),
  deceptionIncidents: (limit = 50) =>
    request<DeceptionIncidents>(`/security/deception/incidents?limit=${Math.max(1, Math.min(limit, 500))}`),
}
