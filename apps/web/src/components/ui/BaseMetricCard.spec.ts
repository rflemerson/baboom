import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseMetricCard from './BaseMetricCard.vue'

describe('BaseMetricCard', () => {
  it('renders label and value', () => {
    const wrapper = mount(BaseMetricCard, {
      props: {
        label: 'Price / g',
        value: '0.23',
      },
    })

    expect(wrapper.text()).toContain('Price / g')
    expect(wrapper.text()).toContain('0.23')
  })
})
