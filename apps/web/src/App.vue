<script setup lang="ts">
import { ref } from 'vue'
import { RouterView } from 'vue-router'

import AlertSubscribeDialog from '@/components/alerts/AlertSubscribeDialog.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useThemeMode } from '@/composables/useThemeMode'

const alertsOpen = ref(false)
const { isDark, toggleTheme } = useThemeMode()
</script>

<template>
  <div class="app-page">
    <AppHeader
      :is-dark="isDark"
      @open-alerts="alertsOpen = true"
      @toggle-theme="toggleTheme"
    />
    <RouterView />
    <AlertSubscribeDialog v-model="alertsOpen" />
  </div>
</template>
