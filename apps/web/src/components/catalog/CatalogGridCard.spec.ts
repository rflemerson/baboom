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
      },
    })

    expect(wrapper.text()).toContain('Whey Isolado 1kg')
    expect(wrapper.text()).toContain('integralmedica')
    expect(wrapper.text()).toContain('1000 g')
    expect(wrapper.text()).toContain('Whey')
    expect(wrapper.text()).toContain('Isolado')
    expect(wrapper.text()).toContain('86.6% concentration')
    expect(wrapper.text()).toContain('Total price')
    expect(wrapper.text()).not.toContain('Total price (')
  })

  it('names the payment method behind the price', () => {
    const wrapper = mount(CatalogGridCard, {
      props: {
        product: {
          id: 2,
          name: 'Whey 900g',
          packagingDisplay: 'Refill Package',
          price: '96.03',
          paymentMethod: 'pix',
          brand: { name: 'max-titanium' },
          tags: [],
        },
      },
    })

    expect(wrapper.text()).toContain('Total price (Pix)')
    expect(wrapper.text()).toContain('96.03')
  })

  it('warns when the link may open another seller', () => {
    const wrapper = mount(CatalogGridCard, {
      props: {
        product: {
          id: 3,
          name: 'Whey',
          packagingDisplay: 'Refill Package',
          linkSelectsSeller: false,
          brand: { name: 'x' },
          tags: [],
        },
      },
    })

    expect(wrapper.text()).toContain("may open another seller's offer")
  })

  it('tells what to do to get the shown price', () => {
    const wrapper = mount(CatalogGridCard, {
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
    const wrapper = mount(CatalogGridCard, {
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
