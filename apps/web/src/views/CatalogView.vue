<script setup lang="ts">
import { computed, ref } from 'vue'

import CatalogFiltersDrawer from '@/components/catalog/CatalogFiltersDrawer.vue'
import CatalogToolbar from '@/components/catalog/CatalogToolbar.vue'
import { useCatalogFilters } from '@/composables/useCatalogFilters'
import CatalogResults from '@/components/catalog/CatalogResults.vue'
import { useCatalogQuery } from '@/composables/useCatalogQuery'
import { useCatalogViewMode } from '@/composables/useCatalogViewMode'

const {
  brand,
  clearFilters,
  concentrationMax,
  concentrationMin,
  page,
  perPage,
  priceMax,
  priceMin,
  pricePerGramMax,
  pricePerGramMin,
  search,
  setBrand,
  setConcentrationMax,
  setConcentrationMin,
  setPage,
  setPerPage,
  setPriceMax,
  setPriceMin,
  setPricePerGramMax,
  setPricePerGramMin,
  setSearch,
  setSortBy,
  sortBy,
  sortDir,
  sortOptions,
  toggleSortDirection,
  variables,
} = useCatalogFilters()
const { error, loading, pageInfo, products } = useCatalogQuery(variables)
const { setViewMode, viewMode } = useCatalogViewMode()
const filtersOpen = ref(false)

const advancedFiltersActive = computed(() => {
  return Boolean(
    brand.value ||
      priceMin.value !== null ||
      priceMax.value !== null ||
      pricePerGramMin.value !== null ||
      pricePerGramMax.value !== null ||
      concentrationMin.value !== null ||
      concentrationMax.value !== null,
  )
})
</script>

<template>
  <main class="min-h-screen bg-stone-950 px-6 py-12 text-stone-50">
    <div class="mx-auto max-w-6xl">
      <header class="mb-10 flex flex-col gap-3">
        <p class="text-xs uppercase tracking-[0.3em] text-orange-300">Baboom catalog</p>
        <h1 class="text-4xl font-semibold tracking-tight">Public catalog</h1>
        <p class="max-w-2xl text-sm text-stone-300">
          This is the first slice of the Vue migration. The catalog listing is now
          consuming GraphQL directly.
        </p>
      </header>

      <CatalogToolbar
        :advanced-filters-active="advancedFiltersActive"
        :per-page="perPage"
        :search="search"
        :sort-by="sortBy"
        :sort-dir="sortDir"
        :sort-options="sortOptions"
        :view-mode="viewMode"
        @clear="clearFilters"
        @open-filters="filtersOpen = true"
        @toggle:sort-dir="toggleSortDirection"
        @update:per-page="setPerPage"
        @update:search="setSearch"
        @update:sort-by="setSortBy"
        @update:view-mode="setViewMode"
      />

      <CatalogResults
        :page-info="pageInfo"
        :products="products"
        :loading="loading"
        :error-message="error?.message"
        :view-mode="viewMode"
        @update:page="setPage"
      />
    </div>

    <CatalogFiltersDrawer
      v-model="filtersOpen"
      :brand="brand"
      :price-min="priceMin"
      :price-max="priceMax"
      :price-per-gram-min="pricePerGramMin"
      :price-per-gram-max="pricePerGramMax"
      :concentration-min="concentrationMin"
      :concentration-max="concentrationMax"
      @apply="setPage(1)"
      @clear="clearFilters"
      @update:brand="setBrand"
      @update:concentration-max="setConcentrationMax"
      @update:concentration-min="setConcentrationMin"
      @update:price-max="setPriceMax"
      @update:price-min="setPriceMin"
      @update:price-per-gram-max="setPricePerGramMax"
      @update:price-per-gram-min="setPricePerGramMin"
    />
  </main>
</template>
