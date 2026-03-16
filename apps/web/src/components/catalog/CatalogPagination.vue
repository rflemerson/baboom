<script setup lang="ts">
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

import type { CatalogPageInfo } from '@/types/catalog'

defineProps<{
  pageInfo: CatalogPageInfo
}>()

const emit = defineEmits<{
  'update:page': [value: number]
}>()

function buildPages(pageInfo: CatalogPageInfo) {
  const start = Math.max(1, pageInfo.currentPage - 2)
  const end = Math.min(pageInfo.totalPages, pageInfo.currentPage + 2)

  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
}
</script>

<template>
  <nav
    v-if="pageInfo.totalPages > 1"
    class="app-pagination mt-8 flex flex-col gap-4 pt-6 text-sm md:flex-row md:items-center md:justify-between"
  >
    <div class="app-pagination__summary flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-center md:justify-start md:text-left">
      <span>{{ pageInfo.totalCount }} products</span>
      <span>Page {{ pageInfo.currentPage }} of {{ pageInfo.totalPages }}</span>
      <span>{{ pageInfo.perPage }} per page</span>
    </div>

    <div class="flex flex-wrap items-center justify-center gap-2 md:justify-end">
      <button
        type="button"
        class="app-button app-button--ghost app-button--control inline-flex items-center gap-2 px-3 sm:px-4 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!pageInfo.hasPreviousPage"
        @click="emit('update:page', pageInfo.currentPage - 1)"
      >
        <ChevronLeft class="h-4 w-4" />
        <span class="hidden sm:inline">Previous</span>
      </button>

      <button
        v-for="pageNumber in buildPages(pageInfo)"
        :key="pageNumber"
        type="button"
        class="app-pagination__page app-button app-button--control transition"
        :class="
          pageNumber === pageInfo.currentPage
            ? 'app-button--accent'
            : 'app-button--ghost'
        "
        @click="emit('update:page', pageNumber)"
      >
        {{ pageNumber }}
      </button>

      <button
        type="button"
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
