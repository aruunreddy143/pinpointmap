import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Printer, SearchX } from 'lucide-react'
import { useSession } from '@/app/providers'
import { PlaceIdChip, QrCode } from '@/components/codes'
import { useToast } from '@/components/toast'
import { Button, Card, EmptyState, InlineError, Pill, Skeleton, StatusPill, VisibilityPill, cx } from '@/components/ui'
import { can } from '@/lib/permissions'
import { formatDisplay } from '@/lib/placeId'
import { useAsync } from '@/lib/useAsync'
import { getPlace, listHistory, listUnits, setVisibility } from '@/mocks/api'

const TONE = { ok: 'bg-ok', accent: 'bg-accent', warn: 'bg-warn', muted: 'bg-muted' }

export function PlaceDetailPage() {
  const { id = '' } = useParams()
  const { role } = useSession()
  const toast = useToast()
  const place = useAsync(() => getPlace(id), [id])
  const units = useAsync(() => listUnits(id), [id])
  const history = useAsync(() => listHistory(id), [id])
  const [busy, setBusy] = useState(false)

  if (place.loading && !place.data) {
    return (
      <div className="mx-auto max-w-6xl p-4 md:p-7">
        <Skeleton className="mb-6 h-9 w-72" />
        <div className="grid gap-5 lg:grid-cols-[340px_1fr_300px]">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    )
  }
  if (place.error) return <div className="p-6"><InlineError title="Could not load this place" text={place.error} onRetry={place.reload} /></div>
  // Out-of-jurisdiction places answer 404 (not 403) so their existence is not revealed.
  if (!place.data) return <div className="p-6"><EmptyState icon={SearchX} title="Place not found" text="It may not exist or may be outside your jurisdiction." action={<Link to="/staff/places"><Button>Back to places</Button></Link>} /></div>

  const p = place.data
  const canPrint = !!role && can(role, 'place:print') && !!p.publicId && p.status === 'active'
  const canEdit = !!role && can(role, 'place:update')

  const makePublic = async () => {
    setBusy(true)
    await setVisibility(p.id, p.visibility === 'public' ? 'private' : 'public')
    setBusy(false)
    place.reload()
    toast(p.visibility === 'public' ? 'Place is now private' : 'Place is now public')
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 p-4 md:p-7">
      <div>
        <div className="mb-2 text-[13px] text-muted">
          <Link to="/staff/places" className="text-muted">Places</Link> / {p.locality} / <span className="font-medium text-text">{p.name}</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="m-0 text-2xl font-bold">{p.name}</h1>
          <StatusPill status={p.status} />
          <VisibilityPill visibility={p.visibility} />
          <div className="flex-1" />
          {canEdit && <Button disabled title="Editing arrives with the backend">Edit</Button>}
          {canEdit && p.status === 'active' && (
            <Button loading={busy} onClick={makePublic}>
              {p.visibility === 'public' ? 'Make private' : 'Request public'}
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)_300px]">
        <Card className="flex flex-col gap-4 p-5">
          {p.publicId ? (
            <>
              <div className="self-center rounded-xl border border-border bg-white p-3.5">
                <QrCode publicId={p.publicId} size={168} />
              </div>
              <PlaceIdChip publicId={p.publicId} />
            </>
          ) : (
            <p className="m-0 text-muted">The PINPOINT ID is issued when the place is submitted.</p>
          )}
          {canPrint && (
            <Link to={`/staff/places/${p.id}/label`}>
              <Button variant="primary" icon={Printer} className="w-full">Print label</Button>
            </Link>
          )}
          {!canPrint && p.status !== 'active' && <p className="m-0 text-[13px] text-muted">Labels can be printed once the place is verified and active.</p>}
          <dl className="m-0 grid grid-cols-2 gap-3.5 border-t border-border pt-3">
            <Fact k="Coordinates" v={`${p.geo.lat.toFixed(6)}, ${p.geo.lon.toFixed(6)}`} mono />
            <Fact k="Accuracy" v={`± ${p.accuracyM} m · GPS`} />
            <Fact k="District" v={p.district} />
            <Fact k="PIN code" v={p.postalPin} />
          </dl>
        </Card>

        <Card className="flex min-w-0 flex-col overflow-hidden">
          <div className="flex items-center gap-3 border-b border-border px-5 py-4">
            <div className="flex-1">
              <div className="text-base font-bold">Units</div>
              <div className="text-[13px] text-muted">{units.data ? `${units.data.length} units` : 'Loading units'}</div>
            </div>
            {!!units.data?.length && canPrint && <Button size="sm" disabled title="Bulk printing arrives with the backend">Print all labels</Button>}
          </div>
          {units.loading ? (
            <div className="flex flex-col gap-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : !units.data?.length ? (
            <EmptyState icon={SearchX} title="No units" text={p.type === 'building' ? 'Add apartment units to give each door its own ID.' : 'A house is a single place and has no units.'} />
          ) : (
            <div className="max-h-[520px] overflow-y-auto">
              <div className="grid grid-cols-[56px_1fr_84px] gap-2 border-b border-border bg-surface-2 px-5 py-2.5 text-xs font-semibold text-muted">
                <span>Unit</span><span>PINPOINT ID</span><span>Status</span>
              </div>
              {units.data.map((u) => (
                <div key={u.id} className="grid h-12 grid-cols-[56px_1fr_84px] items-center gap-2 border-b border-border px-5">
                  <span className="font-semibold tnum">{u.label}</span>
                  <span className="truncate font-mono text-[11px] text-muted tnum">{u.publicId ? formatDisplay(u.publicId) : ''}</span>
                  <StatusPill status={u.status} />
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-5 lg:col-span-2 xl:col-span-1">
          <h2 className="m-0 mb-4 text-base font-bold">History</h2>
          {history.loading ? (
            <div className="flex flex-col gap-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : !history.data?.length ? (
            <p className="m-0 text-[13px] text-muted">No history yet.</p>
          ) : (
            <ol className="m-0 flex list-none flex-col gap-4 p-0">
              {history.data.map((e) => (
                <li key={e.id} className="flex gap-3">
                  <span className={cx('mt-1.5 size-2.5 shrink-0 rounded-full', TONE[e.tone])} />
                  <div>
                    <div className="font-semibold">{e.title}</div>
                    <div className="text-xs text-muted">{e.actor} · {e.at}</div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
      <div>
        <Pill tone="grey">Mock data. Edits are not saved.</Pill>
      </div>
    </div>
  )
}

function Fact({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div>
      <dt className="mb-0.5 text-xs text-muted">{k}</dt>
      <dd className={cx('m-0 font-semibold', mono ? 'font-mono text-xs tnum' : 'tnum')}>{v}</dd>
    </div>
  )
}
