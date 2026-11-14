import { ALPHABET, checkChar, formatDisplay, makeId, normalize, validate } from './placeId'

const GEO = 'FC98J327K4'

describe('place ID', () => {
  it('round-trips a generated ID', () => {
    const id = makeId(GEO, '56LM')
    expect(id).toHaveLength(18)
    expect(validate(id)).toEqual({ ok: true, canonical: id })
  })

  it('normalizes messy input (case, dashes, spaces)', () => {
    const id = makeId(GEO, '56LM')
    expect(normalize(formatDisplay(id).toLowerCase().replace(/-/g, ' '))).toBe(id)
    expect(validate(formatDisplay(id))).toEqual({ ok: true, canonical: id })
  })

  it('formats for display', () => {
    expect(formatDisplay(makeId(GEO, '56LM'))).toMatch(/^PP1-FC98J327K4-56LM-[A-Z0-9]$/)
  })

  it('detects EVERY single-character typo in the payload', () => {
    const id = makeId(GEO, '56LM')
    for (let pos = 3; pos < id.length; pos++) {
      for (const ch of ALPHABET) {
        if (ch === id[pos]) continue
        const bad = id.slice(0, pos) + ch + id.slice(pos + 1)
        expect(validate(bad).ok, `${bad} should be rejected`).toBe(false)
      }
    }
  })

  it('detects adjacent transpositions of different characters', () => {
    const id = makeId(GEO, '56LM')
    for (let pos = 3; pos < id.length - 1; pos++) {
      if (id[pos] === id[pos + 1]) continue
      const bad = id.slice(0, pos) + id[pos + 1] + id[pos] + id.slice(pos + 2)
      expect(validate(bad).ok, `${bad} should be rejected`).toBe(false)
    }
  })

  it('rejects wrong prefix, length, and characters outside the alphabet', () => {
    const id = makeId(GEO, '56LM')
    expect(validate('PP1-FC98')).toEqual({ ok: false, reason: 'incomplete' })
    expect(validate('XX1' + id.slice(3))).toEqual({ ok: false, reason: 'prefix' })
    expect(validate(id + 'F')).toEqual({ ok: false, reason: 'prefix' })
    expect(validate('PP1' + 'O'.repeat(15))).toEqual({ ok: false, reason: 'characters' })
  })

  it('throws on a payload character outside the alphabet', () => {
    expect(() => checkChar('FC98J327K4O')).toThrow()
  })
})
