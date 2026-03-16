<script setup lang="ts">
import CatalogPagination from '@/components/catalog/CatalogPagination.vue'
import CatalogGridCard from '@/components/catalog/CatalogGridCard.vue'
import CatalogListCard from '@/components/catalog/CatalogListCard.vue'
import type { CatalogViewMode } from '@/composables/useCatalogViewMode'
import type { CatalogPageInfo, CatalogProduct } from '@/types/catalog'

defineProps<{
  pageInfo: CatalogPageInfo | null
  products: CatalogProduct[]
  loading: boolean
  errorMessage?: string
  viewMode: CatalogViewMode
}>()

const emit = defineEmits<{
  'update:page': [value: number]
}>()
</script>

<template>
  <section
    v-if="loading"
    class="app-meta-row app-panel app-panel--soft mb-8 rounded-2xl px-6 py-12 text-center text-sm"
  >
    Loading products...
  </section>

  <section
    v-else-if="errorMessage"
    class="app-panel app-panel--soft mb-8 rounded-2xl border border-dashed px-6 py-12 text-center"
  >
    Error while querying GraphQL: {{ errorMessage }}
  </section>

  <section
    v-else-if="products.length"
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

  <section
    v-else
    class="app-panel app-panel--soft rounded-2xl border border-dashed px-6 py-12 text-center"
  >
    No products found.
  </section>

  <CatalogPagination
    v-if="pageInfo && !loading && !errorMessage && products.length"
    :page-info="pageInfo"
    @update:page="emit('update:page', $event)"
  />
</template>
