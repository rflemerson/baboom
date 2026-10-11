import { describe, expect, it } from 'vitest'
import { paymentMethodLabel } from './payment'

describe('payment labels', () => {
  it('translates known methods and keeps unknown codes verbatim', () => {
    expect(paymentMethodLabel('pix')).toBe('Pix')
    expect(paymentMethodLabel('credit_card')).toBe('Cartão')
    expect(paymentMethodLabel('new_wallet')).toBe('new_wallet')
  })
  it('states no payment when the price states none', () => {
    expect(paymentMethodLabel(null)).toBeNull()
    expect(paymentMethodLabel('')).toBeNull()
  })
})
