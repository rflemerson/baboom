import { onMounted, onUnmounted, ref } from 'vue'

/** A <details> that closes on Escape or on a pointer press outside it. */
export function useDisclosure() {
  const root = ref<HTMLDetailsElement>()

  function close() {
    if (root.value) root.value.open = false
  }
  function closeAndFocus() {
    close()
    root.value?.querySelector('summary')?.focus()
  }
  function outside(event: PointerEvent) {
    if (event.target instanceof Node && !root.value?.contains(event.target)) close()
  }
  function escape(event: KeyboardEvent) {
    if (event.key === 'Escape') closeAndFocus()
  }

  onMounted(() => document.addEventListener('pointerdown', outside))
  onUnmounted(() => document.removeEventListener('pointerdown', outside))

  return { root, close, closeAndFocus, escape }
}
