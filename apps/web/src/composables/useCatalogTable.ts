import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import {
  getCoreRowModel,
  useVueTable,
  type ColumnDef,
  type ColumnFiltersState,
  type PaginationState,
  type SortingState,
  type Updater,
  type VisibilityState,
} from '@tanstack/vue-table'
import { i18n } from '@/i18n'
import type { CatalogPageInfo, CatalogProduct, CatalogProductsVariables } from '@/types/catalog'
import { pricePer100g } from '@/utils/number'

const SORT_KEYS: Record<string, string> = {
  price: 'price',
  pricePerActive: 'price_per_active',
  concentration: 'concentration',
  totalActive: 'total_active',
}

function updated<T>(updater: Updater<T>, previous: T): T {
  return typeof updater === 'function' ? (updater as (value: T) => T)(previous) : updater
}

export function useCatalogTable() {
  const rows = shallowRef<CatalogProduct[]>([])
  const pageInfo = ref<CatalogPageInfo | null>(null)
  const activeName = ref('')
  const sorting = ref<SortingState>([{ id: 'pricePerActive', desc: false }])
  const columnFilters = ref<ColumnFiltersState>([])
  const globalFilter = ref('')
  const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 12 })
  const compact =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(max-width: 640px)').matches
  const columnVisibility = ref<VisibilityState>({
    totalActive: !compact,
    flavors: !compact,
    brand: false,
    category: false,
    packaging: false,
    mass: false,
    tags: false,
  })
  const scenario = ref('')
  const debouncedFilters = ref<ColumnFiltersState>([])
  const debouncedSearch = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  const { t } = i18n.global

  const columns = computed<ColumnDef<CatalogProduct>[]>(() => [
    {
      id: 'product',
      accessorKey: 'name',
      header: t('catalog.column.product'),
      enableHiding: false,
    },
    {
      id: 'pricePerActive',
      accessorFn: (row) => pricePer100g(row.pricePerActive),
      header: t('catalog.column.pricePerActive'),
      enableSorting: true,
    },
    {
      id: 'price',
      accessorKey: 'price',
      header: t('catalog.column.price'),
      enableSorting: true,
    },
    {
      id: 'concentration',
      accessorKey: 'concentration',
      header: t('catalog.column.concentration'),
      enableSorting: true,
    },
    {
      id: 'totalActive',
      accessorKey: 'totalActive',
      header: t('catalog.column.totalActive'),
      enableSorting: true,
    },
    {
      id: 'flavors',
      accessorFn: (row) => row.nutritionProfile?.flavors.join(', '),
      header: t('catalog.column.flavors'),
      enableColumnFilter: true,
    },
    {
      id: 'brand',
      accessorFn: (row) => row.brand.name,
      header: t('catalog.column.brand'),
      enableColumnFilter: true,
    },
    {
      id: 'category',
      accessorFn: (row) => row.category?.name,
      header: t('catalog.column.category'),
      enableColumnFilter: true,
    },
    { id: 'packaging', accessorKey: 'packagingDisplay', header: t('catalog.column.packaging') },
    { id: 'mass', accessorKey: 'netMass', header: t('catalog.column.mass') },
    {
      id: 'tags',
      accessorFn: (row) => row.tags.map((tag) => tag.name).join(', '),
      header: t('catalog.column.tags'),
    },
    { id: 'offer', accessorKey: 'externalLink', header: t('catalog.column.offer') },
  ])

  function resetPage() {
    pagination.value = { ...pagination.value, pageIndex: 0 }
  }
  const table = useVueTable({
    get data() {
      return rows.value
    },
    get columns() {
      return columns.value
    },
    get rowCount() {
      return pageInfo.value?.totalCount ?? 0
    },
    defaultColumn: { enableSorting: false, enableColumnFilter: false, sortDescFirst: false },
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => `${row.id}:${row.nutritionProfile?.id ?? 'none'}`,
    manualFiltering: true,
    manualSorting: true,
    manualPagination: true,
    enableMultiSort: false,
    enableSortingRemoval: false,
    state: {
      get sorting() {
        return sorting.value
      },
      get columnFilters() {
        return columnFilters.value
      },
      get globalFilter() {
        return globalFilter.value
      },
      get pagination() {
        return pagination.value
      },
      get columnVisibility() {
        return columnVisibility.value
      },
    },
    onSortingChange: (updater) => {
      sorting.value = updated(updater, sorting.value)
      resetPage()
    },
    onColumnFiltersChange: (updater) => {
      columnFilters.value = updated(updater, columnFilters.value)
    },
    onGlobalFilterChange: (updater) => {
      globalFilter.value = updated(updater, globalFilter.value)
    },
    onPaginationChange: (updater) => {
      pagination.value = updated(updater, pagination.value)
    },
    onColumnVisibilityChange: (updater) => {
      columnVisibility.value = updated(updater, columnVisibility.value)
    },
  })

  watch(
    [globalFilter, columnFilters],
    () => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        debouncedSearch.value = globalFilter.value.trim()
        debouncedFilters.value = [...columnFilters.value]
        resetPage()
      }, 250)
    },
    { deep: true },
  )
  watch(scenario, resetPage)
  onScopeDispose(() => clearTimeout(timer))

  function chosen(id: string): string[] {
    const value: unknown = debouncedFilters.value.find((filter) => filter.id === id)?.value
    return Array.isArray(value) ? value.filter((name) => typeof name === 'string') : []
  }
  const variables = computed<CatalogProductsVariables>(() => {
    const sort = sorting.value[0]
    return {
      filters: {
        page: pagination.value.pageIndex + 1,
        perPage: pagination.value.pageSize,
        search: debouncedSearch.value || null,
        brands: chosen('brand'),
        flavors: chosen('flavors'),
        categories: chosen('category'),
        sortBy: SORT_KEYS[sort?.id ?? 'pricePerActive'] ?? 'price_per_active',
        sortDir: sort?.desc ? 'desc' : 'asc',
        scenario: scenario.value || null,
      },
    }
  })
  const filtersActive = computed(() => Boolean(globalFilter.value || columnFilters.value.length))

  function clearFilters() {
    clearTimeout(timer)
    table.setGlobalFilter('')
    table.resetColumnFilters(true)
    debouncedSearch.value = ''
    debouncedFilters.value = []
    resetPage()
  }

  return { table, rows, pageInfo, activeName, scenario, variables, filtersActive, clearFilters }
}
