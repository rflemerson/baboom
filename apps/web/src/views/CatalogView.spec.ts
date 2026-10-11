import { computed, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/composables/useCatalogQuery', () => ({
  useCatalogQuery: vi.fn(),
}))

import { useCatalogQuery } from '@/composables/useCatalogQuery'
import CatalogView from './CatalogView.vue'

function queryResult() {
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
  }
}

function scenarioOptions(wrapper: ReturnType<typeof mount>) {
  const select = wrapper
    .findAll('details')
    .find((details) => details.find('summary[aria-label="Preço que o catálogo compara"]').exists())
  return select?.findAll('.app-select__menu button') ?? []
}

describe('CatalogView', () => {
  it('renders the fetched item', () => {
    vi.mocked(useCatalogQuery).mockReturnValue(queryResult())

    const wrapper = mount(CatalogView)

    expect(wrapper.text()).toContain('100% Whey Concentrado 900g')
  })

  it('leads with the best price and offers the catalog price', () => {
    vi.mocked(useCatalogQuery).mockReturnValue(queryResult())

    const wrapper = mount(CatalogView)

    const options = scenarioOptions(wrapper)
    expect(options.map((option) => option.text())).toEqual(['Melhor preço', 'Preço de catálogo'])
  })

  it('shows a recoverable error and retries the API request', async () => {
    const query = queryResult()
    vi.mocked(useCatalogQuery).mockReturnValue({
      ...query,
      error: computed(() => new Error('Failed request')),
    })
    const wrapper = mount(CatalogView)
    expect(wrapper.get('[role="alert"]').text()).toContain('Não foi possível carregar o catálogo')
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(query.refetch).toHaveBeenCalledOnce()
  })

  it('renders the 100 g price without rounding the per-gram value first', () => {
    vi.mocked(useCatalogQuery).mockReturnValue(queryResult())
    const wrapper = mount(CatalogView)
    expect(wrapper.findAll('td').some((cell) => cell.text().includes('18,00'))).toBe(true)
    expect(wrapper.text()).toContain('Por 100 g de Protein')
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
