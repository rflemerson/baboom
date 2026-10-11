export interface CatalogProductsFilters {
  brands?: string[]
  stock?: string[]
  categories?: string[]
  flavors?: string[]
  page?: number | null
  perPage?: number | null
  active?: string | null
  scenario?: string | null
  // False drops the prices that need that benefit.
  coupon?: boolean
  cashback?: boolean
  points?: boolean
  search?: string | null
  sortBy?: string | null
  sortDir?: string | null
}

export interface CatalogProductsVariables {
  filters?: CatalogProductsFilters | null
}

export interface CatalogPageInfo {
  currentPage: number
  perPage: number
  totalPages: number
  totalCount: number
  hasPreviousPage: boolean
  hasNextPage: boolean
}

export interface CatalogProduct {
  id: number
  nutritionProfile?: {
    id: number
    nutritionFactsId: number
    flavors: string[]
  } | null
  name: string
  packagingDisplay: string
  netMass?: string | null
  price?: string | null
  // The store's own price before any benefit; equal to price when none applies.
  listPrice?: string | null
  pricePerActive?: string | null
  concentration?: string | null
  totalActive?: string | null
  externalLink?: string | null
  paymentMethod?: string | null
  couponCodes?: string[]
  cashback?: {
    amount: string
    currency: string
  } | null
  points?: number | null
  // Promotions the store has that never enter the price (no code to publish).
  storePromotions?: { title: string; kind: 'coupon' | 'cashback' | 'points' | 'promotion' }[]
  routeInstructions?: string | null
  stockStatus?: CatalogStockStatus
  optimizationStatus?: 'complete' | 'bounded' | null
  currency?: string | null
  linkSelectsSeller?: boolean | null
  brand: {
    name: string
  }
  category?: {
    name: string
  } | null
  tags: Array<{
    name: string
  }>
}

export interface CatalogActive {
  slug: string
  name: string
}

export interface CatalogScenario {
  key: string
  version: number | null
}

export interface CatalogMarket {
  country: string
  currency: string
}

export interface CatalogProductsResponse {
  active: CatalogActive | null
  massUnit: string
  market?: CatalogMarket
  scenario?: CatalogScenario
  pageInfo: CatalogPageInfo
  items: CatalogProduct[]
}

export interface CatalogFilterOption {
  name: string
  label: string
}

export interface CatalogFilterOptions {
  brands: CatalogFilterOption[]
  flavors: CatalogFilterOption[]
  categories: CatalogFilterOption[]
}

export const STOCK_STATUSES = ['in_stock', 'out_of_stock', 'preorder', 'unknown'] as const
export type CatalogStockStatus = (typeof STOCK_STATUSES)[number]
