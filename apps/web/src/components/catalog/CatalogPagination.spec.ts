import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CatalogPagination from './CatalogPagination.vue'

describe('CatalogPagination', () => {
  it('emits page updates from previous, numbered, and next controls', async () => {
    const wrapper = mount(CatalogPagination, {
      props: {
        pageInfo: {
          currentPage: 3,
          perPage: 12,
          totalPages: 6,
          totalCount: 72,
          hasPreviousPage: true,
          hasNextPage: true,
        },
      },
    })

    expect(wrapper.text()).toContain('72 products')
    expect(wrapper.text()).toContain('Page 3 of 6')
    expect(wrapper.text()).toContain('12 per page')

    const buttons = wrapper.findAll('button')

    await buttons[0]?.trigger('click')
    await buttons[2]?.trigger('click')
    await buttons[buttons.length - 1]?.trigger('click')

    expect(wrapper.emitted('update:page')?.[0]).toEqual([2])
    expect(wrapper.emitted('update:page')?.[1]).toEqual([2])
    expect(wrapper.emitted('update:page')?.[2]).toEqual([4])
  })
})
