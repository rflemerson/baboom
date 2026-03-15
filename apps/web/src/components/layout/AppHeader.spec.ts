import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AppHeader from './AppHeader.vue'

describe('AppHeader', () => {
  it('emits when the alerts button is clicked', async () => {
    const wrapper = mount(AppHeader)

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('open-alerts')).toHaveLength(1)
  })
})
