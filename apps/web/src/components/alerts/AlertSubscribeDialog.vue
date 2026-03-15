<script setup lang="ts">
import { watch } from 'vue'

import { useAlertSubscription } from '@/composables/useAlertSubscription'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { canSubmit, email, errorMessage, loading, reset, status, submit } =
  useAlertSubscription()

watch(
  () => props.modelValue,
  (isOpen) => {
    if (!isOpen) {
      reset()
    }
  },
)

async function onSubmit() {
  await submit()
}
</script>

<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6 backdrop-blur-sm"
    @click.self="emit('update:modelValue', false)"
  >
    <section class="w-full max-w-md rounded-3xl border border-white/10 bg-stone-950 p-6 text-white shadow-2xl">
      <div v-if="status === 'success'" class="space-y-4 text-center">
        <p class="text-xs uppercase tracking-[0.24em] text-emerald-300">Subscribed</p>
        <h2 class="text-2xl font-semibold">You are on the alert list.</h2>
        <p class="text-sm text-stone-300">
          We will notify <strong>{{ email }}</strong> when prices move.
        </p>
        <button
          type="button"
          class="w-full rounded-xl bg-orange-500 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-orange-400"
          @click="emit('update:modelValue', false)"
        >
          Close
        </button>
      </div>

      <div v-else-if="status === 'duplicate'" class="space-y-4 text-center">
        <p class="text-xs uppercase tracking-[0.24em] text-sky-300">Already subscribed</p>
        <h2 class="text-2xl font-semibold">This email is already subscribed.</h2>
        <p class="text-sm text-stone-300">
          Try a different email if you want another alert recipient.
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
          <div>
            <p class="text-xs uppercase tracking-[0.24em] text-orange-300">Price alerts</p>
            <h2 class="mt-2 text-2xl font-semibold">Stay on top of price drops.</h2>
          </div>
          <button
            type="button"
            class="rounded-xl border border-white/10 px-3 py-2 text-sm transition hover:border-orange-400"
            @click="emit('update:modelValue', false)"
          >
            Close
          </button>
        </div>

        <p class="text-sm text-stone-300">
          Enter your email and we will let you know when tracked products become more interesting.
        </p>

        <form class="space-y-4" @submit.prevent="onSubmit">
          <label class="flex flex-col gap-2">
            <span class="text-xs uppercase tracking-[0.24em] text-stone-400">Email</span>
            <input
              v-model="email"
              type="email"
              placeholder="you@example.com"
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white outline-none transition focus:border-orange-400"
            >
          </label>

          <p v-if="errorMessage" class="text-sm text-red-300">
            {{ errorMessage }}
          </p>

          <button
            type="submit"
            :disabled="!canSubmit"
            class="w-full rounded-xl bg-orange-500 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ loading ? 'Subscribing...' : 'Subscribe' }}
          </button>
        </form>
      </div>
    </section>
  </div>
</template>
