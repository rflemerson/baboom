<script setup lang="ts">
import { BellRing } from 'lucide-vue-next'

defineEmits<{
  'open-alerts': []
}>()
</script>

<template>
  <header class="border-b border-white/10 bg-stone-950/90 backdrop-blur">
    <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4 text-white">
      <div class="flex items-center gap-4">
        <img
          src="/images/logo-header-600w.svg"
          alt="Baboom"
          class="h-11 w-11 rounded-2xl border border-white/10 bg-white/5 object-cover p-1"
        />
        <div class="flex flex-col gap-1">
          <img src="/images/logo-name.svg" alt="Baboom" class="h-4 w-auto" />
          <p class="text-sm text-stone-300">Protein catalog</p>
        </div>
      </div>

      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-100 transition hover:border-orange-400 hover:text-white"
        @click="$emit('open-alerts')"
      >
        <BellRing class="h-4 w-4" />
        <span>Price alerts</span>
      </button>
    </div>
  </header>
</template>
