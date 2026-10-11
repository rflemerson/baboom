<script setup lang="ts">
import BaseSelect from '@/components/ui/BaseSelect.vue'
import { FlaskConical } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { CatalogActive } from '@/types/catalog'

defineProps<{
  active: CatalogActive | null
  scenario: string
  scenarioAvailable: boolean
}>()
const emit = defineEmits<{ 'update:scenario': [value: string] }>()
const { t } = useI18n()
</script>

<template>
  <section class="app-catalog-toolbar" :aria-label="t('catalog.comparisonSettings')">
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="flex min-w-0 flex-col gap-1.5">
        <span class="app-copy-soft text-[10px] tracking-wide uppercase">{{
          t('catalog.compareActive')
        }}</span>
        <BaseSelect
          :label="t('catalog.compareActive')"
          :model-value="active?.slug ?? ''"
          :disabled="!active"
          :options="[{ value: active?.slug ?? '', label: active?.name || t('common.missing') }]"
        >
          <template #icon><FlaskConical class="app-copy-brand h-3.5 w-3.5 shrink-0" /></template>
        </BaseSelect>
      </div>
      <div class="flex min-w-0 flex-col gap-1.5">
        <span class="app-copy-soft text-[10px] tracking-wide uppercase">{{
          t('catalog.paymentScenario')
        }}</span>
        <BaseSelect
          :label="t('catalog.scenarioLabel')"
          :model-value="scenario"
          :options="[
            { value: '', label: t('catalog.normalPrice') },
            ...(scenarioAvailable ? [{ value: 'best', label: t('catalog.bestPrice') }] : []),
          ]"
          @update:model-value="emit('update:scenario', $event)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.app-catalog-toolbar {
  border: 1px solid var(--app-border);
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--app-surface-strong);
}
</style>
