import { ALPHABET, makeId } from '@/lib/placeId'
import type { Place, PlaceEvent, ReviewItem } from '@/lib/types'

// Mock data only. Coordinates and cell codes are illustrative, NOT real DIGIPIN output.

export function seqFor(n: number): string {
  let v = (n * 7919 + 1013) % 65536
  let out = ''
  for (let i = 0; i < 4; i++) {
    out = ALPHABET[v % 16] + out
    v = Math.floor(v / 16)
  }
  return out
}

type Seed = {
  key: string
  type: 'house' | 'building'
  name: string
  lat: number
  lon: number
  geo: string
  address: string
  landmark: string
  locality: string
  postalPin: string
  status: Place['status']
  visibility: Place['visibility']
  accuracyM: number
  units: number
  by: string
  age: string
}

const seeds: Seed[] = [
  { key: 'p1', type: 'building', name: 'Sunrise Apartments', lat: 12.971599, lon: 77.594566, geo: 'FC98J327K4', address: '12th Main', landmark: 'Opposite Metro Station, Gate 2', locality: 'Indiranagar', postalPin: '560038', status: 'active', visibility: 'public', accuracyM: 4, units: 48, by: 'Arun R.', age: '5 days' },
  { key: 'p2', type: 'house', name: 'Sunrise Villa', lat: 12.971699, lon: 77.594566, geo: 'FC98J327K4', address: '12th Main', landmark: 'Next to Sunrise Apartments', locality: 'Indiranagar', postalPin: '560038', status: 'active', visibility: 'public', accuracyM: 5, units: 0, by: 'Arun R.', age: '6 days' },
  { key: 'p3', type: 'building', name: 'Lakeview Residency', lat: 12.9698, lon: 77.7499, geo: 'J3K4L9M2T8', address: 'Lake Road', landmark: 'Near Forum Mall', locality: 'Whitefield', postalPin: '560066', status: 'pending_verification', visibility: 'private', accuracyM: 6, units: 24, by: 'Arun R.', age: '2 days' },
  { key: 'p4', type: 'house', name: '14, 3rd Cross', lat: 12.9308, lon: 77.5838, geo: 'C9F3J7K4L2', address: '14, 3rd Cross', landmark: 'Behind Shopping Complex', locality: 'Jayanagar', postalPin: '560011', status: 'pending_verification', visibility: 'private', accuracyM: 8, units: 0, by: 'Meena S.', age: '2 days' },
  { key: 'p5', type: 'building', name: 'Green Court', lat: 12.9121, lon: 77.6446, geo: '8J2K9C5L7M', address: '27th Main', landmark: 'Opposite Park', locality: 'HSR Layout', postalPin: '560102', status: 'pending_verification', visibility: 'private', accuracyM: 7, units: 60, by: 'Meena S.', age: '1 day' },
  { key: 'p6', type: 'house', name: '7, Temple Road', lat: 13.0035, lon: 77.5707, geo: '7P3K4L6M9C', address: '7, Temple Road', landmark: 'Near Temple', locality: 'Malleshwaram', postalPin: '560003', status: 'pending_verification', visibility: 'private', accuracyM: 10, units: 0, by: 'Meena S.', age: '1 day' },
  { key: 'p7', type: 'building', name: 'Palm Heights', lat: 12.9352, lon: 77.6245, geo: 'K6L2M8T3F9', address: '5th Block', landmark: 'Near Water Tank', locality: 'Koramangala', postalPin: '560095', status: 'pending_verification', visibility: 'private', accuracyM: 5, units: 18, by: 'Arun R.', age: '5 hours' },
  { key: 'p8', type: 'building', name: 'Orchid Residency', lat: 12.9279, lon: 77.6271, geo: 'M4T9F2J6K8', address: '6th Block', landmark: 'Opposite School', locality: 'Koramangala', postalPin: '560095', status: 'active', visibility: 'private', accuracyM: 4, units: 18, by: 'Arun R.', age: '9 days' },
  { key: 'p9', type: 'house', name: '22, Lake View Road', lat: 12.9857, lon: 77.7093, geo: 'L8C3F5J2M4', address: '22, Lake View Road', landmark: 'Near Bridge', locality: 'Marathahalli', postalPin: '560037', status: 'active', visibility: 'private', accuracyM: 6, units: 0, by: 'Meena S.', age: '12 days' },
]

