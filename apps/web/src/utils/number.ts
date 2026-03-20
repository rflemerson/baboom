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
