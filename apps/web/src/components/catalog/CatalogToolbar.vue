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
  <section class="mb-8 rounded-2xl border border-white/10 bg-white/5 p-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div class="grid flex-1 gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto]">
        <label class="flex flex-col gap-2">
          <span class="text-xs uppercase tracking-[0.24em] text-stone-400">Search</span>
          <div class="relative">
            <Search class="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-500" />
            <input
              :value="search"
              type="search"
              placeholder="Search products, brands, categories, or tags"
              class="w-full rounded-xl border border-white/10 bg-stone-950 px-11 py-3 text-sm text-white outline-none transition focus:border-orange-400"
              @input="onSearchInput"
            >
          </div>
        </label>

        <label class="flex flex-col gap-2">
          <span class="text-xs uppercase tracking-[0.24em] text-stone-400">Sort by</span>
          <select
            :value="sortBy"
            class="rounded-xl border border-white/10 bg-stone-950 px-4 py-3 text-sm text-white outline-none transition focus:border-orange-400"
            @change="onSortByChange"
          >
            <option
              v-for="option in sortOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="flex flex-col gap-2">
          <span class="text-xs uppercase tracking-[0.24em] text-stone-400">Per page</span>
          <select
            :value="perPage"
            class="rounded-xl border border-white/10 bg-stone-950 px-4 py-3 text-sm text-white outline-none transition focus:border-orange-400"
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
          class="inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium transition"
          :class="
            advancedFiltersActive
              ? 'border-orange-400 bg-orange-400/15 text-orange-200'
              : 'border-white/10 text-stone-200 hover:border-orange-400'
          "
          @click="emit('openFilters')"
        >
          <SlidersHorizontal class="h-4 w-4" />
          <span>Advanced filters</span>
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-stone-950 px-4 py-3 text-sm font-medium text-white transition hover:border-orange-400"
          @click="emit('toggle:sortDir')"
        >
          <ArrowDownUp class="h-4 w-4" />
          <span>{{ sortDir === 'asc' ? 'Ascending' : 'Descending' }}</span>
        </button>
        <div class="flex overflow-hidden rounded-xl border border-white/10">
          <button
            type="button"
            class="inline-flex items-center gap-2 px-4 py-3 text-sm font-medium transition"
            :class="
              viewMode === 'grid'
                ? 'bg-orange-400/15 text-orange-200'
                : 'bg-stone-950 text-stone-200 hover:text-white'
            "
            @click="emit('update:viewMode', 'grid')"
          >
            <Grid3X3 class="h-4 w-4" />
            <span>Grid</span>
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-2 border-l border-white/10 px-4 py-3 text-sm font-medium transition"
            :class="
              viewMode === 'list'
                ? 'bg-orange-400/15 text-orange-200'
                : 'bg-stone-950 text-stone-200 hover:text-white'
            "
            @click="emit('update:viewMode', 'list')"
          >
            <List class="h-4 w-4" />
            <span>List</span>
          </button>
        </div>
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-200 transition hover:border-white/30"
          @click="emit('clear')"
        >
          <RotateCcw class="h-4 w-4" />
          <span>Clear filters</span>
        </button>
      </div>
    </div>
  </section>
</template>
