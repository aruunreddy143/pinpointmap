import vectors from '../../../shared/test-vectors/place_ids.json'
import { formatDisplay, makeId, normalize, validate } from './placeId'

// The same file is read by the backend's pytest (backend/tests/test_place_id.py).
// If either implementation changes, both suites must still pass against it.

describe('shared place ID vectors', () => {
  it.each(vectors.valid)('makes, formats and validates $id', (v) => {
    expect(makeId(v.geo, v.seq)).toBe(v.id)
    expect(formatDisplay(v.id)).toBe(v.display)
    expect(validate(v.display)).toEqual({ ok: true, canonical: v.id })
  })

  it.each(vectors.invalid)('rejects "$input" as $reason', (c) => {
    expect(validate(c.input)).toEqual({ ok: false, reason: c.reason })
  })

  it.each(vectors.normalize)('normalizes "$input"', (c) => {
    expect(normalize(c.input)).toBe(c.canonical)
  })
})
