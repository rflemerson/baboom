<script setup lang="ts">
defineProps<{
  label: string
  value: string
  compact?: boolean
  inlineAction?: boolean
}>()
</script>

<template>
  <div class="app-metric rounded-2xl" :class="compact ? 'px-4 py-2.5' : 'px-4 py-3'">
    <div v-if="inlineAction" class="flex items-center justify-between gap-3">
      <div>
        <p class="app-metric__label">{{ label }}</p>
        <p
          class="app-metric__value mt-1.5"
          :class="compact ? 'text-base font-semibold sm:text-lg' : 'text-lg font-semibold sm:text-xl'"
        >
          {{ value }}
        </p>
      </div>
      <slot name="action" />
    </div>
    <template v-else>
      <p class="app-metric__label">{{ label }}</p>
      <p
        class="app-metric__value mt-1.5"
        :class="compact ? 'text-base font-semibold sm:text-lg' : 'text-lg font-semibold sm:text-xl'"
      >
        {{ value }}
      </p>
      <slot />
    </template>
  </div>
</template>
