<script setup lang="ts">
// Attribution console for front-door activity. Every figure shown here is a
// passive observation: what the client sent, when, and how often. Nothing on
// this page probes, contacts or identifies the observed host.
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NEmpty, NSpin, NTag } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import { api } from '@/api/client'
import type { DeceptionIncidents, DeceptionSeverity, DeceptionSource } from '@/types/api'

const loading = ref(true)
const error = ref('')
const report = ref<DeceptionIncidents | null>(null)
const selected = ref<string>('')

const sources = computed(() => report.value?.sources || [])
const summary = computed(() => report.value?.summary || null)
const active = computed<DeceptionSource | null>(
  () => sources.value.find((item) => item.source === selected.value) || sources.value[0] || null,
)
const evidence = computed(() => (report.value?.recent_evidence || []).slice(0, 12))

const SEVERITY_LABELS: Record<DeceptionSeverity, string> = {
  info: '观察',
  low: '低',
  medium: '中',
  high: '高',
  critical: '严重',
}

const CLASSIFICATION_LABELS: Record<string, string> = {
  observed: '仅观察到访问',
  manual_probing: '人工试探',
  automated_tooling: '自动化工具',
  automated_bruteforce: '自动化爆破',
  password_brute_force: '口令穷举',
  credential_stuffing: '撞库攻击',
}

const EVENT_LABELS: Record<string, string> = {
  login_failure: '登录失败',
  login_success: '登录成功',
  gate_failure: '入口门失败',
  sandbox_opened: '进入蜜罐',
  sandbox_request: '蜜罐内操作',
}

function severityType(value: DeceptionSeverity | string) {
  if (value === 'critical' || value === 'high') return 'error'
  if (value === 'medium') return 'warning'
  if (value === 'low') return 'info'
  return 'default'
}

function severityLabel(value: DeceptionSeverity | string) {
  return SEVERITY_LABELS[value as DeceptionSeverity] || value
}

function classificationLabel(value: string) {
  return CLASSIFICATION_LABELS[value] || value
}

function eventLabel(value: string) {
  return EVENT_LABELS[value] || value
}

function paceLabel(value: number | null) {
  if (value === null) return '样本不足'
  if (value < 1) return `${value}s · 机器节奏`
  if (value < 5) return `${value}s · 偏快`
  return `${value}s · 接近人工`
}

