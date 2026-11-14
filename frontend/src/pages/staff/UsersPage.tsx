import { useState } from 'react'
import { Check, Copy, ShieldOff, UserPlus } from 'lucide-react'
import { useSession } from '@/app/providers'
import { useToast } from '@/components/toast'
import { Button, Card, EmptyState, Field, InlineError, Pill, Skeleton, inputClass } from '@/components/ui'
import { can, ROLE_LABEL } from '@/lib/permissions'
import type { Role } from '@/lib/types'
import { useAsync } from '@/lib/useAsync'
import { inviteStaff, listStaff, type StaffRow } from '@/mocks/auth'

const ASSIGNABLE: Role[] = ['registrar', 'verifier', 'printer', 'auditor', 'admin']
const DISTRICTS = ['Bengaluru Urban', 'Mysuru', 'Mangaluru']

export function UsersPage() {
  const { role } = useSession()
  const toast = useToast()
  const staff = useAsync(listStaff, [])
  const [email, setEmail] = useState('')
  const [newRole, setNewRole] = useState<Role>('registrar')
  const [district, setDistrict] = useState(DISTRICTS[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [last, setLast] = useState<StaffRow | null>(null)

  if (!role || !can(role, 'user:manage')) {
    return <div className="p-6"><EmptyState icon={ShieldOff} title="You can't manage users" text="Only admins can invite staff and assign roles." /></div>
  }

  const link = (t: string) => `${window.location.origin}/invite/${t}`

  const invite = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const r = await inviteStaff(email, newRole, district)
    setBusy(false)
    if ('error' in r) return setError(r.error)
    setLast(r)
    setEmail('')
    staff.reload()
    toast(`Invite created for ${r.email}`)
  }

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast('Invite link copied')
    } catch {
      toast('Could not copy. Select the link and copy it.', 'bad')
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 p-4 md:p-7">
      <div>
        <h1 className="m-0 text-[22px] font-bold">Users and roles</h1>
        <p className="m-0 text-[13px] text-muted">Staff accounts are created by invite only. Each role applies to one district.</p>
      </div>
      <Card className="p-5">
        <h2 className="m-0 mb-4 flex items-center gap-2 text-base font-bold"><UserPlus size={18} aria-hidden />Invite a staff member</h2>
        <form onSubmit={invite} className="grid items-start gap-4 md:grid-cols-[1fr_180px_180px_auto]" noValidate>
          <Field label="Work email" htmlFor="u-email"><input id="u-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="name@organisation.gov.in" /></Field>
          <Field label="Role" htmlFor="u-role">
            <select id="u-role" value={newRole} onChange={(e) => setNewRole(e.target.value as Role)} className={inputClass}>{ASSIGNABLE.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select>
          </Field>
          <Field label="District" htmlFor="u-dist">
            <select id="u-dist" value={district} onChange={(e) => setDistrict(e.target.value)} className={inputClass}>{DISTRICTS.map((d) => <option key={d}>{d}</option>)}</select>
          </Field>
          <div className="md:pt-[22px]"><Button type="submit" variant="primary" loading={busy} disabled={!email.includes('@')}>Send invite</Button></div>
        </form>
        {error && <div className="mt-4"><InlineError title="Could not invite" text={error} /></div>}
        {last?.inviteToken && (
          <div role="status" className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-ok-soft p-3.5 text-sm">
            <Check size={16} className="text-ok" aria-hidden />
            <span className="flex-1 break-all">Invite for <strong>{last.email}</strong> ready. In production this is emailed. Link: <span className="font-mono text-xs">{link(last.inviteToken)}</span></span>
            <Button size="sm" icon={Copy} onClick={() => copy(link(last.inviteToken!))}>Copy link</Button>
          </div>
        )}
      </Card>
      <Card className="overflow-hidden">
        {staff.loading && !staff.data ? (
          <div className="flex flex-col gap-3 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : (
          <ul className="m-0 list-none p-0">
            {staff.data?.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border px-5 py-3 last:border-b-0">
                <span className="min-w-[200px] flex-1"><span className="block font-semibold">{s.name || s.email}</span><span className="block text-[13px] text-muted">{s.name ? s.email : 'Waiting for the invite to be accepted'}</span></span>
                <span className="text-[13px] text-muted">{s.district}</span>
                <Pill tone="accent">{ROLE_LABEL[s.role]}</Pill>
                <Pill tone={s.status === 'active' ? 'ok' : 'warn'}>{s.status === 'active' ? 'Active' : 'Invited'}</Pill>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
