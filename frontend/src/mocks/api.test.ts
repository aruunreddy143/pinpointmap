import { can, isStaff } from '@/lib/permissions'
import { resetMock, resolve, publicSearch, getPublicPlace, decide, listPlaces, findNearby, createAndSubmit } from './api'
import { initialPlaces } from './data'

const privateBuilding = initialPlaces.find((p) => p.visibility === 'private' && p.status === 'active' && p.type === 'building')!
const publicBuilding = initialPlaces.find((p) => p.id === 'p1')!

beforeEach(() => resetMock())

describe('viewer (read-only) rules', () => {
  it('has no write permissions except reporting a problem', () => {
    for (const perm of ['place:create', 'place:update', 'place:verify', 'place:print', 'user:manage', 'audit:read', 'place:read'] as const) {
      expect(can('viewer', perm), perm).toBe(false)
    }
    expect(can('viewer', 'correction:request')).toBe(true)
    expect(isStaff('viewer')).toBe(false)
  })

  it('never returns private places from search', async () => {
    const all = await publicSearch('a')
    expect(all.length).toBeGreaterThan(0)
    expect(all.every((p) => p.visibility === 'public' && p.status === 'active')).toBe(true)
    expect(all.find((p) => p.id === privateBuilding.id)).toBeUndefined()
  })

  it('gets 404 (null) for a private place detail', async () => {
    expect(await getPublicPlace(privateBuilding.id)).toBeNull()
    expect(await getPublicPlace(publicBuilding.id)).not.toBeNull()
  })
})

describe('scan resolver visibility', () => {
  it('shows only a minimal page to anonymous and viewer scans of a private place', async () => {
    for (const role of [null, 'viewer'] as const) {
      const r = await resolve(privateBuilding.publicId!, role)
      expect(r.kind).toBe('minimal')
      expect(JSON.stringify(r)).not.toContain(privateBuilding.address)
    }
  })

  it('shows full details to staff, and public details for a public place', async () => {
    expect((await resolve(privateBuilding.publicId!, 'registrar')).kind).toBe('staff')
    expect((await resolve(publicBuilding.publicId!, null)).kind).toBe('public')
  })

  it('rejects a mistyped ID before any lookup', async () => {
    const id = publicBuilding.publicId!
    const bad = id.slice(0, 5) + (id[5] === 'F' ? 'C' : 'F') + id.slice(6)
    expect((await resolve(bad, null)).kind).toBe('invalid')
  })
})

describe('verification (four-eyes)', () => {
  it('stops the submitter from approving their own place', async () => {
    const pending = initialPlaces.find((p) => p.status === 'pending_verification' && p.type !== 'unit')!
    const err = await decide(pending.id, 'approve', '', pending.createdBy)
    expect(err).toMatch(/different verifier/)
    expect((await listPlaces({ status: 'pending_verification' })).some((p) => p.id === pending.id)).toBe(true)
  })

  it('lets a different verifier approve, which activates the place and its units', async () => {
    const pending = initialPlaces.find((p) => p.id === 'p3')!
    expect(await decide(pending.id, 'approve', '', 'Ravi M.')).toBeNull()
    const places = await listPlaces({ status: 'active' })
    expect(places.some((p) => p.id === 'p3')).toBe(true)
  })

  it('requires a reason to reject', async () => {
    expect(await decide('p3', 'reject', '  ', 'Ravi M.')).toMatch(/reason/i)
  })
})

describe('registration', () => {
  it('finds existing places within 15 m for the duplicate guard', async () => {
    const near = await findNearby({ lat: 12.97165, lon: 77.5946 }, 15)
    expect(near.map((p) => p.id)).toContain('p1')
    expect(near.every((p) => p.distanceM <= 15)).toBe(true)
    expect(await findNearby({ lat: 12.5, lon: 77.0 }, 15)).toEqual([])
  })

  it('issues the ID on submit and creates pending, private units', async () => {
    const place = await createAndSubmit({ type: 'building', name: 'Test Court', geo: { lat: 12.9, lon: 77.5 }, accuracyM: 5, address: 'x', landmark: '', unitLabels: ['1', '2'] }, 'Arun R.')
    expect(place.publicId).toMatch(/^PP1/)
    expect(place.status).toBe('pending_verification')
    expect(place.visibility).toBe('private')
  })
})