const places: Place[] = []
let n = 0
for (const s of seeds) {
  const verified = s.status === 'active' ? '2026-11-12' : null
  const issued = s.status !== 'draft'
  places.push({
    id: s.key,
    publicId: issued ? makeId(s.geo, seqFor(++n)) : null,
    type: s.type,
    parentId: null,
    label: null,
    name: s.name,
    geo: { lat: s.lat, lon: s.lon },
    accuracyM: s.accuracyM,
    source: 'gps',
    address: s.address,
    landmark: s.landmark,
    locality: s.locality,
    district: 'Bengaluru Urban',
    state: 'Karnataka',
    postalPin: s.postalPin,
    status: s.status,
    visibility: s.visibility,
    createdBy: s.by,
    createdAt: '2026-11-10',
    verifiedAt: verified,
  })
  const parent = places[places.length - 1]
  for (let i = 0; i < s.units; i++) {
    const floor = Math.floor(i / 4) + 1
    const label = `${floor}0${(i % 4) + 1}`
    places.push({
      ...parent,
      id: `${s.key}-u${i}`,
      publicId: makeId(s.geo, seqFor(++n)),
      type: 'unit',
      parentId: s.key,
      label,
      name: `${s.name}, ${label}`,
      status: i === 3 && s.key === 'p1' ? 'pending_verification' : i === 6 && s.key === 'p1' ? 'retired' : s.status,
    })
  }
}

export const initialPlaces = places

export const initialEvents: PlaceEvent[] = [
  { id: 'e1', placeId: 'p1', title: 'Label printed (48 units)', actor: 'Sunita K.', at: 'Today, 10:42', tone: 'muted' },
  { id: 'e2', placeId: 'p1', title: 'Verified and activated', actor: 'Ravi M. (verifier)', at: '12 Nov', tone: 'ok' },
  { id: 'e3', placeId: 'p1', title: 'Units 101 to 1204 added', actor: 'Arun R.', at: '11 Nov', tone: 'accent' },
  { id: 'e4', placeId: 'p1', title: 'Pin moved 3 m', actor: 'Arun R.', at: '11 Nov', tone: 'warn' },
  { id: 'e5', placeId: 'p1', title: 'Draft submitted', actor: 'Arun R.', at: '10 Nov', tone: 'accent' },
]

export const initialReview: ReviewItem[] = [
  { id: 'r1', placeId: 'p3', kind: 'new', submittedBy: 'Arun R.', ageLabel: '2 days', nearestM: 38, duplicateSuspect: false, checks: [
    { title: 'Pin accuracy', detail: '± 6 m, within the 20 m limit', ok: true },
    { title: 'No duplicate nearby', detail: 'Nearest active place is 38 m away', ok: true },
    { title: 'Address matches locality', detail: 'Whitefield, 560066', ok: true },
    { title: 'Entrance point set', detail: 'Not set. Optional, but helps delivery', ok: false },
    { title: 'Unit labels unique', detail: '24 units, no repeated labels', ok: true },
  ] },
  { id: 'r2', placeId: 'p4', kind: 'new', submittedBy: 'Meena S.', ageLabel: '2 days', nearestM: 21, duplicateSuspect: false, checks: [
    { title: 'Pin accuracy', detail: '± 8 m, within the 20 m limit', ok: true },
    { title: 'No duplicate nearby', detail: 'Nearest active place is 21 m away', ok: true },
    { title: 'Address matches locality', detail: 'Jayanagar, 560011', ok: true },
  ] },
  { id: 'r3', placeId: 'p5', kind: 'new', submittedBy: 'Meena S.', ageLabel: '1 day', nearestM: 9, duplicateSuspect: true, checks: [
    { title: 'Pin accuracy', detail: '± 7 m, within the 20 m limit', ok: true },
    { title: 'No duplicate nearby', detail: 'An active place is 9 m away. Check it is different', ok: false },
    { title: 'Unit labels unique', detail: '60 units, no repeated labels', ok: true },
  ] },
  { id: 'r4', placeId: 'p6', kind: 'new', submittedBy: 'Meena S.', ageLabel: '1 day', nearestM: 54, duplicateSuspect: false, checks: [
    { title: 'Pin accuracy', detail: '± 10 m, within the 20 m limit', ok: true },
    { title: 'No duplicate nearby', detail: 'Nearest active place is 54 m away', ok: true },
  ] },
  { id: 'r5', placeId: 'p7', kind: 'new', submittedBy: 'Arun R.', ageLabel: '5 hours', nearestM: 31, duplicateSuspect: false, checks: [
    { title: 'Pin accuracy', detail: '± 5 m, within the 20 m limit', ok: true },
    { title: 'No duplicate nearby', detail: 'Nearest active place is 31 m away', ok: true },
  ] },
]
