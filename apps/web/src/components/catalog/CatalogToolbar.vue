<script setup lang="ts">
import {
  Search,
  SlidersHorizontal,
  X,
  ArrowDownWideNarrow,
  ArrowUpNarrowWide,
  Grid3X3,
  List,
} from 'lucide-vue-next'
import { computed } from 'vue'

import type { CatalogViewMode } from '@/composables/useCatalogViewMode'
import BaseBinaryToggle, { type BinaryToggleOption } from '@/components/ui/BaseBinaryToggle.vue'

type SortOption = {
  label: string
  value: string
}

const props = defineProps<{
  advancedFiltersActive?: boolean
  perPage: number
  search: string
  sortBy: string
  sortDir: string
  sortOptions: readonly SortOption[]
  viewMode: CatalogViewMode
}>()

const emit = defineEmits<{
  clear: []
  openFilters: []
  'update:viewMode': [value: CatalogViewMode]
  'update:perPage': [value: number]
  'update:search': [value: string]
  'update:sortBy': [value: string]
  'toggle:sortDir': []
}>()

const sortDirectionOptions = computed<readonly [BinaryToggleOption, BinaryToggleOption]>(() => [
  {
    ariaLabel: 'Ascending',
    icon: ArrowUpNarrowWide,
    title: 'Ascending',
    value: 'asc',
  },
  {
    ariaLabel: 'Descending',
    icon: ArrowDownWideNarrow,
    title: 'Descending',
    value: 'desc',
  },
])

const viewModeOptions = computed<readonly [BinaryToggleOption, BinaryToggleOption]>(() => [
  {
    ariaLabel: 'Grid view',
    icon: Grid3X3,
    title: 'Grid view',
    value: 'grid',
  },
  {
    ariaLabel: 'List view',
    icon: List,
    title: 'List view',
    value: 'list',
  },
])

function onPerPageChange(event: Event) {
  const target = event.target as HTMLSelectElement
  emit('update:perPage', Number(target.value))
}

function onSearchInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:search', target.value)
}

function onSortByChange(event: Event) {
  const target = event.target as HTMLSelectElement
  emit('update:sortBy', target.value)
}
</script>

<template>
  <section class="app-toolbar mb-6 rounded-2xl p-3 sm:mb-8 sm:p-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div
        class="grid flex-1 gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto]"
      >
        <label class="flex flex-col gap-2 sm:col-span-2 xl:col-span-1">
          <span class="app-section-title">Search</span>
          <div class="relative">
            <Search
              class="app-copy-soft pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2"
            />
            <input
              :value="search"
              aria-label="Search catalog"
              type="search"
              placeholder="Search products, brands, or tags"
              class="app-input rounded-xl px-11 py-2.5 text-sm sm:py-3"
              @input="onSearchInput"
            />
          </div>
        </label>

        <label class="flex flex-col gap-2">
          <span class="app-section-title">Sort by</span>
          <select
            :value="sortBy"
            aria-label="Sort catalog results"
            class="app-select rounded-xl px-4 py-2.5 text-sm sm:py-3"
            @change="onSortByChange"
          >
            <option v-for="option in sortOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="flex flex-col gap-2">
          <span class="app-section-title">Per page</span>
          <select
            :value="perPage"
            aria-label="Results per page"
            class="app-select rounded-xl px-4 py-2.5 text-sm sm:py-3"
            @change="onPerPageChange"
          >
            <option :value="12">12</option>
            <option :value="24">24</option>
            <option :value="48">48</option>
          </select>
        </label>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2 self-end sm:gap-3 lg:self-auto">
        <button
          type="button"
          data-test="open-filters"
          :aria-label="advancedFiltersActive ? 'Filters active' : 'Open filters'"
          :title="advancedFiltersActive ? 'Filters active' : 'Open filters'"
          class="app-button app-button--control app-button--icon-square"
          :class="advancedFiltersActive ? 'app-button--accent' : 'app-button--ghost'"
          @click="emit('openFilters')"
        >
          <SlidersHorizontal class="h-4 w-4" />
        </button>
        <BaseBinaryToggle
          name="Sort direction"
          :model-value="props.sortDir"
          :options="sortDirectionOptions"
          test-id="sort-direction-toggle"
          @update:modelValue="emit('toggle:sortDir')"
        />
        <BaseBinaryToggle
          name="View mode"
          :model-value="props.viewMode"
          :options="viewModeOptions"
          test-id="view-mode-toggle"
          @update:modelValue="emit('update:viewMode', $event as CatalogViewMode)"
        />
        <button
          type="button"
          data-test="clear-filters"
          class="app-button app-button--ghost app-button--control app-button--icon-square"
          title="Clear filters"
          aria-label="Clear filters"
          @click="emit('clear')"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
    </div>
  </section>
</template>
