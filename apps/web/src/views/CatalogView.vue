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
const { error, loading, pageInfo, products, refetch } = useCatalogQuery(variables)
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

const filtersActive = computed(() => {
  return Boolean(search.value || advancedFiltersActive.value)
})

function applyAdvancedFilters(payload: {
  brand: string
  concentrationMax: number | null
  concentrationMin: number | null
  priceMax: number | null
  priceMin: number | null
  pricePerGramMax: number | null
  pricePerGramMin: number | null
}) {
  setBrand(payload.brand)
  setPriceMin(payload.priceMin)
  setPriceMax(payload.priceMax)
  setPricePerGramMin(payload.pricePerGramMin)
  setPricePerGramMax(payload.pricePerGramMax)
  setConcentrationMin(payload.concentrationMin)
  setConcentrationMax(payload.concentrationMax)
}
</script>

<template>
  <main class="app-page px-4 py-8 sm:px-6 sm:py-12">
    <div class="app-shell">
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
        :filters-active="filtersActive"
        :page-info="pageInfo"
        :products="products"
        :loading="loading"
        :error-message="error?.message"
        :view-mode="viewMode"
        @clear-filters="clearFilters"
        @retry="refetch()"
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
      @apply="applyAdvancedFilters"
      @clear="clearFilters"
    />
  </main>
</template>
