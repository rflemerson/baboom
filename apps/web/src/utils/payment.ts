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

/**
 * Label a total price with the payment it assumes: the named method, or "at
 * once" when the cash scenario priced it without the store naming the method.
 */
export function totalPriceLabel(
  code: string | null | undefined,
  scenarioKey: string | null = null,
): string {
  const method = paymentMethodLabel(code)
  if (method) {
    return `Total price (${method})`
  }
  return scenarioKey === 'cash' ? 'Total price (at once)' : 'Total price'
}
