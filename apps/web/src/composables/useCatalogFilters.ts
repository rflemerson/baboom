import { computed, onScopeDispose, ref, watch } from 'vue'

import type { CatalogProductsVariables } from '@/types/catalog'

export const CATALOG_SORT_OPTIONS = [
  { label: 'Price / g', value: 'price_per_gram' },
  { label: 'Price', value: 'last_price' },
  { label: 'Protein', value: 'total_protein' },
  { label: 'Concentration', value: 'concentration' },
] as const

export const CATALOG_SEARCH_DEBOUNCE_MS = 250

const DEFAULT_CATALOG_PRODUCTS_VARIABLES: CatalogProductsVariables = {
  page: 1,
  perPage: 12,
  search: null,
  brand: null,
  priceMin: null,
  priceMax: null,
  pricePerGramMin: null,
  pricePerGramMax: null,
  concentrationMin: null,
  concentrationMax: null,
  sortBy: 'price_per_gram',
  sortDir: 'asc',
}

export function useCatalogFilters() {
  const search = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.search ?? '')
  const debouncedSearch = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.search ?? '')
  const brand = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.brand ?? '')
  const priceMin = ref<number | null>(DEFAULT_CATALOG_PRODUCTS_VARIABLES.priceMin ?? null)
  const priceMax = ref<number | null>(DEFAULT_CATALOG_PRODUCTS_VARIABLES.priceMax ?? null)
  const pricePerGramMin = ref<number | null>(
    DEFAULT_CATALOG_PRODUCTS_VARIABLES.pricePerGramMin ?? null,
  )
  const pricePerGramMax = ref<number | null>(
    DEFAULT_CATALOG_PRODUCTS_VARIABLES.pricePerGramMax ?? null,
  )
  const concentrationMin = ref<number | null>(
    DEFAULT_CATALOG_PRODUCTS_VARIABLES.concentrationMin ?? null,
  )
  const concentrationMax = ref<number | null>(
    DEFAULT_CATALOG_PRODUCTS_VARIABLES.concentrationMax ?? null,
  )
  const sortBy = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.sortBy)
  const sortDir = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.sortDir)
  const page = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.page)
  const perPage = ref(DEFAULT_CATALOG_PRODUCTS_VARIABLES.perPage)
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

  watch(
    search,
    (value) => {
      if (searchDebounceTimer) {
        clearTimeout(searchDebounceTimer)
      }

      searchDebounceTimer = setTimeout(() => {
        debouncedSearch.value = value
      }, CATALOG_SEARCH_DEBOUNCE_MS)
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
    }
  })

  const variables = computed<CatalogProductsVariables>(() => ({
    page: page.value,
    perPage: perPage.value,
    search: debouncedSearch.value.trim() || null,
    brand: brand.value.trim() || null,
    priceMin: priceMin.value,
    priceMax: priceMax.value,
    pricePerGramMin: pricePerGramMin.value,
    pricePerGramMax: pricePerGramMax.value,
    concentrationMin: concentrationMin.value,
    concentrationMax: concentrationMax.value,
    sortBy: sortBy.value,
    sortDir: sortDir.value,
  }))

  function setSearch(value: string) {
    search.value = value
    page.value = 1
  }

  function setBrand(value: string) {
    brand.value = value
    page.value = 1
  }

  function setPriceMin(value: number | null) {
    priceMin.value = value
    page.value = 1
  }

  function setPriceMax(value: number | null) {
    priceMax.value = value
    page.value = 1
  }

  function setPricePerGramMin(value: number | null) {
    pricePerGramMin.value = value
    page.value = 1
  }

  function setPricePerGramMax(value: number | null) {
    pricePerGramMax.value = value
    page.value = 1
  }

  function setConcentrationMin(value: number | null) {
    concentrationMin.value = value
    page.value = 1
  }

  function setConcentrationMax(value: number | null) {
    concentrationMax.value = value
    page.value = 1
  }

  function setSortBy(value: CatalogProductsVariables['sortBy']) {
    sortBy.value = value
    page.value = 1
  }

  function toggleSortDirection() {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    page.value = 1
  }

  function setPerPage(value: number) {
    perPage.value = value
    page.value = 1
  }

  function setPage(value: number) {
    page.value = value
  }

  function clearFilters() {
    search.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.search ?? ''
    brand.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.brand ?? ''
    priceMin.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.priceMin ?? null
    priceMax.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.priceMax ?? null
    pricePerGramMin.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.pricePerGramMin ?? null
    pricePerGramMax.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.pricePerGramMax ?? null
    concentrationMin.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.concentrationMin ?? null
    concentrationMax.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.concentrationMax ?? null
    sortBy.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.sortBy
    sortDir.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.sortDir
    page.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.page
    perPage.value = DEFAULT_CATALOG_PRODUCTS_VARIABLES.perPage
  }

  return {
    brand,
    clearFilters,
    concentrationMax,
    concentrationMin,
    page,
    perPage,
    priceMax,
    priceMin,
    pricePerGramMax,
    pricePerGramMin,
    search,
    setBrand,
    setConcentrationMax,
    setConcentrationMin,
    setPage,
    setPerPage,
    setPriceMax,
    setPriceMin,
    setPricePerGramMax,
    setPricePerGramMin,
    setSearch,
    setSortBy,
    sortBy,
    sortDir,
    sortOptions: CATALOG_SORT_OPTIONS,
    toggleSortDirection,
    variables,
  }
}
