import { computed, ref, watch } from 'vue'
import { useMutation } from '@vue/apollo-composable'

import { SubscribeAlertsDocument } from '@/gql/graphql'

const INVALID_EMAIL_MESSAGE = 'Please enter a valid email address.'
const DEBUG_ALERTS = import.meta.env.DEV

function debugLog(message: string, payload?: unknown) {
  if (!DEBUG_ALERTS) {
    return
  }

  console.log(message, payload)
}

function isValidEmail(value: string) {
  if (!value || value.includes(' ')) {
    return false
  }

  const parts = value.split('@')
  if (parts.length !== 2) {
    return false
  }

  const [localPart, domain] = parts
  if (!localPart || !domain || domain.startsWith('.') || domain.endsWith('.')) {
    return false
  }

  const domainParts = domain.split('.')
  if (domainParts.length < 2 || domainParts.some((part) => part.length === 0)) {
    return false
  }

  return true
}

export function useAlertSubscription() {
  const email = ref('')
  const status = ref<'idle' | 'success' | 'duplicate' | 'error'>('idle')
  const errorMessage = ref<string | null>(null)

  const { loading, mutate } = useMutation(SubscribeAlertsDocument)

  const normalizedEmail = computed(() => email.value.trim())
  const hasEmail = computed(() => normalizedEmail.value.length > 0)
  const emailIsValid = computed(() =>
    normalizedEmail.value.length === 0 ? true : isValidEmail(normalizedEmail.value),
  )
  const canSubmit = computed(() => hasEmail.value && emailIsValid.value && !loading.value)
  const showFieldError = computed(
    () => status.value === 'error' && errorMessage.value === INVALID_EMAIL_MESSAGE,
  )

  watch(email, (value) => {
    debugLog('[alerts] email changed', { rawEmail: value })
  })

  watch(
    () => normalizedEmail.value,
    (value) => {
      debugLog('[alerts] normalized email updated', { normalizedEmail: value })
    },
  )

  watch(
    () => ({
      hasEmail: hasEmail.value,
      emailIsValid: emailIsValid.value,
      canSubmit: canSubmit.value,
      loading: loading.value,
    }),
    (value) => {
      debugLog('[alerts] derived state updated', value)
    },
    { deep: true },
  )

  watch(status, (value) => {
    debugLog('[alerts] status changed', { status: value })
  })

  watch(errorMessage, (value) => {
    debugLog('[alerts] error message changed', { errorMessage: value })
  })

  async function submit() {
    debugLog('[alerts] submit started', {
      rawEmail: email.value,
      normalizedEmail: normalizedEmail.value,
      hasEmail: hasEmail.value,
      emailIsValid: emailIsValid.value,
      canSubmit: canSubmit.value,
      loading: loading.value,
    })

    errorMessage.value = null
    status.value = 'idle'

    if (!hasEmail.value || !emailIsValid.value) {
      debugLog('[alerts] submit blocked by local validation', {
        rawEmail: email.value,
        normalizedEmail: normalizedEmail.value,
        hasEmail: hasEmail.value,
        emailIsValid: emailIsValid.value,
      })
      status.value = 'error'
      errorMessage.value = INVALID_EMAIL_MESSAGE
      return
    }

    debugLog('[alerts] sending GraphQL mutation', {
      email: normalizedEmail.value,
    })

    let response

    try {
      response = await mutate({
        email: normalizedEmail.value,
      })
    } catch (error) {
      debugLog('[alerts] GraphQL mutation threw', { error })
      status.value = 'error'
      errorMessage.value = 'Unable to subscribe right now.'
      return
    }

    debugLog('[alerts] GraphQL mutation resolved', { response })

    const result = response?.data?.subscribeAlerts

    if (!result) {
      debugLog('[alerts] missing subscribeAlerts payload', { response })
      status.value = 'error'
      errorMessage.value = 'Unexpected response from the server.'
      return
    }

    if (result.success) {
      debugLog('[alerts] subscription created successfully', { result })
      status.value = 'success'
      email.value = result.email ?? email.value
      return
    }

    if (result.alreadySubscribed) {
      debugLog('[alerts] duplicate subscription detected', { result })
      status.value = 'duplicate'
      return
    }

    debugLog('[alerts] backend returned error payload', { result })
    status.value = 'error'
    errorMessage.value = result.errors?.[0]?.message ?? 'Unable to subscribe right now.'
  }

  function reset() {
    debugLog('[alerts] reset called', {
      rawEmail: email.value,
      status: status.value,
      errorMessage: errorMessage.value,
    })
    email.value = ''
    status.value = 'idle'
    errorMessage.value = null
  }

  return {
    canSubmit,
    emailIsValid,
    email,
    errorMessage,
    hasEmail,
    loading,
    reset,
    showFieldError,
    status,
    submit,
  }
}
