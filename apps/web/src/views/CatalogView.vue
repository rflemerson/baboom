<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import { useI18n } from 'vue-i18n'
import CatalogToolbar from '@/components/catalog/CatalogToolbar.vue'
import CatalogTable from '@/components/catalog/CatalogTable.vue'
import CatalogCardList from '@/components/catalog/CatalogCardList.vue'
import CatalogTableFilters from '@/components/catalog/CatalogTableFilters.vue'
import CatalogColumnPicker from '@/components/catalog/CatalogColumnPicker.vue'
import CatalogPagination from '@/components/catalog/CatalogPagination.vue'
import { useCatalogTable } from '@/composables/useCatalogTable'
import { useCatalogQuery } from '@/composables/useCatalogQuery'

const { t } = useI18n()
const {
  table,
  rows,
  pageInfo: tablePageInfo,
  activeName,
  activeSlug,
  scenario,
  benefits,
  variables,
  filtersActive,
  clearFilters,
} = useCatalogTable()
const { active, error, loading, massUnit, pageInfo, products, refetch } = useCatalogQuery(variables)
watchEffect(() => {
  rows.value = products.value
  tablePageInfo.value = pageInfo.value
  activeName.value = active.value?.name ?? ''
})
const hasRows = computed(() => !error.value && products.value.length > 0)
// What the cards sort by, where there is no column header to click.
const SORT_CHOICES = [
  'pricePerActive:asc',
  'price:asc',
  'price:desc',
  'concentration:desc',
  'totalActive:desc',
] as const
const sortChoice = computed(() => {
  const sort = table.getState().sorting[0]
  return sort ? `${sort.id}:${sort.desc ? 'desc' : 'asc'}` : SORT_CHOICES[0]
})
function setSortChoice(value: string) {
  const [id, direction] = value.split(':')
  table.setSorting([{ id: id ?? 'pricePerActive', desc: direction === 'desc' }])
}
function setPage(page: number) {
  table.setPageIndex(page - 1)
}
</script>

<template>
  <main id="catalog" class="app-catalog-page py-4 sm:py-6">
    <div class="app-shell px-4 sm:px-6">
      <CatalogToolbar
        v-model:active-slug="activeSlug"
        v-model:benefits="benefits"
        :active="active"
        :scenario="scenario"
        @update:scenario="scenario = $event"
      />
      <div class="my-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <BaseSelect
            :label="t('catalog.perPage')"
            :model-value="String(table.getState().pagination.pageSize)"
            :options="
              [12, 24, 48].map((size) => ({
                value: String(size),
                label: t('catalog.rowsPerPage', { count: size }),
              }))
            "
            @update:model-value="table.setPageSize(Number($event))"
          />
          <output v-if="pageInfo" class="app-copy-muted text-xs whitespace-nowrap">{{
            t('catalog.results', { count: pageInfo.totalCount })
          }}</output>
        </div>
        <div class="flex items-center gap-2">
          <CatalogTableFilters :table="table" />
          <CatalogColumnPicker class="hidden md:block" :table="table" />
        </div>
      </div>
      <div class="mb-3 flex items-center justify-between gap-3 md:hidden">
        <span class="app-copy-muted text-xs">{{ t('catalog.sortBy') }}</span>
        <BaseSelect
          :label="t('catalog.sortBy')"
          :model-value="sortChoice"
          :options="
            SORT_CHOICES.map((value) => ({
              value,
              label: t(`catalog.sortChoice.${value.replace(':', '_')}`),
            }))
          "
          @update:model-value="setSortChoice"
        />
      </div>
      <CatalogTable
        :class="{ 'hidden md:block': hasRows }"
        :table="table"
        :active-name="activeName"
        :mass-unit="massUnit"
        :loading="loading"
      >
        <template v-if="error || !products.length" #state>
          <section
            v-if="error"
            class="app-panel app-state-panel rounded-xl px-6 py-12 text-center"
            role="alert"
          >
            <h2 class="font-semibold">{{ t('catalog.loadError') }}</h2>
            <p class="app-copy-muted mt-2 text-sm">{{ t('catalog.requestError') }}</p>
            <button class="app-button app-button--primary mt-4" type="button" @click="refetch()">
              {{ t('catalog.retry') }}
            </button>
          </section>
          <section
            v-else-if="loading && !products.length"
            class="app-panel rounded-xl p-6"
            aria-busy="true"
          >
            <output class="sr-only">{{ t('catalog.loading') }}</output>
            <div v-for="index in 8" :key="index" class="app-skeleton my-3 h-9 rounded" />
          </section>
          <section v-else class="app-panel app-state-panel rounded-xl px-6 py-12 text-center">
            <h2 class="font-semibold">{{ t('catalog.noResults') }}</h2>
            <p class="app-copy-muted mt-2 text-sm">
              {{ t(filtersActive ? 'catalog.emptyHint' : 'catalog.emptyCatalog') }}
            </p>
            <button
              v-if="filtersActive"
              type="button"
              class="app-button app-button--secondary mt-4"
              @click="clearFilters"
            >
              {{ t('catalog.clearFilters') }}
            </button>
          </section>
        </template>
      </CatalogTable>
      <CatalogCardList
        v-if="hasRows"
        class="md:hidden"
        :table="table"
        :active-name="activeName"
        :mass-unit="massUnit"
      />
      <div v-if="pageInfo && products.length && !error" class="mt-4">
        <CatalogPagination :page-info="pageInfo" :disabled="loading" @update:page="setPage" />
      </div>
    </div>
  </main>
</template>

<style scoped lang="scss">
.app-catalog-page {
  min-height: calc(100vh - 7rem);
}
</style>
