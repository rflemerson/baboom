<script setup lang="ts">
import { ref } from 'vue'
import { RouterView } from 'vue-router'

import AlertSubscribeDialog from '@/components/alerts/AlertSubscribeDialog.vue'
import AppHeader from '@/components/layout/AppHeader.vue'

const alertsOpen = ref(false)
</script>

<template>
  <div class="min-h-screen bg-stone-950">
    <AppHeader @open-alerts="alertsOpen = true" />
    <RouterView />
    <AlertSubscribeDialog v-model="alertsOpen" />
  </div>
</template>
