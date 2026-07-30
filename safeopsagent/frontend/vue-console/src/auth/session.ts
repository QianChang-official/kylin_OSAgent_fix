import { reactive } from 'vue'
import { api } from '@/api/client'
import type { AuthCredentials, AuthSession } from '@/types/api'

interface AuthState {
  initialized: boolean
  loading: boolean
  error: string
  session: AuthSession | null
}

export const authState = reactive<AuthState>({
  initialized: false,
  loading: false,
  error: '',
  session: null,
})

let sessionRequest: Promise<AuthSession> | null = null

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '无法确认登录状态。'
}

export function authenticationEnabled(session: AuthSession | null): boolean {
  return Boolean(session?.enabled)
}

export async function ensureAuthSession(force = false): Promise<AuthSession> {
  const currentSessionExpired = Boolean(
    authState.session?.enabled
    && authState.session.authenticated
    && authState.session.expires_at
    && authState.session.expires_at <= Math.floor(Date.now() / 1000),
  )
  if (!force && authState.session && !currentSessionExpired) return authState.session
  if (sessionRequest) return sessionRequest

  authState.loading = true
  authState.error = ''
  sessionRequest = api.authSession()
    .then((session) => {
      authState.session = session
      return session
    })
    .catch((error: unknown) => {
      authState.error = errorMessage(error)
      throw error
    })
    .finally(() => {
      authState.initialized = true
      authState.loading = false
      sessionRequest = null
    })

  return sessionRequest
}

export async function signIn(credentials: AuthCredentials): Promise<AuthSession> {
  authState.loading = true
  authState.error = ''
  try {
    const session = await api.authLogin(credentials)
    authState.session = session
    authState.initialized = true
    return session
  } catch (error) {
    authState.error = errorMessage(error)
    throw error
  } finally {
    authState.loading = false
  }
}

export async function signOut(): Promise<AuthSession> {
  authState.loading = true
  authState.error = ''
  try {
    await api.authLogout()
    const session: AuthSession = {
      enabled: authState.session?.enabled ?? true,
      authenticated: false,
      username: null,
      expires_at: null,
      csrf_token: null,
    }
    authState.session = session
    authState.initialized = true
    return session
  } catch (error) {
    authState.error = errorMessage(error)
    throw error
  } finally {
    authState.loading = false
  }
}
