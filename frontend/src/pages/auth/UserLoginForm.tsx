import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, Smartphone } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Button, Field, InlineError, inputClass } from '@/components/ui'
import { identifierHint, maskIdentifier, parseIdentifier, type Identifier } from '@/lib/identifier'
import { completeSignup, requestCode, verifyCode } from '@/lib/authApi'
import { ApiError } from '@/lib/http'
import { CodeInput } from './AuthShell'

type Step = 'identify' | 'code' | 'name'
const RESEND_SECONDS = 30

/** Normal-user sign in AND sign up in one flow: a new mobile/email simply asks for a name after the code. */
export function UserLoginForm() {
  const { startSession } = useSession()
  const nav = useNavigate()
  const [step, setStep] = useState<Step>('identify')
  const [text, setText] = useState('')
  const [id, setId] = useState<Identifier | null>(null)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [signupToken, setSignupToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [wait, setWait] = useState(0)

  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait(wait - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])

  const parsed = parseIdentifier(text)
  const hint = identifierHint(text)

  const send = async (target: Identifier) => {
    setBusy(true)
    setError(null)
    try {
      await requestCode(target.value)
    } catch (err) {
      setBusy(false)
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
      return false
    }
    setBusy(false)
    setId(target)
    setCode('')
    setWait(RESEND_SECONDS)
    return true
  }

  const submitIdentifier = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!parsed) return
    if (await send(parsed)) setStep('code')
  }

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || code.length !== 6) return
    setBusy(true)
    setError(null)
    try {
      const r = await verifyCode(id.value, code)
      if (r.status === 'ok') {
        startSession(r.session)
        nav('/app')
      } else {
        setSignupToken(r.signupToken)
        setStep('name')
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const submitName = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || name.trim().length < 2) return
    setBusy(true)
    setError(null)
    try {
      startSession(await completeSignup(id.value, signupToken, name))
      nav('/app')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  if (step === 'identify') {
    return (
      <form onSubmit={submitIdentifier} className="flex flex-col gap-4" noValidate>
        <Field label="Mobile number or email" htmlFor="identifier" hint="New here? We'll create your read-only account after you confirm the code.">
          <input id="identifier" value={text} onChange={(e) => { setText(e.target.value); setError(null) }} className={inputClass} placeholder="98765 43210 or you@example.com" autoComplete="username" inputMode="email" autoFocus aria-invalid={!!hint} aria-describedby="identifier-status" />
        </Field>
        <div id="identifier-status" role="status" className="-mt-2 flex min-h-5 items-center gap-1.5 text-[13px] font-medium">
          {parsed ? (
            <span className="flex items-center gap-1.5 text-ok">{parsed.kind === 'mobile' ? <Smartphone size={14} aria-hidden /> : <Mail size={14} aria-hidden />}{parsed.kind === 'mobile' ? `Code will be sent by SMS to ${parsed.display}` : `Code will be sent by email to ${parsed.display}`}</span>
          ) : hint ? (
            <span className="text-bad">{hint}</span>
          ) : null}
        </div>
        {error && <InlineError title="Could not send the code" text={error} />}
        <Button type="submit" variant="primary" size="lg" disabled={!parsed} loading={busy}>Send code</Button>
      </form>
    )
  }

  if (step === 'code' && id) {
    return (
      <form onSubmit={submitCode} className="flex flex-col gap-4" noValidate>
        <p className="m-0 text-[13.5px] leading-relaxed text-muted">We sent a 6-digit code {id.kind === 'mobile' ? 'by SMS' : 'by email'} to <strong className="text-text">{maskIdentifier(id)}</strong>. It expires in 5 minutes.</p>
        <Field label="Enter the code" htmlFor="otp">
          <CodeInput id="otp" value={code} onChange={(v) => { setCode(v); setError(null) }} invalid={!!error} describedBy="otp-error" />
        </Field>
        <div id="otp-error" aria-live="polite">{error && <InlineError title="Check the code" text={error} />}</div>
        <Button type="submit" variant="primary" size="lg" disabled={code.length !== 6} loading={busy}>Verify</Button>
        <div className="flex items-center justify-between text-[13px]">
          <button type="button" className="font-semibold text-accent" onClick={() => { setStep('identify'); setError(null) }}>Use a different {id.kind === 'mobile' ? 'number' : 'email'}</button>
          <button type="button" disabled={wait > 0 || busy} onClick={() => void send(id)} className="font-semibold text-accent disabled:text-muted">{wait > 0 ? `Resend in ${wait}s` : 'Resend code'}</button>
        </div>
      </form>
    )
  }

  return (
    <form onSubmit={submitName} className="flex flex-col gap-4" noValidate>
      <p className="m-0 text-[13.5px] leading-relaxed text-muted">Code confirmed. This looks like a new account. Your account is read-only: you can search and view public places.</p>
      <Field label="Your name" htmlFor="name"><input id="name" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} autoComplete="name" autoFocus placeholder="Priya Kumar" /></Field>
      {error && <InlineError title="Could not create the account" text={error} />}
      <Button type="submit" variant="primary" size="lg" disabled={name.trim().length < 2} loading={busy}>Create account</Button>
    </form>
  )
}
