<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton, NCollapse, NCollapseItem, NEmpty, NInput, NSpin, NTable, NTag } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import TraceTimeline from '@/components/TraceTimeline.vue'
import { api } from '@/api/client'
import type { AuditLog, TraceResponse } from '@/types/api'
import { compactJson, decisionLabel, decisionType, executionLabel, formatTime, getRuleLabels, riskLabel, riskType } from '@/utils/presentation'

const route = useRoute()
const loadingLogs = ref(true)
const loadingTrace = ref(false)
const error = ref('')
const logs = ref<AuditLog[]>([])
const requestId = ref(String(route.query.request_id || ''))
const trace = ref<TraceResponse | null>(null)

const selectedAudit = computed(() => trace.value?.audit || logs.value.find((item) => item.request_id === requestId.value) || null)
const rules = computed(() => selectedAudit.value ? getRuleLabels(selectedAudit.value as Record<string, unknown>) : [])

async function loadLogs() {
  loadingLogs.value = true
  error.value = ''
  try {
    logs.value = await api.auditLogs(20)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '审计日志加载失败'
  } finally {
    loadingLogs.value = false
  }
}

async function loadTrace(id = requestId.value) {
  const cleaned = id.trim()
  if (!cleaned) return
  requestId.value = cleaned
  loadingTrace.value = true
  error.value = ''
  try {
    trace.value = await api.auditTrace(cleaned)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '审计证据链加载失败'
  } finally {
    loadingTrace.value = false
  }
}

onMounted(async () => {
  await loadLogs()
  if (requestId.value) await loadTrace(requestId.value)
})
</script>

<template>
  <page-header
    eyebrow="Audit trace"
    title="审计追踪"
    description="每一次智能运维请求都会生成 request_id，可回放接收请求、风险判断、工具规划、执行状态和审计保存过程。"
  >
    <template #actions><n-button secondary :loading="loadingLogs" @click="loadLogs">刷新日志</n-button></template>
  </page-header>

  <n-alert v-if="error" class="section-block" type="error" title="审计数据不可用" :bordered="false">{{ error }}</n-alert>

  <section class="section-block panel">
    <div class="section-heading"><div><h2>最近操作记录</h2><p>展示真实审计日志，可选择任意 request_id 查看证据链。</p></div></div>
    <n-spin :show="loadingLogs">
      <div v-if="logs.length" class="audit-table-wrap">
        <n-table size="small" :bordered="false">
          <thead>
            <tr><th>时间</th><th>请求摘要</th><th>风险</th><th>安全决策</th><th>执行状态</th><th>工具</th><th>request_id</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.request_id">
              <td>{{ formatTime(log.created_at || log.timestamp) }}</td>
              <td>{{ log.user_input || log.intent || '受控工具调用' }}</td>
              <td><n-tag size="small" :type="riskType(log.risk_score)" :bordered="false">{{ log.risk_score ?? 0 }} / 100</n-tag></td>
              <td><n-tag size="small" :type="decisionType(log.security_decision)" :bordered="false">{{ decisionLabel(log.security_decision) }}</n-tag></td>
              <td>{{ executionLabel(log as Record<string, unknown>) }}</td>
              <td>{{ log.selected_tool || '未选择工具' }}</td>
              <td><code>{{ log.request_id }}</code></td>
              <td><n-button size="small" text type="primary" @click="loadTrace(log.request_id)">查看证据链</n-button></td>
            </tr>
          </tbody>
        </n-table>
      </div>
      <div v-if="logs.length" class="audit-mobile-list">
        <article v-for="log in logs" :key="log.request_id" class="audit-card">
          <div class="audit-card-head">
            <strong>{{ log.user_input || log.intent || '受控工具调用' }}</strong>
            <n-tag size="small" :type="decisionType(log.security_decision)" :bordered="false">{{ decisionLabel(log.security_decision) }}</n-tag>
          </div>
          <p>{{ formatTime(log.created_at || log.timestamp) }}</p>
          <p>{{ log.request_id }}</p>
          <n-button size="small" secondary type="primary" @click="loadTrace(log.request_id)">查看证据链</n-button>
        </article>
      </div>
      <n-empty v-if="!logs.length && !loadingLogs" description="暂无审计日志" />
    </n-spin>
  </section>

  <section class="section-block panel">
    <div class="section-heading"><div><h2>证据链查询</h2><p>输入 request_id 后回放单次请求的安全执行链路。</p></div></div>
    <div class="form-actions">
      <n-input v-model:value="requestId" placeholder="输入 request_id" @keydown.enter.prevent="loadTrace()" />
      <n-button type="primary" :loading="loadingTrace" :disabled="!requestId.trim()" @click="loadTrace()">查看证据链</n-button>
    </div>
  </section>

  <section v-if="trace" class="section-block grid-2">
    <div class="panel">
      <div class="section-heading"><div><h2>审计摘要</h2><p>以人类可读方式展示本次操作的关键结论。</p></div></div>
      <template v-if="selectedAudit">
        <div class="data-list">
          <div class="data-row"><span>request_id</span><strong>{{ selectedAudit.request_id || requestId }}</strong></div>
          <div class="data-row"><span>请求内容</span><strong>{{ selectedAudit.user_input || selectedAudit.intent || '未返回' }}</strong></div>
          <div class="data-row"><span>安全决策</span><strong>{{ decisionLabel(selectedAudit.security_decision) }}</strong></div>
          <div class="data-row"><span>风险评分</span><strong>{{ selectedAudit.risk_score ?? 0 }} / 100 · {{ riskLabel(selectedAudit.risk_band || selectedAudit.risk_level_text, selectedAudit.risk_score) }}</strong></div>
          <div class="data-row"><span>执行状态</span><strong>{{ executionLabel(selectedAudit as Record<string, unknown>) }}</strong></div>
          <div class="data-row"><span>工具</span><strong>{{ selectedAudit.selected_tool || '未选择工具' }}</strong></div>
        </div>
        <div class="rule-strip">
          <span>规则标签</span>
          <n-tag v-if="!rules.length" size="small" :bordered="false">无高风险规则</n-tag>
          <n-tag v-for="rule in rules" :key="rule" size="small" type="warning" :bordered="false">{{ rule }}</n-tag>
        </div>
      </template>
      <n-empty v-else description="该 request_id 未返回审计摘要" />
    </div>
    <div class="panel">
      <div class="section-heading"><div><h2>Trace 时间线</h2><p>阶段名称来自后端真实审计回放。</p></div></div>
      <trace-timeline :items="trace.timeline" />
    </div>
  </section>

  <section v-if="trace" class="section-block panel">
    <n-collapse>
      <n-collapse-item title="高级详情" name="trace-json">
        <pre>{{ compactJson(trace) }}</pre>
      </n-collapse-item>
    </n-collapse>
  </section>
</template>
