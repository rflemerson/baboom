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

    expect(wrapper.text()).toContain('Alertas')
    expect(wrapper.text()).toContain('Informe seu e-mail para receber avisos.')
    expect(wrapper.text()).toContain('Inscrever')
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

    expect(wrapper.text()).toContain('Inscrição feita!')
  })

  it('renders inline validation feedback on error', () => {
    vi.mocked(useAlertSubscription).mockReturnValue({
      canSubmit: computed(() => false),
      email: ref('invalid-email'),
      emailIsValid: computed(() => false),
      errorMessage: ref('Informe um e-mail válido.'),
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

    expect(wrapper.text()).toContain('Informe um e-mail válido.')
    expect(wrapper.find('input[type="email"]').classes()).toContain('is-invalid')
  })

  it('closes on escape', async () => {
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
      attachTo: document.body,
      props: {
        modelValue: true,
      },
    })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
    wrapper.unmount()
  })
})
