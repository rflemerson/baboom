<script setup lang="ts">
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

import type { CatalogPageInfo } from '@/types/catalog'

type PaginationItem =
  | { type: 'page'; value: number }
  | { type: 'ellipsis'; key: string }

defineProps<{
  pageInfo: CatalogPageInfo
}>()

const emit = defineEmits<{
  'update:page': [value: number]
}>()

function buildPages(pageInfo: CatalogPageInfo): PaginationItem[] {
  if (pageInfo.totalPages <= 7) {
    return Array.from({ length: pageInfo.totalPages }, (_, index) => ({
      type: 'page',
      value: index + 1,
    }))
  }

  const start = Math.max(2, pageInfo.currentPage - 1)
  const end = Math.min(pageInfo.totalPages - 1, pageInfo.currentPage + 1)
  const items: PaginationItem[] = [{ type: 'page', value: 1 }]

  if (start > 2) {
    items.push({ type: 'ellipsis', key: 'start' })
  }

  for (let value = start; value <= end; value += 1) {
    items.push({ type: 'page', value })
  }

  if (end < pageInfo.totalPages - 1) {
    items.push({ type: 'ellipsis', key: 'end' })
  }

  items.push({ type: 'page', value: pageInfo.totalPages })

  return items
}
</script>

<template>
  <nav
    v-if="pageInfo.totalPages > 1"
    aria-label="Catalog pages"
    class="app-pagination mt-8 flex flex-col gap-4 pt-6 text-sm md:flex-row md:items-center md:justify-between"
  >
    <div class="app-pagination__summary flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-center md:justify-start md:text-left">
      <span>{{ pageInfo.totalCount }} products</span>
      <span>Page {{ pageInfo.currentPage }} of {{ pageInfo.totalPages }}</span>
      <span>{{ pageInfo.perPage }} per page</span>
    </div>

    <div class="app-pagination__nav flex flex-wrap items-center justify-center gap-2 rounded-2xl p-2 md:justify-end">
      <button
        type="button"
        aria-label="Go to previous page"
        class="app-button app-button--ghost app-button--control inline-flex items-center gap-2 px-3 sm:px-4 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!pageInfo.hasPreviousPage"
        @click="emit('update:page', pageInfo.currentPage - 1)"
      >
        <ChevronLeft class="h-4 w-4" />
        <span class="hidden sm:inline">Previous</span>
      </button>

      <template v-for="item in buildPages(pageInfo)" :key="item.type === 'page' ? item.value : item.key">
        <button
          v-if="item.type === 'page'"
          type="button"
          :aria-current="item.value === pageInfo.currentPage ? 'page' : undefined"
          :aria-label="
            item.value === pageInfo.currentPage
              ? `Current page, page ${item.value}`
              : `Go to page ${item.value}`
          "
          class="app-pagination__page app-button app-button--control"
          :class="
            item.value === pageInfo.currentPage
              ? 'app-button--accent'
              : 'app-button--ghost'
          "
          @click="emit('update:page', item.value)"
        >
          {{ item.value }}
        </button>
        <span
          v-else
          aria-hidden="true"
          class="app-copy-soft inline-flex min-w-[2rem] items-center justify-center text-sm"
        >
          ...
        </span>
      </template>

      <button
        type="button"
        aria-label="Go to next page"
        class="app-button app-button--ghost app-button--control inline-flex items-center gap-2 px-3 sm:px-4 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!pageInfo.hasNextPage"
        @click="emit('update:page', pageInfo.currentPage + 1)"
      >
        <span class="hidden sm:inline">Next</span>
        <ChevronRight class="h-4 w-4" />
      </button>
    </div>
  </nav>
</template>
