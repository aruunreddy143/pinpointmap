import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Role } from '@/lib/types'

// ---------- Session (mock) ----------
// Real auth (staff email + password + TOTP, viewers by mobile OTP) arrives with the backend.
// Until then a demo role picker lets us see every role's view.

const USER_NAMES: Record<Role, string> = {
  super_admin: 'Sunita K.',
  admin: 'Sunita K.',
  registrar: 'Arun R.',
  verifier: 'Ravi M.',
  printer: 'Sunita K.',
  auditor: 'Dev P.',
  viewer: 'Priya K.',
}

interface Session {
  role: Role | null
  userName: string
  signIn: (role: Role, name?: string) => void
  signOut: () => void
}

interface Stored {
  role: Role
  name?: string
}

const SessionCtx = createContext<Session | null>(null)
const ROLE_KEY = 'pinpoint.mock.role'

const ROLES: Role[] = ['super_admin', 'admin', 'registrar', 'verifier', 'printer', 'auditor', 'viewer']

function readStored(): Stored | null {
  // Dev-only shortcut for demos and screenshots: /staff/map?as=verifier&theme=dark
  if (import.meta.env.DEV) {
    const as = new URLSearchParams(window.location.search).get('as') as Role | null
    if (as && ROLES.includes(as)) return { role: as }
  }
  try {
    const raw = localStorage.getItem(ROLE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Stored
    return ROLES.includes(parsed.role) ? parsed : null
  } catch {
    return null
  }
}

export function SessionProvider({ children, initialRole }: { children: ReactNode; initialRole?: Role | null }) {
  const [session, setSession] = useState<Stored | null>(() => (initialRole !== undefined ? (initialRole ? { role: initialRole } : null) : readStored()))
  const signIn = useCallback((r: Role, name?: string) => {
    setSession({ role: r, name })
    try {
      localStorage.setItem(ROLE_KEY, JSON.stringify({ role: r, name }))
    } catch {
      /* storage unavailable: session lasts for this page only */
    }
  }, [])
  const signOut = useCallback(() => {
    setSession(null)
    try {
      localStorage.removeItem(ROLE_KEY)
    } catch {
      /* ignore */
    }
  }, [])
  const role = session?.role ?? null
  const userName = session ? session.name ?? USER_NAMES[session.role] : ''
  const value = useMemo(() => ({ role, userName, signIn, signOut }), [role, userName, signIn, signOut])
  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>
}

export function useSession(): Session {
  const ctx = useContext(SessionCtx)
  if (!ctx) throw new Error('useSession must be used inside SessionProvider')
  return ctx
}

// ---------- Theme ----------
type Theme = 'light' | 'dark'
const THEME_KEY = 'pinpoint.theme'
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void } | null>(null)

function initialTheme(): Theme {
  if (import.meta.env.DEV) {
    const t = new URLSearchParams(window.location.search).get('theme')
    if (t === 'light' || t === 'dark') return t
  }
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    /* ignore */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(THEME_KEY, next)
      } catch {
        /* ignore */
      }
      return next
    })
  }, [])
  const value = useMemo(() => ({ theme, toggle }), [theme, toggle])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeCtx)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
