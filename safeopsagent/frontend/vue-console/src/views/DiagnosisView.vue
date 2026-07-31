<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NInput, NProgress, NTag, useMessage } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import ResultSummary from '@/components/ResultSummary.vue'
import ToolPlanCards from '@/components/ToolPlanCards.vue'
import ToolResultMetrics from '@/components/ToolResultMetrics.vue'
import { api } from '@/api/client'
import type { ChatResponse, ToolCallResponse, ToolPlanItem, ToolResultItem } from '@/types/api'
import { executionLabel, metricLabel, modeLabel, plannerLabel, riskType, toolLabel } from '@/utils/presentation'

const route = useRoute()
const router = useRouter()
const messageApi = useMessage()
const prompt = ref('')
const loading = ref(false)
const confirming = ref(false)
const error = ref('')
const result = ref<ChatResponse | ToolCallResponse | null>(null)
const sessionId = ref(localStorage.getItem('safeops-session-id') || crypto.randomUUID())
localStorage.setItem('safeops-session-id', sessionId.value)

const toolPlans = computed<ToolPlanItem[]>(() => Array.isArray(result.value?.tool_plan) ? result.value.tool_plan as ToolPlanItem[] : [])
const diagnosis = computed(() => (result.value as ChatResponse | null)?.diagnosis || null)
const rootCauseChains = computed<any[]>(() => (diagnosis.value as any)?.root_cause_chains || [])

const toolResults = computed<ToolResultItem[]>(() => {
  const current = result.value as ChatResponse | null
  if (Array.isArray(current?.tool_results) && current.tool_results.length) {
    return current.tool_results.filter((item): item is ToolResultItem => Boolean(item && typeof item === 'object'))
  }
  const primary = normalizeToolResult(current?.tool_result)
  return primary?.tool || primary?.data ? [primary] : []
})

const diagnosticConclusion = computed(() => {
  if (!result.value) return ''
  if (diagnosis.value?.summary) return diagnosis.value.summary
  const decision = String(result.value.security_decision || '').toLowerCase()
  if (decision === 'reject' || decision === 'forbidden') return '系统已拒绝该请求，未执行任何系统命令。'
  if (result.value.execution_status === 'environment_limited') return '安全检查已通过，但当前环境缺少对应系统命令，无法完成本次只读检查。'
  if (result.value.execution_status === 'success') return '本次只读诊断已完成，系统未被修改。'
  if (result.value.confirmation_required) return '该操作需要人工确认，当前尚未执行。'
  return result.value.summary || '后端已返回诊断结果。'
})

const examples = [
  '查看当前系统运行情况',
  'check memory status',
  '检查 CPU 和系统负载',
  '检查端口 22 占用',
  '查看 sshd 服务状态',
  '生成安全清理计划',
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function normalizeToolResult(value: unknown): ToolResultItem | null {
  return isRecord(value) ? value as ToolResultItem : null
}

function severityLabel(value?: string): string {
  return {
    normal: '状态正常',
    notice: '需要关注',
    warning: '存在异常',
    critical: '高优先级异常',
    unknown: '信息不足',
  }[String(value || 'unknown')] || '信息不足'
}

function severityType(value?: string): 'success' | 'info' | 'warning' | 'error' | 'default' {
  if (value === 'normal') return 'success'
  if (value === 'notice') return 'info'
  if (value === 'warning') return 'warning'
  if (value === 'critical') return 'error'
  return 'default'
}

function evidenceValue(value: unknown, unit: string): string {
  if (value === undefined || value === null || value === '') return '未知'
  return `${String(value)}${unit ? ` ${unit}` : ''}`
}

async function submit(value = prompt.value) {
  const cleaned = value.trim()
  if (!cleaned) return
  prompt.value = cleaned
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await api.chat(cleaned, sessionId.value)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '诊断请求失败'
  } finally {
    loading.value = false
  }
}

async function confirm(token: string) {
  confirming.value = true
  try {
    result.value = await api.confirmTool(token, sessionId.value)
    messageApi.success('确认请求已完成，结果已重新经过安全校验。')
  } catch (caught) {
    messageApi.error(caught instanceof Error ? caught.message : '确认失败')
  } finally {
    confirming.value = false
  }
}

function openTrace(requestId: string) {
  router.push({ path: '/audit', query: { request_id: requestId } })
}

onMounted(() => {
  const fromQuery = String(route.query.prompt || '')
  if (fromQuery) {
    prompt.value = fromQuery
    submit(fromQuery)
  }
})
</script>

