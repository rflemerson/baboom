import { describe, expect, it } from 'vitest'

import { useCatalogFilters } from './useCatalogFilters'

describe('useCatalogFilters', () => {
  it('builds default query variables', () => {
    const { variables } = useCatalogFilters()

    expect(variables.value).toEqual({
      brand: null,
      concentrationMax: null,
      concentrationMin: null,
      page: 1,
      perPage: 12,
      priceMax: null,
      priceMin: null,
      pricePerGramMax: null,
      pricePerGramMin: null,
      search: null,
      sortBy: 'price_per_gram',
      sortDir: 'asc',
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
})
