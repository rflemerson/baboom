const PAYMENT_METHOD_LABELS: Record<string, string> = {
  pix: 'Pix',
  boleto: 'Boleto',
  credit_card: 'Card',
  debit_card: 'Debit card',
  wallet: 'Wallet',
  gift_card: 'Gift card',
}

/** Name the payment method behind a price, or null when the price states none. */
export function paymentMethodLabel(code: string | null | undefined): string | null {
  if (!code) {
    return null
  }
  return PAYMENT_METHOD_LABELS[code] ?? code
}

/** Label a total price with the payment it assumes, when there is one. */
export function totalPriceLabel(code: string | null | undefined): string {
  const method = paymentMethodLabel(code)
  return method ? `Total price (${method})` : 'Total price'
}
