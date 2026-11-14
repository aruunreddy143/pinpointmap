import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import QRCode from 'qrcode'
import { LinkIcon } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Button, Field, InlineError, Skeleton, inputClass } from '@/components/ui'
import { ROLE_LABEL } from '@/lib/permissions'
import { useAsync } from '@/lib/useAsync'
import { acceptInvite, DEMO_TOTP, getInvite, passwordProblem } from '@/mocks/auth'
import { AuthShell, CodeInput, DemoHint } from './AuthShell'

const MOCK_SECRET = 'JBSWY3DPEHPK3PXP'

export function AcceptInvitePage() {
  const { token = '' } = useParams()
  const { signIn } = useSession()
  const nav = useNavigate()
  const invite = useAsync(() => getInvite(token), [token])
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [qr, setQr] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const email = invite.data?.email
  useEffect(() => {
    if (!email) return
    const uri = `otpauth://totp/PINPOINT:${encodeURIComponent(email)}?secret=${MOCK_SECRET}&issuer=PINPOINT`
    QRCode.toString(uri, { type: 'svg', margin: 0 }).then(setQr)
  }, [email])

  if (invite.loading && !invite.data) {
    return <AuthShell title="Accept your invite"><Skeleton className="h-40" /></AuthShell>
  }
  if (!invite.data) {
    return (
      <AuthShell title="Invite not valid" footer={<Link to="/" className="text-[13px] font-semibold text-accent">← Go to sign in</Link>}>
        <InlineError title="This invite link is invalid or already used" text="Ask your admin to send a new invite." />
      </AuthShell>
    )
  }

  const problem = password ? passwordProblem(password) : null
  const ready = name.trim().length > 1 && !passwordProblem(password) && code.length === 6

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const r = await acceptInvite(token, name, password, code)
    setBusy(false)
    if (!r.ok) return setError(r.error)
    signIn(r.role, r.name)
    nav('/staff/map')
  }

  return (
    <AuthShell title="Set up your account" subtitle={`You were invited to PINPOINT as ${ROLE_LABEL[invite.data.role]} (${invite.data.email}).`}>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <Field label="Your name" htmlFor="inv-name"><input id="inv-name" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} autoComplete="name" autoFocus /></Field>
        <Field label="Choose a password" htmlFor="inv-pass" hint="At least 10 characters with upper case, lower case and a number.">
          <input id="inv-pass" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} autoComplete="new-password" aria-invalid={!!problem} />
          {problem && <div role="status" className="mt-1 text-xs font-semibold text-bad">{problem}</div>}
        </Field>
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-4">
          <div className="font-bold">Set up your authenticator app</div>
          <p className="m-0 text-[13px] leading-relaxed text-muted">Scan this code with an authenticator app (Google Authenticator, Microsoft Authenticator, Authy), then enter the 6-digit code it shows.</p>
          <div className="flex items-center gap-4">
            <div role="img" aria-label="Authenticator setup QR code" className="size-32 shrink-0 rounded-lg bg-white p-2 [&>svg]:size-full" dangerouslySetInnerHTML={{ __html: qr }} />
            <div className="min-w-0 text-xs text-muted"><LinkIcon size={13} className="mb-1 inline" aria-hidden /> Can't scan? Enter this key:<div className="mt-1 break-all font-mono text-[12.5px] text-text">{MOCK_SECRET}</div></div>
          </div>
          <Field label="Code from the app" htmlFor="inv-code"><CodeInput id="inv-code" value={code} onChange={(v) => { setCode(v); setError(null) }} invalid={!!error} /></Field>
        </div>
        <DemoHint>the code is {DEMO_TOTP}.</DemoHint>
        {error && <InlineError title="Could not finish setup" text={error} />}
        <Button type="submit" variant="primary" size="lg" disabled={!ready} loading={busy}>Create account and sign in</Button>
      </form>
    </AuthShell>
  )
}
