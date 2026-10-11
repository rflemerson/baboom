import { i18n } from '@/i18n'

const PAYMENT_METHOD_KEYS = {
  pix: 'payment.pix',
  boleto: 'payment.boleto',
  credit_card: 'payment.credit_card',
  debit_card: 'payment.debit_card',
  wallet: 'payment.wallet',
  gift_card: 'payment.gift_card',
} as const

/** Name the payment method behind a price, or null when the price states none. */
export function paymentMethodLabel(code: string | null | undefined): string | null {
  if (!code) {
    return null
  }
  if (!Object.prototype.hasOwnProperty.call(PAYMENT_METHOD_KEYS, code)) return code
  return i18n.global.t(PAYMENT_METHOD_KEYS[code as keyof typeof PAYMENT_METHOD_KEYS])
}
