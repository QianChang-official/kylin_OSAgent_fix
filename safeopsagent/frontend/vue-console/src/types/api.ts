export type AgentMode = 'model_api' | 'offline_safe'
export type ModelProvider = 'deepseek' | 'qwen' | 'kimi' | 'custom' | 'offline_safe'
export type PlannerSource = 'domestic_model' | 'offline_safe'

export interface AgentStatus {
  status: string
  agent_mode: AgentMode
  model_provider: ModelProvider
  model_vendor: string
  model_name: string
  planner_source: PlannerSource
  configured_provider?: string
  guardrail_enabled: boolean
  risk_scoring_enabled: boolean
  audit_enabled: boolean
  tools_count: number
  readonly_tools_count: number
  security_summary?: string
  deployment_hint?: string
}

export interface HealthResponse {
  status: string
  agent: string
  version: string
}

export interface AuthSession {
  enabled: boolean
  authenticated: boolean
  username: string | null
  expires_at: number | null
  csrf_token: string | null
}

export interface AuthCredentials {
  username: string
  password: string
}

export interface SystemProbe {
  kernel: string
  os_release: string
  python_version: string
  available_commands: string[]
  missing_commands: string[]
}

export interface SecuritySource {
  name: string
  url: string
  usage: string
}

export interface CodexSecurityResource {
  id: string
  source: string
  title: string
  url: string
  package: string
  pinned_version: string
  summary: string
  commands: string[]
  safeops_usage: string[]
}

export interface AiToolCategory {
  slug: string
  name: string
  url: string
  safeops_usage: string
  restricted?: boolean
}

export interface AiSecurityArticle {
  id: number
  title: string
  url: string
  topics: string[]
  safeops_usage: string
}

export interface ProjectApplication {
  area: string
  controls: string[]
  mapped_sources: string[]
}

export interface SecurityResources {
  last_checked_at: string
  sources: SecuritySource[]
  codex_security: CodexSecurityResource
  tool_categories: AiToolCategory[]
  articles: AiSecurityArticle[]
  project_applications: ProjectApplication[]
  policy: {
    restricted_category_count: number
    summary: string
  }
}

export interface AiSecurityIntelSource {
  name: string
  feed_url: string
}

export interface AiSecurityIntelItem {
  title: string
  description: string
  published_at: string
  article_url: string
  mapping_rules: string[]
  project_controls: string[]
}

export interface AiSecurityIntelResponse {
  source: AiSecurityIntelSource
  untrusted: boolean
  automatic_model_ingestion: boolean
  mapping_mode: string
  item_count: number
  items: AiSecurityIntelItem[]
  delivery: 'network' | 'local_snapshot'
  snapshot_used: boolean
}

export interface CodexScanTarget {
  kind: string
  display_name: string
  revision: string
}

export interface CodexScanSummary {
  directory_id: string
  scan_id: string
  completed_at: string
  target: CodexScanTarget
  coverage: string
  finding_count: number
  severity_counts: Record<string, number>
  integrity_verified: boolean
  authenticity_verified: boolean
  trust_basis: string
}

export interface CodexScansResponse {
  configured: boolean
  scans: CodexScanSummary[]
  discovery_limited?: boolean
  discovery_limit_reasons?: string[]
  entries_examined?: number
}

export interface ToolPlanItem {
  tool_name: string
  arguments?: Record<string, unknown>
  reason?: string
  status?: string
  risk_score?: number
  result?: unknown
  error?: string
}

export interface ToolResultItem {
  tool?: string
  status?: string
  data?: unknown
  raw_output?: string
  error?: string
  arguments?: Record<string, unknown>
}

export interface DiagnosisEvidence {
  metric: string
  value: unknown
  unit: string
  source_tool: string
  context?: string
}

export interface DiagnosisResult {
  summary: string
  severity: 'normal' | 'notice' | 'warning' | 'critical' | 'unknown'
  findings: string[]
  recommendations: string[]
  next_actions: string[]
  evidence: DiagnosisEvidence[]
}

export interface ChatResponse {
  response?: string
  summary?: string
  analysis?: string
  next_step?: string
  environment_message?: string
  environment_limited?: boolean
  intent?: string
  request_id: string
  session_id?: string
  risk_score?: number
  risk_level?: string | number
  risk_band?: string
  security_decision?: string
  security_reason?: string
  execution_status?: string
  executed?: boolean
  selected_tool?: string
  matched_rules?: string[]
  rule_hits?: Record<string, unknown> | string[]
  rule_labels?: string[]
  tool_plan?: ToolPlanItem[]
  tool_result?: ToolResultItem | Record<string, unknown> | null
  tool_results?: ToolResultItem[]
  agent_mode?: AgentMode
  model_provider?: ModelProvider
  model_vendor?: string
  model_name?: string
  planner_source?: PlannerSource
  planner_explanation?: string
  planner_confidence?: number
  confirmation_required?: boolean
  confirmation_token?: string | null
  dry_run_result?: Record<string, unknown> | null
  diagnosis?: DiagnosisResult
  error?: string
  [key: string]: unknown
}

