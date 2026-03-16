import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CatalogResults from './CatalogResults.vue'

const pageInfo = {
  currentPage: 1,
  perPage: 12,
  totalPages: 1,
  totalCount: 1,
  hasPreviousPage: false,
  hasNextPage: false,
}

const products = [
  {
    id: 1,
    name: 'Creatina Monohidratada 300g',
    packagingDisplay: 'Container Package',
    weight: 300,
    lastPrice: '89.90',
    pricePerGram: null,
    concentration: '0',
    totalProtein: '0',
    externalLink: 'https://example.com/creatina',
    brand: { name: 'max-titanium' },
    category: { name: 'Creatina' },
    tags: [{ name: 'Creatina' }],
  },
]

describe('CatalogResults', () => {
  it('renders loading state', () => {
    const wrapper = mount(CatalogResults, {
      props: {
        pageInfo: null,
        products: [],
        loading: true,
        viewMode: 'grid',
      },
    })

    expect(wrapper.text()).toContain('Loading products...')
    expect(wrapper.findAll('[data-test="catalog-loading-card"]')).toHaveLength(6)
  })

  it('renders an empty state', async () => {
    const wrapper = mount(CatalogResults, {
      props: {
        pageInfo,
        filtersActive: true,
        products: [],
        loading: false,
        viewMode: 'grid',
      },
    })

    expect(wrapper.text()).toContain('No products matched this search')
    expect(wrapper.text()).toContain('Clear filters')

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('clear-filters')).toHaveLength(1)
  })

  it('renders an error state', async () => {
    const wrapper = mount(CatalogResults, {
      props: {
        pageInfo,
        filtersActive: true,
        products: [],
        loading: false,
        errorMessage: 'GraphQL exploded',
        viewMode: 'grid',
      },
    })

    expect(wrapper.text()).toContain("We couldn't load the catalog")
    expect(wrapper.text()).toContain('GraphQL exploded')

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('renders result cards', () => {
    const wrapper = mount(CatalogResults, {
      props: {
        pageInfo,
        products,
        loading: false,
        viewMode: 'grid',
      },
    })

    expect(wrapper.text()).toContain('Creatina Monohidratada 300g')
  })
})
