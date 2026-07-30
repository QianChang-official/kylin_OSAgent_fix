<script setup lang="ts">
/**
 * Single-series metric sparkline with the learned baseline band behind it.
 *
 * Form: stat-tile trend (choosing-a-form → "a single current value + trend").
 * One series, so no legend — the tile title names what is plotted.
 *
 * Marks follow the fixed specs: 2px line with round join/cap, r=4 end marker
 * carrying a 2px surface ring, band fill at ~10% opacity, hairline gridline.
 * The only direct label is the endpoint, which the tile header already shows,
 * so the plot itself stays free of numbers.
 *
 * Series hue #3987e5 was validated against this console's dark surface
 * (#111820): passes lightness band, chroma floor and 3:1 contrast.
 */
import { computed, ref } from 'vue'

interface Point {
  ts: number
  value: number
}

const props = withDefaults(defineProps<{
  points: Point[]
  unit?: string
  normalLower?: number | null
  normalUpper?: number | null
  baselineLearned?: boolean
  anomalous?: boolean
}>(), {
  unit: '',
  normalLower: null,
  normalUpper: null,
  baselineLearned: false,
  anomalous: false,
})

const WIDTH = 280
const HEIGHT = 64
const PAD_X = 3
const PAD_Y = 6

const hover = ref<number | null>(null)

const bounds = computed(() => {
  const values = props.points.map((item) => item.value)
  const candidates = [...values]
  if (props.baselineLearned && props.normalLower != null) candidates.push(props.normalLower)
  if (props.baselineLearned && props.normalUpper != null) candidates.push(props.normalUpper)
  if (!candidates.length) return { min: 0, max: 1 }
  let min = Math.min(...candidates)
  let max = Math.max(...candidates)
  if (max - min < 1e-6) {
    min -= 1
    max += 1
  }
  const headroom = (max - min) * 0.12
  return { min: min - headroom, max: max + headroom }
})

function x(index: number): number {
  const count = props.points.length
  if (count <= 1) return PAD_X
  return PAD_X + (index / (count - 1)) * (WIDTH - PAD_X * 2)
}

function y(value: number): number {
  const { min, max } = bounds.value
  const ratio = (value - min) / (max - min)
  return HEIGHT - PAD_Y - ratio * (HEIGHT - PAD_Y * 2)
}

