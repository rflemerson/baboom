<script setup lang="ts">
import CatalogGridCard from '@/components/catalog/CatalogGridCard.vue'
import type { CatalogPageInfo, CatalogProduct } from '@/types/catalog'

defineProps<{
  pageInfo: CatalogPageInfo | null
  products: CatalogProduct[]
  loading: boolean
  errorMessage?: string
}>()
</script>

<template>
  <section
    class="mb-8 rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-stone-200"
  >
    <p v-if="loading">Loading products...</p>
    <p v-else-if="errorMessage">Error while querying GraphQL: {{ errorMessage }}</p>
    <div v-else-if="pageInfo" class="flex flex-wrap gap-6">
      <span>Total: {{ pageInfo.totalCount }}</span>
      <span>Page: {{ pageInfo.currentPage }} / {{ pageInfo.totalPages }}</span>
      <span>Per page: {{ pageInfo.perPage }}</span>
    </div>
  </section>

  <section
    v-if="!loading && !errorMessage && products.length"
    class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
  >
    <CatalogGridCard
      v-for="product in products"
      :key="product.id"
      :product="product"
    />
  </section>

  <section
    v-else-if="!loading && !errorMessage"
    class="rounded-2xl border border-dashed border-white/15 bg-white/5 px-6 py-12 text-center text-stone-300"
  >
    No products found.
  </section>
</template>
