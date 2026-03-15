<script setup lang="ts">
import { watch } from 'vue'
import { BellRing, Mail, X } from 'lucide-vue-next'

import { useAlertSubscription } from '@/composables/useAlertSubscription'

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
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6 backdrop-blur-sm"
    @click.self="emit('update:modelValue', false)"
  >
    <section
      class="w-full max-w-md rounded-3xl border border-white/10 bg-stone-950 p-6 text-white shadow-2xl"
    >
      <div v-if="status === 'success'" class="space-y-4 text-center">
        <p class="text-xs tracking-[0.24em] text-emerald-300 uppercase">Subscribed</p>
        <h2 class="text-2xl font-semibold">You're Subscribed!</h2>
        <p class="text-sm text-stone-300">
          We&apos;ve added <strong>{{ email }}</strong> to our list. You&apos;ll be the first to
          know about price drops!
        </p>
        <div class="flex gap-3">
          <button
            type="button"
            class="flex-1 rounded-xl bg-orange-500 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-orange-400"
            @click="emit('update:modelValue', false)"
          >
            Close
          </button>
          <button
            type="button"
            class="flex-1 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-100 transition hover:border-white/30"
            @click="reset"
          >
            Subscribe another email
          </button>
        </div>
      </div>

      <div v-else-if="status === 'duplicate'" class="space-y-4 text-center">
        <p class="text-xs tracking-[0.24em] text-sky-300 uppercase">Already subscribed</p>
        <h2 class="text-2xl font-semibold">Already Subscribed</h2>
        <p class="text-sm text-stone-300">
          The email <strong>{{ email }}</strong> is already in our database.
        </p>
        <div class="flex gap-3">
          <button
            type="button"
            class="flex-1 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-100 transition hover:border-white/30"
            @click="reset"
          >
            Use another email
          </button>
          <button
            type="button"
            class="flex-1 rounded-xl bg-orange-500 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-orange-400"
            @click="emit('update:modelValue', false)"
          >
            Close
          </button>
        </div>
      </div>

      <div v-else class="space-y-5">
        <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3">
            <div
              class="mt-1 rounded-2xl border border-orange-400/20 bg-orange-400/10 p-3 text-orange-300"
            >
              <BellRing class="h-5 w-5" />
            </div>
            <div>
              <p class="text-xs tracking-[0.24em] text-orange-300 uppercase">Alerts</p>
              <h2 class="mt-2 text-2xl font-semibold">Enter your email to receive notifications.</h2>
            </div>
          </div>
          <button
            type="button"
            class="rounded-xl border border-white/10 p-2 text-sm transition hover:border-orange-400"
            @click="emit('update:modelValue', false)"
          >
            <X class="h-4 w-4" />
            <span class="sr-only">Close</span>
          </button>
        </div>

        <form class="space-y-4" @submit.prevent="onSubmit">
          <label class="flex flex-col gap-2">
            <span class="text-xs tracking-[0.24em] text-stone-400 uppercase">Email</span>
            <div class="relative">
              <Mail
                class="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-stone-500"
              />
              <input
                v-model="email"
                type="email"
                placeholder="your@email.com"
                class="w-full rounded-xl border bg-stone-900 px-11 py-3 text-sm text-white transition outline-none"
                :class="
                  showFieldError
                    ? 'border-red-400 focus:border-red-400'
                    : 'border-white/10 focus:border-orange-400'
                "
              />
            </div>
          </label>

          <p v-if="errorMessage" class="text-sm text-red-300">
            {{ errorMessage }}
          </p>

          <div class="flex gap-3">
            <button
              type="button"
              class="flex-1 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-100 transition hover:border-white/30"
              @click="emit('update:modelValue', false)"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="!canSubmit"
              class="flex-1 rounded-xl bg-orange-500 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {{ loading ? 'Subscribing...' : 'Subscribe' }}
            </button>
          </div>
        </form>
      </div>
    </section>
  </div>
</template>
