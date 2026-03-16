import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { RouterLinkStub } from '@vue/test-utils'

import AppHeader from './AppHeader.vue'

describe('AppHeader', () => {
  it('emits when the alerts button is clicked', async () => {
    const wrapper = mount(AppHeader, {
      props: {
        isDark: false,
      },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    await wrapper.get('[data-test="alerts-trigger"]').trigger('click')

    expect(wrapper.emitted('open-alerts')).toHaveLength(1)
  })

  it('links both brand images to the catalog route', () => {
    const wrapper = mount(AppHeader, {
      props: {
        isDark: false,
      },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    const links = wrapper.findAllComponents(RouterLinkStub)

    expect(links).toHaveLength(2)
    expect(links[0]?.props('to')).toBe('/')
    expect(links[1]?.props('to')).toBe('/')
  })

  it('emits when the theme button is clicked', async () => {
    const wrapper = mount(AppHeader, {
      props: {
        isDark: false,
      },
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    await wrapper.get('[data-test="theme-toggle"]').trigger('click')

    expect(wrapper.emitted('toggle-theme')).toHaveLength(1)
  })
})
