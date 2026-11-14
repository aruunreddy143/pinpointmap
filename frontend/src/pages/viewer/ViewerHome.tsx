import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, ChevronRight, Home, Lock, ScanLine, Search, SearchX } from 'lucide-react'
import { Card, EmptyState, InlineError, Skeleton, inputClass } from '@/components/ui'
import { formatDisplay } from '@/lib/placeId'
import { useAsync } from '@/lib/useAsync'
import { publicSearch } from '@/mocks/api'

export function ViewerHome() {
  const [q, setQ] = useState('')
  const results = useAsync(() => publicSearch(q), [q])
  const searching = q.trim().length > 0

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="m-0 mb-1.5 mt-2 text-[26px] font-bold leading-tight">Find any place by its PINPOINT ID</h1>
        <p className="m-0 leading-relaxed text-muted">Search or scan a code to see public place details.</p>
      </div>
      <div className="flex gap-2.5">
        <div className="flex h-[52px] flex-1 items-center gap-2.5 rounded-[14px] border-[1.5px] border-border bg-surface px-3.5 text-muted focus-within:border-accent">
          <Search size={18} aria-hidden />
          <input aria-label="Search places" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, address or ID" className={`${inputClass} !h-full border-0 !bg-transparent !px-0 !text-[15px] focus-visible:!outline-none`} />
        </div>
        <Link to="/app/scan" aria-label="Scan a code" className="flex size-[52px] items-center justify-center rounded-[14px] bg-accent text-accent-ink"><ScanLine size={22} aria-hidden /></Link>
      </div>
      {results.error && <InlineError title="Search failed" text={results.error} onRetry={results.reload} />}
      {searching && (
        <div>
          {results.loading ? (
            <div className="flex flex-col gap-2.5"><Skeleton className="h-20" /><Skeleton className="h-20" /></div>
          ) : results.data && results.data.length > 0 ? (
            <>
              <div className="mb-2.5 text-xs font-semibold uppercase text-muted">{results.data.length} public result{results.data.length > 1 ? 's' : ''}</div>
              <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                {results.data.map((p) => {
                  const Icon = p.type === 'building' ? Building2 : Home
                  return (
                    <li key={p.id}>
                      <Link to={`/app/places/${p.id}`} className="flex items-center gap-3 rounded-2xl border border-border bg-surface p-3.5 no-underline text-text shadow-card transition-colors hover:border-accent">
                        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent"><Icon size={22} aria-hidden /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block font-semibold">{p.name}</span>
                          <span className="block text-[12.5px] text-muted">{p.type === 'building' ? 'Apartment building' : 'House'} · {p.locality}</span>
                          <span className="mt-0.5 block truncate font-mono text-[11px] text-muted tnum">{p.publicId && formatDisplay(p.publicId)}</span>
                        </span>
                        <ChevronRight size={18} className="text-muted" aria-hidden />
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </>
          ) : (
            <Card><EmptyState icon={SearchX} title="No public places found" text="Check the spelling or the ID. Private places never appear in search." /></Card>
          )}
        </div>
      )}
      <div className="flex gap-2.5 rounded-[14px] bg-surface-2 p-4 text-[12.5px] leading-relaxed text-muted">
        <Lock size={18} className="mt-0.5 shrink-0" aria-hidden />
        <span>Private places never appear in search. Scanning one shows only that it is registered.</span>
      </div>
    </div>
  )
}
