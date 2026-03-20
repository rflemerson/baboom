import { describe, expect, it, vi } from 'vitest'

import { CATALOG_SEARCH_DEBOUNCE_MS, useCatalogFilters } from './useCatalogFilters'

describe('useCatalogFilters', () => {
  it('builds default query variables', () => {
    const { variables } = useCatalogFilters()

    expect(variables.value).toEqual({
      filters: {
        brand: null,
        concentrationMax: null,
        concentrationMin: null,
        page: 1,
        perPage: 12,
        priceMax: null,
        priceMin: null,
        pricePerProteinGramMax: null,
        pricePerProteinGramMin: null,
        search: null,
        sortBy: 'price_per_protein_gram',
        sortDir: 'asc',
      },
    })
  })

  it('resets the page when filters change', () => {
    const {
      page,
      setBrand,
      setConcentrationMax,
      setPage,
      setPerPage,
      setPriceMin,
      setSearch,
      setSortBy,
      toggleSortDirection,
    } = useCatalogFilters()

    setPage(3)
    setSearch('whey')
    expect(page.value).toBe(1)

    setPage(4)
    setSortBy('last_price')
    expect(page.value).toBe(1)

    setPage(2)
    toggleSortDirection()
    expect(page.value).toBe(1)

    setPage(5)
    setPerPage(24)
    expect(page.value).toBe(1)

    setPage(6)
    setBrand('max')
    expect(page.value).toBe(1)

    setPage(7)
    setPriceMin(100)
    expect(page.value).toBe(1)

    setPage(8)
    setConcentrationMax(90)
    expect(page.value).toBe(1)
  })

  it('debounces the search variable used by the query', async () => {
    vi.useFakeTimers()

    const { setSearch, variables } = useCatalogFilters()

    setSearch('whey')
    expect(variables.value.filters?.search).toBeNull()

    await vi.advanceTimersByTimeAsync(CATALOG_SEARCH_DEBOUNCE_MS)

    expect(variables.value.filters?.search).toBe('whey')

    vi.useRealTimers()
  })
})
