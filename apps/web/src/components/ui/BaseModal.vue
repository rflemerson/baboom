<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    ariaLabelledby?: string
    closeOnBackdrop?: boolean
    closeOnEscape?: boolean
    containerClass?: string
    initialFocus?: string
    modelValue: boolean
    panelClass?: string
    role?: 'dialog' | 'alertdialog'
  }>(),
  {
    ariaLabelledby: undefined,
    closeOnBackdrop: true,
    closeOnEscape: true,
    containerClass: 'items-center justify-center',
    initialFocus: undefined,
    panelClass: '',
    role: 'dialog',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const panelRef = ref<HTMLElement | null>(null)
let previousActiveElement: HTMLElement | null = null

const panelClasses = computed(() => ['app-dialog', props.panelClass].filter(Boolean).join(' '))

function getFocusableElements() {
  if (!panelRef.value) {
    return []
  }

  return Array.from(
    panelRef.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute('disabled') && element.tabIndex !== -1)
}

function focusInitialElement() {
  if (!panelRef.value) {
    return
  }

  const preferredTarget = props.initialFocus
    ? panelRef.value.querySelector<HTMLElement>(props.initialFocus)
    : null

  if (preferredTarget) {
    preferredTarget.focus()
    return
  }

  const [firstFocusable] = getFocusableElements()
  if (firstFocusable) {
    firstFocusable.focus()
    return
  }

  panelRef.value.focus()
}

function close() {
  emit('update:modelValue', false)
}

function onBackdropClick() {
  if (props.closeOnBackdrop) {
    close()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (!props.modelValue) {
    return
  }

  if (event.key === 'Escape' && props.closeOnEscape) {
    event.preventDefault()
    close()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = getFocusableElements()
  if (focusableElements.length === 0) {
    event.preventDefault()
    panelRef.value?.focus()
    return
  }

  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]
  const activeElement = document.activeElement as HTMLElement | null

  if (!event.shiftKey && activeElement === lastElement) {
    event.preventDefault()
    firstElement?.focus()
  } else if (event.shiftKey && activeElement === firstElement) {
    event.preventDefault()
    lastElement?.focus()
  }
}

watch(
  () => props.modelValue,
  async (isOpen) => {
    if (isOpen) {
      previousActiveElement = document.activeElement as HTMLElement | null
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      focusInitialElement()
      return
    }

    document.removeEventListener('keydown', onKeydown)
    previousActiveElement?.focus?.()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div
    v-if="modelValue"
    class="app-dialog-backdrop fixed inset-0 z-50 flex px-6"
    :class="containerClass"
    @click.self="onBackdropClick"
  >
    <section
      ref="panelRef"
      :aria-labelledby="ariaLabelledby"
      aria-modal="true"
      :class="panelClasses"
      :role="role"
      tabindex="-1"
    >
      <slot />
    </section>
  </div>
</template>