export interface JsonSchemaProperty {
  type?: 'string' | 'integer' | 'boolean'
  description?: string
  minimum?: number
  maximum?: number
  minLength?: number
  maxLength?: number
  pattern?: string
  default?: unknown
}

export interface ToolDefinition {
  name: string
  description: string
  inputSchema: {
    type: string
    properties: Record<string, JsonSchemaProperty>
    required?: string[]
  }
}

export interface ToolCallResponse {
  success: boolean
  request_id: string
  original_request_id?: string
  tool_name: string
  arguments?: Record<string, unknown>
  risk_score?: number
  risk_level?: string | number
  risk_band?: string
  security_decision?: string
  security_reason?: string
  confirmation_required?: boolean
  confirmation_token?: string | null
  dry_run_result?: Record<string, unknown> | null
  executed?: boolean
  result?: Record<string, unknown> | null
  error?: string
  matched_rules?: string[]
  rule_labels?: string[]
  [key: string]: unknown
}

export interface AuditLog {
  id?: number
  created_at?: string
  timestamp?: string
  request_id: string
  session_id?: string
  user_input?: string
  intent?: string
  agent_mode?: AgentMode
  selected_tool?: string
  risk_score?: number
  risk_band?: string
  risk_level_text?: string
  security_decision?: string
  security_reason?: string
  execution_status?: string
  executed?: boolean
  summary?: string
  rule_labels?: string[]
  [key: string]: unknown
}

export interface TimelineItem {
  title: string
  status: string
  description: string
}

export interface TraceResponse {
  found: boolean
  request_id?: string
  audit?: AuditLog
  trace?: {
    events?: Array<Record<string, unknown>>
    [key: string]: unknown
  }
  timeline?: TimelineItem[]
  [key: string]: unknown
}

export interface MetricBaseline {
  metric: string
  median: number
  mad: number
  sample_count: number
  normal_lower: number
  normal_upper: number
  learned: boolean
}

export interface MetricPoint {
  ts: number
  value: number
}

export interface MetricSeries {
  label: string
  unit: string
  points: MetricPoint[]
  latest: number | null
  baseline: MetricBaseline
  available: boolean
  sample_count: number
}

export interface MonitorMetrics {
  metrics: Record<string, MetricSeries>
  tracked: string[]
  sample_count: number
  sampler_running: boolean
  sample_interval_seconds: number
  collector_source: string
}

export interface MetricAnomaly {
  metric: string
  label: string
  value: number
  baseline_median: number
  normal_lower: number
  normal_upper: number
  deviation: number
  z_score: number | null
  severity: 'warning' | 'critical'
  triggered_by: string[]
  sample_count: number
  explanation: string
  ts: number
}

export interface MonitorHost {
  hostname: string
  system: string
  release: string
  machine: string
  python_version: string
  logical_cores: number | null
  uptime_seconds: number | null
  boot_time: number | null
  os_release?: string
}

export interface MonitorOverview {
  host: MonitorHost
  health: 'healthy' | 'warning' | 'critical'
  anomaly_count: number
  sample_count: number
  sampler_running: boolean
  sample_interval_seconds: number
  collector_source: string
}

export type DeceptionSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical'

export interface DeceptionSummary {
  enabled: boolean
  trigger_attempts: number
  tracked_sources: number
  sandbox_sessions_open: number
  total_login_failures: number
  total_gate_failures: number
  total_sandbox_requests: number
  highest_severity: DeceptionSeverity
  evidence_path: string
  evidence_error: string
  reverse_dns_enabled: boolean
}

export interface DeceptionActivity {
  at: string
  event: string
  [key: string]: unknown
}

export interface DeceptionSource {
  source: string
  network_scope: string
  first_seen: string
  last_seen: string
  observed_seconds: number
  login_failures: number
  gate_failures: number
  login_successes: number
  sandbox_sessions: number
  sandbox_requests: number
  total_attempts: number
  usernames_tried: string[]
  distinct_passwords: number
  credential_digests: string[]
  user_agents: string[]
  fingerprints: string[]
  median_interval_seconds: number | null
  forwarded_chain: string[]
  proxy_trusted: boolean
  automated_agent: boolean
  reverse_dns: string
  sandbox_active: boolean
  classification: string
  severity: DeceptionSeverity
  recent_activity: DeceptionActivity[]
}

export interface DeceptionEvidence {
  at: string
  event: string
  severity: DeceptionSeverity
  classification: string
  detail: Record<string, unknown>
  client: Record<string, unknown>
  dossier: Record<string, unknown>
}

export interface DeceptionIncidents {
  summary: DeceptionSummary
  gate_enabled: boolean
  sources: DeceptionSource[]
  recent_evidence: DeceptionEvidence[]
}
