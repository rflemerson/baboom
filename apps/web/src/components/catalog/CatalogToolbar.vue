<script setup lang="ts">
import BaseSelect from '@/components/ui/BaseSelect.vue'
import { Coins, FlaskConical, Star, Ticket } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCatalogFilterOptions } from '@/composables/useCatalogFilterOptions'
import type { CatalogActive } from '@/types/catalog'

const props = defineProps<{
  active: CatalogActive | null
  scenario: string
}>()
// The chosen active; empty until the buyer picks one other than the default.
const activeSlug = defineModel<string>('activeSlug', { required: true })
// The benefits the price may count on, whichever the scenario.
const benefits = defineModel<string[]>('benefits', { required: true })
const emit = defineEmits<{ 'update:scenario': [value: string] }>()
const { t } = useI18n()
const { options } = useCatalogFilterOptions()
// The actives curators show, or the one the catalog answered with until they load.
const activeOptions = computed(() =>
  options.value.actives.length
    ? options.value.actives.map((active) => ({ value: active.name, label: active.label }))
    : [{ value: props.active?.slug ?? '', label: props.active?.name || t('common.missing') }],
)
</script>

<template>
  <section class="app-catalog-toolbar" :aria-label="t('catalog.comparisonSettings')">
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="flex min-w-0 flex-col gap-1.5">
        <span class="app-copy-soft text-[10px] tracking-wide uppercase">{{
          t('catalog.compareActive')
        }}</span>
        <BaseSelect
          :label="t('catalog.compareActive')"
          :model-value="activeSlug || active?.slug || ''"
          :disabled="!active"
          :options="activeOptions"
          @update:model-value="activeSlug = $event"
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
            { value: 'best', label: t('catalog.bestPrice') },
            { value: 'normal', label: t('catalog.catalogPrice') },
          ]"
          @update:model-value="emit('update:scenario', $event)"
        />
      </div>
      <div class="flex min-w-0 flex-col gap-1.5">
        <span class="app-copy-soft text-[10px] tracking-wide uppercase">{{
          t('catalog.benefits')
        }}</span>
        <BaseSelect
          v-model="benefits"
          :label="t('catalog.benefits')"
          :empty-label="t('catalog.noBenefits')"
          :options="[
            { value: 'coupon', label: t('catalog.coupons'), icon: Ticket },
            { value: 'cashback', label: t('catalog.cashback'), icon: Coins },
            { value: 'points', label: t('catalog.points'), icon: Star },
          ]"
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
