import { effectScope, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCatalogTable } from './useCatalogTable'

const scopes: ReturnType<typeof effectScope>[] = []
function setupTable() {
  const scope = effectScope()
  scopes.push(scope)
  const catalog = scope.run(useCatalogTable)
  if (!catalog) throw new Error('No table')
  return catalog
}
afterEach(() => {
  scopes.splice(0).forEach((scope) => scope.stop())
  vi.useRealTimers()
})

describe('catalog server table', () => {
  it('uses API pagination and numeric sort keys rather than sorting only loaded rows', () => {
    const { table, variables } = setupTable()
    table.setPageIndex(3)
    table.getColumn('price')?.toggleSorting(true)
    expect(variables.value.filters).toMatchObject({ page: 1, sortBy: 'price', sortDir: 'desc' })
    table.setPageSize(24)
    expect(variables.value.filters?.perPage).toBe(24)
    expect(table.getColumn('product')?.getCanSort()).toBe(false)
    expect(table.options.manualFiltering).toBe(true)
    expect(table.options.manualSorting).toBe(true)
    expect(table.options.manualPagination).toBe(true)
  })

  it('debounces the search and the chosen brands, flavors and categories', async () => {
    vi.useFakeTimers()
    const { table, variables } = setupTable()
    table.setGlobalFilter(' whey ')
    table.getColumn('brand')?.setFilterValue(['dux', 'growth'])
    table.getColumn('flavors')?.setFilterValue(['Chocolate'])
    table.getColumn('category')?.setFilterValue(['Plant protein'])
    expect(variables.value.filters?.search).toBeNull()
    await nextTick()
    await vi.advanceTimersByTimeAsync(250)
    expect(variables.value.filters).toMatchObject({
      search: 'whey',
      brands: ['dux', 'growth'],
      flavors: ['Chocolate'],
      categories: ['Plant protein'],
    })
  })

  it('clears filters without resetting the price scenario or visible columns', async () => {
    vi.useFakeTimers()
    const { table, scenario, clearFilters, variables, filtersActive } = setupTable()
    scenario.value = 'best'
    table.getColumn('tags')?.toggleVisibility(true)
    table.getColumn('brand')?.setFilterValue(['dux'])
    await nextTick()
    await vi.advanceTimersByTimeAsync(250)
    expect(variables.value.filters?.brands).toEqual(['dux'])
    clearFilters()
    expect(filtersActive.value).toBe(false)
    expect(variables.value.filters?.brands).toEqual([])
    expect(scenario.value).toBe('best')
    expect(table.getColumn('tags')?.getIsVisible()).toBe(true)
  })

  it('keeps nutrition profiles of the same product as separate rows', () => {
    const { table, rows } = setupTable()
    const product = {
      id: 1,
      name: 'Whey',
      packagingDisplay: 'Refill',
      brand: { name: 'Dux' },
      tags: [],
    }
    rows.value = [
      { ...product, nutritionProfile: { id: 10, nutritionFactsId: 1, flavors: ['Chocolate'] } },
      { ...product, nutritionProfile: { id: 11, nutritionFactsId: 2, flavors: ['Vanilla'] } },
    ]
    expect(table.getRowModel().rows.map((row) => row.id)).toEqual(['1:10', '1:11'])
  })
})
