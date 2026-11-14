/**
 * PINPOINT ID: PP1 + 10-char geo cell + 4-char suffix + 1 check character.
 * See .claude/skills/pinpoint-id-format. The check character is Luhn mod-16 over the
 * 14 payload characters. The geo cell grid itself (DIGIPIN) is NOT implemented here:
 * it must match India Post's official spec and lives on the backend.
 */
export const ALPHABET = 'FC98J327K456LMPT'
const N = ALPHABET.length
export const PREFIX = 'PP1'

export function checkChar(payload: string): string {
  let factor = 2
  let sum = 0
  for (let i = payload.length - 1; i >= 0; i--) {
    const code = ALPHABET.indexOf(payload[i])
    if (code < 0) throw new Error(`Invalid character: ${payload[i]}`)
    let addend = factor * code
    factor = factor === 2 ? 1 : 2
    addend = Math.floor(addend / N) + (addend % N)
    sum += addend
  }
  return ALPHABET[(N - (sum % N)) % N]
}

export function makeId(geo: string, seq: string): string {
  const payload = geo + seq
  return PREFIX + payload + checkChar(payload)
}

/** Upper-case and strip separators so "pp1 fc98-..." becomes the canonical form. */
export function normalize(input: string): string {
  return input.toUpperCase().replace(/[^A-Z0-9]/g, '')
}

export type IdCheck = { ok: true; canonical: string } | { ok: false; reason: 'incomplete' | 'prefix' | 'characters' | 'checksum' }

export function validate(input: string): IdCheck {
  const c = normalize(input)
  if (c.length < 18) return { ok: false, reason: 'incomplete' }
  if (c.length > 18 || !c.startsWith(PREFIX)) return { ok: false, reason: 'prefix' }
  const body = c.slice(3)
  if ([...body].some((ch) => !ALPHABET.includes(ch))) return { ok: false, reason: 'characters' }
  if (checkChar(body.slice(0, 14)) !== body[14]) return { ok: false, reason: 'checksum' }
  return { ok: true, canonical: c }
}

/** PP1-FC98J327K4-56LM-T */
export function formatDisplay(canonical: string): string {
  const c = normalize(canonical)
  return `${c.slice(0, 3)}-${c.slice(3, 13)}-${c.slice(13, 17)}-${c.slice(17)}`
}
