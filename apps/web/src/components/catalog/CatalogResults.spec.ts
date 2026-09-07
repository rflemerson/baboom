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
    netMass: '300',
    lastPrice: '89.90',
    pricePerActive: null,
    concentration: '0',
    totalActive: '0',
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
        errorMessage: 'API exploded',
        viewMode: 'grid',
      },
    })

    expect(wrapper.text()).toContain("We couldn't load the catalog")
    expect(wrapper.text()).toContain('API exploded')

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

  it.each(['grid', 'list'] as const)(
    'keeps profiles distinct when sorting %s cards',
    async (viewMode) => {
      const base = products[0]!
      const chocolate = {
        ...base,
        nutritionProfile: { id: 10, nutritionFactsId: 100, flavors: ['Chocolate', 'Cocoa'] },
        concentration: '70',
      }
      const vanilla = {
        ...base,
        nutritionProfile: { id: 11, nutritionFactsId: 101, flavors: ['Vanilla'] },
        concentration: '80',
      }
      const wrapper = mount(CatalogResults, {
        props: { pageInfo, products: [chocolate, vanilla], loading: false, viewMode },
      })
      const cards = () => wrapper.findAll('article')
      expect(cards()).toHaveLength(2)
      expect(cards()[0]!.text()).toContain('Chocolate, Cocoa')
      expect(cards()[0]!.text()).toContain('70.0% concentration')
      expect(cards()[1]!.text()).toContain('Vanilla')
      expect(cards()[1]!.text()).toContain('80.0% concentration')
      await wrapper.setProps({ products: [vanilla, chocolate] })
      expect(cards()[0]!.text()).toContain('Vanilla')
      expect(cards()[1]!.text()).toContain('Chocolate, Cocoa')
      await wrapper.setProps({ products: [chocolate] })
      expect(cards()).toHaveLength(1)
      expect(cards()[0]!.text()).toContain('Chocolate, Cocoa')
    },
  )
})
