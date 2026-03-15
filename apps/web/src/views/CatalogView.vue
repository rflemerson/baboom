<script setup lang="ts">
import CatalogResults from '@/components/catalog/CatalogResults.vue'
import { useCatalogQuery } from '@/composables/useCatalogQuery'

const { error, loading, pageInfo, products } = useCatalogQuery()
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

      <CatalogResults
        :page-info="pageInfo"
        :products="products"
        :loading="loading"
        :error-message="error?.message"
      />
    </div>
  </main>
</template>
