import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CatalogGridCard from './CatalogGridCard.vue'

describe('CatalogGridCard', () => {
  it('renders the product information', () => {
    const wrapper = mount(CatalogGridCard, {
      props: {
        product: {
          id: 1,
          name: 'Whey Isolado 1kg',
          packagingDisplay: 'Container Package',
          weight: 1000,
          lastPrice: '199.90',
          pricePerProteinGram: '0.23',
          concentration: '86.6',
          totalProtein: '866',
          externalLink: 'https://example.com/whey-isolado',
          brand: { name: 'integralmedica' },
          category: { name: 'Whey Protein' },
          tags: [{ name: 'Whey' }, { name: 'Isolado' }],
        },
      },
    })

    expect(wrapper.text()).toContain('Whey Isolado 1kg')
    expect(wrapper.text()).toContain('integralmedica')
    expect(wrapper.text()).toContain('1000 g')
    expect(wrapper.text()).toContain('Whey')
    expect(wrapper.text()).toContain('Isolado')
    expect(wrapper.text()).toContain('86.6% concentration')
  })
})
