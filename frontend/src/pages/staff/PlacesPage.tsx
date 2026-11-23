import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, Home, PlusCircle, Search, SearchX } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Button, Card, EmptyState, InlineError, Segmented, Skeleton, StatusPill, VisibilityPill, inputClass } from '@/components/ui'
import { formatDisplay } from '@/lib/placeId'
import { can } from '@/lib/permissions'
import type { Place } from '@/lib/types'
import { useAsync } from '@/lib/useAsync'
import { listPlaces } from '@/lib/api'

type Filter = 'all' | 'active' | 'pending_verification'

export function PlacesPage() {
  const { role } = useSession()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<Filter>('all')
  const { data, loading, error, reload } = useAsync(() => listPlaces({ q, status }), [q, status])

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 p-4 md:p-7">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <h1 className="m-0 text-[22px] font-bold">Places</h1>
          <p className="m-0 text-[13px] text-muted">Houses and buildings in your jurisdiction. Open one to see its units.</p>
        </div>
        {role && can(role, 'place:create') && (
          <Link to="/staff/register">
            <Button variant="primary" icon={PlusCircle}>
              Register place
            </Button>
          </Link>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-10 min-w-[240px] flex-1 items-center gap-2 rounded-[10px] border border-border bg-surface px-3 text-muted focus-within:border-accent">
          <Search size={16} aria-hidden />
          <input aria-label="Search places" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, address or ID" className={`${inputClass} !h-full border-0 !bg-transparent !px-0 focus-visible:!outline-none`} />
        </div>
        <div className="w-full sm:w-[300px]">
          <Segmented
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: 'All' },
              { value: 'active', label: 'Active' },
              { value: 'pending_verification', label: 'Pending' },
            ]}
          />
        </div>
      </div>
      {error && <InlineError title="Could not load places" text={error} onRetry={reload} />}
      <Card className="overflow-hidden">
        {loading && !data ? (
          <div className="flex flex-col gap-3 p-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : data && data.length === 0 ? (
          <EmptyState icon={SearchX} title="No places match" text="Try a different search or clear the status filter." action={<Button onClick={() => { setQ(''); setStatus('all') }}>Clear filters</Button>} />
        ) : (
          <ul className="m-0 list-none p-0">
            {data?.map((p) => (
              <PlaceRow key={p.id} place={p} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function PlaceRow({ place: p }: { place: Place }) {
  const Icon = p.type === 'building' ? Building2 : Home
  return (
    <li className="border-b border-border last:border-b-0">
      <Link to={`/staff/places/${p.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 no-underline text-text transition-colors hover:bg-surface-2">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
          <Icon size={20} aria-hidden />
        </span>
        <span className="min-w-[180px] flex-1">
          <span className="block font-semibold">{p.name}</span>
          <span className="block text-[13px] text-muted">
            {p.locality} · {p.postalPin}
          </span>
        </span>
        <span className="hidden font-mono text-xs text-muted tnum sm:block">{p.publicId ? formatDisplay(p.publicId) : 'ID issued on submit'}</span>
        <span className="flex items-center gap-2">
          <VisibilityPill visibility={p.visibility} />
          <StatusPill status={p.status} />
        </span>
      </Link>
    </li>
  )
}
