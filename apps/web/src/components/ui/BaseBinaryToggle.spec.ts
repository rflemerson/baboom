import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { Grid3X3, List } from 'lucide-vue-next'

import BaseBinaryToggle from './BaseBinaryToggle.vue'

describe('BaseBinaryToggle', () => {
  it('toggles to the opposite value when clicked', async () => {
    const wrapper = mount(BaseBinaryToggle, {
      props: {
        modelValue: 'grid',
        name: 'View mode',
        options: [
          {
            ariaLabel: 'Grid view',
            icon: Grid3X3,
            title: 'Grid view',
            value: 'grid',
          },
          {
            ariaLabel: 'List view',
            icon: List,
            title: 'List view',
            value: 'list',
          },
        ],
        testId: 'view-toggle',
      },
    })

    await wrapper.get('[data-test="view-toggle"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['list']])
  })
})
