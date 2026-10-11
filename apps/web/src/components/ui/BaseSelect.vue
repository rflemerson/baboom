<script setup lang="ts" generic="T extends string | string[]">
import { computed, type Component } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'
import { useDisclosure } from '@/composables/useDisclosure'

// A list model picks several options and keeps the menu open.
const props = defineProps<{
  modelValue: T
  options: { value: string; label: string; icon?: Component }[]
  label: string
  disabled?: boolean
  emptyLabel?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
const { root, closeAndFocus, escape } = useDisclosure()
const multiple = computed(() => Array.isArray(props.modelValue))
function isSelected(value: string): boolean {
  return Array.isArray(props.modelValue)
    ? props.modelValue.includes(value)
    : props.modelValue === value
}
const selected = computed(() => props.options.filter((option) => isSelected(option.value)))
const summary = computed(
  () => selected.value.map((option) => option.label).join(', ') || props.emptyLabel || '',
)
function select(value: string) {
  if (!Array.isArray(props.modelValue)) {
    emit('update:modelValue', value as T)
    closeAndFocus()
    return
  }
  const chosen = isSelected(value)
    ? props.modelValue.filter((option) => option !== value)
    : props.options
        .map((option) => option.value)
        .filter((option) => option === value || isSelected(option))
  emit('update:modelValue', chosen as T)
}
</script>

<template>
  <details ref="root" class="app-select" @keydown="escape">
    <summary
      :aria-label="label"
      :aria-disabled="disabled || undefined"
      @click="disabled && $event.preventDefault()"
    >
      <slot name="icon">
        <component
          :is="option.icon"
          v-for="option in selected.filter((option) => option.icon)"
          :key="option.value"
          class="app-copy-brand h-3.5 w-3.5 shrink-0"
          aria-hidden="true"
        />
      </slot>
      <span class="min-w-0 flex-1 truncate">{{ summary }}</span>
      <ChevronDown class="h-3.5 w-3.5 shrink-0" />
    </summary>
    <div class="app-select__menu" :aria-label="label" :aria-multiselectable="multiple || undefined">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        :aria-pressed="isSelected(option.value)"
        @click="select(option.value)"
      >
        <span class="flex items-center gap-2">
          <component :is="option.icon" v-if="option.icon" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ option.label }}
        </span>
        <Check v-if="isSelected(option.value)" class="h-3.5 w-3.5" />
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
