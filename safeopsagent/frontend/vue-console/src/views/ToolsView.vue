<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NCollapse, NCollapseItem, NEmpty, NInput, NInputNumber, NSelect, NSpin, NTag, useMessage } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import ResultSummary from '@/components/ResultSummary.vue'
import ToolResultMetrics from '@/components/ToolResultMetrics.vue'
import { api } from '@/api/client'
import type { JsonSchemaProperty, ToolCallResponse, ToolDefinition } from '@/types/api'
import { compactJson } from '@/utils/presentation'

const router = useRouter()
const messageApi = useMessage()
const loading = ref(true)
const calling = ref(false)
const confirming = ref(false)
const error = ref('')
const tools = ref<ToolDefinition[]>([])
const selectedName = ref('')
const argumentValues = reactive<Record<string, string | number | null>>({})
const result = ref<ToolCallResponse | null>(null)
const sessionId = `tools-${crypto.randomUUID()}`

const toolMeta: Record<string, { title: string; group: string; scene: string; output: string }> = {
  get_cpu_status: { title: 'CPU 与负载', group: '系统资源', scene: '检查 CPU 使用率、核心数、负载和高占用进程', output: 'CPU、Load Average、核心数、Top 进程' },
  safe_cleanup_scan: { title: '清理候选扫描', group: '可恢复处置', scene: '在临时目录白名单中只读扫描旧文件', output: '候选路径、大小、修改时间、安全提示' },
  safe_cleanup_plan: { title: '安全清理计划', group: '可恢复处置', scene: '生成绑定文件元数据的 dry-run 计划', output: '计划编号、计划哈希、候选文件、总大小' },
  safe_cleanup_quarantine: { title: '受控文件隔离', group: '可恢复处置', scene: '人工确认后将未变化的候选文件移入同盘隔离区', output: '隔离编号、移动文件、恢复凭据' },
  safe_cleanup_restore: { title: '隔离文件恢复', group: '可恢复处置', scene: '人工确认后将隔离文件恢复到原路径', output: '恢复文件、恢复状态、审计编号' },
  get_memory_status: { title: '内存状态', group: '系统资源', scene: '排查内存压力与可用容量', output: '总内存、已用、可用、Swap' },
  disk_usage: { title: '磁盘使用', group: '系统资源', scene: '检查文件系统空间占用', output: '文件系统、挂载点、容量、使用率' },
  process_list: { title: '运行进程', group: '系统资源', scene: '查看高 CPU 进程与运行状态', output: '进程、PID、CPU、内存' },
  network_status: { title: '网络监听', group: '网络与服务', scene: '检查 TCP / UDP 监听情况', output: '协议、本地地址、状态、进程' },
  get_port_usage: { title: '端口占用', group: '网络与服务', scene: '定位指定端口的监听进程', output: '端口、监听地址、PID、进程' },
  get_service_status: { title: '服务状态', group: '网络与服务', scene: '查询 systemd 服务活动状态', output: '服务名、active 状态、状态摘要' },
  journal_query: { title: '系统日志', group: '日志与文件', scene: '读取近期 systemd 日志', output: '日志行、时间和内容摘要' },
  large_file_scan: { title: '大文件检查', group: '日志与文件', scene: '在允许目录内检查大文件', output: '文件路径、大小、扫描告警' },
}

const selectedTool = computed(() => tools.value.find((tool) => tool.name === selectedName.value) || null)
const groups = computed(() => {
  const output: Record<string, ToolDefinition[]> = {}
  for (const tool of tools.value) {
    const group = toolMeta[tool.name]?.group || '其他工具'
    output[group] ||= []
    output[group].push(tool)
  }
  return output
})
const selectOptions = computed(() => tools.value.map((tool) => ({ label: `${toolMeta[tool.name]?.title || tool.name} · ${tool.name}`, value: tool.name })))
const resultData = computed(() => {
  const payload = result.value?.result
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? (payload as Record<string, unknown>).data
    : null
})
const resultStatus = computed(() => {
  const payload = result.value?.result
  return payload && typeof payload === 'object' && !Array.isArray(payload) ? String((payload as Record<string, unknown>).status || '') : ''
})
const resultRecord = computed(() => resultData.value && typeof resultData.value === 'object' && !Array.isArray(resultData.value)
  ? resultData.value as Record<string, unknown>
  : null)
const canPrepareQuarantine = computed(() => result.value?.tool_name === 'safe_cleanup_plan'
  && typeof resultRecord.value?.plan_id === 'string'
  && typeof resultRecord.value?.plan_hash === 'string'
  && Number(resultRecord.value?.candidate_count || 0) > 0)
