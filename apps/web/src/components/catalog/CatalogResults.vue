<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, RotateCw, SearchX } from 'lucide-vue-next'

import CatalogPagination from '@/components/catalog/CatalogPagination.vue'
import CatalogGridCard from '@/components/catalog/CatalogGridCard.vue'
import CatalogListCard from '@/components/catalog/CatalogListCard.vue'
import type { CatalogViewMode } from '@/composables/useCatalogViewMode'
import type { CatalogPageInfo, CatalogProduct } from '@/types/catalog'

const emit = defineEmits<{
  'clear-filters': []
  retry: []
  'update:page': [value: number]
}>()

const props = defineProps<{
  filtersActive?: boolean
  pageInfo: CatalogPageInfo | null
  products: CatalogProduct[]
  loading: boolean
  errorMessage?: string
  viewMode: CatalogViewMode
}>()

const loadingPlaceholders = computed(() =>
  Array.from({ length: props.viewMode === 'grid' ? 6 : 3 }, (_, index) => index),
)
</script>

<template>
  <section v-if="loading" class="mb-8 space-y-4" aria-busy="true">
    <output class="sr-only" aria-live="polite">Loading products...</output>
    <div class="app-meta-row flex items-center justify-between rounded-2xl px-1 text-sm">
      <p class="app-copy-muted">Loading products...</p>
      <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">Fetching catalog</span>
    </div>

    <div
      :class="
        viewMode === 'grid' ? 'grid gap-4 md:grid-cols-2 xl:grid-cols-3' : 'flex flex-col gap-4'
      "
    >
      <article
        v-for="placeholder in loadingPlaceholders"
        :key="placeholder"
        class="app-skeleton-card rounded-2xl p-4 sm:p-5"
        data-test="catalog-loading-card"
      >
        <div
          class="mb-4 rounded-2xl px-3 py-4 sm:px-4 sm:py-5"
          style="background: var(--app-brand-soft)"
        >
          <div class="app-skeleton mb-3 h-3 w-20 rounded-full" />
          <div class="app-skeleton h-6 w-full rounded-full" />
          <div class="app-skeleton mt-2 h-6 w-4/5 rounded-full" />
        </div>

        <div class="mb-4 flex flex-wrap gap-2">
          <div class="app-skeleton h-7 w-24 rounded-full" />
          <div class="app-skeleton h-7 w-16 rounded-full" />
          <div class="app-skeleton h-7 w-28 rounded-full" />
          <div class="app-skeleton h-7 w-20 rounded-full" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="app-skeleton app-skeleton-card h-20 rounded-2xl" />
          <div class="app-skeleton app-skeleton-card h-20 rounded-2xl" />
        </div>

        <div class="app-skeleton app-skeleton-card mt-3 h-24 rounded-3xl" />
      </article>
    </div>
  </section>

  <section
    v-else-if="errorMessage"
    class="app-panel app-state-panel mb-8 rounded-2xl px-6 py-12 text-center"
    role="alert"
  >
    <AlertTriangle class="app-status--danger mx-auto h-8 w-8" />
    <h2 class="mt-4 text-xl font-semibold">We couldn&apos;t load the catalog</h2>
    <p class="app-copy-muted mx-auto mt-3 max-w-xl text-sm sm:text-base">
      Something went wrong while loading products. You can try again now, or adjust your filters if
      the issue keeps happening.
    </p>
    <p class="app-copy-soft mx-auto mt-3 max-w-xl text-xs sm:text-sm">
      {{ errorMessage }}
    </p>
    <div class="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
      <button
        type="button"
        class="app-button app-button--primary app-button--control"
        @click="emit('retry')"
      >
        <RotateCw class="h-4 w-4" />
        <span>Try again</span>
      </button>
      <button
        v-if="filtersActive"
        type="button"
        class="app-button app-button--secondary app-button--control"
        @click="emit('clear-filters')"
      >
        Clear filters
      </button>
    </div>
  </section>

  <section
    v-else-if="products.length"
    aria-live="polite"
    :class="
      viewMode === 'grid' ? 'grid gap-4 md:grid-cols-2 xl:grid-cols-3' : 'flex flex-col gap-4'
    "
  >
    <component
      v-for="product in products"
      :key="product.id"
      :is="viewMode === 'grid' ? CatalogGridCard : CatalogListCard"
      :product="product"
    />
  </section>

  <section v-else class="app-panel app-state-panel rounded-2xl px-6 py-12 text-center">
    <output class="sr-only" aria-live="polite">No products matched this search.</output>
    <SearchX class="app-copy-soft mx-auto h-8 w-8" />
    <h2 class="mt-4 text-xl font-semibold">No products matched this search</h2>
    <p class="app-copy-muted mx-auto mt-3 max-w-xl text-sm sm:text-base">
      {{
        filtersActive
          ? 'Try widening your price range, changing the search term, or clearing filters to see more results.'
          : 'There are no products available right now. Check back again soon.'
      }}
    </p>
    <div v-if="filtersActive" class="mt-6">
      <button
        type="button"
        class="app-button app-button--secondary app-button--control"
        @click="emit('clear-filters')"
      >
        Clear filters
      </button>
    </div>
  </section>

  <CatalogPagination
    v-if="pageInfo && !loading && !errorMessage && products.length"
    :page-info="pageInfo"
    @update:page="emit('update:page', $event)"
  />
</template>
