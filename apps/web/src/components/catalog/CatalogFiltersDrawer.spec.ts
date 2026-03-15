import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CatalogFiltersDrawer from './CatalogFiltersDrawer.vue'

describe('CatalogFiltersDrawer', () => {
  it('emits advanced filter updates and actions', async () => {
    const wrapper = mount(CatalogFiltersDrawer, {
      props: {
        brand: '',
        concentrationMax: null,
        concentrationMin: null,
        modelValue: true,
        priceMax: null,
        priceMin: null,
        pricePerGramMax: null,
        pricePerGramMin: null,
      },
    })

    const inputs = wrapper.findAll('input')

    await inputs[0]?.setValue('max')
    await inputs[1]?.setValue('50')
    await inputs[2]?.setValue('150')
    await inputs[3]?.setValue('0.1')
    await inputs[4]?.setValue('0.5')
    await inputs[5]?.setValue('70')
    await inputs[6]?.setValue('90')
    await wrapper.findAll('button')[1]?.trigger('click')
    await wrapper.findAll('button')[2]?.trigger('click')

    expect(wrapper.emitted('update:brand')?.[0]).toEqual(['max'])
    expect(wrapper.emitted('update:priceMin')?.[0]).toEqual([50])
    expect(wrapper.emitted('update:priceMax')?.[0]).toEqual([150])
    expect(wrapper.emitted('update:pricePerGramMin')?.[0]).toEqual([0.1])
    expect(wrapper.emitted('update:pricePerGramMax')?.[0]).toEqual([0.5])
    expect(wrapper.emitted('update:concentrationMin')?.[0]).toEqual([70])
    expect(wrapper.emitted('update:concentrationMax')?.[0]).toEqual([90])
    expect(wrapper.emitted('clear')).toHaveLength(1)
    expect(wrapper.emitted('apply')).toHaveLength(1)
  })

  it('closes on escape', async () => {
    const wrapper = mount(CatalogFiltersDrawer, {
      attachTo: document.body,
      props: {
        brand: '',
        concentrationMax: null,
        concentrationMin: null,
        modelValue: true,
        priceMax: null,
        priceMin: null,
        pricePerGramMax: null,
        pricePerGramMin: null,
      },
    })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
    wrapper.unmount()
  })
})