function durationLabel(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${(seconds / 3600).toFixed(1)} 小时`
}

async function load() {
  loading.value = true
  try {
    report.value = await api.deceptionIncidents(50)
    error.value = ''
    if (!sources.value.some((item) => item.source === selected.value)) {
      selected.value = sources.value[0]?.source || ''
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '溯源数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <page-header
    eyebrow="Attribution"
    title="溯源画像"
    description="公开登录页是诱饵。持续猜测凭据的客户端会进入蜜罐，其来源、指纹、节奏与尝试记录在此汇总，全部为被动观测。"
  >
    <template #actions><n-button secondary :loading="loading" @click="load">刷新</n-button></template>
  </page-header>

  <n-alert v-if="error" class="section-block" type="error" title="溯源数据不可用" :bordered="false">{{ error }}</n-alert>

  <n-spin :show="loading">
    <section v-if="summary" class="section-block">
      <div class="grid-4">
        <article class="metric-card">
          <div class="metric-card-header"><span>追踪来源</span></div>
          <div class="metric-value">{{ summary.tracked_sources }}</div>
          <p class="metric-caption">按真实来源地址归并，代理头仅在可信代理后采信。</p>
        </article>
        <article class="metric-card">
          <div class="metric-card-header"><span>活跃蜜罐会话</span></div>
          <div class="metric-value">{{ summary.sandbox_sessions_open }}</div>
          <p class="metric-caption">会话内所有数据均为合成，真实处理函数不可达。</p>
        </article>
        <article class="metric-card">
          <div class="metric-card-header"><span>凭据失败</span></div>
          <div class="metric-value">{{ summary.total_login_failures + summary.total_gate_failures }}</div>
          <p class="metric-caption">登录 {{ summary.total_login_failures }} · 入口门 {{ summary.total_gate_failures }}</p>
        </article>
        <article class="metric-card">
          <div class="metric-card-header"><span>最高定级</span></div>
          <div class="metric-value">
            <n-tag :type="severityType(summary.highest_severity)" :bordered="false" size="large">
              {{ severityLabel(summary.highest_severity) }}
            </n-tag>
          </div>
          <p class="metric-caption">连续失败 {{ summary.trigger_attempts }} 次后转入蜜罐。</p>
        </article>
      </div>

      <div class="posture-strip">
        <n-tag size="small" :type="report?.gate_enabled ? 'success' : 'warning'" :bordered="false">
          入口门 {{ report?.gate_enabled ? '已启用' : '未配置' }}
        </n-tag>
        <n-tag size="small" :type="summary.enabled ? 'success' : 'default'" :bordered="false">
          蜜罐 {{ summary.enabled ? '已启用' : '已关闭' }}
        </n-tag>
        <n-tag size="small" :bordered="false">
          反向 DNS {{ summary.reverse_dns_enabled ? '已开启' : '关闭（默认零外连）' }}
        </n-tag>
        <n-tag v-if="summary.evidence_error" size="small" type="warning" :bordered="false">
          证据写入异常：{{ summary.evidence_error }}
        </n-tag>
      </div>
    </section>

    <n-empty v-if="!loading && !sources.length" class="section-block" description="尚未观测到前门异常活动。" />

    <section v-if="sources.length" class="section-block dossier-layout">
      <aside class="source-list panel">
        <div class="section-heading"><div><h2>来源列表</h2><p>按最近活动排序。</p></div></div>
        <button
          v-for="item in sources"
          :key="item.source"
          type="button"
          class="source-row"
          :class="{ active: active?.source === item.source }"
          @click="selected = item.source"
        >
          <div class="source-row-head">
            <strong>{{ item.source }}</strong>
            <n-tag size="small" :type="severityType(item.severity)" :bordered="false">{{ severityLabel(item.severity) }}</n-tag>
          </div>
          <span>{{ classificationLabel(item.classification) }} · {{ item.total_attempts }} 次尝试</span>
          <small v-if="item.sandbox_active" class="source-flag">蜜罐会话进行中</small>
        </button>
      </aside>

      <div v-if="active" class="dossier panel">
        <div class="section-heading">
          <div>
            <h2>{{ active.source }}</h2>
            <p>{{ active.first_seen }} 起观测，持续 {{ durationLabel(active.observed_seconds) }}。</p>
          </div>
          <n-tag :type="severityType(active.severity)" :bordered="false">{{ severityLabel(active.severity) }}</n-tag>
        </div>

        <div class="grid-3">
          <article class="fact"><span>行为分类</span><strong>{{ classificationLabel(active.classification) }}</strong></article>
          <article class="fact"><span>请求节奏</span><strong>{{ paceLabel(active.median_interval_seconds) }}</strong></article>
          <article class="fact"><span>客户端类型</span><strong>{{ active.automated_agent ? '自动化工具' : '疑似浏览器' }}</strong></article>
          <article class="fact"><span>网段归属</span><strong>{{ active.network_scope }}</strong></article>
          <article class="fact"><span>蜜罐会话</span><strong>{{ active.sandbox_sessions }} 次 / {{ active.sandbox_requests }} 请求</strong></article>
          <article class="fact"><span>失败次数</span><strong>登录 {{ active.login_failures }} · 门 {{ active.gate_failures }}</strong></article>
        </div>

        <div class="detail-block">
          <h3>尝试的账号</h3>
          <div class="chip-row">
            <n-tag v-for="name in active.usernames_tried" :key="name" size="small" :bordered="false">{{ name }}</n-tag>
            <span v-if="!active.usernames_tried.length" class="muted">无</span>
          </div>
        </div>

        <div class="detail-block">
          <h3>口令摘要 <small>共 {{ active.distinct_passwords }} 个不同口令，仅保留密钥摘要，不存明文</small></h3>
          <div class="chip-row">
            <code v-for="digest in active.credential_digests.slice(0, 8)" :key="digest">{{ digest }}</code>
            <span v-if="!active.credential_digests.length" class="muted">无</span>
          </div>
        </div>

        <div class="detail-block">
          <h3>客户端指纹 <small>由客户端自行发送的头部派生，源地址轮换后仍可关联</small></h3>
          <div class="chip-row">
            <code v-for="print in active.fingerprints" :key="print">{{ print }}</code>
          </div>
          <p v-if="active.user_agents.length" class="agent-line">User-Agent：{{ active.user_agents.join(' · ') }}</p>
          <p v-if="active.forwarded_chain.length" class="agent-line">
            代理链：{{ active.forwarded_chain.join(' → ') }}
            <n-tag size="small" :type="active.proxy_trusted ? 'success' : 'warning'" :bordered="false">
              {{ active.proxy_trusted ? '来自可信代理' : '未采信' }}
            </n-tag>
          </p>
          <p v-if="active.reverse_dns" class="agent-line">反向 DNS：{{ active.reverse_dns }}</p>
        </div>

        <div class="detail-block">
          <h3>行为时间线</h3>
          <ol class="timeline">
            <li v-for="(item, index) in active.recent_activity.slice().reverse().slice(0, 10)" :key="index">
              <span class="timeline-at">{{ item.at }}</span>
              <strong>{{ eventLabel(item.event) }}</strong>
              <span class="timeline-detail">
                {{ [item.username, item.tool_name, item.path, item.reason].filter(Boolean).join(' · ') }}
              </span>
            </li>
          </ol>
        </div>
      </div>
    </section>

    <section v-if="evidence.length" class="section-block panel">
      <div class="section-heading">
        <div><h2>证据链</h2><p>追加写入本机，不可原地改写。以下为最近记录。</p></div>
        <n-tag v-if="summary?.evidence_path" size="small" :bordered="false">{{ summary.evidence_path }}</n-tag>
      </div>
      <ol class="evidence-list">
        <li v-for="(item, index) in evidence" :key="index">
          <n-tag size="small" :type="severityType(item.severity)" :bordered="false">{{ severityLabel(item.severity) }}</n-tag>
          <span class="evidence-at">{{ item.at }}</span>
          <strong>{{ eventLabel(item.event) }}</strong>
          <span class="evidence-source">{{ item.dossier?.source }}</span>
          <span class="evidence-class">{{ classificationLabel(item.classification) }}</span>
        </li>
      </ol>
    </section>
  </n-spin>
</template>

<style scoped>
.posture-strip { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.dossier-layout { display: grid; grid-template-columns: minmax(0, 260px) minmax(0, 1fr); gap: 16px; align-items: start; }
.source-list { display: grid; gap: 8px; align-content: start; }
.source-row {
  display: grid;
  gap: 5px;
  width: 100%;
  padding: 11px 12px;
  border: 1px solid #26313c;
  border-radius: 7px;
  background: #0f151c;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.source-row:hover { border-color: #2bc4d966; }
.source-row.active { border-color: #2bc4d9; background: #10222a; }
.source-row-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.source-row-head strong { font-size: 13px; overflow-wrap: anywhere; }
.source-row span { color: #7e8d98; font-size: 11px; }
.source-flag { color: #f2bd5b; font-size: 11px; }
.dossier { min-width: 0; }
.fact { padding: 12px; border: 1px solid #26313c; border-radius: 7px; background: #0f151c; }
.fact span { display: block; color: #7b8894; font-size: 11px; }
.fact strong { display: block; margin-top: 5px; font-size: 13px; overflow-wrap: anywhere; }
.detail-block { margin-top: 18px; }
.detail-block h3 { margin: 0 0 9px; font-size: 13px; }
.detail-block h3 small { margin-left: 8px; color: #6e7b87; font-size: 11px; font-weight: 400; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip-row code { padding: 3px 7px; border: 1px solid #2a3642; border-radius: 5px; background: #090d11; color: #c9d5da; font-size: 11px; }
.muted { color: #6e7b87; font-size: 12px; }
.agent-line { margin: 8px 0 0; color: #7e8d98; font-size: 11px; line-height: 1.6; overflow-wrap: anywhere; }
.timeline { margin: 0; padding: 0; list-style: none; display: grid; gap: 7px; }
.timeline li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; padding-bottom: 7px; border-bottom: 1px solid #1e2731; font-size: 12px; }
.timeline li:last-child { border-bottom: 0; }
.timeline-at { color: #6e7b87; font-size: 11px; font-variant-numeric: tabular-nums; }
.timeline-detail { color: #7e8d98; font-size: 11px; overflow-wrap: anywhere; }
.evidence-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.evidence-list li { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; padding-bottom: 8px; border-bottom: 1px solid #1e2731; font-size: 12px; }
.evidence-list li:last-child { border-bottom: 0; }
.evidence-at { color: #6e7b87; font-size: 11px; font-variant-numeric: tabular-nums; }
.evidence-source { color: #9fb0bb; }
.evidence-class { color: #7e8d98; font-size: 11px; }
@media (max-width: 960px) {
  .dossier-layout { grid-template-columns: 1fr; }
}
</style>
