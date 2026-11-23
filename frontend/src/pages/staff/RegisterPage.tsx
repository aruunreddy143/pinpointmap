import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, CircleAlert, LocateFixed, Lock, ShieldOff } from 'lucide-react'
import { useSession } from '@/app/providers'
import { MapView } from '@/components/LazyMap'
import { useToast } from '@/components/toast'
import { Button, Card, EmptyState, Field, Pill, Segmented, cx, inputClass } from '@/components/ui'
import { can } from '@/lib/permissions'
import { formatDisplay } from '@/lib/placeId'
import type { LatLon, Place } from '@/lib/types'
import { parseUnitLabels } from '@/lib/units'
import { createAndSubmit, findNearby } from '@/lib/api'

const STEPS = ['Location', 'Details', 'Visibility', 'Review'] as const
const DUPLICATE_RADIUS_M = 15
const MAX_GOOD_ACCURACY_M = 20

type Nearby = Place & { distanceM: number }

export function RegisterPage() {
  const { role } = useSession()
  const toast = useToast()
  const nav = useNavigate()
  const [step, setStep] = useState(0)
  const [type, setType] = useState<'house' | 'building'>('building')
  const [geo, setGeo] = useState<LatLon>({ lat: 12.97165, lon: 77.5946 })
  const [accuracy, setAccuracy] = useState(4)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [landmark, setLandmark] = useState('')
  const [unitText, setUnitText] = useState('101-110')
  const [nearby, setNearby] = useState<Nearby[]>([])
  const [override, setOverride] = useState(false)
  const [reason, setReason] = useState('')
  const [confirmAccuracy, setConfirmAccuracy] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let live = true
    findNearby(geo, DUPLICATE_RADIUS_M).then((n) => live && setNearby(n))
    return () => {
      live = false
    }
  }, [geo])

  const units = useMemo(() => (type === 'building' ? parseUnitLabels(unitText) : { labels: [], error: null }), [type, unitText])
  const lowAccuracy = accuracy > MAX_GOOD_ACCURACY_M

  if (!role || !can(role, 'place:create')) {
    return <div className="p-6"><EmptyState icon={ShieldOff} title="You can't register places" text="Your role does not include creating places. Ask an admin to assign the registrar role." /></div>
  }

  const duplicateBlocks = nearby.length > 0 && !(override && reason.trim().length > 0)
  const accuracyBlocks = lowAccuracy && !confirmAccuracy
  const locationOk = !duplicateBlocks && !accuracyBlocks
  const detailsOk = name.trim().length > 1 && address.trim().length > 1 && !units.error && (type === 'house' || units.labels.length > 0)
  const canNext = step === 0 ? locationOk : step === 1 ? detailsOk : true

  const submit = async () => {
    setSaving(true)
    try {
      const place = await createAndSubmit({
        type,
        name: name.trim(),
        geo,
        accuracyM: accuracy,
        address: address.trim(),
        landmark: landmark.trim(),
        unitLabels: units.labels,
        differentPlaceReason: nearby.length > 0 ? reason.trim() : undefined,
      })
      toast(`Submitted. ID ${place.publicId ? formatDisplay(place.publicId) : ''} issued, waiting for a verifier.`)
      nav(`/staff/places/${place.id}`)
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Could not submit. Please try again.', 'bad')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 p-4 md:p-7">
      <div>
        <h1 className="m-0 mb-0.5 text-[22px] font-bold">Register a place</h1>
        <p className="m-0 text-[13px] text-muted">The PINPOINT ID is issued when you submit. A different verifier must approve it.</p>
      </div>
      <ol className="m-0 flex list-none flex-wrap items-center gap-x-3 gap-y-2 p-0" aria-label="Progress">
        {STEPS.map((label, i) => (
          <li key={label} className="flex items-center gap-2.5" aria-current={i === step ? 'step' : undefined}>
            <span className={cx('flex size-7 items-center justify-center rounded-full border text-[13px] font-bold', i < step ? 'border-ok bg-ok-soft text-ok' : i === step ? 'border-accent bg-accent text-accent-ink' : 'border-border bg-surface text-muted')}>
              {i < step ? <Check size={14} aria-hidden /> : i + 1}
            </span>
            <span className={cx('font-semibold', i === step ? 'text-text' : 'text-muted')}>{label}</span>
            {i < STEPS.length - 1 && <span className="hidden h-0.5 w-8 rounded bg-border sm:block" />}
          </li>
        ))}
      </ol>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,470px)_minmax(0,1fr)]">
        <Card className="flex flex-col gap-4 p-5">
          {step === 0 && (
            <>
              <div>
                <span className="mb-1.5 block text-xs font-semibold text-muted">Place type</span>
                <Segmented label="Place type" value={type} onChange={setType} options={[{ value: 'house', label: 'House' }, { value: 'building', label: 'Apartment building' }]} />
              </div>
              <div>
                <span className="mb-1.5 block text-xs font-semibold text-muted">Pin location</span>
                <dl className="m-0 flex flex-col gap-2.5 rounded-xl border border-border bg-surface-2 p-3.5">
                  <Row k="Coordinates" v={`${geo.lat.toFixed(6)}° N, ${geo.lon.toFixed(6)}° E`} mono />
                  <Row k="Accuracy" v={lowAccuracy ? `± ${accuracy} m, poor` : `± ${accuracy} m, good`} tone={lowAccuracy ? 'warn' : 'ok'} />
                  <Row k="Locality" v="Indiranagar, Bengaluru 560038" />
                </dl>
                <p className="m-0 mt-2 text-xs text-muted">Drag the pin or click the map. The ID's location cell is computed by the server when you submit.</p>
              </div>
              <div className="flex gap-2">
                <Button icon={LocateFixed} onClick={() => setAccuracy(4)}>Use my GPS (± 4 m)</Button>
                <Button onClick={() => setAccuracy(28)} title="Demo: simulate a weak GPS fix">Simulate weak GPS</Button>
              </div>
              {lowAccuracy && (
                <div role="alert" className="flex items-start gap-3 rounded-xl bg-warn-soft p-3.5 text-sm">
                  <CircleAlert size={18} className="mt-0.5 shrink-0 text-warn" aria-hidden />
                  <div className="flex-1">
                    <div className="font-bold">GPS is weaker than ± {MAX_GOOD_ACCURACY_M} m</div>
                    <p className="m-0 mt-1">Check the pin on the satellite layer before continuing.</p>
                    <label className="mt-2 flex items-center gap-2 font-semibold"><input type="checkbox" checked={confirmAccuracy} onChange={(e) => setConfirmAccuracy(e.target.checked)} />I checked the pin on the map</label>
                  </div>
                </div>
              )}
            </>
          )}

          {step === 1 && (
            <>
              <Field label={type === 'building' ? 'Building name' : 'House name or number'} htmlFor="name"><input id="name" className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="Sunrise Apartments" /></Field>
              <Field label="Street address" htmlFor="addr"><input id="addr" className={inputClass} value={address} onChange={(e) => setAddress(e.target.value)} placeholder="12th Main, Indiranagar" /></Field>
              <Field label="Landmark (optional)" htmlFor="lm"><input id="lm" className={inputClass} value={landmark} onChange={(e) => setLandmark(e.target.value)} placeholder="Opposite Metro Station, Gate 2" /></Field>
              {type === 'building' && (
                <Field label="Unit labels" htmlFor="units" hint="Ranges and single labels, separated by commas. Example: 101-110, 201-210, 3A">
                  <input id="units" className={cx(inputClass, units.error && 'border-bad')} value={unitText} onChange={(e) => setUnitText(e.target.value)} aria-invalid={!!units.error} aria-describedby="units-preview" />
                  <div id="units-preview" className={cx('mt-2 text-[13px]', units.error ? 'font-semibold text-bad' : 'text-muted')} role={units.error ? 'alert' : undefined}>
                    {units.error ?? `${units.labels.length} units: ${units.labels.slice(0, 6).join(', ')}${units.labels.length > 6 ? ', …' : ''}`}
                  </div>
                </Field>
              )}
            </>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-start gap-3 rounded-xl border border-accent bg-accent-soft p-4">
                <Lock size={18} className="mt-0.5 text-accent" aria-hidden />
                <div><div className="font-bold">Private (default)</div><p className="m-0 mt-1 text-[13px] text-muted">Scanning the code shows only "Registered PINPOINT place". Address and location stay hidden.</p></div>
              </div>
              <div className="rounded-xl border border-border p-4 text-[13px] text-muted">Making a place public needs the owner's recorded consent and a verifier's approval. Do that from the place page after it is active.</div>
            </div>
          )}

          {step === 3 && (
            <dl className="m-0 flex flex-col gap-2.5">
              <Row k="Type" v={type === 'building' ? 'Apartment building' : 'House'} />
              <Row k="Name" v={name} />
              <Row k="Address" v={address} />
              {landmark && <Row k="Landmark" v={landmark} />}
              <Row k="Coordinates" v={`${geo.lat.toFixed(6)}, ${geo.lon.toFixed(6)}`} mono />
              <Row k="Accuracy" v={`± ${accuracy} m`} />
              {type === 'building' && <Row k="Units" v={String(units.labels.length)} />}
              <Row k="Visibility" v="Private" />
            </dl>
          )}

          <div className="mt-auto flex items-center justify-between border-t border-border pt-4">
            <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
            {step < 3 ? (
              <Button variant="primary" disabled={!canNext} onClick={() => setStep(step + 1)}>Continue <ArrowRight size={16} aria-hidden /></Button>
            ) : (
              <Button variant="primary" loading={saving} onClick={submit}>Submit for verification</Button>
            )}
          </div>
        </Card>

        <div className="flex min-w-0 flex-col gap-4">
          <Card className="relative h-[420px] overflow-hidden lg:h-[480px]">
            <MapView ariaLabel="Pin location map" center={geo} zoom={17} pin={{ geo, onMove: setGeo }} className="absolute inset-0" />
          </Card>
          {step === 0 && nearby.length > 0 && (
            <div role="alert" className="flex items-start gap-3 rounded-xl bg-warn-soft p-4">
              <CircleAlert size={20} className="mt-0.5 shrink-0 text-warn" aria-hidden />
              <div className="flex-1 text-sm">
                <div className="font-bold">Similar place{nearby.length > 1 ? 's' : ''} within {DUPLICATE_RADIUS_M} m</div>
                <ul className="m-0 mt-1 list-none p-0">
                  {nearby.map((n) => (
                    <li key={n.id}>“{n.name}” · {n.type === 'building' ? 'Building' : 'House'} · {n.distanceM} m away</li>
                  ))}
                </ul>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Link to={`/staff/places/${nearby[0].id}`}><Button size="sm" variant="primary">Open existing</Button></Link>
                  <Button size="sm" onClick={() => setOverride(true)} disabled={override}>This is different…</Button>
                </div>
                {override && (
                  <div className="mt-3">
                    <Field label="Why is this a different place? (required)" htmlFor="reason"><input id="reason" className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Separate building next door" /></Field>
                    {reason.trim() && <Pill tone="ok" icon={Check}>Reason recorded</Pill>}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Row({ k, v, mono, tone }: { k: string; v: string; mono?: boolean; tone?: 'ok' | 'warn' }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted">{k}</dt>
      <dd className={cx('m-0 text-right font-medium', mono && 'font-mono text-[12.5px] tnum', tone === 'ok' && 'font-semibold text-ok', tone === 'warn' && 'font-semibold text-warn')}>{v}</dd>
    </div>
  )
}
