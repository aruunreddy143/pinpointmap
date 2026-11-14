import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Check, CircleAlert } from 'lucide-react'
import { cx } from './ui'

interface ToastItem {
  id: number
  text: string
  tone: 'ok' | 'bad'
}
const ToastCtx = createContext<((text: string, tone?: 'ok' | 'bad') => void) | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((text: string, tone: 'ok' | 'bad' = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((x) => [...x, { id, text, tone }])
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 3500)
  }, [])
  const value = useMemo(() => push, [push])
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex flex-col items-center gap-2 px-4">
        {items.map((t) => (
          <div key={t.id} className={cx('pointer-events-auto flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-medium shadow-card', t.tone === 'bad' ? 'text-bad' : 'text-text')}>
            {t.tone === 'ok' ? <Check size={16} className="text-ok" aria-hidden /> : <CircleAlert size={16} aria-hidden />}
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
