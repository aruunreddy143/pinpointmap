import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { Eye, History, ListChecks, ListTree, LogOut, MapPin, Map as MapIcon, Moon, PlusCircle, ScanLine, Search, Sun, Users, type LucideIcon } from 'lucide-react'
import { useSession, useTheme } from './providers'
import { can, isStaff, ROLE_LABEL } from '@/lib/permissions'
import type { Permission, Role } from '@/lib/types'
import { listReview } from '@/lib/api'
import { Pill, cx } from '@/components/ui'

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 no-underline text-text">
      <span className="flex size-8 items-center justify-center rounded-[9px] bg-accent text-accent-ink">
        <MapPin size={18} strokeWidth={2.2} aria-hidden />
      </span>
      <span className="text-[17px] font-bold tracking-wide">PINPOINT</span>
    </Link>
  )
}

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  return (
    <button type="button" onClick={toggle} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} className="flex size-9 items-center justify-center rounded-[10px] border border-border bg-surface text-text transition-colors hover:bg-surface-2">
      {theme === 'dark' ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </button>
  )
}

function UserMenu({ showRole = true }: { showRole?: boolean }) {
  const { role, userName, signOut } = useSession()
  const nav = useNavigate()
  return (
    <div className="flex items-center gap-2">
      {role && showRole && <Pill tone="accent">{ROLE_LABEL[role]}</Pill>}
      <ThemeToggle />
      <button
        type="button"
        onClick={() => {
          signOut()
          nav('/')
        }}
        aria-label={`Sign out ${userName}`}
        title="Sign out"
        className="flex h-9 items-center gap-2 rounded-[10px] border border-border bg-surface px-3 text-[13px] font-semibold text-text transition-colors hover:bg-surface-2"
      >
        <span className="hidden size-6 items-center justify-center rounded-full bg-grey-soft text-[11px] sm:flex">{userName.split(' ').map((s) => s[0]).join('')}</span>
        <LogOut size={15} className="text-muted" aria-hidden />
      </button>
    </div>
  )
}

/** Renders children only when the signed-in role passes; otherwise redirects to sign-in. */
export function RequireRole({ allow }: { allow: 'staff' | 'viewer' }) {
  const { role, ready } = useSession()
  if (!ready) return <div className="min-h-screen bg-bg" aria-busy="true" />
  if (!role) return <Navigate to="/" replace />
  if (allow === 'staff' && !isStaff(role)) return <Navigate to="/app" replace />
  if (allow === 'viewer' && isStaff(role)) return <Navigate to="/staff/map" replace />
  return <Outlet />
}

export function RoleGate({ role, permission, children, fallback = null }: { role: Role; permission: Permission; children: ReactNode; fallback?: ReactNode }) {
  return <>{can(role, permission) ? children : fallback}</>
}

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  perm: Permission
  badge?: number
}

export function StaffShell() {
  const { role } = useSession()
  const [pending, setPending] = useState(0)
  useEffect(() => {
    listReview('new').then((r) => setPending(r.length))
  }, [])
  if (!role) return null
  const items: NavItem[] = [
    { to: '/staff/map', label: 'Map', icon: MapIcon, perm: 'place:read' },
    { to: '/staff/places', label: 'Places', icon: ListTree, perm: 'place:read' },
    { to: '/staff/register', label: 'Register', icon: PlusCircle, perm: 'place:create' },
    { to: '/staff/review', label: 'Review queue', icon: ListChecks, perm: 'place:verify', badge: pending },
    { to: '/staff/scan', label: 'Scan', icon: ScanLine, perm: 'place:read' },
    { to: '/staff/users', label: 'Users', icon: Users, perm: 'user:manage' },
    { to: '/staff/audit', label: 'Audit log', icon: History, perm: 'audit:read' },
  ]
  const visible = items.filter((i) => can(role, i.perm))
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-[60px] shrink-0 items-center gap-4 border-b border-border bg-surface px-4 md:px-5">
        <Logo />
        <div className="hidden h-6 w-px bg-border md:block" />
        <span className="hidden text-[13px] font-medium text-muted md:block">Karnataka · Bengaluru Urban</span>
        <div className="flex-1" />
        <UserMenu />
      </header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <nav aria-label="Main" className="flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-surface p-2 md:w-[216px] md:flex-col md:border-b-0 md:border-r md:p-3">
          {visible.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              className={({ isActive }) =>
                cx('flex h-10 shrink-0 items-center gap-3 rounded-[10px] px-3 font-medium no-underline transition-colors', isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-surface-2 hover:text-text')
              }
            >
              <i.icon size={18} aria-hidden />
              <span className="flex-1 whitespace-nowrap">{i.label}</span>
              {!!i.badge && <span className="flex h-5 min-w-[22px] items-center justify-center rounded-full bg-warn-soft px-1.5 text-xs font-semibold text-warn tnum">{i.badge}</span>}
            </NavLink>
          ))}
        </nav>
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function ViewerShell() {
  const items = [
    { to: '/app', label: 'Search', icon: Search, end: true },
    { to: '/app/scan', label: 'Scan', icon: ScanLine, end: false },
  ]
  return (
    <div className="mx-auto flex h-full max-w-[520px] flex-col">
      <header className="flex shrink-0 items-center gap-3 px-5 pb-3 pt-5">
        <Logo />
        <div className="flex-1" />
        <Pill tone="grey" icon={Eye}>
          Read-only
        </Pill>
        <UserMenu showRole={false} />
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">
        <Outlet />
      </main>
      <nav aria-label="Primary" className="flex shrink-0 border-t border-border bg-surface px-3 pb-3 pt-1.5">
        {items.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => cx('flex flex-1 flex-col items-center gap-1 rounded-xl py-2 text-xs font-semibold no-underline', isActive ? 'text-accent' : 'text-muted')}>
            <i.icon size={22} aria-hidden />
            {i.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
