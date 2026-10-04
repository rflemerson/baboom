export function formatDecimal(
  value: string | number | null | undefined,
  fractionDigits = 2,
): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }

  const numericValue = typeof value === 'number' ? value : Number.parseFloat(String(value))

  if (Number.isNaN(numericValue)) {
    return '-'
  }

  return numericValue.toFixed(fractionDigits)
}

/** Format a price with the currency it is charged in, when the API names one. */
export function formatMoney(
  value: string | number | null | undefined,
  currency: string | null | undefined,
): string {
  const amount = formatDecimal(value)
  return currency && amount !== '-' ? `${currency} ${amount}` : amount
}
