import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MailCheck } from 'lucide-react'
import { Button, Field, InlineError, inputClass } from '@/components/ui'
import { requestPasswordReset } from '@/lib/authApi'
import { ApiError } from '@/lib/http'
import { AuthShell } from './AuthShell'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Reset your password" subtitle="For staff accounts. Normal users don't have a password: just request a new code on the sign-in page." footer={<Link to="/" className="text-[13px] font-semibold text-accent">← Back to sign in</Link>}>
      {sent ? (
        <div role="status" className="flex flex-col items-center gap-3 py-4 text-center">
          <span className="flex size-12 items-center justify-center rounded-full bg-ok-soft text-ok"><MailCheck size={22} aria-hidden /></span>
          <div className="font-bold">Check your email</div>
          <p className="m-0 text-[13.5px] leading-relaxed text-muted">If an account exists for that address, we sent a reset link. You will also need your authenticator app to sign in afterwards.</p>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <Field label="Work email" htmlFor="reset-email"><input id="reset-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} autoComplete="username" autoFocus /></Field>
          {error && <InlineError title="Could not send the link" text={error} />}
          <Button type="submit" variant="primary" size="lg" disabled={!email.includes('@')} loading={busy}>Send reset link</Button>
          <p className="m-0 text-xs text-muted">Lost your authenticator app? Ask an admin to reset it.</p>
        </form>
      )}
    </AuthShell>
  )
}
