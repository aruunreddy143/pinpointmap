import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Button, Field, InlineError, inputClass } from '@/components/ui'
import { staffLogin, staffVerifyTotp } from '@/lib/authApi'
import { ApiError } from '@/lib/http'
import { CodeInput } from './AuthShell'

export function StaffLoginForm() {
  const { startSession } = useSession()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [ticket, setTicket] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submitCreds = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setTicket(await staffLogin(email, password))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticket) return
    setBusy(true)
    setError(null)
    try {
      startSession(await staffVerifyTotp(ticket, code))
      nav('/staff/map')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  if (ticket) {
    return (
      <form onSubmit={submitCode} className="flex flex-col gap-4" noValidate>
        <p className="m-0 text-[13.5px] leading-relaxed text-muted">Open your authenticator app and enter the 6-digit code for PINPOINT.</p>
        <Field label="Authenticator code" htmlFor="totp"><CodeInput id="totp" value={code} onChange={(v) => { setCode(v); setError(null) }} invalid={!!error} describedBy="totp-error" /></Field>
        <div id="totp-error" aria-live="polite">{error && <InlineError title="Check the code" text={error} />}</div>
        <Button type="submit" variant="primary" size="lg" disabled={code.length !== 6} loading={busy}>Sign in</Button>
        <button type="button" className="self-start text-[13px] font-semibold text-accent" onClick={() => { setTicket(null); setCode(''); setError(null) }}>Back</button>
      </form>
    )
  }

  return (
    <form onSubmit={submitCreds} className="flex flex-col gap-4" noValidate>
      <Field label="Work email" htmlFor="staff-email"><input id="staff-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} autoComplete="username" autoFocus placeholder="you@organisation.gov.in" /></Field>
      <Field label="Password" htmlFor="staff-password">
        <div className="relative">
          <input id="staff-password" type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} className={`${inputClass} pr-11`} autoComplete="current-password" />
          <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(!show)} className="absolute right-1 top-1 flex size-8 items-center justify-center rounded-lg text-muted hover:bg-surface-2">{show ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}</button>
        </div>
      </Field>
      {error && <InlineError title="Could not sign in" text={error} />}
      <Button type="submit" variant="primary" size="lg" disabled={!email || !password} loading={busy}>Continue</Button>
      <div className="flex justify-between text-[13px]">
        <Link to="/forgot" className="font-semibold text-accent">Forgot password?</Link>
        <span className="text-muted">No account? Ask your admin for an invite.</span>
      </div>
    </form>
  )
}
