export type Identifier =
  | { kind: 'email'; value: string; display: string }
  | { kind: 'mobile'; value: string; display: string }

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

/**
 * Accepts an email address or an Indian mobile number and normalizes it.
 * Mobile: 10 digits starting 6-9, optionally written with +91, 91 or a leading 0, spaces or dashes.
 * Returns null when the input is neither.
 */
export function parseIdentifier(input: string): Identifier | null {
  const text = input.trim()
  if (!text) return null
  if (text.includes('@')) {
    return EMAIL.test(text) ? { kind: 'email', value: text.toLowerCase(), display: text.toLowerCase() } : null
  }
  let digits = text.replace(/[\s\-().]/g, '')
  if (!/^\+?\d+$/.test(digits)) return null
  digits = digits.replace(/^\+/, '')
  if (digits.length === 12 && digits.startsWith('91')) digits = digits.slice(2)
  else if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1)
  if (!/^[6-9]\d{9}$/.test(digits)) return null
  return { kind: 'mobile', value: `+91${digits}`, display: `+91 ${digits.slice(0, 5)} ${digits.slice(5)}` }
}

/** Shows enough to recognise it, not enough to leak it: m***@mail.com, +91 ••••• •3210 */
export function maskIdentifier(id: Identifier): string {
  if (id.kind === 'email') {
    const [name, domain] = id.value.split('@')
    return `${name[0]}***@${domain}`
  }
  return `+91 ••••• •${id.value.slice(-4)}`
}

/** What to tell the user while they are typing. */
export function identifierHint(input: string): string | null {
  const text = input.trim()
  if (!text) return null
  if (parseIdentifier(text)) return null
  if (text.includes('@')) return 'That email address looks incomplete.'
  if (/^[+\d\s\-().]+$/.test(text)) return 'Enter a 10-digit Indian mobile number starting with 6, 7, 8 or 9.'
  return 'Enter a mobile number or an email address.'
}
