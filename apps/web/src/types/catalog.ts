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
  name: string
  packagingDisplay: string
  netMass?: string | null
  lastPrice?: string | null
  pricePerActive?: string | null
  concentration?: string | null
  totalActive?: string | null
  externalLink?: string | null
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

export interface CatalogProductsResponse {
  active: CatalogActive | null
  massUnit: string
  pageInfo: CatalogPageInfo
  items: CatalogProduct[]
}
