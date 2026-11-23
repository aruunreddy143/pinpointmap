import type { Role } from '@/lib/types'
import { ApiError, apiRequest, setAccessToken, setUnauthorizedHandler } from './http'

// Shapes mirror backend/app/schemas/auth.py.
export interface RoleGrant {
  role: Exclude<Role, 'viewer'>
  jurisdiction_id: string
}
export interface ApiUser {
  id: string
  name: string
  kind: 'staff' | 'viewer'
  email: string | null
  roles: RoleGrant[]
}
export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: ApiUser
}

const STAFF_PRIORITY: RoleGrant['role'][] = ['super_admin', 'admin', 'registrar', 'verifier', 'printer', 'auditor']

/** The single role the UI shows for a user: the most powerful one they hold. */
export function roleOf(user: ApiUser): Role {
  if (user.kind === 'viewer') return 'viewer'
  const held = new Set(user.roles.map((r) => r.role))
  return STAFF_PRIORITY.find((r) => held.has(r)) ?? 'auditor'
}

function accept(res: TokenResponse): TokenResponse {
  setAccessToken(res.access_token)
  return res
}

// ---------- Normal users: one-time code ----------
export async function requestCode(identifier: string): Promise<void> {
  await apiRequest('/auth/otp/request', { method: 'POST', body: { identifier } })
}

export type VerifyCodeResult = { status: 'ok'; session: TokenResponse } | { status: 'new'; signupToken: string }

export async function verifyCode(identifier: string, code: string): Promise<VerifyCodeResult> {
  const { status, data } = await apiRequest<TokenResponse | { signup_token: string }>('/auth/otp/verify', { method: 'POST', body: { identifier, code } })
  if (status === 202 && 'signup_token' in data) return { status: 'new', signupToken: data.signup_token }
  return { status: 'ok', session: accept(data as TokenResponse) }
}

export async function completeSignup(identifier: string, signupToken: string, name: string): Promise<TokenResponse> {
  const { data } = await apiRequest<TokenResponse>('/auth/otp/signup', { method: 'POST', body: { identifier, signup_token: signupToken, name: name.trim() } })
  return accept(data)
}

// ---------- Staff: password, then authenticator code ----------
export async function staffLogin(email: string, password: string): Promise<string> {
  const { data } = await apiRequest<{ ticket: string }>('/auth/staff/login', { method: 'POST', body: { email: email.trim(), password } })
  return data.ticket
}

export async function staffVerifyTotp(ticket: string, code: string): Promise<TokenResponse> {
  const { data } = await apiRequest<TokenResponse>('/auth/staff/totp', { method: 'POST', body: { ticket, code } })
  return accept(data)
}

// ---------- Session ----------
/** Restores a session from the httpOnly refresh cookie. Returns null when there is none. */
export async function refreshSession(): Promise<TokenResponse | null> {
  try {
    const { data } = await apiRequest<TokenResponse>('/auth/refresh', { method: 'POST', csrf: true })
    return accept(data)
  } catch {
    setAccessToken(null)
    return null
  }
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/auth/logout', { method: 'POST', csrf: true })
  } catch {
    /* the cookie may already be gone; still clear local state */
  }
  setAccessToken(null)
}

// ---------- Password reset ----------
export async function requestPasswordReset(email: string): Promise<void> {
  await apiRequest('/auth/password/forgot', { method: 'POST', body: { email: email.trim() } })
}

// ---------- Invites ----------
export interface InviteInfo {
  email: string
  role: Role
  totp_secret: string
  totp_uri: string
}

/** Null when the link is invalid or already used. */
export async function getInvite(token: string): Promise<InviteInfo | null> {
  try {
    const { data } = await apiRequest<InviteInfo>(`/auth/invites/${encodeURIComponent(token)}`)
    return data
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

export async function acceptInvite(token: string, name: string, password: string, totpCode: string): Promise<TokenResponse> {
  const { data } = await apiRequest<TokenResponse>(`/auth/invites/${encodeURIComponent(token)}/accept`, {
    method: 'POST',
    body: { name: name.trim(), password, totp_code: totpCode },
  })
  return accept(data)
}

export function passwordProblem(password: string): string | null {
  if (password.length < 10) return 'Use at least 10 characters.'
  if (!/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) return 'Include upper case, lower case and a number.'
  return null
}

// A signed-in request that gets a 401 tries one silent refresh from the cookie, then retries.
setUnauthorizedHandler(async () => (await refreshSession()) !== null)
