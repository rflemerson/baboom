<script setup lang="ts">
import { SlidersHorizontal } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Table } from '@tanstack/vue-table'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import { useCatalogFilterOptions } from '@/composables/useCatalogFilterOptions'
import { useDisclosure } from '@/composables/useDisclosure'
import {
  STOCK_STATUSES,
  type CatalogFilterOption,
  type CatalogFilterOptions,
  type CatalogProduct,
} from '@/types/catalog'

const props = defineProps<{ table: Table<CatalogProduct> }>()
const { t } = useI18n()
const { options } = useCatalogFilterOptions()
// Column whose filter holds the choice, and the options it is chosen from.
const FIELDS = {
  concentration: 'concentration',
  stock: 'stock',
  brand: 'brands',
  flavors: 'flavors',
  category: 'categories',
} as const satisfies Record<string, keyof CatalogFilterOptions | 'stock' | 'concentration'>
type Field = keyof typeof FIELDS
const { root, escape } = useDisclosure()
const field = ref<Field>('concentration')
const range = computed(() => field.value === 'concentration')
const chosen = computed<string[]>(() => {
  const value: unknown = props.table.getColumn(field.value)?.getFilterValue()
  return Array.isArray(value) ? value : []
})

const changed = computed(
  () =>
    JSON.stringify(props.table.getState().columnFilters) !==
    JSON.stringify(props.table.initialState.columnFilters),
)
// Stock states and concentration steps are fixed; the rest comes from the catalog.
const choices = computed<CatalogFilterOption[]>(() => {
  const source = FIELDS[field.value]
  if (source === 'concentration') return []
  if (source !== 'stock') return options.value[source]
  return STOCK_STATUSES.map((name) => ({ name, label: t(`catalog.stock.${name}`) }))
})

function header(id: string): string {
  return String(props.table.getColumn(id)?.columnDef.header ?? id)
}
// The concentration filter is [min, max] in percent; an empty bound is open.
function setBound(index: number, value: string) {
  const next = [chosen.value[0] ?? '', chosen.value[1] ?? '']
  next[index] = value.trim()
  props.table.getColumn('concentration')?.setFilterValue(next.some(Boolean) ? next : undefined)
}
function toggle(name: string, checked: boolean) {
  const next = checked ? [...chosen.value, name] : chosen.value.filter((item) => item !== name)
  props.table.getColumn(field.value)?.setFilterValue(next.length ? next : undefined)
}
</script>

<template>
  <details ref="root" name="catalog-menu" class="app-menu" @keydown="escape">
    <summary class="app-button app-button--secondary">
      <SlidersHorizontal class="h-3.5 w-3.5" />{{ t('catalog.filters') }}
    </summary>
    <section class="app-menu__panel app-filter-panel" :aria-label="t('catalog.filters')">
      <div class="flex flex-col gap-1.5">
        <span class="app-copy-soft">{{ t('catalog.filterBy') }}</span>
        <BaseSelect
          :label="t('catalog.filterBy')"
          :model-value="field"
          :options="Object.keys(FIELDS).map((id) => ({ value: id, label: header(id) }))"
          @update:model-value="field = $event as Field"
        />
      </div>
      <fieldset v-if="range" class="mt-3 flex flex-col gap-1.5">
        <legend class="app-copy-soft mb-1.5">{{ t('catalog.concentration.range') }}</legend>
        <div class="flex items-center gap-2">
          <template v-for="(bound, index) in ['min', 'max']" :key="bound">
            <span v-if="index" class="app-copy-soft" aria-hidden="true">–</span>
            <label class="app-range-field">
              <span class="sr-only">{{ t(`catalog.concentration.${bound}`) }}</span>
              <input
                type="number"
                inputmode="decimal"
                min="0"
                max="100"
                step="1"
                :value="chosen[index] ?? ''"
                :placeholder="index ? '100' : '0'"
                @change="setBound(index, ($event.target as HTMLInputElement).value)"
              />
              <span class="app-copy-soft" aria-hidden="true">%</span>
            </label>
          </template>
        </div>
      </fieldset>
      <ul v-else class="app-filter-panel__list mt-3">
        <li v-for="option in choices" :key="option.name">
          <label class="flex items-center gap-2 py-1.5">
            <input
              type="checkbox"
              :checked="chosen.includes(option.name)"
              @change="toggle(option.name, ($event.target as HTMLInputElement).checked)"
            />{{ option.label }}
          </label>
        </li>
        <li v-if="!choices.length" class="app-copy-soft py-1.5">
          {{ t('catalog.noOptions') }}
        </li>
      </ul>
      <button
        v-if="changed"
        type="button"
        class="app-menu__action mt-3"
        @click="table.resetColumnFilters()"
      >
        {{ t('catalog.clearFilters') }}
      </button>
    </section>
  </details>
</template>

<style scoped lang="scss">
.app-filter-panel {
  min-width: 18rem;
}

.app-range-field {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 0.25rem;
  min-height: var(--app-control-height);
  border: 1px solid var(--app-border);
  border-radius: 0.875rem;
  padding: 0 0.875rem;
  background: var(--app-surface-soft);
  font-size: 0.75rem;

  &:focus-within {
    border-color: var(--app-brand);
  }

  input {
    width: 100%;
    min-width: 0;
    border: 0;
    background: transparent;
    color: var(--app-text);
    font: inherit;
    outline: none;
    appearance: textfield;

    &::-webkit-inner-spin-button,
    &::-webkit-outer-spin-button {
      margin: 0;
      appearance: none;
    }

    &::placeholder {
      color: var(--app-text-soft);
    }
  }
}

.app-filter-panel__list {
  max-height: 16rem;
  overflow-y: auto;
}
</style>
