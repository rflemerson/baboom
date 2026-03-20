<script setup lang="ts">
import { watch } from 'vue'
import { CircleAlert, CircleCheckBig, Mail } from 'lucide-vue-next'

import { useAlertSubscription } from '@/composables/useAlertSubscription'
import BaseModal from '@/components/ui/BaseModal.vue'

const DEBUG_ALERTS = import.meta.env.DEV

function debugLog(message: string, payload?: unknown) {
  if (!DEBUG_ALERTS) {
    return
  }

  console.log(message, payload)
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { canSubmit, email, errorMessage, loading, reset, showFieldError, status, submit } =
  useAlertSubscription()
const titleId = 'alert-subscribe-dialog-title'

watch(
  () => props.modelValue,
  (isOpen) => {
    debugLog('[alerts-dialog] modelValue changed', { isOpen })
    if (!isOpen) {
      debugLog('[alerts-dialog] dialog closed, resetting state')
      reset()
    }
  },
)

async function onSubmit() {
  debugLog('[alerts-dialog] form submit triggered', {
    email: email.value,
    status: status.value,
    errorMessage: errorMessage.value,
    canSubmit: canSubmit.value,
    loading: loading.value,
    showFieldError: showFieldError.value,
  })
  await submit()
  debugLog('[alerts-dialog] form submit finished', {
    email: email.value,
    status: status.value,
    errorMessage: errorMessage.value,
    canSubmit: canSubmit.value,
    loading: loading.value,
    showFieldError: showFieldError.value,
  })
}
</script>

<template>
  <BaseModal
    :aria-labelledby="titleId"
    container-class="items-center justify-center"
    initial-focus='input[type="email"]'
    :model-value="modelValue"
    panel-class="w-full max-w-md rounded-2xl p-6 sm:p-8"
    @update:modelValue="emit('update:modelValue', $event)"
  >
    <div v-if="status === 'success'" class="space-y-5 text-center">
      <div class="flex justify-center">
        <CircleCheckBig class="app-status--success h-16 w-16" />
      </div>
      <h2 :id="titleId" class="text-2xl font-semibold">You're Subscribed!</h2>
      <p class="app-copy-muted text-sm">
        We&apos;ve added <strong>{{ email }}</strong> to our list. You&apos;ll be the first to know
        about price drops!
      </p>
      <div class="flex flex-col gap-3 sm:flex-row sm:justify-center">
        <button
          type="button"
          class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="emit('update:modelValue', false)"
        >
          Close
        </button>
        <button
          type="button"
          class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="reset"
        >
          Subscribe another email
        </button>
      </div>
    </div>

    <div v-else-if="status === 'duplicate'" class="space-y-5 text-center">
      <div class="flex justify-center">
        <CircleAlert class="app-status--info h-14 w-14" />
      </div>
      <h2 :id="titleId" class="text-2xl font-semibold">Already Subscribed</h2>
      <p class="app-copy-muted text-sm">
        The email <strong>{{ email }}</strong> is already in our database.
      </p>
      <div class="flex flex-col gap-3 sm:flex-row sm:justify-end">
        <button
          type="button"
          class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="emit('update:modelValue', false)"
        >
          Close
        </button>
        <button
          type="button"
          class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="reset"
        >
          Use another email
        </button>
      </div>
    </div>

    <div v-else class="space-y-5">
      <div class="space-y-3">
        <h2 :id="titleId" class="text-2xl font-semibold">Alerts</h2>
        <p class="app-copy-muted text-sm">Enter your email to receive notifications.</p>
      </div>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <label class="flex flex-col gap-2">
          <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">Email</span>
          <div class="relative">
            <Mail
              class="app-copy-soft pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2"
            />
            <input
              v-model="email"
              type="email"
              placeholder="your@email.com"
              class="app-input rounded-xl px-11 py-3 text-sm"
              :class="{ 'is-invalid': showFieldError }"
            />
          </div>
        </label>

        <p v-if="errorMessage" class="app-status--danger text-sm">
          {{ errorMessage }}
        </p>

        <div class="flex gap-3">
          <button
            type="button"
            class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
            @click="emit('update:modelValue', false)"
          >
            Cancel
          </button>
          <button
            type="submit"
            :disabled="!canSubmit"
            class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          >
            {{ loading ? 'Subscribing...' : 'Subscribe' }}
          </button>
        </div>
      </form>
    </div>
  </BaseModal>
</template>
