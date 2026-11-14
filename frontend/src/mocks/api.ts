import { validate } from '@/lib/placeId'
import type { LatLon, Place, PlaceEvent, ReviewItem, Resolution, Role } from '@/lib/types'
import { isStaff } from '@/lib/permissions'
import { makeId, ALPHABET } from '@/lib/placeId'
import { initialEvents, initialPlaces, initialReview, seqFor } from './data'

// In-memory mock of the future backend. Same shapes and rules (visibility, 404 vs 403,
// four-eyes) so screens can be built now and pointed at the real API later.

let places: Place[] = structuredClone(initialPlaces)
let events: PlaceEvent[] = structuredClone(initialEvents)
let review: ReviewItem[] = structuredClone(initialReview)
const corrections: { placeId: string; note: string }[] = []
let counter = 1000

const delay = <T,>(value: T, ms = 220): Promise<T> => new Promise((r) => setTimeout(() => r(value), ms))

export function resetMock(): void {
  places = structuredClone(initialPlaces)
  events = structuredClone(initialEvents)
  review = structuredClone(initialReview)
  corrections.length = 0
}

export function distanceM(a: LatLon, b: LatLon): number {
  const R = 6371000
  const rad = (d: number) => (d * Math.PI) / 180
  const dLat = rad(b.lat - a.lat)
  const dLon = rad(b.lon - a.lon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

const isTop = (p: Place) => p.type !== 'unit'

export interface PlaceQuery {
  q?: string
  status?: Place['status'] | 'all'
}

export function listPlaces(query: PlaceQuery = {}): Promise<Place[]> {
  const q = query.q?.trim().toLowerCase() ?? ''
  const out = places.filter(isTop).filter((p) => {
    if (query.status && query.status !== 'all' && p.status !== query.status) return false
    if (!q) return true
    return [p.name, p.address, p.locality, p.publicId ?? ''].join(' ').toLowerCase().includes(q)
  })
  return delay(out)
}

export function getPlace(id: string): Promise<Place | null> {
  return delay(places.find((p) => p.id === id) ?? null)
}

export function listUnits(parentId: string): Promise<Place[]> {
  return delay(places.filter((p) => p.parentId === parentId))
}

export function listHistory(placeId: string): Promise<PlaceEvent[]> {
  return delay(events.filter((e) => e.placeId === placeId))
}

export function listReview(kind: ReviewItem['kind']): Promise<(ReviewItem & { place: Place })[]> {
  const out = review
    .filter((r) => r.kind === kind)
    .map((r) => ({ ...r, place: places.find((p) => p.id === r.placeId)! }))
    .filter((r) => r.place)
  return delay(out)
}

export function findNearby(geo: LatLon, radiusM = 15): Promise<(Place & { distanceM: number })[]> {
  const out = places
    .filter(isTop)
    .filter((p) => p.status === 'active' || p.status === 'pending_verification')
    .map((p) => ({ ...p, distanceM: Math.round(distanceM(geo, p.geo)) }))
    .filter((p) => p.distanceM <= radiusM)
    .sort((a, b) => a.distanceM - b.distanceM)
  return delay(out, 150)
}

export interface NewPlaceInput {
  type: 'house' | 'building'
  name: string
  geo: LatLon
  accuracyM: number
  address: string
  landmark: string
  unitLabels: string[]
}

/** Mock: derive an illustrative geo cell from coordinates. The real one is DIGIPIN, computed on the backend. */
function mockGeoCell(g: LatLon): string {
  let v = Math.abs(Math.round(g.lat * 1e5)) * 31 + Math.abs(Math.round(g.lon * 1e5))
  let out = ''
  for (let i = 0; i < 10; i++) {
    out += ALPHABET[v % 16]
    v = Math.floor(v / 16) + 7 * (i + 1)
  }
  return out
}

export function createAndSubmit(input: NewPlaceInput, actor: string): Promise<Place> {
  const id = `n${++counter}`
  const geoCell = mockGeoCell(input.geo)
  const parent: Place = {
    id,
    publicId: makeId(geoCell, seqFor(counter)),
    type: input.type,
    parentId: null,
    label: null,
    name: input.name,
    geo: input.geo,
    accuracyM: input.accuracyM,
    source: 'gps',
    address: input.address,
    landmark: input.landmark,
    locality: 'Indiranagar',
    district: 'Bengaluru Urban',
    state: 'Karnataka',
    postalPin: '560038',
    status: 'pending_verification',
    visibility: 'private',
    createdBy: actor,
    createdAt: '2026-11-14',
    verifiedAt: null,
  }
  places.push(parent)
  input.unitLabels.forEach((label, i) => {
    places.push({ ...parent, id: `${id}-u${i}`, publicId: makeId(geoCell, seqFor(counter * 100 + i)), type: 'unit', parentId: id, label, name: `${input.name}, ${label}` })
  })
  review.push({ id: `r${counter}`, placeId: id, kind: 'new', submittedBy: actor, ageLabel: 'just now', nearestM: 40, duplicateSuspect: false, checks: [{ title: 'Pin accuracy', detail: `± ${input.accuracyM} m`, ok: input.accuracyM <= 20 }] })
  events.push({ id: `ev${counter}`, placeId: id, title: 'Draft submitted', actor, at: 'Just now', tone: 'accent' })
  return delay(parent, 400)
}

/** Four-eyes: the verifier must not be the submitter. Returns an error string or null. */
export function decide(placeId: string, decision: 'approve' | 'reject', reason: string, verifier: string): Promise<string | null> {
  const place = places.find((p) => p.id === placeId)
  if (!place) return delay('Place not found')
  if (place.createdBy === verifier) return delay('You submitted this place, so a different verifier must approve it.')
  if (decision === 'reject' && !reason.trim()) return delay('A reason is required to reject.')
  const next = decision === 'approve' ? 'active' : 'rejected'
  places = places.map((p) => (p.id === placeId || p.parentId === placeId ? { ...p, status: next, verifiedAt: decision === 'approve' ? '2026-11-14' : null } : p))
  review = review.filter((r) => r.placeId !== placeId)
  events.push({ id: `ev${++counter}`, placeId, title: decision === 'approve' ? 'Verified and activated' : `Rejected: ${reason}`, actor: verifier, at: 'Just now', tone: decision === 'approve' ? 'ok' : 'warn' })
  return delay(null, 350)
}

export function setVisibility(placeId: string, visibility: Place['visibility']): Promise<void> {
  places = places.map((p) => (p.id === placeId ? { ...p, visibility } : p))
  return delay(undefined, 200)
}

// ---- Viewer (read-only normal user) ----

export function publicSearch(q: string): Promise<Place[]> {
  const t = q.trim().toLowerCase()
  if (!t) return delay([])
  const out = places
    .filter(isTop)
    .filter((p) => p.visibility === 'public' && p.status === 'active')
    .filter((p) => [p.name, p.address, p.locality, p.publicId ?? ''].join(' ').toLowerCase().includes(t))
  return delay(out)
}

/** Viewer detail: only public + active places exist for a viewer; anything else is a 404. */
export function getPublicPlace(id: string): Promise<{ place: Place; units: Place[] } | null> {
  const place = places.find((p) => p.id === id)
  if (!place || place.visibility !== 'public' || place.status !== 'active') return delay(null)
  return delay({ place, units: places.filter((p) => p.parentId === place.id && p.status !== 'retired') })
}

export function submitCorrection(placeId: string, note: string): Promise<void> {
  corrections.push({ placeId, note })
  return delay(undefined, 300)
}

/** What a scan of /p/{id} shows, depending on who scans. Mirrors the backend resolver rules. */
export function resolve(input: string, role: Role | null): Promise<Resolution> {
  const check = validate(input)
  if (!check.ok) return delay({ kind: 'invalid' }, 80)
  const place = places.find((p) => p.publicId === check.canonical)
  if (!place) return delay({ kind: 'not_found' })
  const units = places.filter((p) => p.parentId === place.id && p.status !== 'retired')
  if (role && isStaff(role)) return delay({ kind: 'staff', place, units })
  if (place.visibility === 'public' && place.status === 'active') return delay({ kind: 'public', place, units })
  return delay({ kind: 'minimal', publicId: check.canonical })
}
