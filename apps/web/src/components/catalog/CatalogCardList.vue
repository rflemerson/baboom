<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { Table } from '@tanstack/vue-table'
import type { CatalogProduct } from '@/types/catalog'
import { formatDecimal, formatMoney, formatQuantity, pricePer100g } from '@/utils/number'
import { usePriceDisplay } from '@/composables/usePriceDisplay'
import CatalogBenefits from './CatalogBenefits.vue'

defineProps<{
  table: Table<CatalogProduct>
  activeName: string
  massUnit: string
}>()
const { t } = useI18n()
const { discounted, hasBenefits } = usePriceDisplay()
</script>

<template>
  <ul class="grid gap-3" :aria-label="t('catalog.tableLabel')">
    <li
      v-for="row in table.getRowModel().rows"
      :key="row.id"
      class="app-catalog-card"
      :data-testid="`catalog-card-${row.id}`"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="text-sm font-semibold">{{ row.original.name }}</h2>
          <p class="app-copy-soft mt-1 text-xs">
            {{ row.original.brand.name
            }}<span v-if="row.original.netMass">
              · {{ formatQuantity(row.original.netMass) }} {{ massUnit }}</span
            >
            ·
            <span
              :class="
                row.original.stockStatus === 'in_stock' ? 'app-status--success' : 'app-copy-soft'
              "
              >{{ t(`catalog.stock.${row.original.stockStatus ?? 'unknown'}`) }}</span
            >
          </p>
        </div>
        <a
          v-if="row.original.externalLink"
          :href="row.original.externalLink"
          target="_blank"
          rel="noopener noreferrer"
          class="app-button app-button--secondary shrink-0 whitespace-nowrap"
          :aria-label="t('catalog.offerLabel', { product: row.original.name })"
          >{{ t('catalog.offer') }}<ArrowUpRight class="h-3.5 w-3.5"
        /></a>
      </div>

      <div class="app-catalog-card__metric mt-3 flex items-end justify-between gap-3">
        <div>
          <p class="app-copy-soft text-[11px]">
            {{ t('catalog.activeBasis', { active: activeName || t('catalog.activeFallback') }) }}
          </p>
          <p class="app-copy-brand mt-1 text-lg font-semibold">
            {{ formatMoney(pricePer100g(row.original.pricePerActive), row.original.currency) }}
          </p>
        </div>
        <div class="text-right text-xs">
          <p class="font-medium">{{ formatMoney(row.original.price, row.original.currency) }}</p>
          <s
            v-if="discounted(row.original)"
            class="app-copy-soft block"
            :aria-label="t('catalog.listPrice')"
            >{{ formatMoney(row.original.listPrice, row.original.currency) }}</s
          >
          <p v-if="row.original.concentration != null" class="app-copy-soft mt-1">
            {{ formatDecimal(row.original.concentration, 1) }}%
            {{ t('catalog.column.concentration').toLowerCase() }}
          </p>
        </div>
      </div>
      <CatalogBenefits v-if="hasBenefits(row.original)" class="mt-2" :product="row.original" />
      <p v-if="row.original.optimizationStatus === 'bounded'" class="app-copy-soft mt-1 text-xs">
        {{ t('catalog.bounded') }}
      </p>

      <p v-if="row.original.linkSelectsSeller === false" class="app-copy-soft mt-2 text-xs">
        {{ t('catalog.sellerWarning') }}
      </p>
    </li>
  </ul>
</template>

<style scoped lang="scss">
.app-catalog-card {
  border: 1px solid var(--app-border);
  border-radius: 0.75rem;
  padding: 0.875rem;
  background: var(--app-surface-strong);
}

.app-catalog-card__metric {
  border-radius: 0.5rem;
  padding: 0.75rem;
  background: var(--app-brand-soft);
}
</style>
