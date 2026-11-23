import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Flag, Navigation } from 'lucide-react'
import { PlaceIdChip } from './codes'
import { MapView } from './LazyMap'
import { useToast } from './toast'
import { Button, Card, Pill, inputClass } from './ui'
import { formatDisplay } from '@/lib/placeId'
import type { Place } from '@/lib/types'
import { submitCorrection } from '@/lib/api'

/** Read-only view of a public place. No edit, print, history or status-change controls exist here. */
export function PublicPlaceView({ place, units, canReport, backTo }: { place: Place; units: Place[]; canReport: boolean; backTo?: string }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const send = async () => {
    setBusy(true)
    await submitCorrection(place.id, note.trim())
    setBusy(false)
    setOpen(false)
    setNote('')
    toast('Thanks. Your report was sent to the verifiers.')
  }

  return (
    <div className="flex flex-col gap-4 pb-4">
      {backTo && <Link to={backTo} className="text-[13px] text-muted">← Back to search</Link>}
      <Card className="relative h-[170px] overflow-hidden">
        <MapView ariaLabel={`Map showing ${place.name}`} center={place.geo} zoom={16} markers={[{ id: place.id, geo: place.geo, status: place.status, label: place.name }]} selectedId={place.id} className="absolute inset-0" />
      </Card>
      <div>
        <div className="mb-2.5 flex gap-2">
          <Pill tone="accent">{place.type === 'building' ? 'Apartment building' : 'House'}</Pill>
          <Pill tone="ok" icon={Check}>Verified</Pill>
        </div>
        <h1 className="m-0 mb-1 text-2xl font-bold">{place.name}</h1>
        <p className="m-0 leading-relaxed text-muted">{place.address}, {place.locality} {place.postalPin}{place.landmark && <><br />{place.landmark}</>}</p>
      </div>
      {place.publicId && <PlaceIdChip publicId={place.publicId} />}
      <div className="flex gap-2.5">
        <a className="flex-1 no-underline" target="_blank" rel="noopener noreferrer" href={`https://www.google.com/maps/search/?api=1&query=${place.geo.lat},${place.geo.lon}`}>
          <Button variant="primary" size="lg" icon={Navigation} className="w-full">Open in Maps</Button>
        </a>
      </div>
      {units.length > 0 && (
        <Card className="overflow-hidden">
          <div className="flex justify-between border-b border-border px-4 py-3"><span className="font-bold">Units</span><span className="text-[13px] text-muted tnum">{units.length} total</span></div>
          <ul className="m-0 max-h-60 list-none overflow-y-auto p-0">
            {units.slice(0, 20).map((u) => (
              <li key={u.id} className="flex h-11 items-center gap-3 border-b border-border px-4 last:border-b-0">
                <span className="w-12 font-semibold tnum">{u.label}</span>
                <span className="truncate font-mono text-[11px] text-muted tnum">{u.publicId ? formatDisplay(u.publicId) : ''}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Card className="flex flex-col gap-3 p-4">
        <div className="flex items-center gap-3">
          <span className="flex-1 text-[13px] text-muted">Something wrong or out of date?</span>
          {canReport ? (
            <Button icon={Flag} onClick={() => setOpen(!open)} aria-expanded={open}>Report a problem</Button>
          ) : (
            <Link to="/"><Button>Sign in to report</Button></Link>
          )}
        </div>
        {open && (
          <div className="flex flex-col gap-2">
            <label htmlFor="report-note" className="text-xs font-semibold text-muted">What is wrong? (max 500 characters)</label>
            <textarea id="report-note" maxLength={500} rows={3} value={note} onChange={(e) => setNote(e.target.value)} className={`${inputClass} h-auto py-2`} placeholder="The gate is on the other side of the building" />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" loading={busy} disabled={note.trim().length < 5} onClick={send}>Send report</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
