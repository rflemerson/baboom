<script setup lang="ts">
import { Bomb, MoonStar, SunMedium } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

defineProps<{
  isDark: boolean
}>()

defineEmits<{
  'open-alerts': []
  'toggle-theme': []
}>()
</script>

<template>
  <header class="app-header">
    <div class="app-shell flex min-h-14 items-center justify-between gap-3 px-4 py-2 sm:px-6">
      <div class="flex items-center gap-2 sm:gap-3">
        <RouterLink to="/" class="block shrink-0" :aria-label="t('header.home')">
          <picture class="block">
            <source srcset="/images/logo-header-600w.avif" type="image/avif" />
            <source srcset="/images/logo-header-600w.webp" type="image/webp" />
            <img
              src="/images/logo-header-600w.svg"
              :alt="t('header.logo')"
              class="h-auto w-9 sm:w-10"
              width="100"
              height="81"
            />
          </picture>
        </RouterLink>
        <RouterLink to="/" class="block" :aria-label="t('header.home')">
          <img src="/images/logo-name.svg" alt="Baboom" class="h-5 w-auto sm:h-6" />
        </RouterLink>
      </div>

      <div class="flex items-center gap-2 justify-self-end">
        <button
          type="button"
          :aria-label="isDark ? t('header.light') : t('header.dark')"
          class="app-button app-button--ghost app-button--icon-square"
          data-test="theme-toggle"
          @click="$emit('toggle-theme')"
        >
          <SunMedium v-if="isDark" class="h-4 w-4" />
          <MoonStar v-else class="h-4 w-4" />
        </button>

        <button
          type="button"
          :aria-label="t('header.openAlerts')"
          data-test="alerts-trigger"
          class="app-button app-button--ghost alert-trigger"
          @click="$emit('open-alerts')"
        >
          <Bomb class="alert-trigger__icon h-4 w-4" />
          <span>{{ t('header.alerts') }}</span>
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped lang="scss">
.app-header {
  border-bottom: 1px solid var(--app-border);
  background: color-mix(in srgb, var(--app-surface-strong) 92%, transparent);
  color: var(--app-text);
  backdrop-filter: blur(14px);
  transition:
    background var(--app-theme-duration) var(--app-theme-easing),
    border-color var(--app-theme-duration) var(--app-theme-easing);
}

.alert-trigger:hover .alert-trigger__icon,
.alert-trigger:focus-visible .alert-trigger__icon {
  animation: alert-bomb-wiggle 420ms ease-in-out;
  transform-origin: center;
}

@keyframes alert-bomb-wiggle {
  0%,
  100% {
    transform: rotate(0deg) translateY(0);
  }

  20% {
    transform: rotate(-14deg) translateY(-1px);
  }

  40% {
    transform: rotate(10deg) translateY(0);
  }

  60% {
    transform: rotate(-8deg) translateY(-1px);
  }

  80% {
    transform: rotate(6deg) translateY(0);
  }
}
</style>
