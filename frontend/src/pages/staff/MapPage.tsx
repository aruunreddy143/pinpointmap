import { useCallback, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Lock, MapPinned, Printer, Search } from 'lucide-react'
import { useSession } from '@/app/providers'
import { MapView } from '@/components/LazyMap'
import type { MapMarker } from '@/components/MapView'
import { PlaceIdChip } from '@/components/codes'
import { Button, Pill, Skeleton, StatusPill, inputClass } from '@/components/ui'
import { can } from '@/lib/permissions'
import { formatDisplay } from '@/lib/placeId'
import { useAsync } from '@/lib/useAsync'
import { listPlaces, listUnits } from '@/lib/api'

export function MapPage() {
  const { role } = useSession()
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<string | null>('p1')
  const places = useAsync(() => listPlaces({ q }), [q])
  const units = useAsync(() => (selected ? listUnits(selected) : Promise.resolve([])), [selected])
  const select = useCallback((id: string) => setSelected(id), [])

  const markers: MapMarker[] = useMemo(() => (places.data ?? []).map((p) => ({ id: p.id, geo: p.geo, status: p.status, label: p.name })), [places.data])
  const place = places.data?.find((p) => p.id === selected) ?? null
  const center = place?.geo ?? { lat: 12.9716, lon: 77.5946 }
  const wide = typeof window !== 'undefined' && window.matchMedia('(min-width: 768px)').matches

  return (
    <div className="flex h-full min-h-[640px] flex-col md:relative md:min-h-0">
      <div className="relative h-[46vh] min-h-[280px] md:absolute md:inset-0 md:h-auto">
        <MapView ariaLabel="Map of registered places" markers={markers} selectedId={selected} onSelect={select} center={center} zoom={14} padRight={wide ? 380 : 0} className="absolute inset-0" />
        <div className="absolute left-3 top-3 z-10 flex h-11 w-[min(420px,calc(100%-24px))] items-center gap-2.5 rounded-xl border border-border bg-surface px-3.5 text-muted shadow-card">
          <Search size={18} aria-hidden />
          <input aria-label="Search places on the map" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, address or ID" className={`${inputClass} !h-full border-0 !bg-transparent !px-0 focus-visible:!outline-none`} />
        </div>
      </div>
      <aside aria-label="Place details" className="flex min-h-0 flex-1 flex-col overflow-hidden border-t border-border bg-surface md:absolute md:bottom-4 md:right-4 md:top-4 md:w-[360px] md:flex-none md:rounded-2xl md:border md:shadow-card">
        {!place ? (
          places.loading ? (
            <div className="flex flex-col gap-3 p-5">
              <Skeleton className="h-6 w-24" />
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-12" />
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center text-muted">
              <MapPinned size={28} aria-hidden />
              <div className="font-semibold text-text">Select a place</div>
              <div className="text-sm">Click a pin on the map to see its details.</div>
            </div>
          )
        ) : (
          <>
            <div className="border-b border-border p-5">
              <div className="mb-3 flex flex-wrap gap-2">
                <Pill tone="accent">{place.type === 'building' ? 'Building' : 'House'}</Pill>
                <StatusPill status={place.status} />
              </div>
              <h2 className="m-0 mb-1 text-xl font-bold">{place.name}</h2>
              <div className="text-[13px] text-muted">{place.address}, {place.locality} {place.postalPin}</div>
              {place.publicId && (
                <div className="mt-3.5">
                  <PlaceIdChip publicId={place.publicId} />
                </div>
              )}
            </div>
            <dl className="m-0 grid grid-cols-2 gap-3.5 border-b border-border p-5">
              <Fact k="Units" v={units.loading ? '…' : String(units.data?.length ?? 0)} />
              <Fact k="Pin accuracy" v={`± ${place.accuracyM ?? "?"} m · GPS`} />
              <Fact k="Visibility" v={place.visibility === 'private' ? 'Private' : 'Public'} icon={place.visibility === 'private'} />
              <Fact k="Verified" v={place.verifiedAt ?? 'Not yet'} />
            </dl>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
              {units.loading ? (
                <div className="flex flex-col gap-2 p-2">
                  <Skeleton className="h-9" />
                  <Skeleton className="h-9" />
                </div>
              ) : (units.data?.length ?? 0) === 0 ? (
                <p className="p-3 text-[13px] text-muted">No units. This is a single place.</p>
              ) : (
                <ul className="m-0 list-none p-0">
                  {units.data!.slice(0, 8).map((u) => (
                    <li key={u.id} className="flex h-10 items-center gap-3 rounded-lg px-2">
                      <span className="w-12 font-semibold tnum">{u.label}</span>
                      <span className="flex-1 truncate font-mono text-[11.5px] text-muted">{u.publicId ? formatDisplay(u.publicId) : ''}</span>
                      <StatusPill status={u.status} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex gap-2 border-t border-border p-4">
              <Link to={`/staff/places/${place.id}`} className="flex-1">
                <Button variant="primary" className="w-full">
                  Open details
                </Button>
              </Link>
              {role && can(role, 'place:print') && place.publicId && (
                <Link to={`/staff/places/${place.id}/label`}>
                  <Button icon={Printer} aria-label="Print label">
                    Label
                  </Button>
                </Link>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function Fact({ k, v, icon }: { k: string; v: string; icon?: boolean }) {
  return (
    <div>
      <dt className="mb-0.5 text-xs text-muted">{k}</dt>
      <dd className="m-0 flex items-center gap-1.5 font-semibold tnum">
        {icon && <Lock size={13} aria-hidden />}
        {v}
      </dd>
    </div>
  )
}
