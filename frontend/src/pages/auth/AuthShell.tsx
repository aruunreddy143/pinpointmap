import type { ReactNode } from 'react'
import { Logo } from '@/app/layouts'
import { Card } from '@/components/ui'

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle?: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-full max-w-md flex-col gap-6 px-5 py-8">
      <Logo />
      <div>
        <h1 className="m-0 mb-1.5 text-[26px] font-bold leading-tight">{title}</h1>
        {subtitle && <p className="m-0 leading-relaxed text-muted">{subtitle}</p>}
      </div>
      <Card className="flex flex-col gap-4 p-5">{children}</Card>
      {footer}
    </div>
  )
}

/** One-time / authenticator code box: numeric keypad on phones, autofill from SMS where supported. */
export function CodeInput({ id, value, onChange, invalid, describedBy }: { id: string; value: string; onChange: (v: string) => void; invalid?: boolean; describedBy?: string }) {
  return (
    <input
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))}
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      placeholder="••••••"
      aria-invalid={invalid}
      aria-describedby={describedBy}
      className={`h-[52px] w-full rounded-[10px] border bg-surface text-center font-mono text-2xl tracking-[0.5em] text-text tnum ${invalid ? 'border-bad' : 'border-border'}`}
    />
  )
}

export function DemoHint({ children }: { children: ReactNode }) {
  if (!import.meta.env.DEV) return null
  return <p className="m-0 rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">Demo: {children}</p>
}
