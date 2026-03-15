import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseModal from './BaseModal.vue'

describe('BaseModal', () => {
  it('emits close on backdrop click', async () => {
    const wrapper = mount(BaseModal, {
      props: {
        modelValue: true,
      },
      slots: {
        default: '<div>Modal content</div>',
      },
    })

    await wrapper.get('.app-dialog-backdrop').trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('emits close on escape', async () => {
    const wrapper = mount(BaseModal, {
      attachTo: document.body,
      props: {
        modelValue: true,
      },
      slots: {
        default: '<button type="button">Focusable</button>',
      },
    })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
    wrapper.unmount()
  })
})
