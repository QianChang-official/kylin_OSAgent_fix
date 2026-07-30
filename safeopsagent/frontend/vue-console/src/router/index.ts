import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory('/console/'),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '工作台' } },
    { path: '/monitor', name: 'monitor', component: () => import('@/views/MonitorView.vue'), meta: { title: '监控大盘' } },
    { path: '/diagnosis', name: 'diagnosis', component: () => import('@/views/DiagnosisView.vue'), meta: { title: '智能诊断' } },
    { path: '/security', name: 'security', component: () => import('@/views/SecurityView.vue'), meta: { title: '安全中心' } },
    { path: '/tools', name: 'tools', component: () => import('@/views/ToolsView.vue'), meta: { title: '工具能力' } },
    { path: '/audit', name: 'audit', component: () => import('@/views/AuditView.vue'), meta: { title: '审计追踪' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '控制台')} · SafeOpsAgent`
})

export default router
