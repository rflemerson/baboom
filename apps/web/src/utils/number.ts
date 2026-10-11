import { i18n } from '@/i18n'

const MISSING = '-'

function numeric(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const amount = typeof value === 'number' ? value : Number.parseFloat(value)
  return Number.isFinite(amount) ? amount : null
}

function format(amount: number, options: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(i18n.global.locale.value, options).format(amount)
}

/** Format a number with a fixed number of decimals, in the interface locale. */
export function formatDecimal(
  value: string | number | null | undefined,
  fractionDigits = 2,
): string {
  const amount = numeric(value)
  if (amount === null) return MISSING
  return format(amount, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
    useGrouping: false,
  })
}

/** Format a quantity with at most two decimals and no trailing zeros. */
export function formatQuantity(value: string | number | null | undefined): string {
  const amount = numeric(value)
  if (amount === null) return MISSING
  return format(amount, { maximumFractionDigits: 2, useGrouping: false })
}

/** Format a price in the currency it is charged in, when the API names one. */
export function formatMoney(
  value: string | number | null | undefined,
  currency: string | null | undefined,
): string {
  const amount = numeric(value)
  if (amount === null) return MISSING
  if (!currency) return formatDecimal(amount)
  return format(amount, { style: 'currency', currency })
}

/** Convert the API's price per gram of active to the display unit. */
export function pricePer100g(value: string | null | undefined): number | null {
  const amount = numeric(value)
  return amount === null ? null : amount * 100
}
