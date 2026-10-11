import type { CatalogProduct } from '@/types/catalog'

// What a price row shows beside the amount itself.
export function usePriceDisplay() {
  function discounted(product: CatalogProduct): boolean {
    return product.listPrice != null && product.price != null
      ? Number(product.listPrice) > Number(product.price)
      : false
  }
  function hasBenefits(product: CatalogProduct): boolean {
    return Boolean(
      product.couponCodes?.length ||
      product.paymentMethod ||
      product.routeInstructions ||
      product.cashback ||
      product.points ||
      product.storePromotions?.length,
    )
  }
  return { discounted, hasBenefits }
}
