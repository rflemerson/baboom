import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BaseSelect from './BaseSelect.vue'

const props = {
  modelValue: '',
  label: 'Payment scenario',
  options: [
    { value: '', label: 'Normal price' },
    { value: 'best', label: 'Best price' },
  ],
}

describe('BaseSelect', () => {
  it('selects an option and closes the popup', async () => {
    const wrapper = mount(BaseSelect, { props })
    const root = wrapper.element as HTMLDetailsElement
    root.open = true
    await wrapper.findAll('button')[1]?.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['best']])
    expect(root.open).toBe(false)
    wrapper.unmount()
  })

  it('closes on Escape and outside clicks', async () => {
    const wrapper = mount(BaseSelect, { props, attachTo: document.body })
    const root = wrapper.element as HTMLDetailsElement
    root.open = true
    await wrapper.trigger('keydown', { key: 'Escape' })
    expect(root.open).toBe(false)
    root.open = true
    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    expect(root.open).toBe(false)
    wrapper.unmount()
  })

  it('picks several options from a list model and stays open', async () => {
    const wrapper = mount(BaseSelect, {
      props: {
        modelValue: ['coupon'],
        label: 'Benefits',
        emptyLabel: 'None',
        options: [
          { value: 'coupon', label: 'Coupons' },
          { value: 'cashback', label: 'Cashback' },
        ],
      },
    })
    const root = wrapper.element as HTMLDetailsElement
    root.open = true
    expect(wrapper.get('summary').text()).toBe('Coupons')
    await wrapper.findAll('button')[1]?.trigger('click')
    await wrapper.findAll('button')[0]?.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[['coupon', 'cashback']], [[]]])
    expect(root.open).toBe(true)
    await wrapper.setProps({ modelValue: [] })
    expect(wrapper.get('summary').text()).toBe('None')
    wrapper.unmount()
  })
})
