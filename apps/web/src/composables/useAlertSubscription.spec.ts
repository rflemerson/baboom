import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import type { UseMutationReturn } from '@vue/apollo-composable'
import type { SubscribeAlertsMutation, SubscribeAlertsMutationVariables } from '@/gql/graphql'

const { mockUseMutation } = vi.hoisted(() => ({
  mockUseMutation: vi.fn<
    (
      ...args: unknown[]
    ) => UseMutationReturn<SubscribeAlertsMutation, SubscribeAlertsMutationVariables>
  >(),
}))

vi.mock('@vue/apollo-composable', () => ({
  useMutation: mockUseMutation,
}))

import { useAlertSubscription } from './useAlertSubscription'

function createUseMutationReturn(
  overrides: Partial<UseMutationReturn<SubscribeAlertsMutation, SubscribeAlertsMutationVariables>>,
): UseMutationReturn<SubscribeAlertsMutation, SubscribeAlertsMutationVariables> {
  return {
    mutate: vi.fn().mockResolvedValue(null),
    loading: ref(false),
    error: ref(null),
    called: ref(false),
    onDone: vi.fn(() => ({ off: vi.fn() })),
    onError: vi.fn(() => ({ off: vi.fn() })),
    ...overrides,
  }
}

describe('useAlertSubscription', () => {
  it('sets success state when the mutation succeeds', async () => {
    mockUseMutation.mockImplementation(() => createUseMutationReturn({
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
    }))

    const { email, status, submit } = useAlertSubscription()

    email.value = 'user@example.com'
    await submit()

    expect(status.value).toBe('success')
  })

  it('sets duplicate state when the email already exists', async () => {
    mockUseMutation.mockImplementation(() => createUseMutationReturn({
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
    }))

    const { email, status, submit } = useAlertSubscription()

    email.value = 'user@example.com'
    await submit()

    expect(status.value).toBe('duplicate')
  })
})