<template>
  <page-header
    eyebrow="Guided diagnosis"
    title="智能诊断"
    description="用自然语言描述系统问题。模型只负责理解与规划，工具执行仍由安全护栏、白名单和最小权限代理控制。"
  />

  <section class="input-panel">
    <div class="example-row">
      <n-button v-for="item in examples" :key="item" size="small" tertiary @click="submit(item)">{{ item }}</n-button>
    </div>
    <n-input
      v-model:value="prompt"
      type="textarea"
      :autosize="{ minRows: 4, maxRows: 8 }"
      maxlength="2000"
      show-count
      placeholder="例如：系统响应变慢，先帮我做只读检查"
      @keydown.ctrl.enter.prevent="submit()"
    />
    <div class="form-actions">
      <span class="form-hint">Ctrl + Enter 发送 · 当前会话 {{ sessionId.slice(0, 8) }}</span>
      <n-button type="primary" :loading="loading" :disabled="!prompt.trim()" @click="submit()">发送诊断请求</n-button>
    </div>
  </section>

  <n-alert v-if="error" class="section-block" type="error" title="请求未送达" :bordered="false">{{ error }}</n-alert>

  <template v-if="result">
    <section class="section-block diagnosis-conclusion">
      <div class="conclusion-card">
        <div>
          <span class="eyebrow">诊断结论</span>
          <h2>{{ diagnosticConclusion }}</h2>
          <p>工具权限：只读 · 修改系统：否 · {{ executionLabel(result as Record<string, unknown>) }}</p>
        </div>
        <n-tag :type="riskType(result.risk_score)" :bordered="false">风险 {{ result.risk_score ?? 0 }} / 100</n-tag>
      </div>
    </section>

    <section v-if="diagnosis" class="section-block diagnosis-body">
      <div class="section-heading">
        <div><h2>诊断依据与建议</h2><p>结论由真实工具结果和确定性规则生成，模型不能修改指标或风险决策。</p></div>
        <n-tag :type="severityType(diagnosis.severity)" :bordered="false">{{ severityLabel(diagnosis.severity) }}</n-tag>
      </div>
      <div v-if="diagnosis.evidence.length" class="evidence-grid">
        <article v-for="(item, index) in diagnosis.evidence" :key="`${item.metric}-${index}`">
          <span>{{ metricLabel(item.metric) }}</span>
          <strong>{{ evidenceValue(item.value, item.unit) }}</strong>
          <small>{{ item.context || toolLabel(item.source_tool) }}</small>
        </article>
      </div>
      <details v-if="diagnosis.evidence.length" class="technical-evidence">
        <summary>查看原始指标字段</summary>
        <div v-for="(item, index) in diagnosis.evidence" :key="`raw-${item.metric}-${index}`">
          <code>{{ item.metric }}</code>
          <span>{{ item.source_tool }}</span>
        </div>
      </details>
      <div v-else class="inline-empty">本次请求没有返回可用于设备诊断的指标。</div>
      <div class="diagnosis-columns">
        <article>
          <span class="eyebrow">异常发现</span>
          <ul v-if="diagnosis.findings.length"><li v-for="item in diagnosis.findings" :key="item">{{ item }}</li></ul>
          <p v-else>暂无发现。</p>
        </article>
        <article>
          <span class="eyebrow">处置建议</span>
          <ul v-if="diagnosis.recommendations.length"><li v-for="item in diagnosis.recommendations" :key="item">{{ item }}</li></ul>
          <p v-else>当前无需额外处置。</p>
        </article>
        <article>
          <span class="eyebrow">下一步动作</span>
          <ul v-if="diagnosis.next_actions.length"><li v-for="item in diagnosis.next_actions" :key="item">{{ item }}</li></ul>
          <p v-else>暂无后续动作。</p>
        </article>
      </div>
    </section>

    <section v-if="rootCauseChains.length" class="section-block root-cause-section">
      <div class="section-heading">
        <div><h2>智能化根因分析</h2><p>跨工具关联推理：症状 → 证据 → 根因 → 安全评估 → 建议，对应赛题"智能化根因分析能力"要求。</p></div>
        <n-tag type="info" :bordered="false">{{ rootCauseChains.length }} 条根因链</n-tag>
      </div>
      <article v-for="(chain, idx) in rootCauseChains" :key="chain.chain_id || idx" class="root-cause-card">
        <header class="rc-header">
          <div>
            <span class="eyebrow">根因链 {{ idx + 1 }} · {{ chain.chain_id }}</span>
            <h3>{{ chain.symptom }}</h3>
          </div>
          <n-tag :type="severityType(chain.severity)" :bordered="false">{{ severityLabel(chain.severity) }}</n-tag>
        </header>
        <div class="rc-root-cause">
          <span class="eyebrow">根因定位</span>
          <p>{{ chain.root_cause }}</p>
        </div>
        <div v-if="typeof chain.confidence === 'number'" class="rc-confidence">
          <span>根因置信度</span>
          <n-progress type="line" :percentage="Math.round(chain.confidence * 100)" :show-indicator="true" />
        </div>
        <div v-if="chain.evidence && chain.evidence.length" class="rc-evidence">
          <span class="eyebrow">关联证据</span>
          <div class="rc-evidence-grid">
            <div v-for="(ev, eidx) in chain.evidence" :key="eidx" class="rc-evidence-item">
              <small>{{ ev.tool }}</small>
              <code>{{ ev.metric }}</code>
              <strong>{{ ev.value }}</strong>
            </div>
          </div>
        </div>
        <div v-if="chain.safety_assessment && Object.keys(chain.safety_assessment).length" class="rc-safety">
          <span class="eyebrow">安全评估</span>
          <div class="rc-safety-body">
            <n-tag v-if="chain.safety_assessment.database_logs_detected" type="warning" size="small" :bordered="false">已识别关键数据库日志</n-tag>
            <n-tag v-if="chain.safety_assessment.critical_files_detected" type="error" size="small" :bordered="false">检测到关键文件</n-tag>
            <span class="rc-safety-counts">可清理 {{ chain.safety_assessment.cleanable_files ?? 0 }} · 受保护 {{ chain.safety_assessment.protected_files ?? 0 }}</span>
            <p v-if="chain.safety_assessment.notes" class="rc-safety-note">{{ chain.safety_assessment.notes }}</p>
            <ul v-if="chain.safety_assessment.database_files && chain.safety_assessment.database_files.length" class="rc-db-files">
              <li v-for="f in chain.safety_assessment.database_files" :key="f">{{ f }}</li>
            </ul>
          </div>
        </div>
        <div class="rc-actions">
          <div v-if="chain.recommendations && chain.recommendations.length">
            <span class="eyebrow">处置建议</span>
            <ul><li v-for="r in chain.recommendations" :key="r">{{ r }}</li></ul>
          </div>
          <div v-if="chain.next_actions && chain.next_actions.length">
            <span class="eyebrow">下一步动作</span>
            <ul><li v-for="a in chain.next_actions" :key="a">{{ a }}</li></ul>
          </div>
        </div>
      </article>
    </section>

    <section v-if="toolResults.length" class="section-block result-stack">
      <div class="section-heading"><div><h2>设备检查结果</h2><p>逐项展示本次受控工具返回的真实数据。</p></div></div>
      <article v-for="(item, index) in toolResults" :key="`${item.tool}-${index}`" class="panel tool-result-panel">
        <tool-result-metrics
          :tool-name="item.tool || toolPlans[index]?.tool_name"
          :data="item.data"
          :status="item.status"
        />
      </article>
    </section>

    <result-summary
      :result="result"
      :confirming="confirming"
      @trace="openTrace"
      @confirm="confirm"
    />

    <section class="section-block grid-2">
      <div class="panel">
        <div class="section-heading"><div><h2>智能理解</h2><p>模型只输出意图和规划，不生成可直接执行的系统命令。</p></div></div>
        <div class="data-list">
          <div class="data-row"><span>识别意图</span><strong>{{ result.intent || '未识别到明确运维意图' }}</strong></div>
          <div class="data-row"><span>规划来源</span><strong>{{ plannerLabel(result.planner_source) }}</strong></div>
          <div class="data-row"><span>运行模式</span><strong>{{ modeLabel(result.agent_mode) }}</strong></div>
          <div class="data-row"><span>模型服务</span><strong>{{ result.model_vendor || '内置安全规划器' }} · {{ result.model_name || 'offline' }}</strong></div>
        </div>
        <div v-if="typeof result.planner_confidence === 'number'" class="confidence-row">
          <span>规划置信度</span><n-progress type="line" :percentage="Math.round(result.planner_confidence * 100)" :show-indicator="true" />
        </div>
      </div>
      <div class="panel">
        <div class="section-heading"><div><h2>分析与建议</h2><p>根据受控工具结果生成的人类可读结论。</p></div></div>
        <div class="narrative-block"><span>分析</span><p>{{ result.analysis || result.planner_explanation || '后端未提供额外分析。' }}</p></div>
        <div class="narrative-block"><span>下一步</span><p>{{ result.next_step || '无需进一步操作，或请补充更具体的系统现象。' }}</p></div>
        <n-alert v-if="result.environment_message" type="warning" :bordered="false">{{ result.environment_message }}</n-alert>
      </div>
    </section>

    <section class="section-block">
      <div class="section-heading">
        <div><h2>受控工具计划</h2><p>每个工具均来自白名单，并独立经过参数与输出检查。</p></div>
        <n-tag :type="riskType(result.risk_score)" :bordered="false">风险 {{ result.risk_score ?? 0 }} / 100</n-tag>
      </div>
      <tool-plan-cards :plans="toolPlans" />
    </section>
  </template>

  <section v-else-if="!loading" class="section-block panel panel-quiet diagnosis-placeholder">
    <strong>描述一个真实系统问题</strong>
    <p>SafeOpsAgent 会先做本地安全预检，再规划只读工具。危险请求不会进入工具执行阶段。</p>
  </section>
