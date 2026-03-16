import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CatalogListCard from './CatalogListCard.vue'

describe('CatalogListCard', () => {
  it('renders the product in list mode', () => {
    const wrapper = mount(CatalogListCard, {
      props: {
        product: {
          id: 1,
          name: 'Whey Isolado 1kg',
          packagingDisplay: 'Container Package',
          weight: 1000,
          lastPrice: '199.90',
          pricePerGram: '0.23',
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
    expect(wrapper.text()).toContain('Container Package')
    expect(wrapper.text()).toContain('Price / g')
    expect(wrapper.text()).toContain('0.23')
    expect(wrapper.get('a[aria-label="View offer"]').attributes('href')).toBe(
      'https://example.com/whey-isolado',
    )
  })
})
