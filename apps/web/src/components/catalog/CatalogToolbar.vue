<script setup lang="ts">
import { Grid3X3, List, RotateCcw, Search, SlidersHorizontal, ArrowDownUp } from 'lucide-vue-next'

import type { CatalogViewMode } from '@/composables/useCatalogViewMode'

type SortOption = {
  label: string
  value: string
}

defineProps<{
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
  <section class="app-panel app-panel--soft mb-8 rounded-2xl p-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div
        class="grid flex-1 gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto]"
      >
        <label class="flex flex-col gap-2">
          <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">Search</span>
          <div class="relative">
            <Search
              class="app-copy-soft pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2"
            />
            <input
              :value="search"
              type="search"
              placeholder="Search products, brands, categories, or tags"
              class="app-input rounded-xl px-11 py-3 text-sm"
              @input="onSearchInput"
            />
          </div>
        </label>

        <label class="flex flex-col gap-2">
          <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">Sort by</span>
          <select
            :value="sortBy"
            class="app-select rounded-xl px-4 py-3 text-sm"
            @change="onSortByChange"
          >
            <option v-for="option in sortOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="flex flex-col gap-2">
          <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">Per page</span>
          <select
            :value="perPage"
            class="app-select rounded-xl px-4 py-3 text-sm"
            @change="onPerPageChange"
          >
            <option :value="12">12</option>
            <option :value="24">24</option>
            <option :value="48">48</option>
          </select>
        </label>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          type="button"
          class="app-button rounded-xl px-4 py-3 text-sm"
          :class="advancedFiltersActive ? 'app-button--accent' : 'app-button--secondary'"
          @click="emit('openFilters')"
        >
          <SlidersHorizontal class="h-4 w-4" />
          <span>Advanced filters</span>
        </button>
        <button
          type="button"
          class="app-button app-button--ghost rounded-xl px-4 py-3 text-sm"
          @click="emit('toggle:sortDir')"
        >
          <ArrowDownUp class="h-4 w-4" />
          <span>{{ sortDir === 'asc' ? 'Ascending' : 'Descending' }}</span>
        </button>
        <div class="flex overflow-hidden rounded-xl border" style="border-color: var(--app-border)">
          <button
            type="button"
            class="app-button px-4 py-3 text-sm"
            :class="viewMode === 'grid' ? 'app-button--accent' : 'app-button--ghost'"
            @click="emit('update:viewMode', 'grid')"
          >
            <Grid3X3 class="h-4 w-4" />
            <span>Grid</span>
          </button>
          <button
            type="button"
            class="app-button px-4 py-3 text-sm"
            style="border-left: 1px solid var(--app-border)"
            :class="viewMode === 'list' ? 'app-button--accent' : 'app-button--ghost'"
            @click="emit('update:viewMode', 'list')"
          >
            <List class="h-4 w-4" />
            <span>List</span>
          </button>
        </div>
        <button
          type="button"
          class="app-button app-button--secondary rounded-xl px-4 py-3 text-sm"
          @click="emit('clear')"
        >
          <RotateCcw class="h-4 w-4" />
          <span>Clear filters</span>
        </button>
      </div>
    </div>
  </section>
</template>
