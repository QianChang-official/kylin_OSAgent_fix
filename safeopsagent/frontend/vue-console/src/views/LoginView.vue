<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NIcon, NInput } from 'naive-ui'
import { Lock, Login, ShieldCheck } from '@vicons/tabler'
import { authState, authenticationEnabled, signIn } from '@/auth/session'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const validationError = ref('')

const error = computed(() => validationError.value || authState.error)

function redirectTarget(): string {
  const target = route.query.redirect
  if (
    typeof target === 'string'
    && target.startsWith('/')
    && !target.startsWith('//')
    && !target.startsWith('/login')
  ) {
    return target
  }
  return '/'
}

async function submit() {
  validationError.value = ''
  const normalizedUsername = username.value.trim()
  if (!normalizedUsername || !password.value) {
    validationError.value = '请输入账号和密码。'
    return
  }

  try {
    const session = await signIn({
      username: normalizedUsername,
      password: password.value,
    })
    password.value = ''
    if (!authenticationEnabled(session) || session.authenticated) {
      await router.replace(redirectTarget())
      return
    }
    validationError.value = '登录未能建立有效会话，请重试。'
  } catch {
    password.value = ''
  }
}
</script>

<template>
  <div class="login-page">
    <header class="login-header">
      <div class="login-brand-mark"><n-icon :component="Lock" :size="22" /></div>
      <div>
        <strong>SafeOpsAgent</strong>
        <span>安全智能运维控制台</span>
      </div>
    </header>

    <main class="login-main">
      <section class="login-panel" aria-labelledby="login-title">
        <div class="login-heading">
          <div class="login-heading-icon"><n-icon :component="ShieldCheck" :size="21" /></div>
          <div>
            <p>Console access</p>
            <h1 id="login-title">登录控制台</h1>
          </div>
        </div>
        <p class="login-description">使用管理员配置的控制台账号继续访问。</p>

        <n-alert v-if="error" type="error" :bordered="false" title="登录失败" aria-live="polite">
          {{ error }}
        </n-alert>

        <form class="login-form" @submit.prevent="submit">
          <label for="login-username">账号</label>
          <n-input
            id="login-username"
            v-model:value="username"
            placeholder="请输入账号"
            autocomplete="username"
            :maxlength="128"
            :disabled="authState.loading"
            autofocus
          />

          <label for="login-password">密码</label>
          <n-input
            id="login-password"
            v-model:value="password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
            :maxlength="512"
            :disabled="authState.loading"
            show-password-on="click"
          />

          <n-button
            class="login-submit"
            type="primary"
            attr-type="submit"
            :loading="authState.loading"
            :disabled="authState.loading"
          >
            <template #icon><n-icon :component="Login" /></template>
            登录
          </n-button>
        </form>
      </section>
    </main>

    <footer class="login-footer">SafeOpsAgent · 受控访问</footer>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  background: #0b0f14;
}

.login-header {
  min-height: 72px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 14px clamp(18px, 4vw, 44px);
  border-bottom: 1px solid #202a35;
  background: #0e141b;
}

.login-brand-mark,
.login-heading-icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: #5bd9e7;
  border: 1px solid #2bc4d966;
  border-radius: 7px;
  background: #10252b;
}

.login-brand-mark { width: 40px; height: 40px; }
.login-heading-icon { width: 38px; height: 38px; }
.login-header strong,
.login-header span { display: block; }
.login-header strong { font-size: 16px; }
.login-header span { margin-top: 3px; color: #82909d; font-size: 11px; }

.login-main {
  width: 100%;
  display: grid;
  place-items: center;
  padding: 32px 18px;
}

.login-panel {
  width: min(420px, 100%);
  padding: 24px;
  border: 1px solid #26313c;
  border-radius: 8px;
  background: #111820;
}

.login-heading { display: flex; align-items: center; gap: 12px; }
.login-heading p { margin: 0 0 3px; color: #42c6d7; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.login-heading h1 { margin: 0; font-size: 21px; line-height: 1.25; }
.login-description { margin: 14px 0 18px; color: #86949f; font-size: 13px; line-height: 1.65; }
.login-panel .n-alert { margin-bottom: 16px; }
.login-form { display: grid; gap: 9px; }
.login-form label { margin-top: 4px; color: #aab7bf; font-size: 12px; font-weight: 600; }
.login-submit { width: 100%; margin-top: 10px; }
.login-footer { padding: 18px; color: #62717d; font-size: 11px; text-align: center; }

@media (max-width: 520px) {
  .login-header { min-height: 62px; padding: 11px 14px; }
  .login-brand-mark { width: 36px; height: 36px; }
  .login-main { place-items: start center; padding: 22px 14px; }
  .login-panel { padding: 19px; }
}
</style>
