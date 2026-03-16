<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'

import type { CatalogProduct } from '@/types/catalog'
import BaseMetricCard from '@/components/ui/BaseMetricCard.vue'
import { formatDecimal } from '@/utils/number'

defineProps<{
  product: CatalogProduct
}>()
</script>

<template>
  <article class="app-card rounded-2xl p-5">
    <div class="mb-4 rounded-2xl px-4 py-5 text-center" style="background: var(--app-brand-soft)">
      <p class="app-card__brand">{{ product.brand.name }}</p>
      <h2 class="app-card__title mt-2 text-lg font-semibold">
        {{ product.name }}
      </h2>
    </div>

    <div class="mb-4 flex flex-wrap items-center gap-2">
      <span class="app-chip app-chip--accent px-3 py-1 text-xs">
        {{ product.packagingDisplay }}
      </span>
      <span class="app-chip px-3 py-1 text-xs">{{ product.weight }} g</span>
      <span class="app-chip px-3 py-1 text-xs">
        {{ product.category?.name ?? 'Uncategorized' }}
      </span>
      <span v-if="product.concentration" class="app-chip px-3 py-1 text-xs">
        {{ product.concentration }}% concentration
      </span>
      <span
        v-for="tag in product.tags.slice(0, 3)"
        :key="`${product.id}-${tag.name}`"
        class="app-chip px-2.5 py-1 text-xs"
      >
        {{ tag.name }}
      </span>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <BaseMetricCard compact label="Total price" :value="formatDecimal(product.lastPrice)" />
      <BaseMetricCard compact label="Total protein" :value="formatDecimal(product.totalProtein)" />
    </div>

    <BaseMetricCard
      class="mt-3 rounded-3xl"
      inline-action
      label="Price / g"
      :value="formatDecimal(product.pricePerGram)"
    >
      <template #action>
        <a
          v-if="product.externalLink"
          :href="product.externalLink"
          target="_blank"
          rel="noreferrer"
          class="app-button app-button--primary app-button--icon-square rounded-2xl"
          aria-label="View offer"
          title="View offer"
        >
          <ArrowUpRight class="h-4 w-4" />
        </a>
      </template>
    </BaseMetricCard>
  </article>
</template>
