import { ApiError, apiBlob, apiRequest } from './http'
import type { LatLon, LocationSource, Place, PlaceEvent, PlaceStatus, PlaceType, Resolution, ReviewItem, Role, Visibility } from './types'

// Real API client for places, review, public views, staff and audit.
// Wire shapes are snake_case (docs/api-contract.md); this file maps them to the camelCase types the screens use.

// ---------- Wire shapes ----------
interface PlaceDto {
  id: string
  public_id: string | null
  type: PlaceType
  parent_id: string | null
  label: string | null
  name: string
  geo: LatLon
  accuracy_m: number | null
  source: LocationSource
  address: string
  landmark: string
  locality: string
  district: string
  state: string
  postal_pin: string
  status: PlaceStatus
  visibility: Visibility
  jurisdiction_id: string
  created_by_name: string
  created_at: string
  verified_at: string | null
  unit_count?: number | null
}
interface PublicPlaceDto {
  id: string
  public_id: string
  type: PlaceType
  parent_id: string | null
  label: string | null
  name: string
  geo: LatLon
  address: string
  landmark: string
  locality: string
  district: string
  state: string
  postal_pin: string
}
interface EventDto {
  id: string
  place_id: string
  title: string
  actor_name: string
  at: string
  tone: PlaceEvent['tone']
}
interface ReviewDto {
  id: string
  place_id: string
  kind: ReviewItem['kind']
  submitted_by: string
  submitted_at: string
  nearest_m: number | null
  duplicate_suspect: boolean
  checks: ReviewItem['checks']
  place: PlaceDto
}
interface ResolveDto {
  kind: 'invalid' | 'not_found' | 'minimal' | 'public' | 'tombstone' | 'staff'
  public_id?: string | null
  place?: PublicPlaceDto | null
  staff_place?: PlaceDto | null
  units: PublicPlaceDto[]
  staff_units: PlaceDto[]
  status?: PlaceStatus | null
  successor_ids: string[]
}

// ---------- Mapping ----------
const date = (iso: string) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
const dateTime = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' })

function age(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins} minutes`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} ${hours === 1 ? 'hour' : 'hours'}`
  return `${Math.round(hours / 24)} days`
}

function toPlace(d: PlaceDto): Place {
  return {
    id: d.id,
    publicId: d.public_id,
    type: d.type,
    parentId: d.parent_id,
    label: d.label,
    name: d.name,
    geo: d.geo,
    accuracyM: d.accuracy_m,
    source: d.source,
    address: d.address,
    landmark: d.landmark,
    locality: d.locality,
    district: d.district,
    state: d.state,
    postalPin: d.postal_pin,
    status: d.status,
    visibility: d.visibility,
    createdBy: d.created_by_name,
    createdAt: date(d.created_at),
    verifiedAt: d.verified_at ? date(d.verified_at) : null,
  }
}

/** The public view carries fewer fields; the rest are filled with neutral values. */
function fromPublic(d: PublicPlaceDto): Place {
  return {
    id: d.id,
    publicId: d.public_id,
    type: d.type,
    parentId: d.parent_id,
    label: d.label,
    name: d.name,
    geo: d.geo,
    accuracyM: null,
    source: 'gps',
    address: d.address,
    landmark: d.landmark,
    locality: d.locality,
    district: d.district,
    state: d.state,
    postalPin: d.postal_pin,
    status: 'active',
    visibility: 'public',
    createdBy: '',
    createdAt: '',
    verifiedAt: null,
  }
}

const toEvent = (d: EventDto): PlaceEvent => ({ id: d.id, placeId: d.place_id, title: d.title, actor: d.actor_name, at: dateTime(d.at), tone: d.tone })

