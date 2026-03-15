import { computed, ref } from 'vue'
import { useMutation } from '@vue/apollo-composable'

import { SubscribeAlertsDocument } from '@/gql/graphql'

export function useAlertSubscription() {
  const email = ref('')
  const status = ref<'idle' | 'success' | 'duplicate' | 'error'>('idle')
  const errorMessage = ref<string | null>(null)

  const { loading, mutate } = useMutation(SubscribeAlertsDocument)

  const canSubmit = computed(() => email.value.trim().length > 0 && !loading.value)

  async function submit() {
    errorMessage.value = null

    const response = await mutate({
      email: email.value.trim(),
    })

    const result = response?.data?.subscribeAlerts

    if (!result) {
      status.value = 'error'
      errorMessage.value = 'Unexpected response from the server.'
      return
    }

    if (result.success) {
      status.value = 'success'
      email.value = result.email ?? email.value
      return
    }

    if (result.alreadySubscribed) {
      status.value = 'duplicate'
      return
    }

    status.value = 'error'
    errorMessage.value = result.errors?.[0]?.message ?? 'Unable to subscribe right now.'
  }

  function reset() {
    email.value = ''
    status.value = 'idle'
    errorMessage.value = null
  }

  return {
    canSubmit,
    email,
    errorMessage,
    loading,
    reset,
    status,
    submit,
  }
}
