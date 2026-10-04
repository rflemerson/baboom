import { computed, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/composables/useCatalogQuery', () => ({
  useCatalogQuery: vi.fn(),
}))

import { useCatalogQuery } from '@/composables/useCatalogQuery'
import CatalogView from './CatalogView.vue'

function queryResult(scenarioAvailable: boolean) {
  return {
    active: computed(() => ({ slug: 'protein', name: 'Protein' })),
    massUnit: computed(() => 'g'),
    error: computed(() => null),
    loading: computed(() => false),
    pageInfo: computed(() => ({
      currentPage: 1,
      perPage: 12,
      totalPages: 1,
      totalCount: 1,
      hasPreviousPage: false,
      hasNextPage: false,
    })),
    products: computed(() => [
      {
        id: 1,
        name: '100% Whey Concentrado 900g',
        packagingDisplay: 'Refill Package',
        netMass: '900',
        price: '129.90',
        pricePerActive: '0.18',
        concentration: '80',
        totalActive: '720',
        externalLink: 'https://example.com/whey',
        brand: { name: 'max-titanium' },
        category: { name: 'Whey Protein' },
        tags: [{ name: 'Whey' }],
      },
    ]),
    refetch: vi.fn(),
    result: ref(null),
    scenarioAvailable: ref(scenarioAvailable),
  }
}

describe('CatalogView', () => {
  it('renders the fetched item', () => {
    vi.mocked(useCatalogQuery).mockReturnValue(queryResult(true))

    const wrapper = mount(CatalogView)

    expect(wrapper.text()).toContain('100% Whey Concentrado 900g')
  })

  it('offers the best price where the market has projections', () => {
    vi.mocked(useCatalogQuery).mockReturnValue(queryResult(true))

    const wrapper = mount(CatalogView)

    const options = wrapper.findAll('select[aria-label="Price the catalog compares"] option')
    expect(options.map((option) => option.text())).toEqual(['Normal price', 'Best price'])
  })

  it('hides the best price where the market still reads current prices', () => {
    vi.mocked(useCatalogQuery).mockReturnValue(queryResult(false))

    const wrapper = mount(CatalogView)

    const options = wrapper.findAll('select[aria-label="Price the catalog compares"] option')
    expect(options.map((option) => option.text())).toEqual(['Normal price'])
  })
})
