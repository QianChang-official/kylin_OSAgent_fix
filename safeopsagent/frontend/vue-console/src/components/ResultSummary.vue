<script setup lang="ts">
import { computed } from 'vue'
import { NAlert, NButton, NCollapse, NCollapseItem, NDescriptions, NDescriptionsItem, NTag } from 'naive-ui'
import {
  compactJson,
  decisionLabel,
  decisionType,
  executionLabel,
  getRuleLabels,
  isEnvironmentLimited,
  plannerLabel,
  riskLabel,
  riskType,
} from '@/utils/presentation'

const props = defineProps<{
  result: Record<string, unknown>
  confirming?: boolean
}>()

const emit = defineEmits<{
  trace: [requestId: string]
  confirm: [token: string]
}>()

const rules = computed(() => getRuleLabels(props.result))
const requestId = computed(() => String(props.result.request_id || props.result.original_request_id || ''))
const summary = computed(() => String(props.result.summary || props.result.response || props.result.error || '后端已返回结果。'))
const environmentLimited = computed(() => isEnvironmentLimited(props.result))
const token = computed(() => typeof props.result.confirmation_token === 'string' ? props.result.confirmation_token : '')
const dryRun = computed(() => {
  const value = props.result.dry_run_result
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
})
</script>

<template>
  <section class="result-summary panel">
    <div class="section-heading">
      <div>
        <h2>执行结论</h2>
        <p>{{ summary }}</p>
      </div>
      <n-tag :type="decisionType(result.security_decision)" :bordered="false">
        {{ decisionLabel(result.security_decision) }}
      </n-tag>
    </div>

    <n-alert
      v-if="environmentLimited"
      class="environment-note"
      type="warning"
      :bordered="false"
      title="环境能力受限"
    >
      当前环境缺少部分 Linux / 麒麟运维命令，安全链路正常工作，但该工具无法完成真实系统检查。建议在银河麒麟、Linux 或 WSL 环境进行完整演示。
    </n-alert>

    <n-descriptions class="result-facts" bordered :column="4" size="small">
      <n-descriptions-item label="风险评分">{{ result.risk_score ?? 0 }} / 100</n-descriptions-item>
      <n-descriptions-item label="风险等级">{{ riskLabel(result.risk_level || result.risk_band, result.risk_score) }}</n-descriptions-item>
      <n-descriptions-item label="安全决策">{{ decisionLabel(result.security_decision) }}</n-descriptions-item>
      <n-descriptions-item label="执行状态">{{ executionLabel(result) }}</n-descriptions-item>
      <n-descriptions-item label="工具">{{ result.selected_tool || result.tool_name || '未选择工具' }}</n-descriptions-item>
      <n-descriptions-item label="规划来源">{{ plannerLabel(result.planner_source) }}</n-descriptions-item>
      <n-descriptions-item label="request_id" :span="2">{{ requestId || '未返回' }}</n-descriptions-item>
    </n-descriptions>

    <div class="rule-strip">
      <span>命中规则</span>
      <n-tag v-if="!rules.length" size="small" :bordered="false">无高风险规则</n-tag>
      <n-tag v-for="rule in rules" :key="rule" size="small" type="warning" :bordered="false">{{ rule }}</n-tag>
    </div>

    <div v-if="result.confirmation_required || token" class="dry-run-panel">
      <n-tag type="warning" :bordered="false">需要人工确认</n-tag>
      <h3>Dry-run 结果</h3>
      <p>该操作需要人工确认，当前尚未执行。确认后仍会再次经过安全校验与审计记录。</p>
      <n-descriptions v-if="dryRun" class="dry-run-facts" bordered :column="2" size="small">
        <n-descriptions-item label="受控工具">{{ dryRun.tool_name || result.tool_name || '未返回' }}</n-descriptions-item>
        <n-descriptions-item label="风险评分">{{ dryRun.risk_score ?? result.risk_score ?? '未返回' }} / 100</n-descriptions-item>
        <n-descriptions-item label="安全决策">{{ decisionLabel(dryRun.security_decision || result.security_decision) }}</n-descriptions-item>
        <n-descriptions-item label="当前状态">尚未执行</n-descriptions-item>
        <n-descriptions-item label="说明" :span="2">{{ dryRun.message || '该操作需要人工确认，尚未执行。' }}</n-descriptions-item>
      </n-descriptions>
      <n-button v-if="token" type="warning" :loading="confirming" @click="emit('confirm', token)">确认执行</n-button>
    </div>

    <div class="result-actions">
      <n-button v-if="requestId" secondary type="primary" @click="emit('trace', requestId)">查看安全证据链</n-button>
      <span class="request-id">{{ requestId || '暂无 request_id' }}</span>
    </div>

    <n-collapse class="payload-collapse">
      <n-collapse-item title="高级详情" name="payload">
        <pre>{{ compactJson(result) }}</pre>
      </n-collapse-item>
    </n-collapse>
  </section>
</template>
