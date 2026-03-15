<script setup lang="ts">
import { watch } from 'vue'
import { BellRing, Mail, X } from 'lucide-vue-next'

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
    panel-class="w-full max-w-md rounded-3xl p-6"
    @update:modelValue="emit('update:modelValue', $event)"
  >
      <div v-if="status === 'success'" class="space-y-4 text-center">
        <p class="app-status--success text-xs tracking-[0.24em] uppercase">Subscribed</p>
        <h2 :id="titleId" class="text-2xl font-semibold">You're Subscribed!</h2>
        <p class="app-copy-muted text-sm">
          We&apos;ve added <strong>{{ email }}</strong> to our list. You&apos;ll be the first to
          know about price drops!
        </p>
        <div class="flex gap-3">
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

      <div v-else-if="status === 'duplicate'" class="space-y-4 text-center">
        <p class="app-status--info text-xs tracking-[0.24em] uppercase">Already subscribed</p>
        <h2 :id="titleId" class="text-2xl font-semibold">Already Subscribed</h2>
        <p class="app-copy-muted text-sm">
          The email <strong>{{ email }}</strong> is already in our database.
        </p>
        <div class="flex gap-3">
          <button
            type="button"
            class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
            @click="reset"
          >
            Use another email
          </button>
          <button
            type="button"
            class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
            @click="emit('update:modelValue', false)"
          >
            Close
          </button>
        </div>
      </div>

      <div v-else class="space-y-5">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-3">
            <div class="app-button--accent mt-1 rounded-2xl border p-3">
              <BellRing class="h-5 w-5" />
            </div>
            <div>
              <p class="app-eyebrow">Alerts</p>
              <h2 :id="titleId" class="mt-2 text-2xl font-semibold">
                Enter your email to receive notifications.
              </h2>
            </div>
          </div>
          <button
            type="button"
            class="app-button app-button--ghost app-button--icon rounded-xl p-2 text-sm"
            @click="emit('update:modelValue', false)"
          >
            <X class="h-4 w-4" />
            <span class="sr-only">Close</span>
          </button>
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
