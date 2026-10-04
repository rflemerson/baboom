export interface CatalogProductsFilters {
  brand?: string | null
  concentrationMax?: number | null
  concentrationMin?: number | null
  page?: number | null
  perPage?: number | null
  priceMax?: number | null
  priceMin?: number | null
  active?: string | null
  pricePerActiveMax?: number | null
  pricePerActiveMin?: number | null
  scenario?: string | null
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
  pricePerActive?: string | null
  concentration?: string | null
  totalActive?: string | null
  externalLink?: string | null
  paymentMethod?: string | null
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
