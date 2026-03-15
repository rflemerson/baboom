import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, ref } from 'vue'

vi.mock('@/composables/useAlertSubscription', () => ({
  useAlertSubscription: vi.fn(),
}))

import { useAlertSubscription } from '@/composables/useAlertSubscription'
import AlertSubscribeDialog from './AlertSubscribeDialog.vue'

describe('AlertSubscribeDialog', () => {
  it('renders the subscribe form when idle', () => {
    vi.mocked(useAlertSubscription).mockReturnValue({
      canSubmit: computed(() => true),
      email: ref(''),
      errorMessage: ref(null),
      loading: ref(false),
      reset: vi.fn(),
      status: ref('idle'),
      submit: vi.fn(),
    })

    const wrapper = mount(AlertSubscribeDialog, {
      props: {
        modelValue: true,
      },
    })

    expect(wrapper.text()).toContain('Price alerts')
    expect(wrapper.text()).toContain('Subscribe')
  })

  it('renders the success state', () => {
    vi.mocked(useAlertSubscription).mockReturnValue({
      canSubmit: computed(() => false),
      email: ref('user@example.com'),
      errorMessage: ref(null),
      loading: ref(false),
      reset: vi.fn(),
      status: ref('success'),
      submit: vi.fn(),
    })

    const wrapper = mount(AlertSubscribeDialog, {
      props: {
        modelValue: true,
      },
    })

    expect(wrapper.text()).toContain('You are on the alert list.')
  })
})
