<script setup lang="ts">
import { computed } from 'vue'
import { NEmpty, NProgress, NTag } from 'naive-ui'

const props = defineProps<{
  toolName?: string
  data?: unknown
  status?: string
}>()

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function records(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isRecord) : []
}

function numberValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.replace('%', ''))
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function ratio(used: number | null, total: number | null): number | null {
  if (used === null || total === null || total <= 0) return null
  return Math.round((used / total) * 1000) / 10
}

function display(value: unknown, fallback = '未返回'): string {
  if (value === undefined || value === null || value === '') return fallback
  return String(value)
}

function formatMb(value: number | null): string {
  return value === null ? '未返回' : `${value.toLocaleString()} MB`
}

function formatPercent(value: number | null): string {
  return value === null ? '未返回' : `${value.toFixed(1)}%`
}

function formatBytes(value: unknown): string {
  const numeric = numberValue(value)
  if (numeric === null) return display(value)
  let current = numeric
  for (const unit of ['B', 'KB', 'MB', 'GB', 'TB']) {
    if (current < 1024 || unit === 'TB') return `${current.toFixed(1)} ${unit}`
    current /= 1024
  }
  return `${numeric} B`
}

const record = computed(() => isRecord(props.data) ? props.data : null)
const list = computed(() => records(props.data))

const memory = computed(() => {
  if (props.toolName !== 'get_memory_status' || !record.value) return null
  const total = numberValue(record.value.total_mb)
  const used = numberValue(record.value.used_mb)
  const swapTotal = numberValue(record.value.swap_total_mb)
  const swapUsed = numberValue(record.value.swap_used_mb)
  return {
    total,
    used,
    free: numberValue(record.value.free_mb),
    available: numberValue(record.value.available_mb),
    swapTotal,
    swapUsed,
    memoryPercent: ratio(used, total),
    swapPercent: ratio(swapUsed, swapTotal),
  }
})

const cpu = computed(() => props.toolName === 'get_cpu_status' ? record.value : null)
const diskRows = computed(() => props.toolName === 'disk_usage' ? list.value : [])
const keyMounts = new Set(['/', '/boot', '/boot/efi', '/tmp', '/home', '/var', '/var/log'])
const virtualFileSystems = new Set([
  'tmpfs', 'devtmpfs', 'proc', 'sysfs', 'cgroup', 'cgroup2', 'efivarfs',
  'securityfs', 'debugfs', 'tracefs', 'pstore', 'configfs', 'fusectl', 'mqueue',
])
function diskMount(item: Record<string, unknown>): string {
  return String(item.mounted_on || item.mount || '')
}
function isVirtualDisk(item: Record<string, unknown>): boolean {
  const filesystem = String(item.filesystem || '').toLowerCase()
  const mount = diskMount(item)
  if (keyMounts.has(mount)) return false
  return virtualFileSystems.has(filesystem)
    || mount === '/dev'
    || mount.startsWith('/dev/')
    || mount === '/proc'
    || mount.startsWith('/proc/')
    || mount === '/sys'
    || mount.startsWith('/sys/')
    || mount === '/run'
    || mount.startsWith('/run/')
}
const primaryDiskRows = computed(() => {
  const keyRows = diskRows.value.filter((item) => keyMounts.has(diskMount(item)))
  if (keyRows.length) return keyRows
  return diskRows.value.filter((item) => !isVirtualDisk(item)).slice(0, 5)
})
const advancedDiskRows = computed(() => (
  diskRows.value.filter((item) => !primaryDiskRows.value.includes(item))
))
const processRows = computed(() => {
  if (props.toolName === 'process_list') return list.value
  if (props.toolName === 'get_cpu_status') return records(record.value?.top_processes)
  return []
})
const cpuProgressStatus = computed<'success' | 'warning' | 'error'>(() => {
  if (!cpu.value) return 'success'
  const usage = numberValue(cpu.value.usage_percent) ?? 0
  const loadPerCore = numberValue(cpu.value.load_per_core) ?? 0
  const topProcessCpu = processRows.value.reduce(
    (highest, item) => Math.max(highest, numberValue(item.cpu) ?? 0),
    0,
  )
  const sustainedSignal = loadPerCore >= 1 || topProcessCpu >= 75
  if (usage >= 95 && sustainedSignal) return 'error'
  if ((usage >= 85 && sustainedSignal) || loadPerCore >= 1) return 'warning'
  return 'success'
})
const networkRows = computed(() => props.toolName === 'network_status' ? list.value : [])
const listeners = computed(() => props.toolName === 'get_port_usage' ? records(record.value?.listeners) : [])
const service = computed(() => props.toolName === 'get_service_status' ? record.value : null)
const logRows = computed(() => props.toolName === 'journal_query' ? list.value : [])
const largeFiles = computed(() => props.toolName === 'large_file_scan' ? records(record.value?.files) : [])
const cleanupRows = computed(() => {
  if (!String(props.toolName || '').startsWith('safe_cleanup_')) return []
  return records(record.value?.candidates || record.value?.items)
})
const cleanup = computed(() => String(props.toolName || '').startsWith('safe_cleanup_') ? record.value : null)
</script>

