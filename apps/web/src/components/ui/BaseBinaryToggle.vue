<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

export type BinaryToggleOption<T extends string = string> = {
  ariaLabel: string
  icon: Component
  title: string
  value: T
}

const props = defineProps<{
  modelValue: string
  name: string
  options: readonly [BinaryToggleOption, BinaryToggleOption]
  testId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const activeIndex = computed(() => (props.options[0].value === props.modelValue ? 0 : 1))

function toggle() {
  const nextValue = props.options[activeIndex.value === 0 ? 1 : 0].value
  emit('update:modelValue', nextValue)
}
</script>

<template>
  <button
    type="button"
    class="app-binary-toggle app-button--control"
    :data-test="testId"
    :aria-label="`${name}: ${options[activeIndex].title}`"
    :title="options[activeIndex].title"
    @click="toggle"
  >
    <span
      class="app-binary-toggle__thumb"
      :class="
        activeIndex === 0 ? 'app-binary-toggle__thumb--start' : 'app-binary-toggle__thumb--end'
      "
    />
    <span
      v-for="(option, index) in options"
      :key="option.value"
      class="app-binary-toggle__option"
      :class="{ 'is-active': activeIndex === index }"
      aria-hidden="true"
    >
      <component :is="option.icon" class="h-4 w-4" />
    </span>
  </button>
</template>
