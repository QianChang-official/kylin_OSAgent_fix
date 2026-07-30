<script setup lang="ts">
import { NEmpty, NTag } from 'naive-ui'
import type { TimelineItem } from '@/types/api'

defineProps<{ items?: TimelineItem[] }>()

function statusType(status: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  const key = String(status || '').toLowerCase()
  if (key === 'success' || key === 'completed') return 'success'
  if (key === 'warning' || key === 'skipped') return 'warning'
  if (key === 'error' || key === 'failed' || key === 'blocked') return 'error'
  return 'info'
}
</script>

<template>
  <div v-if="items?.length" class="trace-timeline">
    <div v-for="(item, index) in items" :key="`${item.title}-${index}`" class="trace-item">
      <div class="trace-rail">
        <span class="trace-dot" :class="`trace-${statusType(item.status)}`" />
        <span v-if="index < items.length - 1" class="trace-line" />
      </div>
      <div class="trace-content">
        <div class="trace-title-row">
          <strong>{{ item.title }}</strong>
          <n-tag size="small" :type="statusType(item.status)" :bordered="false">{{ item.status || '已记录' }}</n-tag>
        </div>
        <p>{{ item.description || '该阶段未返回更多说明。' }}</p>
      </div>
    </div>
  </div>
  <n-empty v-else description="暂无可展示的审计时间线" />
</template>
