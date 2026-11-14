import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Check, CircleAlert, Clock, Loader2, Lock, Archive, Ban, X, type LucideIcon } from 'lucide-react'
import type { PlaceStatus, Visibility } from '@/lib/types'

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}

// ---------- Button ----------
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
  icon?: LucideIcon
  size?: 'sm' | 'md' | 'lg'
}
const VARIANT: Record<Variant, string> = {
  primary: 'bg-accent text-accent-ink hover:brightness-110 active:brightness-95',
  secondary: 'bg-surface text-text border border-border hover:bg-surface-2 active:bg-grey-soft',
  ghost: 'bg-transparent text-muted hover:bg-surface-2 hover:text-text',
  danger: 'bg-surface text-bad border border-border hover:bg-bad-soft',
}
const SIZE = { sm: 'h-8 px-3 text-[13px]', md: 'h-10 px-4 text-sm', lg: 'h-12 px-5 text-[15px]' }

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', loading, icon: Icon, children, className, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-[10px] font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 size={16} className="animate-spin" aria-hidden /> : Icon ? <Icon size={16} aria-hidden /> : null}
      {children}
    </button>
  )
})

// ---------- Pills ----------
type Tone = 'accent' | 'ok' | 'warn' | 'bad' | 'grey'
const TONE: Record<Tone, string> = {
  accent: 'bg-accent-soft text-accent',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
  grey: 'bg-grey-soft text-muted',
}

export function Pill({ tone = 'grey', icon: Icon, children }: { tone?: Tone; icon?: LucideIcon; children: ReactNode }) {
  return (
    <span className={cx('inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-semibold', TONE[tone])}>
      {Icon && <Icon size={13} aria-hidden />}
      {children}
    </span>
  )
}

const STATUS: Record<PlaceStatus, { label: string; tone: Tone; icon: LucideIcon }> = {
  draft: { label: 'Draft', tone: 'grey', icon: Clock },
  pending_verification: { label: 'Pending', tone: 'warn', icon: Clock },
  active: { label: 'Active', tone: 'ok', icon: Check },
  rejected: { label: 'Rejected', tone: 'bad', icon: X },
  retired: { label: 'Retired', tone: 'grey', icon: Archive },
  merged: { label: 'Merged', tone: 'grey', icon: Ban },
  split: { label: 'Split', tone: 'grey', icon: Ban },
}

// Status is always colour + icon + text, never colour alone.
export function StatusPill({ status }: { status: PlaceStatus }) {
  const s = STATUS[status]
  return (
    <Pill tone={s.tone} icon={s.icon}>
      {s.label}
    </Pill>
  )
}

export function VisibilityPill({ visibility }: { visibility: Visibility }) {
  return visibility === 'private' ? (
    <Pill tone="grey" icon={Lock}>
      Private
    </Pill>
  ) : (
    <Pill tone="accent">Public</Pill>
  )
}

// ---------- Card ----------
export function Card({ children, className, as: Tag = 'section', ...rest }: { children: ReactNode; className?: string; as?: 'section' | 'div' | 'aside' } & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag className={cx('rounded-card border border-border bg-surface shadow-card', className)} {...rest}>
      {children}
    </Tag>
  )
}

// ---------- States ----------
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('pp-skeleton', className)} aria-hidden />
}

export function EmptyState({ icon: Icon, title, text, action }: { icon: LucideIcon; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-grey-soft text-muted">
        <Icon size={22} aria-hidden />
      </div>
      <h2 className="m-0 text-base font-bold">{title}</h2>
      <p className="m-0 max-w-sm text-muted">{text}</p>
      {action}
    </div>
  )
}

export function InlineError({ title, text, onRetry }: { title: string; text: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl bg-bad-soft p-4 text-bad">
      <CircleAlert size={18} className="mt-0.5 shrink-0" aria-hidden />
      <div className="flex-1">
        <div className="font-semibold">{title}</div>
        <div className="text-sm opacity-90">{text}</div>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function Field({ label, htmlFor, children, hint }: { label: string; htmlFor: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-semibold text-muted">
        {label}
      </label>
      {children}
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  )
}

export const inputClass =
  'h-10 w-full rounded-[10px] border border-border bg-surface px-3 text-sm text-text placeholder:text-muted'

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-0.5 rounded-[10px] bg-surface-2 p-[3px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            'h-8 flex-1 whitespace-nowrap rounded-lg px-3 text-[13px] font-semibold transition-colors duration-150',
            value === o.value ? 'bg-accent text-accent-ink shadow-card' : 'text-muted hover:text-text',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
