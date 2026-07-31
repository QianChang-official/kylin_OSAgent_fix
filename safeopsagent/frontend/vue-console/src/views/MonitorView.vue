<script setup lang="ts">
/**
 * Monitoring dashboard.
 *
 * The point of this view is not "a panel with graphs" — it is that every
 * threshold shown here was learned from this host's own history rather
 * than hard-coded. Each tile therefore shows the learned normal band
 * behind the trend, and every alert states what the baseline was.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NButton, NIcon, NSpin, NTag, useMessage } from 'naive-ui'
import {
  AlertTriangle,
  CircleCheck,
  Refresh,
  Server,
  WaveSine,
} from '@vicons/tabler'
import PageHeader from '@/components/PageHeader.vue'
import MetricSparkline from '@/components/MetricSparkline.vue'
import { api } from '@/api/client'
import type { MetricAnomaly, MonitorMetrics, MonitorOverview } from '@/types/api'

const overview = ref<MonitorOverview | null>(null)
const metrics = ref<MonitorMetrics | null>(null)
const anomalies = ref<MetricAnomaly[]>([])
const loading = ref(false)
const errorText = ref('')
const message = useMessage()
let timer: number | undefined

const anomalyByMetric = computed(() => {
  const map = new Map<string, MetricAnomaly>()
  anomalies.value.forEach((item) => map.set(item.metric, item))
  return map
})

const orderedMetrics = computed(() => {
  if (!metrics.value) return []
  return metrics.value.tracked
    .map((key) => ({ key, series: metrics.value?.metrics[key] }))
    .filter((item) => item.series) as { key: string; series: NonNullable<MonitorMetrics['metrics'][string]> }[]
})

const healthMeta = computed(() => {
  const health = overview.value?.health
  if (health === 'critical') return { label: '存在严重偏离', type: 'error' as const, icon: AlertTriangle }
  if (health === 'warning') return { label: '存在基线偏离', type: 'warning' as const, icon: AlertTriangle }
  return { label: '各项指标处于学习基线内', type: 'success' as const, icon: CircleCheck }
})

const uptimeText = computed(() => {
  const seconds = overview.value?.host.uptime_seconds
  if (!seconds) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  return days > 0 ? `${days} 天 ${hours} 小时` : `${hours} 小时`
})

async function loadAll(showToast = false) {
  loading.value = true
  try {
    const [nextOverview, nextMetrics, nextAnomalies] = await Promise.all([
      api.monitorOverview(),
      api.monitorMetrics(),
      api.monitorAnomalies(),
    ])
    overview.value = nextOverview
    metrics.value = nextMetrics
    anomalies.value = nextAnomalies
    errorText.value = ''
    if (showToast) message.success('监控数据已刷新')
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '监控数据不可用'
  } finally {
    loading.value = false
  }
}

async function sampleNow() {
  try {
    await api.monitorSample()
    await loadAll()
    message.success('已采集一次样本')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '采样失败')
  }
}

function severityTag(severity: string) {
  return severity === 'critical' ? 'error' : 'warning'
}

function triggerLabel(triggeredBy: string[]): string {
  const labels: Record<string, string> = {
    baseline_deviation: '偏离学习基线',
    absolute_ceiling: '超过绝对告警线',
  }
  return triggeredBy.map((item) => labels[item] || item).join(' · ')
}

onMounted(() => {
  loadAll()
  timer = window.setInterval(() => loadAll(), 15_000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="page">
    <PageHeader
      title="监控大盘"
      description="指标趋势与异常判定。告警阈值由本机历史自学习得出，而不是固定阈值。"
    />

    <n-spin :show="loading && !overview">
      <p v-if="errorText" class="error-text">{{ errorText }}</p>

      <!-- Host + health summary. Facts, not a chart. -->
      <article v-if="overview" class="host-card">
        <div class="host-main">
          <div class="host-icon"><n-icon :component="Server" :size="20" /></div>
          <div class="host-copy">
            <strong>{{ overview.host.hostname || '本机' }}</strong>
            <span>
              {{ overview.host.os_release || `${overview.host.system} ${overview.host.release}` }}
              · {{ overview.host.machine }}
              · {{ overview.host.logical_cores ?? '—' }} 核
            </span>
          </div>
        </div>
        <div class="host-stats">
          <div class="host-stat"><small>运行时长</small><strong>{{ uptimeText }}</strong></div>
          <div class="host-stat"><small>累计样本</small><strong>{{ overview.sample_count }}</strong></div>
          <div class="host-stat"><small>采样间隔</small><strong>{{ overview.sample_interval_seconds }}s</strong></div>
          <div class="host-stat"><small>采样器</small><strong>{{ overview.sampler_running ? '运行中' : '未启动' }}</strong></div>
        </div>
        <div class="host-actions">
          <!-- Status color always ships with an icon + label, never color alone. -->
          <n-tag :type="healthMeta.type" :bordered="false" size="large">
            <template #icon><n-icon :component="healthMeta.icon" /></template>
            {{ healthMeta.label }}
          </n-tag>
          <n-button size="small" secondary @click="sampleNow">
            <template #icon><n-icon :component="WaveSine" /></template>
            立即采样
          </n-button>
          <n-button size="small" quaternary @click="loadAll(true)">
            <template #icon><n-icon :component="Refresh" /></template>
            刷新
          </n-button>
        </div>
      </article>

      <!-- Stat tiles: label · value · trend, one series each (no legend needed). -->
      <div class="metric-grid">
        <article
          v-for="item in orderedMetrics"
          :key="item.key"
          class="metric-tile"
          :class="{ flagged: anomalyByMetric.has(item.key) }"
        >
          <header class="tile-head">
            <span class="tile-label">{{ item.series.label }}</span>
            <n-tag
              v-if="anomalyByMetric.has(item.key)"
              :type="severityTag(anomalyByMetric.get(item.key)!.severity)"
              :bordered="false"
              size="small"
            >
              <template #icon><n-icon :component="AlertTriangle" /></template>
              异常
            </n-tag>
            <n-tag v-else-if="!item.series.available" :bordered="false" size="small">
              本平台不适用
            </n-tag>
            <n-tag v-else-if="!item.series.baseline.learned" :bordered="false" size="small">
              学习中
            </n-tag>
          </header>

          <div class="tile-value">
            {{ item.series.latest ?? '—' }}<span class="tile-unit">{{ item.series.unit }}</span>
          </div>

          <div class="tile-baseline">
            <template v-if="item.series.baseline.learned">
              学习基线 {{ item.series.baseline.median }}{{ item.series.unit }}
              · 正常区间 {{ item.series.baseline.normal_lower }}–{{ item.series.baseline.normal_upper }}{{ item.series.unit }}
            </template>
            <template v-else-if="!item.series.available">
              当前平台不提供该指标（麒麟 / Linux 下正常采集）
            </template>
            <template v-else>
              样本 {{ item.series.baseline.sample_count }} 个，达到 12 个后形成基线
            </template>
          </div>

          <MetricSparkline
            :points="item.series.points"
            :unit="item.series.unit"
            :normal-lower="item.series.baseline.normal_lower"
            :normal-upper="item.series.baseline.normal_upper"
            :baseline-learned="item.series.baseline.learned"
            :anomalous="anomalyByMetric.has(item.key)"
          />
        </article>
      </div>

      <!-- Anomaly detail: a table, because each row carries several facts. -->
      <section class="section-block">
        <div class="section-heading">
          <div>
            <strong>基线偏离告警</strong>
            <span>每条告警都说明本机学习基线与当前偏离程度，可直接核对判定依据</span>
          </div>
          <n-tag :bordered="false" size="small">{{ anomalies.length }} 条</n-tag>
        </div>

        <p v-if="!anomalies.length" class="empty-hint">
          当前没有偏离本机学习基线的指标。基线由中位数与 MAD（中位绝对偏差）从历史样本学习得出，
          对离群值稳健，因此"长期高位"的主机不会被误判为异常。
        </p>

        <table v-else class="anomaly-table">
          <thead>
            <tr>
              <th>指标</th>
              <th>当前值</th>
              <th>学习基线</th>
              <th>偏离</th>
              <th>稳健 z</th>
              <th>触发条件</th>
              <th>判定说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in anomalies" :key="item.metric">
              <td>
                <n-tag :type="severityTag(item.severity)" :bordered="false" size="small">
                  <template #icon><n-icon :component="AlertTriangle" /></template>
                  {{ item.label }}
                </n-tag>
              </td>
              <td class="num">{{ item.value }}</td>
              <td class="num">{{ item.baseline_median }}</td>
              <td class="num">{{ item.deviation > 0 ? '+' : '' }}{{ item.deviation }}</td>
              <td class="num">{{ item.z_score ?? '—' }}</td>
              <td>{{ triggerLabel(item.triggered_by) }}</td>
              <td class="explain">{{ item.explanation }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </n-spin>
  </section>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; }
.error-text { margin: 0 0 12px; color: #f06b73; font-size: 12px; }

.host-card {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 16px; padding: 18px; border: 1px solid #3e2e1e; border-radius: 8px; background: #231810;
}
.host-main { display: flex; align-items: center; gap: 12px; min-width: 240px; }
.host-icon {
  display: grid; place-items: center; width: 40px; height: 40px;
  border-radius: 8px; background: #2b1f0e; color: #eacd76;
}
.host-copy strong { display: block; font-size: 15px; }
.host-copy span { display: block; margin-top: 3px; color: #97887a; font-size: 11px; }

.host-stats { display: flex; flex-wrap: wrap; gap: 22px; }
.host-stat small { display: block; color: #97887a; font-size: 10px; }
.host-stat strong { display: block; margin-top: 3px; font-size: 13px; font-variant-numeric: tabular-nums; }

.host-actions { display: flex; align-items: center; gap: 8px; }

.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.metric-tile {
  padding: 16px; border: 1px solid #3e2e1e; border-radius: 8px; background: #231810;
  transition: border-color .16s;
}
.metric-tile.flagged { border-color: #d03b3b66; }

.tile-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.tile-label { color: #c9bca8; font-size: 12px; }

/* Proportional figures for a large standalone value, not tabular-nums. */
.tile-value { margin: 10px 0 2px; font-size: 27px; font-weight: 600; line-height: 1; }
.tile-unit { margin-left: 3px; font-size: 14px; font-weight: 400; color: #97887a; }

.tile-baseline { margin-bottom: 10px; min-height: 28px; color: #97887a; font-size: 10px; line-height: 1.5; }

.section-block { padding: 18px; border: 1px solid #3e2e1e; border-radius: 8px; background: #231810; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.section-heading strong { display: block; font-size: 14px; }
.section-heading span { display: block; margin-top: 4px; color: #97887a; font-size: 11px; }

.empty-hint { margin: 0; color: #97887a; font-size: 12px; line-height: 1.7; }

.anomaly-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.anomaly-table th {
  padding: 8px 10px; border-bottom: 1px solid #3e2e1e;
  color: #97887a; font-weight: 400; font-size: 11px; text-align: left; white-space: nowrap;
}
.anomaly-table td { padding: 10px; border-bottom: 1px solid #2e2115; vertical-align: top; }
.anomaly-table tr:last-child td { border-bottom: 0; }
.anomaly-table .num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.anomaly-table .explain { color: #c9bca8; line-height: 1.6; min-width: 260px; }
</style>
