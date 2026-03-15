<script setup lang="ts">
defineEmits<{
  'open-alerts': []
}>()
</script>

<template>
  <header class="border-b border-white/10 bg-stone-950/90 backdrop-blur">
    <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4 text-white">
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-orange-400/15 text-orange-300">
          BB
        </div>
        <div>
          <p class="text-xs uppercase tracking-[0.24em] text-orange-300">Baboom</p>
          <h1 class="text-lg font-semibold">Protein catalog</h1>
        </div>
      </div>

      <button
        type="button"
        class="rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-100 transition hover:border-orange-400 hover:text-white"
        @click="$emit('open-alerts')"
      >
        Price alerts
      </button>
    </div>
  </header>
</template>
