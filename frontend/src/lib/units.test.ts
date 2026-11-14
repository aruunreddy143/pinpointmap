import { MAX_UNITS, parseUnitLabels } from './units'

describe('parseUnitLabels', () => {
  it('expands ranges and keeps free-text labels', () => {
    expect(parseUnitLabels('101-103, 2B, Ground-rear')).toEqual({ labels: ['101', '102', '103', '2B', 'Ground-rear'], error: null })
  })

  it('rejects repeated labels, ignoring case', () => {
    const r = parseUnitLabels('101-103, 102, 2b, 2B')
    expect(r.labels).toEqual([])
    expect(r.error).toMatch(/Repeated unit labels: 102, 2B/)
  })

  it('rejects backwards ranges', () => {
    expect(parseUnitLabels('110-101').error).toMatch(/backwards/)
  })

  it('caps the number of units', () => {
    expect(parseUnitLabels(`1-${MAX_UNITS + 1}`).error).toMatch(/at most/)
  })

  it('returns nothing for empty input', () => {
    expect(parseUnitLabels('  ')).toEqual({ labels: [], error: null })
  })
})
