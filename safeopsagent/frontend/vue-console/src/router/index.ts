import { createRouter, createWebHistory } from 'vue-router'
import { authState, authenticationEnabled, ensureAuthSession } from '@/auth/session'

function internalRedirect(value: unknown): string {
  return typeof value === 'string'
    && value.startsWith('/')
    && !value.startsWith('//')
    && !value.startsWith('/login')
    ? value
    : '/'
}

const router = createRouter({
  history: createWebHistory('/console/'),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '工作台', requiresAuth: true } },
    { path: '/monitor', name: 'monitor', component: () => import('@/views/MonitorView.vue'), meta: { title: '监控大盘', requiresAuth: true } },
    { path: '/diagnosis', name: 'diagnosis', component: () => import('@/views/DiagnosisView.vue'), meta: { title: '智能诊断', requiresAuth: true } },
    { path: '/security', name: 'security', component: () => import('@/views/SecurityView.vue'), meta: { title: '安全中心', requiresAuth: true } },
    { path: '/tools', name: 'tools', component: () => import('@/views/ToolsView.vue'), meta: { title: '工具能力', requiresAuth: true } },
    { path: '/audit', name: 'audit', component: () => import('@/views/AuditView.vue'), meta: { title: '审计追踪', requiresAuth: true } },
    { path: '/attribution', name: 'attribution', component: () => import('@/views/DeceptionView.vue'), meta: { title: '溯源画像', requiresAuth: true } },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { title: '登录' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  if (to.name === 'login' && authState.initialized && authState.error && !authState.session) {
    return true
  }

  try {
    const session = await ensureAuthSession()
    const loginRequired = authenticationEnabled(session)

    if (to.name === 'login') {
      if (!loginRequired || session.authenticated) return internalRedirect(to.query.redirect)
      return true
    }

    if (to.meta.requiresAuth && loginRequired && !session.authenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  } catch {
    if (to.name !== 'login' && to.meta.requiresAuth) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  return true
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '控制台')} · SafeOpsAgent`
})

export default router
