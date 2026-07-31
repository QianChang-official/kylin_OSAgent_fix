<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NEmpty, NIcon, NSpin, NTag } from 'naive-ui'
import { Activity, Bulb, Database, GitFork, HeartRateMonitor, Refresh, ShieldCheck, Tool } from '@vicons/tabler'
import { api } from '@/api/client'
import type { AgentStatus, AuditLog, HealthResponse, SystemProbe } from '@/types/api'
import { decisionLabel, decisionType, formatTime, modeLabel } from '@/utils/presentation'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const status = ref<AgentStatus | null>(null)
const health = ref<HealthResponse | null>(null)
const probe = ref<SystemProbe | null>(null)
const logs = ref<AuditLog[]>([])

const modelDisplay = computed(() => {
  if (!status.value) return '状态未返回'
  return status.value.agent_mode === 'model_api'
    ? `${status.value.model_vendor} · ${status.value.model_name}`
    : '内置安全规划器'
})

const chain = [
  ['01', '自然语言请求', '接收运维意图，不直接解释为命令'],
  ['02', '本地安全预检', '危险命令与提示词注入优先拦截'],
  ['03', '模型意图理解', '模型只负责理解与规划'],
  ['04', '工具规划', '最多选择受控只读工具'],
  ['05', '白名单校验', '验证工具身份与参数范围'],
  ['06', '最小权限执行', '统一进入 SafeExecutor'],
  ['07', '审计追踪', 'request_id 回放完整证据链'],
]

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [statusValue, healthValue, probeValue, logValue] = await Promise.all([
      api.agentStatus(),
      api.health(),
      api.systemProbe(),
      api.auditLogs(5),
    ])
    status.value = statusValue
    health.value = healthValue
    probe.value = probeValue
    logs.value = logValue
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '工作台数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <!-- 长城主题横幅：金色日出影像 + 玄色罩面，呼应「中国红 × 金漆」主题 -->
  <section class="page-hero" style="background-image: url('/console/images/greatwall-2.jpg'); background-position: center 42%;">
    <div class="page-hero-inner">
      <p class="eyebrow">Operations workspace</p>
      <h1 class="page-hero-title">安全智能运维工作台</h1>
      <p class="page-hero-desc">统一查看 Agent、模型规划、安全护栏、受控工具和审计链路的真实运行状态。长城为屏、金漆为饰，守护银河麒麟主机的每一次运维决策。</p>
      <div class="page-hero-actions">
        <n-button type="primary" @click="router.push({ path: '/diagnosis' })">
          <template #icon><n-icon :component="Bulb" /></template>发起智能诊断
        </n-button>
        <n-button secondary :loading="loading" @click="load">
          <template #icon><n-icon :component="Refresh" /></template>刷新状态
        </n-button>
      </div>
    </div>
  </section>

  <n-alert v-if="error" type="error" title="工作台暂时无法连接后端" :bordered="false">{{ error }}</n-alert>
  <n-spin :show="loading">
    <div class="grid-4">
      <article class="metric-card">
        <div class="metric-card-header"><span>Agent 状态</span><n-icon class="metric-icon" :component="Activity" :size="19" /></div>
        <div class="metric-value">{{ health?.status === 'ok' ? '在线' : '未连接' }}</div>
        <div class="metric-caption">{{ health ? `${health.agent} 后端服务响应正常` : '等待后端返回健康状态' }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-card-header"><span>智能规划模式</span><n-icon class="metric-icon" :component="GitFork" :size="19" /></div>
        <div class="metric-value">{{ status ? modeLabel(status.agent_mode) : '待获取' }}</div>
        <div class="metric-caption">{{ modelDisplay }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-card-header"><span>受控工具</span><n-icon class="metric-icon" :component="Tool" :size="19" /></div>
        <div class="metric-value">{{ status?.tools_count ?? '—' }}</div>
        <div class="metric-caption">{{ status ? `${status.readonly_tools_count} 个只读工具纳入白名单` : '工具清单尚未返回' }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-card-header"><span>安全与审计</span><n-icon class="metric-icon" :component="ShieldCheck" :size="19" /></div>
        <div class="metric-value">{{ status?.guardrail_enabled && status?.audit_enabled ? '已启用' : '待确认' }}</div>
        <div class="metric-caption">风险评分、危险阻断与审计追踪协同工作</div>
      </article>
    </div>

    <section class="section-block">
      <div class="section-heading">
        <div><h2>安全执行链路</h2><p>模型不能直接触达系统命令，每一层都有明确职责。</p></div>
      </div>
      <div class="security-chain">
        <article v-for="node in chain" :key="node[0]" class="chain-node">
          <span class="chain-index">{{ node[0] }}</span><strong>{{ node[1] }}</strong><p>{{ node[2] }}</p>
        </article>
      </div>
    </section>

    <section class="section-block grid-2">
      <div class="panel">
        <div class="section-heading">
          <div><h2>运行环境</h2><p>信息来自当前后端系统探测。</p></div>
          <n-icon :component="HeartRateMonitor" :size="22" />
        </div>
        <div v-if="probe" class="data-list">
          <div class="data-row"><span>操作系统</span><strong>{{ probe.os_release || '未识别' }}</strong></div>
          <div class="data-row"><span>内核</span><strong>{{ probe.kernel || '未识别' }}</strong></div>
          <div class="data-row"><span>Python</span><strong>{{ probe.python_version || '未识别' }}</strong></div>
          <div class="data-row"><span>可用命令</span><strong>{{ probe.available_commands.length ? probe.available_commands.join(' · ') : '暂无可用命令' }}</strong></div>
          <div class="data-row"><span>缺失命令</span><strong>{{ probe.missing_commands.length ? probe.missing_commands.join(' · ') : '未发现缺失项' }}</strong></div>
        </div>
        <n-empty v-else description="环境信息尚未返回" />
        <n-alert v-if="probe?.missing_commands?.length" class="environment-note" type="warning" :bordered="false" title="当前环境能力不完整">
          部分 Linux / 银河麒麟命令不可用时，工具会返回环境能力受限，不代表 Agent 或安全链路故障。
        </n-alert>
      </div>

      <div class="panel">
        <div class="section-heading">
          <div><h2>最近安全事件</h2><p>展示真实审计记录，不生成虚拟指标。</p></div>
          <n-icon :component="Database" :size="22" />
        </div>
        <div v-if="logs.length" class="data-list">
          <button v-for="log in logs" :key="log.request_id" class="event-row" @click="router.push({ path: '/audit', query: { request_id: log.request_id } })">
            <span><strong>{{ log.user_input || '受控工具调用' }}</strong><small>{{ formatTime(log.created_at) }}</small></span>
            <n-tag size="small" :type="decisionType(log.security_decision)" :bordered="false">{{ decisionLabel(log.security_decision) }}</n-tag>
          </button>
        </div>
        <n-empty v-else description="暂无审计记录" />
        <n-button class="wide-action" secondary @click="router.push('/audit')">进入审计追踪</n-button>
      </div>
    </section>

    <section class="section-block">
      <div class="section-heading">
        <div><h2>快速开始</h2><p>从真实运维请求、安全验证或工具调用进入。</p></div>
      </div>
      <div class="grid-3">
        <button class="quick-action" @click="router.push({ path: '/diagnosis', query: { prompt: 'check memory status' } })">
          <strong>开始智能诊断</strong><span>让 Agent 规划只读检查工具</span>
        </button>
        <button class="quick-action danger" @click="router.push('/security')">
          <strong>验证危险阻断</strong><span>确认高风险请求不会被执行</span>
        </button>
        <button class="quick-action" @click="router.push('/tools')">
          <strong>调用受控工具</strong><span>直接使用工具白名单能力</span>
        </button>
      </div>
    </section>
  </n-spin>
</template>

<style scoped>
.event-row, .quick-action { width: 100%; border: 0; color: inherit; text-align: left; cursor: pointer; }
.event-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid #2e2115; background: transparent; }
.event-row:last-child { border-bottom: 0; }
.event-row:hover strong { color: #eacd76; }
.event-row span { min-width: 0; }
.event-row strong, .event-row small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color .16s ease; }
.event-row strong { max-width: 380px; font-size: 12px; }
.event-row small { margin-top: 4px; color: #97887a; font-size: 10px; }
.wide-action { width: 100%; margin-top: 14px; }
.quick-action { position: relative; min-height: 98px; padding: 17px; border: 1px solid #3e2e1e; border-radius: 8px; background: #231810; transition: border-color .16s, background .16s, transform .16s; }
.quick-action:hover { border-color: #b08d3e88; background: #2c1f14; transform: translateY(-2px); }
.quick-action.danger:hover { border-color: #d12c2577; background: #2b1410; }
.quick-action strong, .quick-action span { display: block; }
.quick-action strong { font-size: 13px; }
.quick-action span { margin-top: 7px; color: #97887a; font-size: 12px; }
</style>
