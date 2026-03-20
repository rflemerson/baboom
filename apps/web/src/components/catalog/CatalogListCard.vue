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
  <article class="app-card rounded-2xl p-4 sm:p-5">
    <div class="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
      <div class="flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <span class="app-card__brand">{{ product.brand.name }}</span>
        </div>

        <h2 class="app-card__title mt-3 text-xl font-semibold sm:text-2xl">{{ product.name }}</h2>

        <div class="mt-4 flex flex-wrap gap-2">
          <span class="app-chip app-chip--accent px-2.5 py-1 text-xs">
            {{ product.packagingDisplay }}
          </span>
          <span class="app-chip px-3 py-1 text-xs"> {{ product.weight }} g </span>
          <span class="app-chip px-3 py-1 text-xs">
            {{ product.category?.name ?? 'Uncategorized' }}
          </span>
          <span v-if="product.concentration" class="app-chip px-3 py-1 text-xs">
            {{ formatDecimal(product.concentration, 1) }}% concentration
          </span>
        </div>

        <ul v-if="product.tags.length" class="mt-4 flex flex-wrap gap-2">
          <li
            v-for="tag in product.tags.slice(0, 3)"
            :key="`${product.id}-${tag.name}`"
            class="app-chip px-2.5 py-1 text-xs"
          >
            {{ tag.name }}
          </li>
        </ul>
      </div>

      <div class="grid gap-3 sm:min-w-[220px] lg:min-w-[220px]">
        <div class="grid grid-cols-2 gap-3">
          <BaseMetricCard compact label="Total price" :value="formatDecimal(product.lastPrice)" />
          <BaseMetricCard
            compact
            label="Max protein"
            :value="formatDecimal(product.totalProtein)"
          />
        </div>

        <BaseMetricCard
          class="rounded-3xl"
          inline-action
          label="Price / protein g"
          :value="formatDecimal(product.pricePerProteinGram)"
        >
          <template #action>
            <a
              v-if="product.externalLink"
              :href="product.externalLink"
              target="_blank"
              rel="noreferrer"
              class="app-button app-button--primary app-button--icon-square rounded-2xl"
              :aria-label="`View offer for ${product.name}`"
              title="View offer"
            >
              <ArrowUpRight class="h-4 w-4" />
            </a>
          </template>
        </BaseMetricCard>
      </div>
    </div>
  </article>
</template>
