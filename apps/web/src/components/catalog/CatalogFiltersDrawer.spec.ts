import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CatalogFiltersDrawer from './CatalogFiltersDrawer.vue'

describe('CatalogFiltersDrawer', () => {
  it('keeps local drafts and emits apply payload', async () => {
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
    await wrapper.findAll('button')[2]?.trigger('click')

    expect(wrapper.emitted('apply')?.[0]).toEqual([
      {
        brand: 'max',
        concentrationMax: 90,
        concentrationMin: 70,
        priceMax: 150,
        priceMin: 50,
        pricePerGramMax: 0.5,
        pricePerGramMin: 0.1,
      },
    ])
  })

  it('clears drafts and closes the drawer', async () => {
    const wrapper = mount(CatalogFiltersDrawer, {
      props: {
        brand: 'dux',
        concentrationMax: 85,
        concentrationMin: 70,
        modelValue: true,
        priceMax: 150,
        priceMin: 50,
        pricePerGramMax: 0.5,
        pricePerGramMin: 0.1,
      },
    })

    await wrapper.findAll('button')[1]?.trigger('click')

    expect(wrapper.emitted('apply')).toBeUndefined()
    expect(wrapper.emitted('clear')).toHaveLength(1)
    const modelValueEvents = wrapper.emitted('update:modelValue')
    expect(modelValueEvents?.[modelValueEvents.length - 1]).toEqual([false])
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
