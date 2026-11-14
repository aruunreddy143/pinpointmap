import { identifierHint, maskIdentifier, parseIdentifier } from './identifier'

describe('parseIdentifier', () => {
  it.each([
    ['98765 43210', '+919876543210'],
    ['+91 98765-43210', '+919876543210'],
    ['919876543210', '+919876543210'],
    ['09876543210', '+919876543210'],
    ['(98765) 43210', '+919876543210'],
  ])('accepts the mobile number %s', (input, value) => {
    expect(parseIdentifier(input)).toMatchObject({ kind: 'mobile', value })
  })

  it('formats a mobile number for display', () => {
    expect(parseIdentifier('9876543210')?.display).toBe('+91 98765 43210')
  })

  it('accepts and lower-cases an email address', () => {
    expect(parseIdentifier('  Priya@Example.COM ')).toEqual({ kind: 'email', value: 'priya@example.com', display: 'priya@example.com' })
  })

  it.each(['', '12345', '5876543210', '98765432101234', 'priya@', '@example.com', 'priya example', 'abc'])('rejects %j', (input) => {
    expect(parseIdentifier(input)).toBeNull()
  })

  it('gives a useful hint while typing, and none when valid', () => {
    expect(identifierHint('')).toBeNull()
    expect(identifierHint('98765')).toMatch(/10-digit/)
    expect(identifierHint('priya@')).toMatch(/incomplete/)
    expect(identifierHint('hello')).toMatch(/mobile number or an email/)
    expect(identifierHint('9876543210')).toBeNull()
  })

  it('masks identifiers', () => {
    expect(maskIdentifier(parseIdentifier('9876543210')!)).toBe('+91 ••••• •3210')
    expect(maskIdentifier(parseIdentifier('priya@example.com')!)).toBe('p***@example.com')
  })
})