const canPrepareRestore = computed(() => result.value?.tool_name === 'safe_cleanup_quarantine'
  && typeof resultRecord.value?.quarantine_id === 'string'
  && typeof resultRecord.value?.manifest_hash === 'string')

function defaultsFor(tool: ToolDefinition): Record<string, string | number | null> {
  const values: Record<string, string | number | null> = {}
  for (const [key, property] of Object.entries(tool.inputSchema.properties || {}) as Array<[string, JsonSchemaProperty]>) {
    if (property.default !== undefined) values[key] = property.default as string | number
    else if (key === 'port') values[key] = 22
    else if (key === 'service_name') values[key] = 'sshd'
    else if (key === 'lines') values[key] = 50
    else if (key === 'path') values[key] = tool.name.startsWith('safe_cleanup_') ? '/tmp' : '/var/log'
    else if (key === 'size') values[key] = '+100M'
    else values[key] = property.type === 'integer' ? property.minimum || 1 : ''
  }
  return values
}

function isReadOnlyTool(name: string): boolean {
  return !['safe_cleanup_quarantine', 'safe_cleanup_restore'].includes(name)
}

function prepareTool(name: string, values: Record<string, unknown>) {
  const tool = tools.value.find((item) => item.name === name)
  if (!tool) {
    messageApi.error('后端未注册所需的受控处置工具。')
    return
  }
  selectTool(tool)
  for (const [key, value] of Object.entries(values)) {
    if (typeof value === 'string' || typeof value === 'number') argumentValues[key] = value
  }
}

function prepareQuarantine() {
  if (!resultRecord.value) return
  prepareTool('safe_cleanup_quarantine', {
    plan_id: resultRecord.value.plan_id,
    plan_hash: resultRecord.value.plan_hash,
  })
}

function prepareRestore() {
  if (!resultRecord.value) return
  prepareTool('safe_cleanup_restore', {
    quarantine_id: resultRecord.value.quarantine_id,
    manifest_hash: resultRecord.value.manifest_hash,
  })
}

function selectTool(tool: ToolDefinition) {
  selectedName.value = tool.name
  Object.keys(argumentValues).forEach((key) => delete argumentValues[key])
  Object.assign(argumentValues, defaultsFor(tool))
  result.value = null
  window.setTimeout(() => document.getElementById('tool-runner')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0)
}

function updateArgument(key: string, value: string | number | null) {
  argumentValues[key] = value
}

function buildArguments(): Record<string, unknown> {
  const required = new Set(selectedTool.value?.inputSchema.required || [])
  return Object.fromEntries(
    Object.entries(argumentValues).filter(([key, value]) => required.has(key) || (value !== '' && value !== null)),
  )
}

async function callSelected() {
  if (!selectedTool.value) return
  calling.value = true
  result.value = null
  try {
    result.value = await api.callTool(selectedTool.value.name, buildArguments(), sessionId)
  } catch (caught) {
    messageApi.error(caught instanceof Error ? caught.message : '工具调用失败')
  } finally {
    calling.value = false
  }
}

async function confirm(token: string) {
  confirming.value = true
  try {
    result.value = await api.confirmTool(token, sessionId)
    messageApi.success('确认完成，工具结果已写入审计记录。')
  } catch (caught) {
    messageApi.error(caught instanceof Error ? caught.message : '确认失败')
  } finally {
    confirming.value = false
  }
}

function openTrace(requestId: string) {
  router.push({ path: '/audit', query: { request_id: requestId } })
}

