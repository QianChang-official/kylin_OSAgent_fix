import type {
  AgentStatus,
  AuditLog,
  ChatResponse,
  HealthResponse,
  MetricAnomaly,
  MonitorMetrics,
  MonitorOverview,
  SystemProbe,
  ToolCallResponse,
  ToolDefinition,
  TraceResponse,
} from '@/types/api'

const API_BASE = String(import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')
const DEFAULT_TIMEOUT_MS = 15_000

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
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        ...(init.headers || {}),
      },
      signal: controller.signal,
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = payload?.detail
      throw new ApiError(typeof detail === 'string' ? detail : `请求失败 (${response.status})`, response.status)
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

export const api = {
  health: () => request<HealthResponse>('/health'),
  agentStatus: () => request<AgentStatus>('/agent/status'),
  systemProbe: () => request<SystemProbe>('/system/probe'),
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
}
