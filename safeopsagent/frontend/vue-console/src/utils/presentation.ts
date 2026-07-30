export function decisionLabel(value: unknown): string {
  const key = String(value || '').toLowerCase()
  const labels: Record<string, string> = {
    allow: '允许执行',
    confirm: '需要确认',
    reject: '已阻断',
    forbidden: '禁止执行',
    failed: '执行失败',
    no_action: '无需执行',
  }
  return labels[key] || '待判断'
}

export function decisionType(value: unknown): 'success' | 'warning' | 'error' | 'info' | 'default' {
  const key = String(value || '').toLowerCase()
  if (key === 'allow') return 'success'
  if (key === 'confirm') return 'warning'
  if (key === 'reject' || key === 'forbidden' || key === 'failed') return 'error'
  return 'info'
}

export function riskLabel(value: unknown, score?: unknown): string {
  const key = String(value || '').toLowerCase()
  const labels: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    forbidden: '禁止级',
  }
  if (labels[key]) return labels[key]
  const numeric = Number(score || 0)
  if (numeric >= 100) return '禁止级'
  if (numeric >= 70) return '高风险'
  if (numeric >= 40) return '中风险'
  return '低风险'
}

export function riskType(score: unknown): 'success' | 'warning' | 'error' | 'info' {
  const numeric = Number(score || 0)
  if (numeric >= 70) return 'error'
  if (numeric >= 40) return 'warning'
  return 'success'
}

export function executionLabel(result: Record<string, unknown>): string {
  const status = String(result.execution_status || '').toLowerCase()
  const nestedStatus = typeof result.result === 'object' && result.result
    ? String((result.result as Record<string, unknown>).status || '').toLowerCase()
    : ''
  const errorText = String(result.error || '').toLowerCase()
  if (status === 'environment_limited') return '环境能力受限'
  if (nestedStatus === 'capability_missing' || errorText.includes('command not found')) return '环境能力受限'
  if (status === 'blocked') return '未执行（已阻断）'
  if (status === 'success') return '已安全执行'
  if (status === 'failed') return '执行失败'
  if (result.executed === true) return '已执行'
  if (result.executed === false) return '未执行'
  return '未返回执行状态'
}

export function isEnvironmentLimited(result: Record<string, unknown>): boolean {
  const nestedStatus = typeof result.result === 'object' && result.result
    ? String((result.result as Record<string, unknown>).status || '').toLowerCase()
    : ''
  const errorText = String(result.error || '').toLowerCase()
  return result.execution_status === 'environment_limited'
    || result.environment_limited === true
    || nestedStatus === 'capability_missing'
    || errorText.includes('command not found')
}

export function modeLabel(mode: unknown): string {
  return String(mode) === 'model_api' ? '国产模型服务模式' : '离线安全模式'
}

export function plannerLabel(source: unknown): string {
  return String(source) === 'domestic_model' ? '国产模型规划' : '内置安全规划'
}

const TOOL_LABELS: Record<string, string> = {
  get_memory_status: '内存状态检查',
  get_cpu_status: 'CPU 与负载检查',
  disk_usage: '磁盘空间检查',
  process_list: '运行进程检查',
  network_status: '网络监听检查',
  get_port_usage: '端口占用检查',
  get_service_status: '服务状态检查',
  journal_query: '系统日志查询',
  large_file_scan: '大文件扫描',
  safe_cleanup_scan: '安全清理扫描',
  safe_cleanup_plan: '安全清理计划',
  safe_cleanup_quarantine: '文件隔离',
  safe_cleanup_restore: '文件恢复',
}

const TOOL_PURPOSES: Record<string, string> = {
  get_memory_status: '读取当前内存与 Swap 使用情况。',
  get_cpu_status: '采集 CPU 瞬时使用率、系统负载和高占用进程。',
  disk_usage: '检查关键挂载点的容量与使用率。',
  process_list: '列出当前高资源占用进程。',
  network_status: '查看网络监听和连接状态。',
  get_port_usage: '确认指定端口的监听进程。',
  get_service_status: '读取 systemd 服务活动状态。',
  journal_query: '查询近期系统日志。',
  large_file_scan: '只读扫描达到阈值的大文件。',
  safe_cleanup_scan: '扫描符合安全边界的可清理候选文件。',
  safe_cleanup_plan: '生成不修改文件的可恢复清理计划。',
  safe_cleanup_quarantine: '经人工确认后将文件移入可恢复隔离区。',
  safe_cleanup_restore: '经人工确认后恢复隔离文件。',
}

const METRIC_LABELS: Record<string, string> = {
  memory_total: '总内存',
  memory_used: '已用内存',
  memory_available: '可用内存',
  memory_free: '空闲内存',
  memory_usage_percent: '内存使用率',
  swap_total: 'Swap 总量',
  swap_used: 'Swap 已用',
  swap_usage_percent: 'Swap 使用率',
  cpu_usage_percent: 'CPU 使用率（瞬时采样）',
  cpu_logical_cores: '逻辑核心数',
  cpu_physical_cores: '物理核心数',
  load_1m: '1 分钟负载',
  load_5m: '5 分钟负载',
  load_15m: '15 分钟负载',
  load_per_core: '每核负载',
  top_cpu_process_percent: '最高进程 CPU 占用',
  disk_usage_percent: '磁盘使用率',
  disk_available: '磁盘可用空间',
  process_cpu_percent: '进程 CPU 占用',
  process_memory_percent: '进程内存占用',
  network_listener_count: '网络监听数量',
  port_listener_count: '端口监听数量',
  service_active_state: '服务活动状态',
  journal_entry_count: '日志条目数',
  journal_error_count: '错误日志数',
  journal_critical_count: '严重日志数',
  large_file_count: '大文件数量',
  large_file_scanned_count: '已扫描文件数',
  cleanup_candidate_count: '清理候选数量',
  cleanup_candidate_bytes: '候选文件总大小',
  cleanup_plan_file_count: '计划文件数量',
  cleanup_plan_bytes: '计划文件总大小',
  cleanup_quarantined_count: '已隔离文件数',
  cleanup_restored_count: '已恢复文件数',
}

export function toolLabel(value: unknown): string {
  const key = String(value || '')
  return TOOL_LABELS[key] || '受控系统检查'
}

export function toolPurpose(value: unknown): string {
  const key = String(value || '')
  return TOOL_PURPOSES[key] || '通过白名单工具执行只读系统检查。'
}

export function metricLabel(value: unknown): string {
  const key = String(value || '')
  return METRIC_LABELS[key] || '系统指标'
}

export function formatTime(value: unknown): string {
  if (!value) return '时间未返回'
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}

export function compactJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}

export function getRuleLabels(result: Record<string, unknown>): string[] {
  if (Array.isArray(result.rule_labels)) return result.rule_labels.map(String)
  if (Array.isArray(result.matched_rules)) return result.matched_rules.map(String)
  return []
}
