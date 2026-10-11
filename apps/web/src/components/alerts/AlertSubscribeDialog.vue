<script setup lang="ts">
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CircleAlert, CircleCheckBig, Mail } from 'lucide-vue-next'

import { useAlertSubscription } from '@/composables/useAlertSubscription'
import BaseModal from '@/components/ui/BaseModal.vue'

const { t } = useI18n()

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
      <h2 :id="titleId" class="text-2xl font-semibold">{{ t('alerts.successTitle') }}</h2>
      <p class="app-copy-muted text-sm">
        {{ t('alerts.successBody', { email }) }}
      </p>
      <div class="flex flex-col gap-3 sm:flex-row sm:justify-center">
        <button
          type="button"
          class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="emit('update:modelValue', false)"
        >
          {{ t('common.close') }}
        </button>
        <button
          type="button"
          class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="reset"
        >
          {{ t('alerts.another') }}
        </button>
      </div>
    </div>

    <div v-else-if="status === 'duplicate'" class="space-y-5 text-center">
      <div class="flex justify-center">
        <CircleAlert class="app-status--info h-14 w-14" />
      </div>
      <h2 :id="titleId" class="text-2xl font-semibold">{{ t('alerts.duplicateTitle') }}</h2>
      <p class="app-copy-muted text-sm">
        {{ t('alerts.duplicateBody', { email }) }}
      </p>
      <div class="flex flex-col gap-3 sm:flex-row sm:justify-end">
        <button
          type="button"
          class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="emit('update:modelValue', false)"
        >
          {{ t('common.close') }}
        </button>
        <button
          type="button"
          class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="reset"
        >
          {{ t('alerts.useAnother') }}
        </button>
      </div>
    </div>

    <div v-else class="space-y-5">
      <div class="space-y-3">
        <h2 :id="titleId" class="text-2xl font-semibold">{{ t('alerts.title') }}</h2>
        <p class="app-copy-muted text-sm">{{ t('alerts.intro') }}</p>
      </div>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <label class="flex flex-col gap-2">
          <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">{{
            t('alerts.email')
          }}</span>
          <div class="relative">
            <Mail
              class="app-copy-soft pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2"
            />
            <input
              v-model="email"
              type="email"
              :placeholder="t('alerts.emailPlaceholder')"
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
            {{ t('common.cancel') }}
          </button>
          <button
            type="submit"
            :disabled="!canSubmit"
            class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          >
            {{ loading ? t('alerts.subscribing') : t('alerts.subscribe') }}
          </button>
        </div>
      </form>
    </div>
  </BaseModal>
</template>
