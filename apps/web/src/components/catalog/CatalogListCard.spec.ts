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
          netMass: '1000',
          price: '199.90',
          pricePerActive: '0.23',
          concentration: '86.6',
          totalActive: '866',
          externalLink: 'https://example.com/whey-isolado',
          brand: { name: 'integralmedica' },
          category: { name: 'Whey Protein' },
          tags: [{ name: 'Whey' }, { name: 'Isolado' }],
        },
        activeName: 'Protein',
        massUnit: 'g',
      },
    })

    expect(wrapper.text()).toContain('Whey Isolado 1kg')
    expect(wrapper.text()).toContain('integralmedica')
    expect(wrapper.text()).toContain('Container Package')
    expect(wrapper.text()).toContain('Price / Protein g')
    expect(wrapper.text()).toContain('0.23')
    expect(wrapper.text()).toContain('86.6% concentration')
    expect(wrapper.get('a[aria-label="View offer for Whey Isolado 1kg"]').attributes('href')).toBe(
      'https://example.com/whey-isolado',
    )
  })

  it('tells what to do to get the shown price', () => {
    const wrapper = mount(CatalogListCard, {
      props: {
        product: {
          id: 4,
          name: 'Whey 900g',
          packagingDisplay: 'Refill Package',
          price: '80.00',
          currency: 'BRL',
          paymentMethod: 'pix',
          couponCodes: ['SYNTH20'],
          cashback: { amount: '15.00', currency: 'BRL' },
          routeInstructions: 'Open the link before adding to the cart.',
          brand: { name: 'x' },
          tags: [],
        },
      },
    })

    const notes = wrapper.get('[data-testid="price-notes"]').text()
    expect(notes).toContain('Use o cupom SYNTH20')
    expect(notes).toContain('Pagando com Pix')
    expect(notes).toContain('+ BRL 15.00 de cashback')
    expect(notes).toContain('Open the link before adding to the cart.')
    expect(wrapper.text()).toContain('BRL 80.00')
  })

  it('shows no price notes when the price needs nothing', () => {
    const wrapper = mount(CatalogListCard, {
      props: {
        product: {
          id: 5,
          name: 'Whey',
          packagingDisplay: 'Refill Package',
          price: '80.00',
          couponCodes: [],
          cashback: null,
          routeInstructions: null,
          brand: { name: 'x' },
          tags: [],
        },
      },
    })

    expect(wrapper.find('[data-testid="price-notes"]').exists()).toBe(false)
  })
})