const linePath = computed(() => {
  if (!props.points.length) return ''
  return props.points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${x(index).toFixed(2)},${y(point.value).toFixed(2)}`)
    .join(' ')
})

const bandRect = computed(() => {
  if (!props.baselineLearned || props.normalLower == null || props.normalUpper == null) return null
  const top = y(props.normalUpper)
  const bottom = y(props.normalLower)
  return {
    y: Math.max(0, Math.min(top, bottom)),
    height: Math.max(1, Math.abs(bottom - top)),
  }
})

const lastPoint = computed(() => {
  if (!props.points.length) return null
  const index = props.points.length - 1
  return { cx: x(index), cy: y(props.points[index].value) }
})

const activeIndex = computed(() => hover.value)
const activePoint = computed(() => {
  const index = activeIndex.value
  if (index == null || !props.points[index]) return null
  return {
    cx: x(index),
    cy: y(props.points[index].value),
    value: props.points[index].value,
    ts: props.points[index].ts,
  }
})

/** Points outside the learned band — the reason this metric is flagged. */
const outliers = computed(() => {
  if (!props.baselineLearned || props.normalLower == null || props.normalUpper == null) return []
  return props.points
    .map((point, index) => ({ point, index }))
    .filter(({ point }) => point.value < (props.normalLower as number) || point.value > (props.normalUpper as number))
    .map(({ point, index }) => ({ cx: x(index), cy: y(point.value) }))
})

function onMove(event: MouseEvent) {
  const target = event.currentTarget as SVGSVGElement
  const rect = target.getBoundingClientRect()
  const ratio = (event.clientX - rect.left) / rect.width
  const count = props.points.length
  if (count === 0) return
  hover.value = Math.max(0, Math.min(count - 1, Math.round(ratio * (count - 1))))
}

function formatTime(ts: number): string {
  const date = new Date(ts * 1000)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

const tooltipStyle = computed(() => {
  const point = activePoint.value
  if (!point) return {}
  const left = (point.cx / WIDTH) * 100
  return { left: `${Math.max(6, Math.min(94, left))}%` }
})
</script>

<template>
  <div class="sparkline-wrap">
    <svg
      class="sparkline"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      preserveAspectRatio="none"
      role="img"
      :aria-label="`趋势曲线，共 ${points.length} 个采样点`"
      @mousemove="onMove"
      @mouseleave="hover = null"
    >
      <!-- learned normal band: the whole point of the baseline engine -->
      <rect
        v-if="bandRect"
        class="band"
        :x="0"
        :y="bandRect.y"
        :width="WIDTH"
        :height="bandRect.height"
      />
      <line v-if="bandRect" class="band-edge" :x1="0" :x2="WIDTH" :y1="bandRect.y" :y2="bandRect.y" />
      <line
        v-if="bandRect"
        class="band-edge"
        :x1="0"
        :x2="WIDTH"
        :y1="bandRect.y + bandRect.height"
        :y2="bandRect.y + bandRect.height"
      />

      <path v-if="linePath" class="line" :d="linePath" />

      <!-- samples that fall outside the learned band -->
      <circle
        v-for="(item, index) in outliers"
        :key="`out-${index}`"
        class="outlier"
        :cx="item.cx"
        :cy="item.cy"
        r="3.5"
      />

      <circle
        v-if="lastPoint"
        class="end-marker"
        :class="{ 'is-anomalous': anomalous }"
        :cx="lastPoint.cx"
        :cy="lastPoint.cy"
        r="4"
      />

      <g v-if="activePoint">
        <line class="crosshair" :x1="activePoint.cx" :x2="activePoint.cx" :y1="0" :y2="HEIGHT" />
        <circle class="hover-marker" :cx="activePoint.cx" :cy="activePoint.cy" r="4" />
      </g>
    </svg>

    <div v-if="activePoint" class="spark-tooltip" :style="tooltipStyle">
      <strong>{{ activePoint.value }}{{ unit }}</strong>
      <small>{{ formatTime(activePoint.ts) }}</small>
    </div>
    <p v-if="!points.length" class="spark-empty">暂无采样数据</p>
  </div>
</template>

<style scoped>
/* Chart roles. Series hue validated against surface #111820 (dark). */
.sparkline-wrap {
  --series-1: #3987e5;
  --status-critical: #d03b3b;
  --surface-1: #111820;
  --gridline: #33434f;
  position: relative;
}

.sparkline { display: block; width: 100%; height: 64px; overflow: visible; }

/* Area wash at ~10% opacity — a wash, never a saturated block. */
.band { fill: var(--series-1); opacity: 0.1; }
/* Hairline, solid, recessive. */
.band-edge { stroke: var(--gridline); stroke-width: 1; vector-effect: non-scaling-stroke; }

.line {
  fill: none;
  stroke: var(--series-1);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
  vector-effect: non-scaling-stroke;
}

/* Status color never travels alone — the tile pairs it with an icon + label. */
.outlier {
  fill: var(--status-critical);
  stroke: var(--surface-1);
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

/* End marker r=4 (>=8px) with a 2px surface ring. */
.end-marker {
  fill: var(--series-1);
  stroke: var(--surface-1);
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}
.end-marker.is-anomalous { fill: var(--status-critical); }

.crosshair { stroke: #47535e; stroke-width: 1; vector-effect: non-scaling-stroke; }
.hover-marker {
  fill: var(--series-1);
  stroke: var(--surface-1);
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

.spark-tooltip {
  position: absolute;
  top: -6px;
  transform: translateX(-50%);
  padding: 4px 8px;
  border: 1px solid #2b3945;
  border-radius: 5px;
  background: #0d141b;
  pointer-events: none;
  white-space: nowrap;
}
.spark-tooltip strong { font-size: 12px; color: #edf5f7; }
.spark-tooltip small { display: block; margin-top: 2px; font-size: 10px; color: #898781; }

.spark-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: #687682;
  font-size: 11px;
}
</style>
