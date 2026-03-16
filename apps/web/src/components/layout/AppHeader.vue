<script setup lang="ts">
import { Bomb, MoonStar, SunMedium } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

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
    <div
      class="app-shell flex items-center justify-between gap-3 px-4 py-3 sm:grid sm:grid-cols-[1fr_auto_1fr] sm:gap-4 sm:px-6 sm:py-4"
    >
      <div class="justify-self-start">
        <RouterLink to="/" class="block">
          <picture class="block">
            <source srcset="/images/logo-header-600w.avif" type="image/avif" />
            <source srcset="/images/logo-header-600w.webp" type="image/webp" />
            <img
              src="/images/logo-header-600w.svg"
              alt="Baboom logo"
              class="h-auto w-11 sm:w-24"
              width="100"
              height="81"
            />
          </picture>
        </RouterLink>
      </div>

      <div class="hidden justify-self-center sm:block">
        <RouterLink to="/" class="block">
          <img src="/images/logo-name.svg" alt="Baboom" class="h-7 w-auto sm:h-10" />
        </RouterLink>
      </div>

      <div class="flex items-center justify-self-end gap-2">
        <button
          type="button"
          aria-label="Open alerts"
          data-test="alerts-trigger"
          class="app-button app-button--ghost app-button--control alert-trigger"
          @click="$emit('open-alerts')"
        >
          <Bomb class="alert-trigger__icon h-4 w-4" />
          <span class="hidden md:inline">Alerts</span>
        </button>

        <button
          type="button"
          :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
          class="app-button app-button--ghost app-button--control app-button--icon-square"
          data-test="theme-toggle"
          @click="$emit('toggle-theme')"
        >
          <SunMedium v-if="isDark" class="h-4 w-4" />
          <MoonStar v-else class="h-4 w-4" />
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped lang="scss">
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
