import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { CATALOG_SORT_OPTIONS } from '@/composables/useCatalogFilters'
import CatalogToolbar from './CatalogToolbar.vue'

describe('CatalogToolbar', () => {
  it('emits search, sort, per-page, drawer, clear, and direction events', async () => {
    const wrapper = mount(CatalogToolbar, {
      props: {
        advancedFiltersActive: false,
        perPage: 12,
        search: '',
        sortBy: 'price_per_gram',
        sortDir: 'asc',
        sortOptions: CATALOG_SORT_OPTIONS,
        viewMode: 'grid',
      },
    })

    await wrapper.get('input[type="search"]').setValue('whey')
    await wrapper.findAll('select')[0]?.setValue('last_price')
    await wrapper.findAll('select')[1]?.setValue('24')

    await wrapper.get('[data-test="open-filters"]').trigger('click')
    await wrapper.get('[data-test="sort-direction-toggle"]').trigger('click')
    await wrapper.get('[data-test="view-mode-toggle"]').trigger('click')
    await wrapper.get('[data-test="clear-filters"]').trigger('click')

    expect(wrapper.emitted('update:search')?.[0]).toEqual(['whey'])
    expect(wrapper.emitted('update:sortBy')?.[0]).toEqual(['last_price'])
    expect(wrapper.emitted('update:perPage')?.[0]).toEqual([24])
    expect(wrapper.emitted('openFilters')).toHaveLength(1)
    expect(wrapper.emitted('toggle:sortDir')).toHaveLength(1)
    expect(wrapper.emitted('update:viewMode')?.[0]).toEqual(['list'])
    expect(wrapper.emitted('update:viewMode')).toHaveLength(1)
    expect(wrapper.emitted('clear')).toHaveLength(1)
  })
})
