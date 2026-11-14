import type { Role } from '@/lib/types'
import { ROLE_LABEL } from '@/lib/permissions'

// Mock of the future auth API. Same rules the backend must enforce: code expiry/attempt limits,
// per-identifier request limits, identical answers whether or not an account exists, invites for staff.

export const DEMO_OTP = '123456'
export const DEMO_TOTP = '123456'
export const DEMO_PASSWORD = 'Passw0rd!'
const MAX_CODE_TRIES = 5
const MAX_CODE_REQUESTS = 3
const MAX_PASSWORD_TRIES = 5

const delay = <T,>(v: T, ms = 300): Promise<T> => new Promise((r) => setTimeout(() => r(v), ms))

// ---------- Normal users (mobile or email + one-time code) ----------
const knownViewers = new Map<string, string>([
  ['+919876543210', 'Priya K.'],
  ['priya@example.com', 'Priya K.'],
])
const codeRequests = new Map<string, number>()
const codeTries = new Map<string, number>()

export type RequestCodeResult = { ok: true } | { ok: false; error: 'rate_limited' }

/** Always the same answer for known and unknown identifiers. */
export async function requestCode(identifier: string): Promise<RequestCodeResult> {
  const n = (codeRequests.get(identifier) ?? 0) + 1
  codeRequests.set(identifier, n)
  codeTries.set(identifier, 0)
  if (n > MAX_CODE_REQUESTS) return delay({ ok: false, error: 'rate_limited' })
  return delay({ ok: true })
}

export type VerifyCodeResult =
  | { status: 'ok'; name: string }
  | { status: 'new' } // code is right but no account yet: ask for a name
  | { status: 'wrong'; triesLeft: number }
  | { status: 'locked' }

export async function verifyCode(identifier: string, code: string): Promise<VerifyCodeResult> {
  const tries = codeTries.get(identifier) ?? 0
  if (tries >= MAX_CODE_TRIES) return delay({ status: 'locked' })
  if (code !== DEMO_OTP) {
    codeTries.set(identifier, tries + 1)
    const left = MAX_CODE_TRIES - tries - 1
    return delay(left <= 0 ? { status: 'locked' } : { status: 'wrong', triesLeft: left })
  }
  const name = knownViewers.get(identifier)
  return delay(name ? { status: 'ok', name } : { status: 'new' })
}

export async function completeSignup(identifier: string, name: string): Promise<{ name: string }> {
  const clean = name.trim()
  knownViewers.set(identifier, clean)
  return delay({ name: clean })
}

// ---------- Staff (email + password + authenticator code) ----------
interface StaffAccount {
  email: string
  name: string
  role: Role
  district: string
  password: string
  active: boolean
}
const staff: StaffAccount[] = [
  { email: 'admin@pinpoint.test', name: 'Sunita K.', role: 'admin', district: 'Bengaluru Urban', password: DEMO_PASSWORD, active: true },
  { email: 'registrar@pinpoint.test', name: 'Arun R.', role: 'registrar', district: 'Bengaluru Urban', password: DEMO_PASSWORD, active: true },
  { email: 'verifier@pinpoint.test', name: 'Ravi M.', role: 'verifier', district: 'Bengaluru Urban', password: DEMO_PASSWORD, active: true },
  { email: 'auditor@pinpoint.test', name: 'Dev P.', role: 'auditor', district: 'Bengaluru Urban', password: DEMO_PASSWORD, active: true },
]
const passwordTries = new Map<string, number>()
const tickets = new Map<string, string>()

export type StaffLoginResult = { status: 'totp'; ticket: string } | { status: 'bad' } | { status: 'locked' }

export async function staffLogin(email: string, password: string): Promise<StaffLoginResult> {
  const key = email.trim().toLowerCase()
  const tries = passwordTries.get(key) ?? 0
  if (tries >= MAX_PASSWORD_TRIES) return delay({ status: 'locked' })
  const acct = staff.find((s) => s.email === key && s.active)
  // Same "bad" answer for an unknown email and a wrong password.
  if (!acct || acct.password !== password) {
    passwordTries.set(key, tries + 1)
    return delay({ status: 'bad' })
  }
  passwordTries.set(key, 0)
  const ticket = `t-${Math.random().toString(36).slice(2)}`
  tickets.set(ticket, key)
  return delay({ status: 'totp', ticket })
}

export type StaffTotpResult = { status: 'ok'; role: Role; name: string } | { status: 'wrong' }

export async function staffVerifyTotp(ticket: string, code: string): Promise<StaffTotpResult> {
  const email = tickets.get(ticket)
  const acct = staff.find((s) => s.email === email)
  if (!acct || code !== DEMO_TOTP) return delay({ status: 'wrong' })
  tickets.delete(ticket)
  return delay({ status: 'ok', role: acct.role, name: acct.name })
}

/** Always succeeds visibly, so it cannot be used to find out which emails have accounts. */
export async function requestPasswordReset(email: string): Promise<void> {
  void email
  return delay(undefined, 400)
}

// ---------- Admin: staff list and invites ----------
export interface StaffRow {
  id: string
  email: string
  name: string
  role: Role
  district: string
  status: 'active' | 'invited'
  inviteToken?: string
}
const invites: StaffRow[] = []

export async function listStaff(): Promise<StaffRow[]> {
  const rows: StaffRow[] = staff.map((s) => ({ id: s.email, email: s.email, name: s.name, role: s.role, district: s.district, status: 'active' }))
  return delay([...rows, ...invites])
}

export async function inviteStaff(email: string, role: Role, district: string): Promise<StaffRow | { error: string }> {
  const key = email.trim().toLowerCase()
  if (staff.some((s) => s.email === key) || invites.some((i) => i.email === key)) return delay({ error: 'That email already has an account or a pending invite.' })
  if (role === 'viewer' || role === 'super_admin') return delay({ error: `${ROLE_LABEL[role]} cannot be assigned by invite.` })
  const row: StaffRow = { id: `inv-${invites.length + 1}`, email: key, name: '', role, district, status: 'invited', inviteToken: `inv${Math.random().toString(36).slice(2, 10)}` }
  invites.push(row)
  return delay(row)
}

export async function getInvite(token: string): Promise<{ email: string; role: Role } | null> {
  const inv = invites.find((i) => i.inviteToken === token)
  return delay(inv ? { email: inv.email, role: inv.role } : null)
}

export function passwordProblem(password: string): string | null {
  if (password.length < 10) return 'Use at least 10 characters.'
  if (!/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) return 'Include upper case, lower case and a number.'
  return null
}

export async function acceptInvite(token: string, name: string, password: string, totpCode: string): Promise<{ ok: true; role: Role; name: string } | { ok: false; error: string }> {
  const inv = invites.find((i) => i.inviteToken === token)
  if (!inv) return delay({ ok: false, error: 'This invite link is invalid or has already been used.' })
  const problem = passwordProblem(password)
  if (problem) return delay({ ok: false, error: problem })
  if (totpCode !== DEMO_TOTP) return delay({ ok: false, error: 'That authenticator code is not right. Check the app and try again.' })
  invites.splice(invites.indexOf(inv), 1)
  staff.push({ email: inv.email, name: name.trim(), role: inv.role, district: inv.district, password, active: true })
  return delay({ ok: true, role: inv.role, name: name.trim() })
}
