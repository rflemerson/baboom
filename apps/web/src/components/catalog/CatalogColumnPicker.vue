<script setup lang="ts">
import { ChevronDown, Columns3 } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { Table } from '@tanstack/vue-table'
import { useDisclosure } from '@/composables/useDisclosure'
import type { CatalogProduct } from '@/types/catalog'

defineProps<{ table: Table<CatalogProduct> }>()
const { t } = useI18n()
const { root, escape } = useDisclosure()
</script>

<template>
  <details ref="root" name="catalog-menu" class="app-menu" @keydown="escape">
    <summary class="app-button app-button--secondary">
      <Columns3 class="h-3.5 w-3.5" />{{ t('catalog.columns') }}<ChevronDown class="h-3 w-3" />
    </summary>
    <fieldset class="app-menu__panel">
      <legend class="sr-only">{{ t('catalog.columnSelection') }}</legend>
      <label
        v-for="column in table.getAllLeafColumns().filter((column) => column.getCanHide())"
        :key="column.id"
        class="flex items-center gap-2 py-1.5"
      >
        <input
          type="checkbox"
          :checked="column.getIsVisible()"
          @change="column.toggleVisibility(($event.target as HTMLInputElement).checked)"
        />{{ column.columnDef.header }}
      </label>
    </fieldset>
  </details>
</template>