</template>

<style scoped>
.diagnosis-conclusion { margin-top: 20px; }
.conclusion-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  padding: 20px;
  border: 1px solid rgba(84, 209, 223, 0.24);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(17, 34, 43, 0.92), rgba(14, 20, 27, 0.92));
}
.conclusion-card h2 { margin: 6px 0 8px; font-size: 22px; line-height: 1.45; }
.conclusion-card p { margin: 0; color: #b0a28e; }
.confidence-row { margin-top: 18px; }
.confidence-row > span { display: block; margin-bottom: 7px; color: #a89a86; font-size: 11px; }
.narrative-block { margin-bottom: 15px; }
.narrative-block > span { color: #eacd76; font-size: 11px; font-weight: 700; }
.narrative-block p { margin: 5px 0 0; color: #d8c9b2; font-size: 13px; line-height: 1.7; }
.diagnosis-placeholder { padding: 34px; text-align: center; }
.diagnosis-placeholder p { color: #97887a; }
.diagnosis-body { min-width: 0; }
.evidence-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
.evidence-grid article { padding: 14px; border: 1px solid rgba(84, 209, 223, .13); border-radius: 9px; background: rgba(10, 20, 29, .68); min-width: 0; }
.evidence-grid span, .evidence-grid small { display: block; color: #97887a; font-size: 10px; overflow-wrap: anywhere; }
.evidence-grid strong { display: block; margin: 7px 0; color: #f4ede0; font-size: 18px; overflow-wrap: anywhere; }
.technical-evidence { margin-top: 10px; color: #97887a; font-size: 11px; }
.technical-evidence summary { color: #97887a; }
.technical-evidence > div { display: flex; gap: 10px; padding: 5px 0; }
.technical-evidence code { color: #b0a28e; }
.diagnosis-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.diagnosis-columns article { padding: 16px; border: 1px solid rgba(255,255,255,.06); border-radius: 10px; background: rgba(255,255,255,.02); }
.diagnosis-columns ul { margin: 10px 0 0; padding-left: 18px; color: #c9bca8; line-height: 1.7; }
.diagnosis-columns p { color: #a89a86; }
.result-stack { min-width: 0; }
.tool-result-panel + .tool-result-panel { margin-top: 12px; }
.inline-empty { padding: 18px; border: 1px dashed rgba(255,255,255,.1); border-radius: 9px; color: #a89a86; }
.root-cause-section { min-width: 0; }
.root-cause-card {
  padding: 18px;
  border: 1px solid rgba(84, 209, 223, 0.18);
  border-radius: 12px;
  background: rgba(10, 20, 29, 0.68);
}
.root-cause-card + .root-cause-card { margin-top: 14px; }
.rc-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; margin-bottom: 14px; }
.rc-header h3 { margin: 6px 0 0; font-size: 16px; color: #f4ede0; }
.rc-root-cause { margin-bottom: 14px; }
.rc-root-cause p { margin: 6px 0 0; color: #d8c9b2; font-size: 13px; line-height: 1.7; }
.rc-confidence { margin-bottom: 14px; }
.rc-confidence > span { display: block; margin-bottom: 6px; color: #a89a86; font-size: 11px; }
.rc-evidence { margin-bottom: 14px; }
.rc-evidence-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-top: 8px; }
.rc-evidence-item { padding: 10px; border: 1px solid rgba(255,255,255,.06); border-radius: 8px; background: rgba(255,255,255,.02); }
.rc-evidence-item small { display: block; color: #97887a; font-size: 10px; }
.rc-evidence-item code { display: block; color: #b0a28e; font-size: 11px; margin: 4px 0; word-break: break-all; }
.rc-evidence-item strong { display: block; color: #f4ede0; font-size: 14px; word-break: break-all; }
.rc-safety { margin-bottom: 14px; }
.rc-safety-body { margin-top: 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.rc-safety-counts { color: #b0a28e; font-size: 12px; }
.rc-safety-note { width: 100%; margin: 8px 0 0; color: #d8c9b2; font-size: 12px; line-height: 1.6; }
.rc-db-files { width: 100%; margin: 6px 0 0; padding-left: 18px; color: #d4a574; font-size: 11px; line-height: 1.6; word-break: break-all; }
.rc-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.rc-actions ul { margin: 8px 0 0; padding-left: 18px; color: #c9bca8; font-size: 12px; line-height: 1.7; }
@media (max-width: 640px) {
  .conclusion-card { display: block; }
  .conclusion-card .n-tag { margin-top: 14px; }
  .diagnosis-columns { grid-template-columns: 1fr; }
  .rc-actions { grid-template-columns: 1fr; }
}
</style>
