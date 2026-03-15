<script setup lang="ts">
import type { CatalogProduct } from '@/types/catalog'

defineProps<{
  product: CatalogProduct
}>()
</script>

<template>
  <article class="rounded-2xl border border-white/10 bg-stone-900/80 p-5 shadow-lg shadow-black/20">
    <div class="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
      <div class="flex-1">
        <div class="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.24em] text-orange-300">
          <span>{{ product.brand.name }}</span>
          <span class="rounded-full bg-white/10 px-2.5 py-1 text-stone-200">
            {{ product.packagingDisplay }}
          </span>
        </div>

        <h2 class="mt-3 text-2xl font-semibold text-white">{{ product.name }}</h2>

        <div class="mt-4 flex flex-wrap gap-2">
          <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-stone-300">
            {{ product.weight }} g
          </span>
          <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-stone-300">
            {{ product.category?.name ?? 'Uncategorized' }}
          </span>
          <span
            v-if="product.concentration"
            class="rounded-full border border-white/10 px-3 py-1 text-xs text-stone-300"
          >
            {{ product.concentration }}% concentration
          </span>
          <span
            v-if="product.totalProtein"
            class="rounded-full border border-white/10 px-3 py-1 text-xs text-stone-300"
          >
            {{ product.totalProtein }} total protein
          </span>
        </div>

        <ul class="mt-4 flex flex-wrap gap-2">
          <li
            v-for="tag in product.tags"
            :key="`${product.id}-${tag.name}`"
            class="rounded-full border border-orange-400/30 bg-orange-400/10 px-2.5 py-1 text-xs text-orange-200"
          >
            {{ tag.name }}
          </li>
        </ul>
      </div>

      <div class="min-w-[220px] border-t border-white/10 pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
        <dl class="grid gap-3 text-sm text-stone-300">
          <div class="flex items-center justify-between gap-4">
            <dt class="text-stone-500">Price</dt>
            <dd>{{ product.lastPrice ?? '-' }}</dd>
          </div>
          <div class="flex items-center justify-between gap-4">
            <dt class="text-stone-500">Price / g</dt>
            <dd>{{ product.pricePerGram ?? '-' }}</dd>
          </div>
        </dl>

        <a
          v-if="product.externalLink"
          :href="product.externalLink"
          target="_blank"
          rel="noreferrer"
          class="mt-5 inline-flex text-sm font-medium text-orange-300 underline-offset-4 hover:underline"
        >
          Open offer
        </a>
      </div>
    </div>
  </article>
</template>
