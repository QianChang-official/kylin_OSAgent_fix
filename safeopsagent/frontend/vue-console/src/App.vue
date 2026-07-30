<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import {
  NConfigProvider,
  NGlobalStyle,
  NIcon,
  NMessageProvider,
  NTag,
  darkTheme,
  type GlobalThemeOverrides,
} from 'naive-ui'
import {
  Activity,
  Bulb,
  ChevronRight,
  LayoutGrid,
  ChartLine,
  ListDetails,
  Lock,
  ShieldCheck,
  Tool,
} from '@vicons/tabler'
import { api } from '@/api/client'
import type { AgentStatus } from '@/types/api'
import { modeLabel } from '@/utils/presentation'

const route = useRoute()
const status = ref<AgentStatus | null>(null)
const statusError = ref('')

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2bc4d9',
    primaryColorHover: '#54d1df',
    primaryColorPressed: '#1f9caf',
    borderRadius: '6px',
    bodyColor: '#0b0f14',
    cardColor: '#111820',
    textColorBase: '#edf5f7',
  },
}

const navItems = [
  { path: '/', title: '工作台', desc: '运行状态', icon: LayoutGrid },
  { path: '/monitor', title: '监控大盘', desc: '自学习基线', icon: ChartLine },
  { path: '/diagnosis', title: '智能诊断', desc: '自然语言运维', icon: Bulb },
  { path: '/security', title: '安全中心', desc: '危险请求验证', icon: ShieldCheck },
  { path: '/tools', title: '工具能力', desc: '受控只读工具', icon: Tool },
  { path: '/audit', title: '审计追踪', desc: '证据链回放', icon: ListDetails },
]

const currentTitle = computed(() => navItems.find((item) => item.path === route.path)?.title || '控制台')
const online = computed(() => Boolean(status.value) && !statusError.value)
const modelText = computed(() => {
  if (!status.value) return '模式待确认'
  return status.value.agent_mode === 'model_api'
    ? `${status.value.model_vendor} · ${status.value.model_name}`
    : '内置安全规划器'
})

async function loadStatus() {
  try {
    status.value = await api.agentStatus()
    statusError.value = ''
  } catch (error) {
    statusError.value = error instanceof Error ? error.message : '状态不可用'
  }
}

onMounted(loadStatus)
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-global-style />
      <div class="app-shell">
        <aside class="sidebar">
          <div class="brand-block">
            <div class="brand-mark"><n-icon :component="Lock" :size="22" /></div>
            <div>
              <strong>SafeOpsAgent</strong>
              <span>安全智能运维控制台</span>
            </div>
          </div>

          <nav class="primary-nav">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              class="nav-item"
              :class="{ active: route.path === item.path }"
            >
              <n-icon :component="item.icon" :size="18" />
              <span class="nav-copy"><strong>{{ item.title }}</strong><small>{{ item.desc }}</small></span>
              <n-icon class="nav-arrow" :component="ChevronRight" :size="14" />
            </router-link>
          </nav>

          <div class="sidebar-security">
            <div class="sidebar-security-title"><n-icon :component="ShieldCheck" /> 安全边界</div>
            <p>模型只负责理解与规划，系统命令必须经过工具白名单、风险评分和最小权限执行器。</p>
            <div class="security-mini-row"><span>工具权限</span><strong>只读为主</strong></div>
            <div class="security-mini-row"><span>审计追踪</span><strong>已启用</strong></div>
          </div>
        </aside>

        <main class="workspace">
          <header class="topbar">
            <div>
              <p class="topbar-context">面向银河麒麟操作系统的安全智能运维 Agent</p>
              <strong>{{ currentTitle }}</strong>
            </div>
            <div class="topbar-status">
              <n-tag :type="online ? 'success' : 'error'" :bordered="false">
                <span class="status-dot" />{{ online ? '后端在线' : '后端离线' }}
              </n-tag>
              <div class="mode-chip">
                <n-icon :component="Activity" />
                <span>{{ status ? modeLabel(status.agent_mode) : '模式待确认' }}</span>
                <small>{{ modelText }}</small>
              </div>
            </div>
          </header>

          <div class="page-container">
            <router-view />
          </div>
        </main>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>