async function load() {
  loading.value = true
  try {
    tools.value = await api.tools()
    if (tools.value.length) selectTool(tools.value[0])
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '工具清单加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <page-header
    eyebrow="Controlled capabilities"
    title="工具能力"
    description="所有系统检查都必须通过工具白名单、参数校验和 SafeExecutor。当前自动执行范围仅包含只读能力。"
  />

  <n-alert v-if="error" type="error" :bordered="false" title="工具清单不可用">{{ error }}</n-alert>
  <n-spin :show="loading">
    <section v-for="(groupTools, group) in groups" :key="group" class="section-block">
      <div class="section-heading"><div><h2>{{ group }}</h2><p>受控工具来自后端实时注册表。</p></div></div>
      <div class="tool-grid">
        <article v-for="tool in groupTools" :key="tool.name" class="tool-card" :class="{ selected: selectedName === tool.name }">
          <div class="tool-meta"><n-tag :type="isReadOnlyTool(tool.name) ? 'success' : 'warning'" size="small" :bordered="false">{{ isReadOnlyTool(tool.name) ? '只读工具' : '人工确认' }}</n-tag><n-tag size="small" :bordered="false">白名单控制</n-tag><n-tag size="small" :bordered="false">写入审计</n-tag></div>
          <h3>{{ toolMeta[tool.name]?.title || tool.name }}</h3>
          <p>{{ toolMeta[tool.name]?.scene || tool.description }}</p>
          <div class="tool-output">输出指标：{{ toolMeta[tool.name]?.output || '以后端返回为准' }}</div>
          <code>{{ tool.name }}</code>
          <n-button class="tool-select" secondary type="primary" @click="selectTool(tool)">配置并调用</n-button>
        </article>
      </div>
    </section>
    <n-empty v-if="!loading && !tools.length" description="后端暂未注册可用工具" />
  </n-spin>

  <section id="tool-runner" class="section-block panel">
    <div class="section-heading"><div><h2>受控工具执行台</h2><p>参数通过后端 Schema 校验后才会进入风险判断。</p></div></div>
    <n-select v-model:value="selectedName" :options="selectOptions" placeholder="选择工具" @update:value="(name) => { const tool = tools.find((item) => item.name === name); if (tool) selectTool(tool) }" />

    <div v-if="selectedTool" class="argument-grid">
      <label v-for="(property, key) in selectedTool.inputSchema.properties" :key="key" class="argument-field">
        <span>{{ key }} <small v-if="selectedTool.inputSchema.required?.includes(String(key))">必填</small></span>
        <n-input-number
          v-if="property.type === 'integer'"
          :value="typeof argumentValues[String(key)] === 'number' ? argumentValues[String(key)] as number : null"
          :min="property.minimum"
          :max="property.maximum"
          @update:value="(value) => updateArgument(String(key), value)"
        />
        <n-input
          v-else
          :value="String(argumentValues[String(key)] ?? '')"
          :maxlength="property.maxLength"
          :placeholder="property.description"
          @update:value="(value) => updateArgument(String(key), value)"
        />
        <small>{{ property.description }}</small>
      </label>
      <div v-if="!Object.keys(selectedTool.inputSchema.properties || {}).length" class="inline-empty">该工具无需参数，可直接执行安全检查。</div>
    </div>
    <div class="form-actions"><span class="form-hint">调用结果会包含风险决策、执行状态和 request_id。</span><n-button type="primary" :loading="calling" :disabled="!selectedTool" @click="callSelected">执行受控工具</n-button></div>
    <n-collapse v-if="selectedTool" class="payload-collapse"><n-collapse-item title="高级：工具 Schema" name="schema"><pre>{{ compactJson(selectedTool.inputSchema) }}</pre></n-collapse-item></n-collapse>
  </section>

  <section v-if="resultData" class="section-block panel">
    <tool-result-metrics :tool-name="result?.tool_name" :data="resultData" :status="resultStatus" />
    <div v-if="canPrepareQuarantine || canPrepareRestore" class="cleanup-actions">
      <div>
        <strong>{{ canPrepareQuarantine ? '计划已生成，文件尚未移动' : '文件已隔离，可按需恢复' }}</strong>
        <p>{{ canPrepareQuarantine ? '下一步只会预览隔离操作并要求一次性人工确认。' : '恢复操作同样需要重新校验和人工确认。' }}</p>
      </div>
      <n-button v-if="canPrepareQuarantine" type="warning" @click="prepareQuarantine">准备隔离确认</n-button>
      <n-button v-if="canPrepareRestore" type="primary" secondary @click="prepareRestore">准备恢复确认</n-button>
    </div>
  </section>

  <result-summary v-if="result" :result="result" :confirming="confirming" @trace="openTrace" @confirm="confirm" />
</template>

<style scoped>
.tool-card.selected { border-color: #b08d3e88; background: #2c1f14; }
.tool-card code { color: #eacd76; font-size: 11px; }
.tool-output { margin: 0 0 10px; color: #c9bca8; font-size: 12px; }
.tool-select { width: 100%; margin-top: 14px; }
.argument-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; margin-top: 16px; }
.argument-field > span, .argument-field > small { display: block; }
.argument-field > span { margin-bottom: 6px; color: #d8c9b2; font-size: 12px; }
.argument-field > span small { margin-left: 5px; color: #f2be45; }
.argument-field > small { margin-top: 5px; color: #97887a; font-size: 10px; }
.cleanup-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 16px; padding: 14px; border: 1px solid rgba(242,189,91,.24); border-radius: 9px; background: rgba(242,189,91,.06); }
.cleanup-actions strong { color: #f4ede0; }
.cleanup-actions p { margin: 5px 0 0; color: #c9bca8; font-size: 12px; }
@media (max-width: 640px) { .argument-grid { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .cleanup-actions { display: block; } .cleanup-actions .n-button { width: 100%; margin-top: 12px; } }
</style>
