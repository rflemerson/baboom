<script setup lang="ts">
import { ArrowDown, ArrowUp, ArrowUpRight } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { Table } from '@tanstack/vue-table'
import type { CatalogProduct } from '@/types/catalog'
import { formatDecimal, formatMoney, formatQuantity, pricePer100g } from '@/utils/number'
import CatalogPriceNotes from './CatalogPriceNotes.vue'

defineProps<{
  table: Table<CatalogProduct>
  activeName: string
  massUnit: string
  loading: boolean
}>()
const { t } = useI18n()
const NUMERIC = ['pricePerActive', 'price', 'concentration', 'totalActive', 'mass']
</script>

<template>
  <div
    class="app-table-scroll"
    tabindex="0"
    role="region"
    :aria-label="t('catalog.tableLabel')"
    :aria-busy="loading"
  >
    <table class="app-catalog-table">
      <caption class="sr-only">
        {{
          t('catalog.tableLabel')
        }}
        —
        {{
          t('catalog.activeBasis', { active: activeName || t('catalog.activeFallback') })
        }}
      </caption>
      <thead>
        <tr v-for="group in table.getHeaderGroups()" :key="group.id">
          <th
            v-for="header in group.headers"
            :key="header.id"
            scope="col"
            :aria-sort="
              header.column.getCanSort()
                ? header.column.getIsSorted() === 'asc'
                  ? 'ascending'
                  : header.column.getIsSorted() === 'desc'
                    ? 'descending'
                    : 'none'
                : undefined
            "
            :class="{
              'app-catalog-table__active': header.column.id === 'pricePerActive',
              'app-catalog-table__numeric': NUMERIC.includes(header.column.id),
            }"
          >
            <div class="app-catalog-table__heading flex items-center gap-2">
              <button
                v-if="header.column.getCanSort()"
                type="button"
                class="app-table-sort"
                :aria-label="t('catalog.sort', { column: String(header.column.columnDef.header) })"
                @click="header.column.toggleSorting()"
              >
                {{ header.column.columnDef.header }}
                <ArrowUp v-if="header.column.getIsSorted() === 'asc'" class="h-3 w-3" />
                <ArrowDown v-else-if="header.column.getIsSorted() === 'desc'" class="h-3 w-3" />
              </button>
              <span v-else>{{ header.column.columnDef.header }}</span>
            </div>
          </th>
        </tr>
      </thead>
      <tbody v-if="$slots.state">
        <tr>
          <td :colspan="table.getVisibleLeafColumns().length"><slot name="state" /></td>
        </tr>
      </tbody>
      <tbody v-else>
        <tr
          v-for="row in table.getRowModel().rows"
          :key="row.id"
          :data-testid="`catalog-row-${row.id}`"
        >
          <td
            v-for="cell in row.getVisibleCells()"
            :key="cell.id"
            :class="{
              'app-catalog-table__active': cell.column.id === 'pricePerActive',
              'app-catalog-table__numeric': NUMERIC.includes(cell.column.id),
              'app-catalog-table__product': cell.column.id === 'product',
            }"
          >
            <template v-if="cell.column.id === 'product'">
              <h2 class="text-sm font-semibold">{{ row.original.name }}</h2>
              <div class="app-copy-soft mt-1 text-xs">
                {{ row.original.brand.name
                }}<span v-if="row.original.netMass">
                  · {{ formatQuantity(row.original.netMass) }} {{ massUnit }}</span
                >
              </div>
            </template>
            <span
              v-else-if="cell.column.id === 'pricePerActive'"
              class="app-copy-brand text-sm font-semibold whitespace-nowrap"
              >{{
                formatMoney(pricePer100g(row.original.pricePerActive), row.original.currency)
              }}</span
            >
            <template v-else-if="cell.column.id === 'price'">
              <span class="font-medium whitespace-nowrap">{{
                formatMoney(row.original.price, row.original.currency)
              }}</span>
              <CatalogPriceNotes :product="row.original" />
              <p
                v-if="row.original.optimizationStatus === 'bounded'"
                class="app-copy-soft mt-1 text-xs"
              >
                {{ t('catalog.bounded') }}
              </p>
            </template>
            <span v-else-if="cell.column.id === 'concentration'" class="whitespace-nowrap">{{
              row.original.concentration == null
                ? t('common.missing')
                : `${formatDecimal(row.original.concentration, 1)}%`
            }}</span>
            <span
              v-else-if="cell.column.id === 'totalActive' || cell.column.id === 'mass'"
              class="whitespace-nowrap"
              >{{
                cell.getValue() == null
                  ? t('common.missing')
                  : formatQuantity(cell.getValue() as string)
              }}</span
            >
            <template v-else-if="cell.column.id === 'offer'">
              <a
                v-if="row.original.externalLink"
                :href="row.original.externalLink"
                target="_blank"
                rel="noopener noreferrer"
                class="app-button app-button--secondary whitespace-nowrap"
                :aria-label="t('catalog.offerLabel', { product: row.original.name })"
                >{{ t('catalog.offer') }}<ArrowUpRight class="h-3.5 w-3.5"
              /></a>
              <span v-else>{{ t('common.missing') }}</span>
              <p
                v-if="row.original.linkSelectsSeller === false"
                class="app-copy-soft mt-1 max-w-40 text-xs"
              >
                {{ t('catalog.sellerWarning') }}
              </p>
            </template>
            <span v-else class="app-copy-muted">{{ cell.getValue() || t('common.missing') }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.app-table-scroll {
  overflow-x: auto;
  border: 1px solid var(--app-border);
  border-radius: 0.75rem;
  background: var(--app-surface);

  &:focus-visible {
    outline: 2px solid var(--app-brand);
    outline-offset: 2px;
  }
}

.app-table-sort {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid var(--app-brand);
    outline-offset: 2px;
  }
}

.app-catalog-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
  text-align: left;

  th,
  td {
    padding: 0.625rem 0.875rem;
    border-bottom: 1px solid var(--app-border);
    vertical-align: middle;
  }

  th {
    background: var(--app-surface-strong);
    color: var(--app-text-soft);
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
  }

  td {
    transition: background var(--app-theme-duration) var(--app-theme-easing);
  }

  tbody tr:last-child td {
    border-bottom: 0;
  }

  .app-catalog-table__active {
    background: color-mix(in srgb, var(--app-brand-soft) 50%, var(--app-surface-strong));
  }

  tbody tr:hover td {
    background: color-mix(in srgb, var(--app-brand-soft) 30%, var(--app-surface-strong));
  }

  tbody tr:hover .app-catalog-table__active {
    background: color-mix(in srgb, var(--app-brand-soft) 80%, var(--app-surface-strong));
  }

  .app-catalog-table__numeric {
    text-align: right;

    .app-catalog-table__heading {
      justify-content: flex-end;
    }
  }

  .app-catalog-table__product {
    min-width: 15rem;
    max-width: 22rem;
  }
}
</style>
