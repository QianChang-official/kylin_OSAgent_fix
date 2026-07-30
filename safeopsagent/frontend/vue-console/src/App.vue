<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NConfigProvider,
  NGlobalStyle,
  NIcon,
  NMessageProvider,
  NSpin,
  NTag,
  NTooltip,
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
  Logout,
  Crosshair,
  ShieldCheck,
  Tool,
  UserCircle,
} from '@vicons/tabler'
import { api } from '@/api/client'
import { authState, authenticationEnabled, signOut } from '@/auth/session'
import type { AgentStatus } from '@/types/api'
import { modeLabel } from '@/utils/presentation'

const route = useRoute()
const router = useRouter()
const status = ref<AgentStatus | null>(null)
const statusError = ref('')
const logoutPending = ref(false)
const logoutError = ref('')

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
  { path: '/attribution', title: '溯源画像', desc: '前门欺骗取证', icon: Crosshair },
]

const currentTitle = computed(() => navItems.find((item) => item.path === route.path)?.title || '控制台')
const isLoginRoute = computed(() => route.name === 'login')
const authEnabled = computed(() => authenticationEnabled(authState.session))
const username = computed(() => authState.session?.username || '已认证用户')
const canLoadStatus = computed(() => (
  authState.initialized
  && !isLoginRoute.value
  && Boolean(authState.session)
  && (!authEnabled.value || Boolean(authState.session?.authenticated))
))
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

async function logout() {
  logoutPending.value = true
  logoutError.value = ''
  try {
    await signOut()
    status.value = null
    if (!authEnabled.value) await router.replace({ name: 'login' })
  } catch (error) {
    logoutError.value = error instanceof Error ? error.message : '退出登录失败。'
  } finally {
    logoutPending.value = false
  }
}

watch(canLoadStatus, (allowed) => {
  if (allowed && !status.value) void loadStatus()
}, { immediate: true })

watch(
  () => authState.session?.authenticated,
  (authenticated) => {
    if (authEnabled.value && authenticated === false && !isLoginRoute.value) {
      void router.replace({ name: 'login', query: { redirect: route.fullPath } })
    }
  },
)
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-global-style />
      <router-view v-if="isLoginRoute" />

      <div v-else-if="!authState.initialized" class="auth-bootstrap">
        <n-spin size="large"><span>正在验证控制台会话</span></n-spin>
      </div>

      <div v-else class="app-shell">
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
              <div v-if="authEnabled && authState.session?.authenticated" class="auth-controls">
                <div class="session-chip">
                  <n-icon :component="UserCircle" :size="18" />
                  <span>{{ username }}</span>
                </div>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <n-button
                      quaternary
                      circle
                      aria-label="退出登录"
                      :loading="logoutPending"
                      @click="logout"
                    >
                      <template #icon><n-icon :component="Logout" /></template>
                    </n-button>
                  </template>
                  退出登录
                </n-tooltip>
              </div>
              <span v-if="logoutError" class="logout-error">{{ logoutError }}</span>
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

<style scoped>
.auth-bootstrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: #82909d;
  background: #0b0f14;
}

.auth-bootstrap span { display: block; margin-top: 12px; font-size: 12px; }
.auth-controls { display: flex; align-items: center; gap: 5px; }
.session-chip {
  max-width: 180px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  color: #9cabb5;
  font-size: 11px;
}
.session-chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.logout-error { max-width: 160px; color: #f58c92; font-size: 10px; line-height: 1.35; }

@media (max-width: 1100px) {
  .session-chip { display: none; }
  .logout-error { display: none; }
}
</style>
