export const MAX_UNITS = 500

export interface UnitParse {
  labels: string[]
  error: string | null
}

/**
 * Expands "101-110, 201-204, 3A" into unit labels. Labels are free text, so "2B" and
 * "Ground-rear" are fine as single entries; only purely numeric A-B tokens are ranges.
 * Repeated labels are an error (labels are unique per building).
 */
export function parseUnitLabels(input: string): UnitParse {
  const labels: string[] = []
  const tokens = input.split(/[,\n]/).map((t) => t.trim()).filter(Boolean)
  for (const t of tokens) {
    const m = /^(\d+)\s*-\s*(\d+)$/.exec(t)
    if (m) {
      const a = Number(m[1])
      const b = Number(m[2])
      if (a > b) return { labels: [], error: `"${t}" runs backwards. Write it as ${b}-${a}.` }
      if (labels.length + (b - a + 1) > MAX_UNITS) return { labels: [], error: `A building can have at most ${MAX_UNITS} units in one go.` }
      for (let n = a; n <= b; n++) labels.push(String(n))
    } else {
      labels.push(t)
    }
  }
  const seen = new Set<string>()
  const dupes = new Set<string>()
  for (const l of labels) {
    const k = l.toLowerCase()
    if (seen.has(k)) dupes.add(l)
    seen.add(k)
  }
  if (dupes.size) return { labels: [], error: `Repeated unit labels: ${[...dupes].join(', ')}.` }
  if (labels.length > MAX_UNITS) return { labels: [], error: `A building can have at most ${MAX_UNITS} units in one go.` }
  return { labels, error: null }
}
