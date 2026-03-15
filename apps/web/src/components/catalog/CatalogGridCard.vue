<script setup lang="ts">
import type { CatalogProduct } from '@/types/catalog'

defineProps<{
  product: CatalogProduct
}>()
</script>

<template>
  <article class="rounded-2xl border border-white/10 bg-stone-900/80 p-5 shadow-lg shadow-black/20">
    <div class="mb-4 flex items-start justify-between gap-4">
      <div>
        <p class="text-xs uppercase tracking-[0.24em] text-orange-300">
          {{ product.brand.name }}
        </p>
        <h2 class="mt-2 text-xl font-semibold text-white">{{ product.name }}</h2>
      </div>
      <span class="rounded-full bg-white/10 px-3 py-1 text-xs text-stone-200">
        {{ product.packagingDisplay }}
      </span>
    </div>

    <dl class="grid grid-cols-2 gap-3 text-sm text-stone-300">
      <div>
        <dt class="text-xs uppercase tracking-wide text-stone-500">Weight</dt>
        <dd>{{ product.weight }} g</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wide text-stone-500">Category</dt>
        <dd>{{ product.category?.name ?? 'Uncategorized' }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wide text-stone-500">Price</dt>
        <dd>{{ product.lastPrice ?? '-' }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wide text-stone-500">Price / g</dt>
        <dd>{{ product.pricePerGram ?? '-' }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wide text-stone-500">Concentration</dt>
        <dd>{{ product.concentration ?? '-' }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wide text-stone-500">Total protein</dt>
        <dd>{{ product.totalProtein ?? '-' }}</dd>
      </div>
    </dl>

    <ul class="mt-4 flex flex-wrap gap-2">
      <li
        v-for="tag in product.tags"
        :key="`${product.id}-${tag.name}`"
        class="rounded-full border border-orange-400/30 bg-orange-400/10 px-2.5 py-1 text-xs text-orange-200"
      >
        {{ tag.name }}
      </li>
    </ul>

    <a
      v-if="product.externalLink"
      :href="product.externalLink"
      target="_blank"
      rel="noreferrer"
      class="mt-5 inline-flex text-sm font-medium text-orange-300 underline-offset-4 hover:underline"
    >
      Open offer
    </a>
  </article>
</template>
