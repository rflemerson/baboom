<script setup lang="ts">
import { BellRing } from 'lucide-vue-next'

defineEmits<{
  'open-alerts': []
}>()
</script>

<template>
  <header class="app-header">
    <div class="app-shell flex items-center justify-between gap-4 px-6 py-4">
      <div class="flex items-center gap-4">
        <img
          src="/images/logo-header-600w.svg"
          alt="Baboom"
          class="app-panel app-panel--soft h-11 w-11 rounded-2xl object-cover p-1"
        />
        <div class="flex flex-col gap-1">
          <img src="/images/logo-name.svg" alt="Baboom" class="h-4 w-auto" />
          <p class="app-copy-muted text-sm">Protein catalog</p>
        </div>
      </div>

      <button
        type="button"
        class="app-button app-button--ghost rounded-xl px-4 py-3 text-sm"
        @click="$emit('open-alerts')"
      >
        <BellRing class="h-4 w-4" />
        <span>Price alerts</span>
      </button>
    </div>
  </header>
</template>
