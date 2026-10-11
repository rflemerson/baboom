import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import { useDisclosure } from './useDisclosure'

const Menu = defineComponent({
  setup() {
    const { root, escape } = useDisclosure()
    return () =>
      h('details', { ref: root, open: true, onKeydown: escape }, [
        h('summary', 'Menu'),
        h('button', { class: 'inside' }, 'Option'),
      ])
  },
})

describe('useDisclosure', () => {
  it('stays open on a press inside and closes on a press outside', () => {
    const wrapper = mount(Menu, { attachTo: document.body })
    const details = wrapper.element as HTMLDetailsElement

    wrapper.get('.inside').element.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    expect(details.open).toBe(true)

    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    expect(details.open).toBe(false)
    wrapper.unmount()
  })

  it('closes on Escape', async () => {
    const wrapper = mount(Menu, { attachTo: document.body })

    await wrapper.trigger('keydown', { key: 'Escape' })

    expect((wrapper.element as HTMLDetailsElement).open).toBe(false)
    wrapper.unmount()
  })
})