<template>
  <section class="tool-metrics">
    <template v-if="memory">
      <div class="metric-heading">
        <div><h3>内存占用</h3><p>来自当前设备的内存与 Swap 数据。</p></div>
        <n-tag type="success" :bordered="false">只读检查</n-tag>
      </div>
      <div class="metric-grid">
        <article class="metric-tile metric-primary">
          <span>内存使用率</span><strong>{{ formatPercent(memory.memoryPercent) }}</strong>
          <n-progress
            type="line"
            :percentage="memory.memoryPercent ?? 0"
            :show-indicator="false"
            :status="(memory.memoryPercent ?? 0) >= 90 ? 'error' : (memory.memoryPercent ?? 0) >= 80 ? 'warning' : 'success'"
          />
        </article>
        <article class="metric-tile"><span>总内存</span><strong>{{ formatMb(memory.total) }}</strong></article>
        <article class="metric-tile"><span>已用内存</span><strong>{{ formatMb(memory.used) }}</strong></article>
        <article class="metric-tile"><span>可用内存</span><strong>{{ formatMb(memory.available) }}</strong></article>
        <article class="metric-tile"><span>空闲内存</span><strong>{{ formatMb(memory.free) }}</strong></article>
        <article class="metric-tile"><span>Swap 总量</span><strong>{{ formatMb(memory.swapTotal) }}</strong></article>
        <article class="metric-tile"><span>Swap 已用</span><strong>{{ formatMb(memory.swapUsed) }}</strong></article>
        <article class="metric-tile"><span>Swap 使用率</span><strong>{{ formatPercent(memory.swapPercent) }}</strong></article>
      </div>
    </template>

    <template v-else-if="cpu">
      <div class="metric-heading">
        <div>
          <h3>CPU 与系统负载</h3>
          <p>
            CPU 为 {{ display(cpu.sample_interval_seconds, '1') }} 秒瞬时采样，
            需结合每核负载与高占用进程判断持续压力。
          </p>
        </div>
        <n-tag :type="cpu.status === 'environment_limited' ? 'warning' : 'success'" :bordered="false">
          {{ cpu.status === 'environment_limited' ? '环境受限' : '只读检查' }}
        </n-tag>
      </div>
      <div class="metric-grid">
        <article class="metric-tile metric-primary">
          <span>CPU 使用率（瞬时采样）</span><strong>{{ formatPercent(numberValue(cpu.usage_percent)) }}</strong>
          <n-progress
            type="line"
            :percentage="numberValue(cpu.usage_percent) ?? 0"
            :show-indicator="false"
            :status="cpuProgressStatus"
          />
        </article>
        <article class="metric-tile"><span>逻辑核心</span><strong>{{ display(cpu.logical_cores) }}</strong></article>
        <article class="metric-tile"><span>物理核心</span><strong>{{ display(cpu.physical_cores, '无法可靠获取') }}</strong></article>
        <article class="metric-tile"><span>1 分钟负载</span><strong>{{ display(cpu.load_1m) }}</strong></article>
        <article class="metric-tile"><span>5 分钟负载</span><strong>{{ display(cpu.load_5m) }}</strong></article>
        <article class="metric-tile"><span>15 分钟负载</span><strong>{{ display(cpu.load_15m) }}</strong></article>
        <article class="metric-tile"><span>每核负载</span><strong>{{ display(cpu.load_per_core) }}</strong></article>
      </div>
    </template>

    <template v-if="diskRows.length">
      <div class="metric-heading"><div><h3>磁盘空间</h3><p>默认展示关键真实挂载点，虚拟与临时文件系统收纳在高级详情中。</p></div></div>
      <n-empty v-if="!primaryDiskRows.length" description="未返回可展示的真实挂载点" />
      <div v-if="primaryDiskRows.length" class="table-scroll">
        <table><thead><tr><th>文件系统</th><th>挂载点</th><th>总量</th><th>已用</th><th>可用</th><th>使用率</th></tr></thead>
          <tbody><tr v-for="(item, index) in primaryDiskRows" :key="index">
            <td>{{ display(item.filesystem) }}</td><td>{{ display(item.mounted_on || item.mount) }}</td>
            <td>{{ display(item.size) }}</td><td>{{ display(item.used) }}</td>
            <td>{{ display(item.available || item.avail) }}</td><td>{{ display(item.use_percent || item.use) }}</td>
          </tr></tbody>
        </table>
      </div>
      <details v-if="advancedDiskRows.length" class="advanced-filesystems">
        <summary>高级详情：其他文件系统（{{ advancedDiskRows.length }}）</summary>
        <div class="table-scroll">
          <table><thead><tr><th>文件系统</th><th>挂载点</th><th>总量</th><th>已用</th><th>可用</th><th>使用率</th></tr></thead>
            <tbody><tr v-for="(item, index) in advancedDiskRows" :key="index">
              <td>{{ display(item.filesystem) }}</td><td>{{ display(item.mounted_on || item.mount) }}</td>
              <td>{{ display(item.size) }}</td><td>{{ display(item.used) }}</td>
              <td>{{ display(item.available || item.avail) }}</td><td>{{ display(item.use_percent || item.use) }}</td>
            </tr></tbody>
          </table>
        </div>
      </details>
    </template>

    <template v-if="processRows.length">
      <div class="metric-heading"><div><h3>{{ toolName === 'get_cpu_status' ? '高 CPU 进程' : '运行进程' }}</h3><p>仅展示后端返回的前十项。</p></div></div>
      <div class="table-scroll">
        <table><thead><tr><th>PID</th><th>用户</th><th>名称</th><th>CPU</th><th>内存</th><th>命令</th></tr></thead>
          <tbody><tr v-for="(item, index) in processRows.slice(0, 10)" :key="index">
            <td>{{ display(item.pid) }}</td><td>{{ display(item.user) }}</td>
            <td>{{ display(item.name || item.command) }}</td><td>{{ display(item.cpu) }}%</td>
            <td>{{ display(item.mem) }}%</td>
            <td><span class="truncate" :title="display(item.command)">{{ display(item.command) }}</span></td>
          </tr></tbody>
        </table>
      </div>
    </template>

    <template v-if="networkRows.length">
      <div class="metric-heading"><div><h3>网络监听</h3><p>协议、本地地址、状态与关联信息。</p></div></div>
      <div class="table-scroll">
        <table><thead><tr><th>协议</th><th>本地地址</th><th>状态</th><th>PID / 进程</th></tr></thead>
          <tbody><tr v-for="(item, index) in networkRows.slice(0, 30)" :key="index">
            <td>{{ display(item.protocol) }}</td><td>{{ display(item.local_address || item.local) }}</td>
            <td>{{ display(item.state) }}</td><td>{{ display(item.process || item.pid) }}</td>
          </tr></tbody>
        </table>
      </div>
    </template>

    <template v-else-if="toolName === 'get_port_usage' && record">
      <div class="metric-heading"><div><h3>端口占用</h3><p>查询端口 {{ display(record.port) }} 的监听进程。</p></div></div>
      <n-empty v-if="!listeners.length" description="未发现监听进程" />
      <div v-else class="table-scroll">
        <table><thead><tr><th>协议</th><th>监听地址</th><th>PID</th><th>进程</th></tr></thead>
          <tbody><tr v-for="(item, index) in listeners" :key="index">
            <td>{{ display(item.protocol) }}</td><td>{{ display(item.local_address) }}</td>
            <td>{{ display(item.pid) }}</td><td>{{ display(item.process) }}</td>
          </tr></tbody>
        </table>
      </div>
    </template>

    <template v-else-if="service">
      <div class="metric-heading"><div><h3>服务状态</h3><p>systemd 活动状态与只读摘要。</p></div></div>
      <div class="fact-list">
        <div><span>服务名称</span><strong>{{ display(service.service_name) }}</strong></div>
        <div><span>活动状态</span><strong>{{ display(service.active_state) }}</strong></div>
        <div><span>启用状态</span><strong>{{ display(service.enabled_state) }}</strong></div>
        <div class="fact-wide"><span>状态摘要</span><details><summary>查看摘要</summary><pre>{{ display(service.status_summary || service.error) }}</pre></details></div>
      </div>
    </template>

    <template v-if="logRows.length">
      <div class="metric-heading"><div><h3>近期系统日志</h3><p>日志内容按安全文本渲染。</p></div></div>
      <div class="log-list">
        <article v-for="(item, index) in logRows.slice(0, 50)" :key="index">
          <span>{{ display(item.timestamp || item.time || item.line, String(index + 1)) }}</span>
          <strong>{{ display(item.level || item.source, '日志') }}</strong>
          <p>{{ display(item.content) }}</p>
        </article>
      </div>
    </template>

    <template v-if="toolName === 'large_file_scan' && record">
      <div class="metric-heading"><div><h3>大文件候选</h3><p>只读扫描结果，不代表可以直接删除。</p></div></div>
      <div class="fact-list compact-facts">
        <div><span>扫描文件</span><strong>{{ display(record.scanned_files) }}</strong></div>
        <div><span>候选数量</span><strong>{{ largeFiles.length }}</strong></div>
      </div>
      <n-empty v-if="!largeFiles.length" description="未发现达到阈值的大文件" />
      <div v-else class="table-scroll">
        <table><thead><tr><th>路径</th><th>大小</th><th>字节数</th><th>安全提示</th></tr></thead>
          <tbody><tr v-for="(item, index) in largeFiles" :key="index">
            <td><span class="truncate" :title="display(item.path)">{{ display(item.path) }}</span></td>
            <td>{{ display(item.size) }}</td><td>{{ display(item.bytes) }}</td><td>先确认归属与备份，不直接删除</td>
          </tr></tbody>
        </table>
      </div>
    </template>

    <template v-if="cleanup">
      <div class="metric-heading">
        <div><h3>可恢复安全清理</h3><p>扫描和计划不会修改文件；隔离与恢复必须人工确认。</p></div>
        <n-tag type="warning" :bordered="false">永久删除：否</n-tag>
      </div>
      <div class="fact-list compact-facts">
        <div><span>候选文件</span><strong>{{ display(cleanup.candidate_count ?? cleanup.moved_count ?? cleanup.restored_count, '0') }}</strong></div>
        <div><span>总大小</span><strong>{{ formatBytes(cleanup.total_bytes) }}</strong></div>
        <div v-if="cleanup.plan_id"><span>计划编号</span><strong class="mono">{{ cleanup.plan_id }}</strong></div>
        <div v-if="cleanup.quarantine_id"><span>隔离编号</span><strong class="mono">{{ cleanup.quarantine_id }}</strong></div>
      </div>
      <n-empty v-if="!cleanupRows.length" description="当前没有可展示的文件项" />
      <div v-else class="table-scroll">
        <table><thead><tr><th>文件路径</th><th>大小</th><th>修改时间</th><th>状态</th></tr></thead>
          <tbody><tr v-for="(item, index) in cleanupRows" :key="index">
            <td><span class="truncate" :title="display(item.path || item.original_path)">{{ display(item.path || item.original_path) }}</span></td>
            <td>{{ formatBytes(item.bytes) }}</td><td>{{ display(item.modified_at || item.modified_at_epoch) }}</td>
            <td>{{ toolName === 'safe_cleanup_restore' ? '已恢复' : toolName === 'safe_cleanup_quarantine' ? '已隔离' : '待确认' }}</td>
          </tr></tbody>
        </table>
      </div>
    </template>

    <n-empty
      v-if="status === 'success' && !memory && !cpu && !diskRows.length && !processRows.length && !networkRows.length && toolName !== 'get_port_usage' && !service && !logRows.length && toolName !== 'large_file_scan' && !cleanup"
      description="工具已执行，但没有可结构化展示的结果"
    />
  </section>
