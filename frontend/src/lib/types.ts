// Mock-phase types. Once the backend exists these are replaced by types generated
// from its OpenAPI schema (see the api-contract-sync skill).

export type PlaceType = 'house' | 'building' | 'unit'
export type PlaceStatus =
  | 'draft'
  | 'pending_verification'
  | 'active'
  | 'rejected'
  | 'retired'
  | 'merged'
  | 'split'
export type Visibility = 'private' | 'public'
export type LocationSource = 'gps' | 'map_click' | 'survey'

export interface LatLon {
  lat: number
  lon: number
}

export interface Place {
  id: string
  publicId: string | null
  type: PlaceType
  parentId: string | null
  label: string | null
  name: string
  geo: LatLon
  accuracyM: number
  source: LocationSource
  address: string
  landmark: string
  locality: string
  district: string
  state: string
  postalPin: string
  status: PlaceStatus
  visibility: Visibility
  createdBy: string
  createdAt: string
  verifiedAt: string | null
}

export interface PlaceEvent {
  id: string
  placeId: string
  title: string
  actor: string
  at: string
  tone: 'ok' | 'accent' | 'warn' | 'muted'
}

export interface ReviewItem {
  id: string
  placeId: string
  kind: 'new' | 'change' | 'merge'
  submittedBy: string
  ageLabel: string
  nearestM: number
  duplicateSuspect: boolean
  checks: { title: string; detail: string; ok: boolean }[]
}

export type Role =
  | 'super_admin'
  | 'admin'
  | 'registrar'
  | 'verifier'
  | 'printer'
  | 'auditor'
  | 'viewer'

export type Permission =
  | 'place:read'
  | 'place:read_public'
  | 'place:create'
  | 'place:update'
  | 'place:verify'
  | 'place:print'
  | 'user:manage'
  | 'audit:read'
  | 'correction:request'

export type Resolution =
  | { kind: 'invalid' }
  | { kind: 'not_found' }
  | { kind: 'minimal'; publicId: string }
  | { kind: 'public'; place: Place; units: Place[] }
  | { kind: 'staff'; place: Place; units: Place[] }