const qs = (params: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

const isNotFound = (e: unknown) => e instanceof ApiError && e.status === 404

// ---------- Staff: places ----------
export interface PlaceQuery {
  q?: string
  status?: Place['status'] | 'all'
}

export async function listPlaces(query: PlaceQuery = {}): Promise<Place[]> {
  const { data } = await apiRequest<PlaceDto[]>(`/places${qs({ q: query.q?.trim(), status: query.status === 'all' ? undefined : query.status, limit: 200 })}`, { auth: true })
  return data.map(toPlace)
}

/** Null when the place does not exist or is outside the caller's jurisdiction (both are a 404). */
export async function getPlace(id: string): Promise<Place | null> {
  try {
    const { data } = await apiRequest<PlaceDto>(`/places/${encodeURIComponent(id)}`, { auth: true })
    return toPlace(data)
  } catch (e) {
    if (isNotFound(e)) return null
    throw e
  }
}

export async function listUnits(parentId: string): Promise<Place[]> {
  const { data } = await apiRequest<PlaceDto[]>(`/places/${encodeURIComponent(parentId)}/units`, { auth: true })
  return data.map(toPlace)
}

export async function listHistory(placeId: string): Promise<PlaceEvent[]> {
  const { data } = await apiRequest<EventDto[]>(`/places/${encodeURIComponent(placeId)}/history`, { auth: true })
  return data.map(toEvent)
}

export async function findNearby(geo: LatLon, radiusM = 15): Promise<(Place & { distanceM: number })[]> {
  const { data } = await apiRequest<(PlaceDto & { distance_m: number })[]>(`/places/nearby${qs({ lat: geo.lat, lon: geo.lon, radius_m: radiusM })}`, { auth: true })
  return data.map((d) => ({ ...toPlace(d), distanceM: d.distance_m }))
}

export interface NewPlaceInput {
  type: 'house' | 'building'
  name: string
  geo: LatLon
  accuracyM: number
  address: string
  landmark: string
  unitLabels: string[]
  /** Required by the server when another place is within 15 m. */
  differentPlaceReason?: string
}

export async function createAndSubmit(input: NewPlaceInput): Promise<Place> {
  const { data } = await apiRequest<PlaceDto>('/places', {
    method: 'POST',
    auth: true,
    body: {
      type: input.type,
      name: input.name,
      geo: input.geo,
      accuracy_m: input.accuracyM,
      address: input.address,
      landmark: input.landmark,
      unit_labels: input.unitLabels,
      different_place_reason: input.differentPlaceReason || undefined,
    },
  })
  return toPlace(data)
}

/** Four-eyes is enforced by the server. Returns the message to show, or null on success. */
export async function decide(placeId: string, decision: 'approve' | 'reject', reason: string): Promise<string | null> {
  try {
    await apiRequest(`/places/${encodeURIComponent(placeId)}/decision`, { method: 'POST', auth: true, body: { decision, reason } })
    return null
  } catch (e) {
    return e instanceof ApiError ? e.message : 'Something went wrong. Please try again.'
  }
}

/** Going public needs a verifier and the name of the owner who consented. */
export async function setVisibility(placeId: string, visibility: Visibility, consentGivenBy?: string): Promise<void> {
  await apiRequest(`/places/${encodeURIComponent(placeId)}/visibility`, {
    method: 'PUT',
    auth: true,
    body: { visibility, consent_given_by: consentGivenBy },
  })
}

export async function listReview(kind: ReviewItem['kind']): Promise<(ReviewItem & { place: Place })[]> {
  const { data } = await apiRequest<ReviewDto[]>(`/review${qs({ kind })}`, { auth: true })
  return data.map((r) => ({
    id: r.id,
    placeId: r.place_id,
    kind: r.kind,
    submittedBy: r.submitted_by,
    ageLabel: age(r.submitted_at),
    nearestM: r.nearest_m,
    duplicateSuspect: r.duplicate_suspect,
    checks: r.checks,
    place: toPlace(r.place),
  }))
}

/** Downloads the print-ready label from the server (the server also records the print in the audit log). */
export async function downloadLabel(placeId: string, format: 'pdf' | 'png' | 'svg' = 'pdf'): Promise<Blob> {
  return apiBlob(`/places/${encodeURIComponent(placeId)}/label${qs({ format })}`)
}

// ---------- Viewer / public ----------
export async function publicSearch(q: string): Promise<Place[]> {
  const t = q.trim()
  if (!t) return []
  const { data } = await apiRequest<PublicPlaceDto[]>(`/public/places${qs({ q: t })}`, { auth: true })
  return data.map(fromPublic)
}

export async function getPublicPlace(id: string): Promise<{ place: Place; units: Place[] } | null> {
  try {
    const { data } = await apiRequest<{ place: PublicPlaceDto; units: PublicPlaceDto[] }>(`/public/places/${encodeURIComponent(id)}`, { auth: true })
    return { place: fromPublic(data.place), units: data.units.map(fromPublic) }
  } catch (e) {
    if (isNotFound(e)) return null
    throw e
  }
}

export async function submitCorrection(placeId: string, note: string): Promise<void> {
  await apiRequest(`/places/${encodeURIComponent(placeId)}/corrections`, { method: 'POST', auth: true, body: { note } })
}

/** What a scan of /p/{id} shows. The server decides from who is signed in (the token), not from the UI role. */
export async function resolve(input: string): Promise<Resolution> {
  let dto: ResolveDto
  try {
    dto = (await apiRequest<ResolveDto>(`/p/${encodeURIComponent(input)}`, { auth: true })).data
  } catch (e) {
    // invalid and not_found are 404s that still carry a `kind`.
    const kind = e instanceof ApiError && e.status === 404 ? (e.body as { kind?: string } | undefined)?.kind : undefined
    if (kind === 'invalid') return { kind: 'invalid' }
    if (kind === 'not_found') return { kind: 'not_found' }
    throw e
  }
  switch (dto.kind) {
    case 'invalid':
      return { kind: 'invalid' }
    case 'not_found':
      return { kind: 'not_found' }
    case 'minimal':
      return { kind: 'minimal', publicId: dto.public_id ?? input }
    case 'tombstone':
      return { kind: 'tombstone', publicId: dto.public_id ?? input, status: dto.status ?? 'retired', successorIds: dto.successor_ids }
    case 'staff':
      return { kind: 'staff', place: toPlace(dto.staff_place!), units: dto.staff_units.map(toPlace) }
    case 'public':
      return { kind: 'public', place: fromPublic(dto.place!), units: dto.units.map(fromPublic) }
  }
}

// ---------- Admin ----------
export interface StaffRow {
  id: string
  email: string
  name: string
  role: Role
  district: string
  status: 'active' | 'invited'
  inviteToken?: string
}
export interface Jurisdiction {
  id: string
  name: string
  code: string
  level: 'state' | 'district' | 'postal_area'
  parentId: string | null
}

export async function listStaff(): Promise<StaffRow[]> {
  const { data } = await apiRequest<
    { id: string; email: string; name: string; role: Role; jurisdiction_name: string; status: 'active' | 'invited'; invite_token: string | null }[]
  >('/admin/staff', { auth: true })
  return data.map((s) => ({ id: s.id, email: s.email, name: s.name, role: s.role, district: s.jurisdiction_name, status: s.status, inviteToken: s.invite_token ?? undefined }))
}

export async function listJurisdictions(): Promise<Jurisdiction[]> {
  const { data } = await apiRequest<{ id: string; name: string; code: string; level: Jurisdiction['level']; parent_id: string | null }[]>('/admin/jurisdictions', { auth: true })
  return data.map((j) => ({ id: j.id, name: j.name, code: j.code, level: j.level, parentId: j.parent_id }))
}

export async function inviteStaff(email: string, role: Role, jurisdictionId: string): Promise<StaffRow | { error: string }> {
  try {
    const { data } = await apiRequest<{ id: string; email: string; role: Role; invite_url: string | null }>('/admin/invites', {
      method: 'POST',
      auth: true,
      body: { email: email.trim(), role, jurisdiction_id: jurisdictionId },
    })
    const token = data.invite_url?.split('/invite/')[1]
    return { id: data.id, email: data.email, name: '', role: data.role, district: '', status: 'invited', inviteToken: token }
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : 'Something went wrong. Please try again.' }
  }
}
