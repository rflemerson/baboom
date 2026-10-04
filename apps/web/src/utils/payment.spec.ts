import { describe, expect, it } from 'vitest'

import { paymentMethodLabel, totalPriceLabel } from './payment'

describe('payment labels', () => {
  it('names known methods and keeps unknown codes verbatim', () => {
    expect(paymentMethodLabel('pix')).toBe('Pix')
    expect(paymentMethodLabel('new_wallet')).toBe('new_wallet')
  })

  it('states no payment when the price states none', () => {
    expect(paymentMethodLabel(null)).toBeNull()
    expect(paymentMethodLabel('')).toBeNull()
    expect(totalPriceLabel(null)).toBe('Total price')
  })

  it('labels a total with its payment method', () => {
    expect(totalPriceLabel('pix')).toBe('Total price (Pix)')
    expect(totalPriceLabel('pix')).toBe('Total price (Pix)')
  })

  it('says "at once" for an unnamed method in the cash scenario', () => {
    expect(totalPriceLabel(null)).toBe('Total price')
  })
})
