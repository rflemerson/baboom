import { computed, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@vue/apollo-composable', () => ({
  useMutation: vi.fn(),
}))

import { useMutation } from '@vue/apollo-composable'
import { useAlertSubscription } from './useAlertSubscription'

describe('useAlertSubscription', () => {
  it('sets success state when the mutation succeeds', async () => {
    vi.mocked(useMutation).mockReturnValue({
      loading: ref(false),
      mutate: vi.fn().mockResolvedValue({
        data: {
          subscribeAlerts: {
            success: true,
            alreadySubscribed: false,
            email: 'user@example.com',
            errors: null,
          },
        },
      }),
    } as never)

    const { email, status, submit } = useAlertSubscription()

    email.value = 'user@example.com'
    await submit()

    expect(status.value).toBe('success')
  })

  it('sets duplicate state when the email already exists', async () => {
    vi.mocked(useMutation).mockReturnValue({
      loading: ref(false),
      mutate: vi.fn().mockResolvedValue({
        data: {
          subscribeAlerts: {
            success: false,
            alreadySubscribed: true,
            email: 'user@example.com',
            errors: null,
          },
        },
      }),
    } as never)

    const { email, status, submit } = useAlertSubscription()

    email.value = 'user@example.com'
    await submit()

    expect(status.value).toBe('duplicate')
  })
})