</template>

<style scoped>
.tool-metrics { min-width: 0; }
.metric-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.metric-heading h3 { margin: 0 0 5px; color: #f4ede0; font-size: 17px; }
.metric-heading p { margin: 0; color: #a89a86; font-size: 12px; line-height: 1.6; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.metric-tile { min-height: 88px; padding: 15px; border: 1px solid rgba(84, 209, 223, .14); border-radius: 10px; background: rgba(9, 18, 28, .72); }
.metric-primary { grid-column: span 2; }
.metric-tile span { display: block; margin-bottom: 8px; color: #a89a86; font-size: 12px; }
.metric-tile strong { display: block; color: #f4ede0; font-size: 21px; line-height: 1.3; }
.metric-tile .n-progress { margin-top: 12px; }
.table-scroll { max-width: 100%; overflow-x: auto; border: 1px solid rgba(255,255,255,.06); border-radius: 9px; }
.advanced-filesystems { margin-top: 12px; color: #97887a; font-size: 11px; }
.advanced-filesystems summary { margin-bottom: 9px; color: #97887a; cursor: pointer; }
table { width: 100%; min-width: 680px; border-collapse: collapse; font-size: 12px; }
th, td { padding: 11px 12px; border-bottom: 1px solid rgba(255,255,255,.06); text-align: left; vertical-align: top; }
th { color: #a89a86; font-weight: 600; background: rgba(255,255,255,.025); }
td { color: #d8c9b2; }
tbody tr:last-child td { border-bottom: 0; }
.truncate { display: block; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fact-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.fact-list > div { padding: 13px; border: 1px solid rgba(255,255,255,.06); border-radius: 9px; background: rgba(255,255,255,.02); min-width: 0; }
.fact-list span { display: block; margin-bottom: 6px; color: #a89a86; font-size: 11px; }
.fact-list strong { color: #f4ede0; overflow-wrap: anywhere; }
.fact-wide { grid-column: 1 / -1; }
.compact-facts { margin-bottom: 14px; }
details summary { color: #eacd76; cursor: pointer; }
pre { max-height: 240px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; color: #c9bca8; }
.log-list { display: grid; gap: 8px; }
.log-list article { display: grid; grid-template-columns: 72px 90px minmax(0, 1fr); gap: 10px; padding: 10px 12px; border: 1px solid rgba(255,255,255,.06); border-radius: 8px; }
.log-list span, .log-list strong { color: #a89a86; font-size: 11px; }
.log-list p { margin: 0; color: #c9bca8; overflow-wrap: anywhere; }
.mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; }
@media (max-width: 640px) {
  .metric-primary { grid-column: span 1; }
  .metric-heading { display: block; }
  .metric-heading .n-tag { margin-top: 10px; }
  .fact-list { grid-template-columns: 1fr; }
  .fact-wide { grid-column: auto; }
  .log-list article { grid-template-columns: 1fr; }
}
</style>
