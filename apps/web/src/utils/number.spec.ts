import { describe, expect, it } from 'vitest'

import { formatDecimal, formatMoney, formatQuantity, pricePer100g } from './number'

const SPACE = ' '

describe('formatDecimal', () => {
  it('formats with fixed decimals in Brazilian Portuguese', () => {
    expect(formatDecimal('0.166527777777778')).toBe('0,17')
    expect(formatDecimal('86.666', 1)).toBe('86,7')
  })

  it('returns a dash for empty values', () => {
    expect(formatDecimal(null)).toBe('-')
    expect(formatDecimal(undefined)).toBe('-')
    expect(formatDecimal('')).toBe('-')
  })
})

describe('formatMoney', () => {
  it('formats a price in its currency', () => {
    expect(formatMoney('96.03', 'BRL')).toBe(`R$${SPACE}96,03`)
    expect(formatMoney('96.03', null)).toBe('96,03')
    expect(formatMoney(null, 'BRL')).toBe('-')
  })
})

describe('pricePer100g', () => {
  it('converts before rounding, including zero', () => {
    expect(formatMoney(pricePer100g('0.166527777777778'), 'BRL')).toBe(`R$${SPACE}16,65`)
    expect(pricePer100g('0')).toBe(0)
  })
  it('keeps absent or invalid prices unavailable', () => {
    for (const value of [null, undefined, '', 'invalid', 'Infinity'])
      expect(pricePer100g(value)).toBeNull()
  })
})

describe('formatQuantity', () => {
  it('formats quantities with at most two decimals and no trailing zeros', () => {
    expect(formatQuantity('1000.000')).toBe('1000')
    expect(formatQuantity('900.500')).toBe('900,5')
    expect(formatQuantity('733.3333')).toBe('733,33')
    expect(formatQuantity(null)).toBe('-')
  })
})
