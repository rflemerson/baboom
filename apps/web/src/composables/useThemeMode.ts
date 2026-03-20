import { computed, onMounted, ref, watch } from 'vue'

const STORAGE_KEY = 'baboom.theme'
const DEFAULT_THEME = 'light'

type ThemeMode = 'light' | 'dark'

function applyTheme(theme: ThemeMode) {
  document.documentElement.dataset.theme = theme
}

function readStoredTheme(): ThemeMode | null {
  if (!('localStorage' in globalThis)) {
    return null
  }

  const storedTheme = globalThis.localStorage.getItem(STORAGE_KEY)

  if (storedTheme === 'light' || storedTheme === 'dark') {
    return storedTheme
  }

  return null
}

function getInitialTheme(): ThemeMode {
  return readStoredTheme() ?? DEFAULT_THEME
}

export function useThemeMode() {
  const theme = ref<ThemeMode>(getInitialTheme())

  onMounted(() => {
    theme.value = getInitialTheme()
  })

  watch(
    theme,
    (currentTheme) => {
      applyTheme(currentTheme)
      globalThis.localStorage.setItem(STORAGE_KEY, currentTheme)
    },
    { immediate: true },
  )

  const isDark = computed(() => theme.value === 'dark')

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return {
    isDark,
    theme,
    toggleTheme,
  }
}
