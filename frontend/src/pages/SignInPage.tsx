import { useNavigate } from 'react-router-dom'
import { Eye, ShieldCheck, ClipboardEdit, BadgeCheck, Printer, ScrollText, UserCog } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Pill } from '@/components/ui'
import { isStaff, ROLE_LABEL } from '@/lib/permissions'
import type { Role } from '@/lib/types'

const ROLES: { role: Role; text: string; icon: typeof Eye }[] = [
  { role: 'admin', text: 'Manage users and roles, and do everything below.', icon: UserCog },
  { role: 'registrar', text: 'Register houses and buildings, add units, edit places.', icon: ClipboardEdit },
  { role: 'verifier', text: 'Approve, reject, merge and retire. Never your own work.', icon: BadgeCheck },
  { role: 'printer', text: 'Print QR and barcode labels.', icon: Printer },
  { role: 'auditor', text: 'Read-only view of places and the audit log.', icon: ScrollText },
  { role: 'viewer', text: 'Search, scan and view public places. Read-only.', icon: Eye },
]

/** Development-only role picker. Not rendered in production builds (see LoginPage). */
export function DemoPicker() {
  const { signIn } = useSession()
  const nav = useNavigate()
  const go = (role: Role) => {
    signIn(role)
    nav(isStaff(role) ? '/staff/map' : '/app')
  }
  return (
    <div className="grid gap-3">
      {ROLES.map((r) => (
        <button key={r.role} type="button" onClick={() => go(r.role)} className="flex items-start gap-3 rounded-xl border border-border bg-surface p-3 text-left transition-colors hover:border-accent">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent"><r.icon size={18} aria-hidden /></span>
          <span className="flex-1">
            <span className="mb-0.5 flex items-center gap-2 text-sm font-bold">{ROLE_LABEL[r.role]}{r.role === 'viewer' ? <Pill tone="grey">Read-only</Pill> : <Pill tone="accent" icon={ShieldCheck}>Staff</Pill>}</span>
            <span className="text-[12.5px] leading-relaxed text-muted">{r.text}</span>
          </span>
        </button>
      ))}
    </div>
  )
}
