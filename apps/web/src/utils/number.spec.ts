import { describe, expect, it } from 'vitest'

import { formatDecimal } from './number'

describe('formatDecimal', () => {
  it('formats decimal strings with two fraction digits by default', () => {
    expect(formatDecimal('0.166527777777778')).toBe('0.17')
  })

  it('returns a dash for empty values', () => {
    expect(formatDecimal(null)).toBe('-')
    expect(formatDecimal(undefined)).toBe('-')
    expect(formatDecimal('')).toBe('-')
  })
})
