import { onMounted, ref, watch } from 'vue'

export type CatalogViewMode = 'grid' | 'list'

const STORAGE_KEY = 'baboom.catalog.viewMode'

export function useCatalogViewMode() {
  const viewMode = ref<CatalogViewMode>('grid')

  onMounted(() => {
    const storedValue = globalThis.localStorage.getItem(STORAGE_KEY)

    if (storedValue === 'grid' || storedValue === 'list') {
      viewMode.value = storedValue
    }
  })

  watch(viewMode, (value) => {
    globalThis.localStorage.setItem(STORAGE_KEY, value)
  })

  function setViewMode(value: CatalogViewMode) {
    viewMode.value = value
  }

  return {
    setViewMode,
    viewMode,
  }
}
