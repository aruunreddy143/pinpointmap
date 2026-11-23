import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { logout as apiLogout, refreshSession, roleOf, type TokenResponse } from '@/lib/authApi'
import type { Role } from '@/lib/types'

// ---------- Session ----------
// Real sign-in goes through the backend (see lib/authApi.ts): the access token is held in memory and the
// session is restored on reload from the httpOnly refresh cookie. In dev builds only, the role picker
// ("Developer shortcut") and `?as=<role>` still open the mock-data screens without signing in.

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
  /** False while the app checks for an existing session on first load. */
  ready: boolean
  /** Start a session from a successful API sign-in. */
  startSession: (res: TokenResponse) => void
  /** Dev-only: open the mock screens as a role without signing in. */
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

function readDemo(): Stored | null {
  if (!import.meta.env.DEV) return null
  // Dev-only shortcut for demos and screenshots: /staff/map?as=verifier&theme=dark
  const as = new URLSearchParams(window.location.search).get('as') as Role | null
  if (as && ROLES.includes(as)) return { role: as }
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
  const [session, setSession] = useState<Stored | null>(() => {
    if (initialRole !== undefined) return initialRole ? { role: initialRole } : null
    return readDemo()
  })
  // Tests pass initialRole, and a dev demo role needs no network: both are ready immediately.
  const [ready, setReady] = useState(() => initialRole !== undefined || session !== null)
  const [expiresIn, setExpiresIn] = useState<number | null>(null)

  const startSession = useCallback((res: TokenResponse) => {
    setSession({ role: roleOf(res.user), name: res.user.name })
    setExpiresIn(res.expires_in)
    setReady(true)
  }, [])

  // Restore a real session from the refresh cookie on first load.
  useEffect(() => {
    if (ready) return
    let live = true
    void refreshSession().then((res) => {
      if (!live) return
      if (res) startSession(res)
      else setReady(true)
    })
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, [])

  // Keep the short-lived access token fresh while a real session is open.
  useEffect(() => {
    if (expiresIn === null) return
    const t = setTimeout(() => {
      void refreshSession().then((res) => {
        if (res) setExpiresIn(res.expires_in)
        else {
          setSession(null)
          setExpiresIn(null)
        }
      })
    }, Math.max(30, expiresIn * 0.8) * 1000)
    return () => clearTimeout(t)
  }, [expiresIn])

  const signIn = useCallback((r: Role, name?: string) => {
    setSession({ role: r, name })
    setReady(true)
    try {
      localStorage.setItem(ROLE_KEY, JSON.stringify({ role: r, name }))
    } catch {
      /* storage unavailable: session lasts for this page only */
    }
  }, [])
  const signOut = useCallback(() => {
    setSession(null)
    setExpiresIn(null)
    void apiLogout()
    try {
      localStorage.removeItem(ROLE_KEY)
    } catch {
      /* ignore */
    }
  }, [])
  const role = session?.role ?? null
  const userName = session ? session.name ?? USER_NAMES[session.role] : ''
  const value = useMemo(() => ({ role, userName, ready, startSession, signIn, signOut }), [role, userName, ready, startSession, signIn, signOut])
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
