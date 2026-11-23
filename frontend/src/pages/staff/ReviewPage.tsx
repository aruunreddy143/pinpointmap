import { useMemo, useState } from 'react'
import { Check, CheckCheck, CircleAlert, ShieldOff, X } from 'lucide-react'
import { useSession } from '@/app/providers'
import { MapView } from '@/components/LazyMap'
import { useToast } from '@/components/toast'
import { Button, Card, EmptyState, InlineError, Segmented, Skeleton, cx, inputClass } from '@/components/ui'
import { can } from '@/lib/permissions'
import type { ReviewItem } from '@/lib/types'
import { useAsync } from '@/lib/useAsync'
import { decide, listReview } from '@/lib/api'

export function ReviewPage() {
  const { role } = useSession()
  const toast = useToast()
  const [kind, setKind] = useState<ReviewItem['kind']>('new')
  const queue = useAsync(() => listReview(kind), [kind])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const items = useMemo(() => queue.data ?? [], [queue.data])
  // Falls back to the first item when nothing (or a vanished item) is selected.
  const current = items.find((i) => i.id === selectedId) ?? items[0] ?? null

  if (!role || !can(role, 'place:verify')) {
    return <div className="p-6"><EmptyState icon={ShieldOff} title="You can't review places" text="Only verifiers and admins can approve or reject. Ask an admin for the verifier role." /></div>
  }

  const act = async (decision: 'approve' | 'reject') => {
    if (!current) return
    setBusy(true)
    setError(null)
    const err = await decide(current.placeId, decision, reason)
    setBusy(false)
    if (err) {
      setError(err)
      return
    }
    setReason('')
    toast(decision === 'approve' ? `Approved. ${current.place.name} is active and its label can be printed.` : `Rejected ${current.place.name}.`)
    queue.reload()
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 p-4 md:p-7">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <h1 className="m-0 text-[22px] font-bold">Review queue</h1>
          <p className="m-0 text-[13px] text-muted">{items.length} waiting · oldest first · you can't approve your own submissions</p>
        </div>
        <div className="w-full sm:w-[340px]">
          <Segmented label="Queue" value={kind} onChange={setKind} options={[{ value: 'new', label: 'New places' }, { value: 'change', label: 'Changes' }, { value: 'merge', label: 'Merges' }]} />
        </div>
      </div>
      {queue.error && <InlineError title="Could not load the queue" text={queue.error} onRetry={queue.reload} />}
      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[380px_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          {queue.loading && !queue.data ? (
            <div className="flex flex-col gap-3 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
          ) : items.length === 0 ? (
            <EmptyState icon={CheckCheck} title="All caught up" text={kind === 'new' ? 'No places are waiting for verification.' : 'Nothing in this queue yet. Corrections from users will appear here.'} />
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1 p-2">
              {items.map((i) => (
                <li key={i.id}>
                  <button type="button" onClick={() => { setSelectedId(i.id); setError(null); setReason('') }} aria-pressed={i.id === current?.id} className={cx('flex w-full flex-col gap-1 rounded-xl border p-3 text-left transition-colors', i.id === current?.id ? 'border-accent bg-accent-soft' : 'border-transparent hover:bg-surface-2')}>
                    <span className="flex items-center gap-2"><span className="flex-1 font-semibold">{i.place.name}</span><span className="text-xs text-muted">{i.ageLabel}</span></span>
                    <span className="text-[12.5px] text-muted">{i.place.type === 'building' ? 'Apartment building' : 'House'} · {i.place.locality} · by {i.submittedBy}</span>
                    <span className={cx('text-xs font-semibold', i.duplicateSuspect ? 'text-warn' : 'text-muted')}>{i.duplicateSuspect ? `Possible duplicate: ${i.nearestM} m` : i.nearestM === null ? "No other place nearby" : `Nearest place ${i.nearestM} m`}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {current && (
          <Card className="flex min-w-0 flex-col overflow-hidden" aria-label="Review detail">
            <div className="flex flex-wrap items-center gap-3 border-b border-border px-6 py-4">
              <div className="flex-1">
                <div className="text-lg font-bold">{current.place.name}</div>
                <div className="text-[13px] text-muted">{current.place.address}, {current.place.locality} · submitted by {current.submittedBy}</div>
              </div>
            </div>
            <div className="grid flex-1 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div className="relative h-[300px] xl:h-auto xl:min-h-[320px]">
                <MapView key={current.place.id} ariaLabel="Submitted pin" center={current.place.geo} zoom={17} markers={[{ id: current.place.id, geo: current.place.geo, status: current.place.status, label: current.place.name }]} selectedId={current.place.id} className="absolute inset-0" />
              </div>
              <div className="flex flex-col gap-3.5 border-t border-border p-5 xl:border-l xl:border-t-0">
                <div className="font-bold">Checklist</div>
                {current.checks.map((c) => (
                  <div key={c.title} className="flex items-start gap-2.5">
                    <span className={cx('mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full', c.ok ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn')}>
                      {c.ok ? <Check size={12} strokeWidth={3} aria-hidden /> : <CircleAlert size={12} strokeWidth={3} aria-hidden />}
                    </span>
                    <div><div className="text-[13px] font-semibold">{c.title}</div><div className="text-xs text-muted">{c.detail}</div></div>
                  </div>
                ))}
              </div>
            </div>
            {error && <div className="px-6 pt-4"><InlineError title="Can't do that" text={error} /></div>}
            <div className="flex flex-wrap items-center gap-3 border-t border-border px-6 py-4">
              <input aria-label="Reason (required to reject)" placeholder="Reason (required to reject)" value={reason} onChange={(e) => setReason(e.target.value)} className={`${inputClass} min-w-[200px] flex-1`} />
              <Button variant="danger" icon={X} disabled={busy} onClick={() => act('reject')}>Reject</Button>
              <Button variant="primary" icon={Check} loading={busy} onClick={() => act('approve')}>Approve and activate</Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
