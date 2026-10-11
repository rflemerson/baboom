<script setup lang="ts">
import { computed } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'
import { useDisclosure } from '@/composables/useDisclosure'

const props = defineProps<{
  modelValue: string
  options: { value: string; label: string }[]
  label: string
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const { root, closeAndFocus, escape } = useDisclosure()
const selected = computed(() => props.options.find((option) => option.value === props.modelValue))
function select(value: string) {
  emit('update:modelValue', value)
  closeAndFocus()
}
</script>

<template>
  <details ref="root" class="app-select" @keydown="escape">
    <summary
      :aria-label="label"
      :aria-disabled="disabled || undefined"
      @click="disabled && $event.preventDefault()"
    >
      <slot name="icon" />
      <span class="min-w-0 flex-1 truncate">{{ selected?.label }}</span>
      <ChevronDown class="h-3.5 w-3.5 shrink-0" />
    </summary>
    <div class="app-select__menu" :aria-label="label">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        :aria-pressed="option.value === modelValue"
        @click="select(option.value)"
      >
        <span>{{ option.label }}</span>
        <Check v-if="option.value === modelValue" class="h-3.5 w-3.5" />
      </button>
    </div>
  </details>
</template>

<style scoped lang="scss">
.app-select {
  position: relative;
  min-width: 0;

  summary {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-height: var(--app-control-height);
    border: 1px solid var(--app-border);
    border-radius: 0.875rem;
    padding: 0.5rem 0.875rem;
    background: var(--app-surface-soft);
    font-size: 0.75rem;
    list-style: none;
    cursor: pointer;

    &::-webkit-details-marker {
      display: none;
    }

    &:focus-visible {
      outline: 2px solid var(--app-brand);
      outline-offset: 2px;
    }
  }
}

.app-select__menu {
  position: absolute;
  inset: calc(100% + 0.375rem) 0 auto;
  z-index: 30;
  border: 1px solid var(--app-border);
  border-radius: 0.875rem;
  padding: 0.375rem;
  background: var(--app-surface-strong);
  box-shadow: var(--app-shadow);

  button {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    border-radius: 0.625rem;
    padding: 0.625rem 0.75rem;
    font-size: 0.75rem;
    text-align: left;
    cursor: pointer;

    &:hover,
    &:focus-visible,
    &[aria-pressed='true'] {
      background: var(--app-surface-soft);
    }
  }
}
</style>
