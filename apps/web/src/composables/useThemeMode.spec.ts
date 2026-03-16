import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'

import { useThemeMode } from './useThemeMode'

describe('useThemeMode', () => {
  beforeEach(() => {
    window.localStorage.clear()
    delete document.documentElement.dataset.theme
  })

  it('defaults to light theme and writes it to the document', async () => {
    const TestComponent = defineComponent({
      setup() {
        return useThemeMode()
      },
      template: '<div />',
    })

    mount(TestComponent)
    await nextTick()

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem('baboom.theme')).toBe('light')
  })

  it('restores the stored theme and toggles it', async () => {
    window.localStorage.setItem('baboom.theme', 'dark')

    const TestComponent = defineComponent({
      setup() {
        return useThemeMode()
      },
      template: '<button @click="toggleTheme">{{ theme }}</button>',
    })

    const wrapper = mount(TestComponent)
    await nextTick()

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(wrapper.text()).toContain('dark')

    await wrapper.get('button').trigger('click')

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem('baboom.theme')).toBe('light')
  })
})
