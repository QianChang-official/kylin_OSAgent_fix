<script setup lang="ts">
// Public front door. When the entry gate is configured this form is a decoy:
// the backend answers every credential submitted here as a failure, and a
// client that keeps guessing is handed a sandbox session whose console is built
// entirely from synthetic data.
//
// The concealed affordance below only *reveals an input*. It is not the secret
// and carries no security weight — anything shipped to a browser is readable.
// The passphrase itself is verified server-side against a PBKDF2 record by
// POST /auth/gate, so reading this bundle reveals nothing usable, and a wrong
// passphrase is answered as an ordinary 404.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NIcon, NInput } from 'naive-ui'
import { Lock, Login, ShieldCheck } from '@vicons/tabler'
import { api } from '@/api/client'
import { authState, authenticationEnabled, signIn } from '@/auth/session'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const validationError = ref('')
const unlocked = ref(false)
const promptOpen = ref(false)
const passphrase = ref('')
const passphraseField = ref<InstanceType<typeof NInput> | null>(null)

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

async function submitPassphrase(candidate: string) {
  const trimmed = candidate.trim()
  if (trimmed.length < 4) return
  if (await api.authGate(trimmed)) {
    unlocked.value = true
    promptOpen.value = false
    passphrase.value = ''
    validationError.value = ''
    authState.error = ''
  } else {
    // Silent on failure: confirming that a gate exists would itself disclose it.
    passphrase.value = ''
  }
}

// Affordance 1: press and hold the brand mark. Reachable by hand, and in the
// DOM it stays an ordinary decorative element with no distinguishing attribute.
let holdTimer: ReturnType<typeof setTimeout> | null = null

function beginPress() {
  cancelPress()
  holdTimer = setTimeout(() => {
    promptOpen.value = true
    requestAnimationFrame(() => passphraseField.value?.focus())
  }, 900)
}

function cancelPress() {
  if (holdTimer) {
    clearTimeout(holdTimer)
    holdTimer = null
  }
}

// Affordance 2: type the passphrase anywhere outside the visible fields and
// press Enter. Buffered locally and submitted once, so the gate's attempt
// budget is spent per submission rather than per keystroke.
let buffer = ''

function onKey(event: KeyboardEvent) {
  const tag = document.activeElement?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return

  if (event.key === 'Enter') {
    const candidate = buffer
    buffer = ''
    void submitPassphrase(candidate)
    return
  }
  if (event.key === 'Backspace') {
    buffer = buffer.slice(0, -1)
    return
  }
  if (event.key === 'Escape') {
    buffer = ''
    return
  }
  if (event.key.length === 1) {
    buffer = (buffer + event.key).slice(-64)
  }
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  cancelPress()
  buffer = ''
})
</script>

<template>
  <div class="login-page">
    <header class="login-header">
      <div
        class="login-brand-mark"
        @mousedown.prevent="beginPress"
        @mouseup="cancelPress"
        @mouseleave="cancelPress"
        @touchstart.passive="beginPress"
        @touchend="cancelPress"
        @touchcancel="cancelPress"
      >
        <n-icon :component="Lock" :size="22" />
      </div>
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
            <p>{{ unlocked ? 'Operator access' : 'Console access' }}</p>
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

          <template v-if="promptOpen && !unlocked">
            <label for="login-key">运维口令</label>
            <div class="login-key-row">
              <n-input
                id="login-key"
                ref="passphraseField"
                v-model:value="passphrase"
                type="password"
                placeholder="请输入运维口令"
                autocomplete="off"
                :maxlength="512"
                show-password-on="click"
                @keyup.enter="submitPassphrase(passphrase)"
              />
              <n-button quaternary type="primary" @click="submitPassphrase(passphrase)">确认</n-button>
            </div>
          </template>

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

    <footer class="login-footer">
      <span :class="{ 'footer-open': unlocked }">SafeOpsAgent</span> · 受控访问
    </footer>
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

.login-brand-mark {
  width: 40px;
  height: 40px;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

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
.login-key-row { display: flex; gap: 8px; }
.login-key-row .n-input { flex: 1; }
.login-submit { width: 100%; margin-top: 10px; }
.login-footer { padding: 18px; color: #62717d; font-size: 11px; text-align: center; }
.footer-open { color: #42c6d7; }

@media (max-width: 520px) {
  .login-header { min-height: 62px; padding: 11px 14px; }
  .login-brand-mark { width: 36px; height: 36px; }
  .login-main { place-items: start center; padding: 22px 14px; }
  .login-panel { padding: 19px; }
  .login-key-row { flex-direction: column; }
  .login-key-row .n-button { width: 100%; }
}
</style>
