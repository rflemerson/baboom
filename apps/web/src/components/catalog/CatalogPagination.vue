<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

import type { CatalogPageInfo } from '@/types/catalog'

const { t } = useI18n()

type PaginationItem = { type: 'page'; value: number } | { type: 'ellipsis'; key: string }

defineProps<{
  pageInfo: CatalogPageInfo
  disabled?: boolean
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
    :aria-label="t('catalog.pagination.label')"
    class="app-pagination flex flex-wrap items-center justify-between gap-3 pt-3 text-xs"
  >
    <span>{{
      t('catalog.pagination.summary', { page: pageInfo.currentPage, pages: pageInfo.totalPages })
    }}</span>

    <div class="flex items-center gap-1">
      <button
        type="button"
        :aria-label="t('catalog.pagination.previousLabel')"
        class="app-pagination__page app-button app-button--ghost"
        :disabled="disabled || !pageInfo.hasPreviousPage"
        @click="emit('update:page', pageInfo.currentPage - 1)"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>

      <template
        v-for="item in buildPages(pageInfo)"
        :key="item.type === 'page' ? item.value : item.key"
      >
        <button
          v-if="item.type === 'page'"
          type="button"
          :disabled="disabled"
          :aria-current="item.value === pageInfo.currentPage ? 'page' : undefined"
          :aria-label="
            item.value === pageInfo.currentPage
              ? t('catalog.pagination.currentLabel', { page: item.value })
              : t('catalog.pagination.pageLabel', { page: item.value })
          "
          class="app-pagination__page app-button"
          :class="item.value === pageInfo.currentPage ? 'app-button--accent' : 'app-button--ghost'"
          @click="emit('update:page', item.value)"
        >
          {{ item.value }}
        </button>
        <span v-else aria-hidden="true" class="app-copy-soft inline-flex w-6 justify-center">
          …
        </span>
      </template>

      <button
        type="button"
        :aria-label="t('catalog.pagination.nextLabel')"
        class="app-pagination__page app-button app-button--ghost"
        :disabled="disabled || !pageInfo.hasNextPage"
        @click="emit('update:page', pageInfo.currentPage + 1)"
      >
        <ChevronRight class="h-4 w-4" />
      </button>
    </div>
  </nav>
</template>

<style scoped lang="scss">
.app-pagination {
  border-top: 1px solid var(--app-border);
  color: var(--app-text-muted);
}

.app-pagination__page {
  min-width: var(--app-control-height);
  padding: 0 0.5rem;
  font-size: 0.75rem;
}
</style>
