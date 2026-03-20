import { computed, onScopeDispose, ref, watch } from 'vue'

import type { CatalogProductsVariables } from '@/types/catalog'

export const CATALOG_SORT_OPTIONS = [
  { label: 'Price / protein g', value: 'price_per_protein_gram' },
  { label: 'Price', value: 'last_price' },
  { label: 'Protein', value: 'total_protein' },
  { label: 'Concentration', value: 'concentration' },
] as const

export const CATALOG_SEARCH_DEBOUNCE_MS = 250

const DEFAULT_CATALOG_PRODUCTS_VARIABLES: CatalogProductsVariables = {
  filters: {
    page: 1,
    perPage: 12,
    search: null,
    brand: null,
    priceMin: null,
    priceMax: null,
    pricePerProteinGramMin: null,
    pricePerProteinGramMax: null,
    concentrationMin: null,
    concentrationMax: null,
    sortBy: 'price_per_protein_gram',
    sortDir: 'asc',
  },
}

export function useCatalogFilters() {
  const defaultFilters = DEFAULT_CATALOG_PRODUCTS_VARIABLES.filters

  const search = ref(defaultFilters?.search ?? '')
  const debouncedSearch = ref(defaultFilters?.search ?? '')
  const brand = ref(defaultFilters?.brand ?? '')
  const priceMin = ref<number | null>(defaultFilters?.priceMin ?? null)
  const priceMax = ref<number | null>(defaultFilters?.priceMax ?? null)
  const pricePerProteinGramMin = ref<number | null>(defaultFilters?.pricePerProteinGramMin ?? null)
  const pricePerProteinGramMax = ref<number | null>(defaultFilters?.pricePerProteinGramMax ?? null)
  const concentrationMin = ref<number | null>(defaultFilters?.concentrationMin ?? null)
  const concentrationMax = ref<number | null>(defaultFilters?.concentrationMax ?? null)
  const sortBy = ref(defaultFilters?.sortBy ?? 'price_per_protein_gram')
  const sortDir = ref(defaultFilters?.sortDir ?? 'asc')
  const page = ref(defaultFilters?.page ?? 1)
  const perPage = ref(defaultFilters?.perPage ?? 12)
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
    filters: {
      page: page.value,
      perPage: perPage.value,
      search: debouncedSearch.value.trim() || null,
      brand: brand.value.trim() || null,
      priceMin: priceMin.value,
      priceMax: priceMax.value,
      pricePerProteinGramMin: pricePerProteinGramMin.value,
      pricePerProteinGramMax: pricePerProteinGramMax.value,
      concentrationMin: concentrationMin.value,
      concentrationMax: concentrationMax.value,
      sortBy: sortBy.value,
      sortDir: sortDir.value,
    },
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

  function setPricePerProteinGramMin(value: number | null) {
    pricePerProteinGramMin.value = value
    page.value = 1
  }

  function setPricePerProteinGramMax(value: number | null) {
    pricePerProteinGramMax.value = value
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

  function setSortBy(
    value: NonNullable<NonNullable<CatalogProductsVariables['filters']>['sortBy']>,
  ) {
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
    search.value = defaultFilters?.search ?? ''
    brand.value = defaultFilters?.brand ?? ''
    priceMin.value = defaultFilters?.priceMin ?? null
    priceMax.value = defaultFilters?.priceMax ?? null
    pricePerProteinGramMin.value = defaultFilters?.pricePerProteinGramMin ?? null
    pricePerProteinGramMax.value = defaultFilters?.pricePerProteinGramMax ?? null
    concentrationMin.value = defaultFilters?.concentrationMin ?? null
    concentrationMax.value = defaultFilters?.concentrationMax ?? null
    sortBy.value = defaultFilters?.sortBy ?? 'price_per_protein_gram'
    sortDir.value = defaultFilters?.sortDir ?? 'asc'
    page.value = defaultFilters?.page ?? 1
    perPage.value = defaultFilters?.perPage ?? 12
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
    pricePerProteinGramMax,
    pricePerProteinGramMin,
    search,
    setBrand,
    setConcentrationMax,
    setConcentrationMin,
    setPage,
    setPerPage,
    setPriceMax,
    setPriceMin,
    setPricePerProteinGramMax,
    setPricePerProteinGramMin,
    setSearch,
    setSortBy,
    sortBy,
    sortDir,
    sortOptions: CATALOG_SORT_OPTIONS,
    toggleSortDirection,
    variables,
  }
}
