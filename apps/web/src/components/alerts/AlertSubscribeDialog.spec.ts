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
      emailIsValid: computed(() => true),
      errorMessage: ref(null),
      hasEmail: computed(() => false),
      loading: ref(false),
      reset: vi.fn(),
      showFieldError: computed(() => false),
      status: ref('idle'),
      submit: vi.fn(),
    })

    const wrapper = mount(AlertSubscribeDialog, {
      props: {
        modelValue: true,
      },
    })

    expect(wrapper.text()).toContain('Alerts')
    expect(wrapper.text()).toContain('Enter your email to receive notifications.')
    expect(wrapper.text()).toContain('Subscribe')
  })

  it('renders the success state', () => {
    vi.mocked(useAlertSubscription).mockReturnValue({
      canSubmit: computed(() => false),
      email: ref('user@example.com'),
      emailIsValid: computed(() => true),
      errorMessage: ref(null),
      hasEmail: computed(() => true),
      loading: ref(false),
      reset: vi.fn(),
      showFieldError: computed(() => false),
      status: ref('success'),
      submit: vi.fn(),
    })

    const wrapper = mount(AlertSubscribeDialog, {
      props: {
        modelValue: true,
      },
    })

    expect(wrapper.text()).toContain("You're Subscribed!")
  })

  it('renders inline validation feedback on error', () => {
    vi.mocked(useAlertSubscription).mockReturnValue({
      canSubmit: computed(() => false),
      email: ref('invalid-email'),
      emailIsValid: computed(() => false),
      errorMessage: ref('Please enter a valid email address.'),
      hasEmail: computed(() => true),
      loading: ref(false),
      reset: vi.fn(),
      showFieldError: computed(() => true),
      status: ref('error'),
      submit: vi.fn(),
    })

    const wrapper = mount(AlertSubscribeDialog, {
      props: {
        modelValue: true,
      },
    })

    expect(wrapper.text()).toContain('Please enter a valid email address.')
    expect(wrapper.find('input[type="email"]').classes()).toContain('border-red-400')
  })
})
