<script setup lang="ts">
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
    class="mt-8 flex flex-col gap-4 border-t border-white/10 pt-6 text-sm text-stone-300 md:flex-row md:items-center md:justify-between"
  >
    <p>
      Showing page {{ pageInfo.currentPage }} of {{ pageInfo.totalPages }}
    </p>

    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="rounded-lg border border-white/10 px-3 py-2 transition hover:border-orange-400 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!pageInfo.hasPreviousPage"
        @click="emit('update:page', pageInfo.currentPage - 1)"
      >
        Previous
      </button>

      <button
        v-for="pageNumber in buildPages(pageInfo)"
        :key="pageNumber"
        type="button"
        class="rounded-lg border px-3 py-2 transition"
        :class="
          pageNumber === pageInfo.currentPage
            ? 'border-orange-400 bg-orange-400/15 text-orange-200'
            : 'border-white/10 hover:border-orange-400'
        "
        @click="emit('update:page', pageNumber)"
      >
        {{ pageNumber }}
      </button>

      <button
        type="button"
        class="rounded-lg border border-white/10 px-3 py-2 transition hover:border-orange-400 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!pageInfo.hasNextPage"
        @click="emit('update:page', pageInfo.currentPage + 1)"
      >
        Next
      </button>
    </div>
  </nav>
</template>
