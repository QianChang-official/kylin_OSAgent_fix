<script setup lang="ts">
import { NEmpty, NTag } from 'naive-ui'
import type { ToolPlanItem } from '@/types/api'
import { toolLabel, toolPurpose } from '@/utils/presentation'

defineProps<{ plans: ToolPlanItem[] }>()

function statusLabel(status: unknown): string {
  const key = String(status || '').toLowerCase()
  if (key === 'success') return '已完成'
  if (key === 'failed') return '执行失败'
  if (key === 'blocked') return '已阻断'
  if (key === 'pending') return '待执行'
  if (key === 'capability_missing') return '环境受限'
  if (key === 'command_failed') return '检查失败'
  if (key === 'parse_warning') return '部分可用'
  if (key === 'no_output') return '暂无结果'
  return key || '已规划'
}

function statusType(status: unknown): 'success' | 'warning' | 'error' | 'info' {
  const key = String(status || '').toLowerCase()
  if (key === 'success') return 'success'
  if (key === 'failed' || key === 'blocked' || key === 'command_failed') return 'error'
  if (key === 'pending' || key === 'capability_missing' || key === 'parse_warning') return 'warning'
  return 'info'
}

function hasArguments(argumentsValue: Record<string, unknown> | undefined): boolean {
  return Boolean(argumentsValue && Object.keys(argumentsValue).length)
}
</script>

<template>
  <div v-if="plans.length" class="tool-plan-grid">
    <article v-for="(plan, index) in plans" :key="`${plan.tool_name}-${index}`" class="tool-plan-card">
      <div class="tool-plan-index">{{ String(index + 1).padStart(2, '0') }}</div>
      <div class="tool-plan-main">
        <div class="tool-plan-title">
          <strong>{{ toolLabel(plan.tool_name) }}</strong>
          <n-tag size="small" :type="statusType(plan.status)" :bordered="false">{{ statusLabel(plan.status) }}</n-tag>
          <n-tag size="small" :bordered="false">只读工具</n-tag>
        </div>
        <p>{{ toolPurpose(plan.tool_name) }}</p>
        <details class="tool-plan-details">
          <summary>查看技术详情</summary>
          <code>{{ plan.tool_name }}</code>
          <p v-if="plan.reason">规划依据：{{ plan.reason }}</p>
          <code v-if="hasArguments(plan.arguments)">参数：{{ JSON.stringify(plan.arguments) }}</code>
        </details>
      </div>
    </article>
  </div>
  <n-empty v-else description="本次请求没有生成可执行工具计划" />
</template>

<style scoped>
.tool-plan-details { margin-top: 8px; color: #97887a; font-size: 11px; }
.tool-plan-details summary { color: #97887a; cursor: pointer; }
.tool-plan-details code { display: block; margin-top: 7px; color: #b0a28e; overflow-wrap: anywhere; }
.tool-plan-details p { min-height: 0; margin: 7px 0 0; color: #a89a86; }
</style>
