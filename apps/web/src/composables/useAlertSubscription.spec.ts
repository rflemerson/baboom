import { describe, expect, it, vi } from 'vitest'

import { useAlertSubscription } from './useAlertSubscription'

describe('useAlertSubscription', () => {
  it('sets a local validation error when the email is invalid', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { email, errorMessage, status, submit } = useAlertSubscription()

    email.value = 'invalid-email'
    await submit()

    expect(status.value).toBe('error')
    expect(errorMessage.value).toBe('Please enter a valid email address.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sets success state when the REST request succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          alreadySubscribed: false,
          email: 'user@example.com',
          errors: null,
        }),
      }),
    )

    const { email, status, submit } = useAlertSubscription()

    email.value = 'user@example.com'
    await submit()

    expect(status.value).toBe('success')
  })

  it('sets duplicate state when the email already exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: false,
          alreadySubscribed: true,
          email: 'user@example.com',
          errors: null,
        }),
      }),
    )

    const { email, status, submit } = useAlertSubscription()

    email.value = 'user@example.com'
    await submit()

    expect(status.value).toBe('duplicate')
  })
})
