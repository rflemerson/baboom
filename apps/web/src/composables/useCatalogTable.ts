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

// The catalog lists what can be bought now, and products where the active is
// at least 10% of the mass, unless a visitor asks otherwise.
function defaultFilters(): ColumnFiltersState {
  return [
    { id: 'stock', value: ['in_stock'] },
    // [min, max] in percent; an empty bound is open.
    { id: 'concentration', value: ['10', ''] },
  ]
}

export function useCatalogTable() {
  const rows = shallowRef<CatalogProduct[]>([])
  const pageInfo = ref<CatalogPageInfo | null>(null)
  const activeName = ref('')
  // The active to compare by; empty asks for the catalog's default.
  const activeSlug = ref('')
  const sorting = ref<SortingState>([{ id: 'pricePerActive', desc: false }])
  const columnFilters = ref<ColumnFiltersState>(defaultFilters())
  const globalFilter = ref('')
  const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 12 })
  const columnVisibility = ref<VisibilityState>({
    flavors: false,
    stock: false,
    brand: false,
    packaging: false,
    mass: false,
    tags: false,
  })
  // The best price leads; "normal" is the catalog price.
  const scenario = ref('best')
  // Coupons count by default; cashback and points only when asked for.
  const benefits = ref<string[]>(['coupon'])
  const debouncedFilters = ref<ColumnFiltersState>(defaultFilters())
  const debouncedSearch = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  const { t } = i18n.global

  const columns = computed<ColumnDef<CatalogProduct>[]>(() => [
    // What it is, how much active, what it costs, what the active costs, then
    // the offer; the rest waits in the column picker.
    {
      id: 'product',
      accessorKey: 'name',
      header: t('catalog.column.product'),
      enableHiding: false,
    },
    {
      id: 'category',
      accessorFn: (row) => row.category?.name,
      header: t('catalog.column.category'),
      enableColumnFilter: true,
    },
    {
      id: 'concentration',
      accessorKey: 'concentration',
      header: t('catalog.column.concentration'),
      enableSorting: true,
      enableColumnFilter: true,
    },
    {
      id: 'totalActive',
      accessorKey: 'totalActive',
      header: t('catalog.column.totalActive'),
      enableSorting: true,
    },
    {
      id: 'price',
      accessorKey: 'price',
      header: t('catalog.column.price'),
      enableSorting: true,
    },
    { id: 'benefits', header: t('catalog.column.benefits') },
    {
      id: 'pricePerActive',
      accessorFn: (row) => pricePer100g(row.pricePerActive),
      header: t('catalog.column.pricePerActive'),
      enableSorting: true,
    },
    { id: 'offer', accessorKey: 'externalLink', header: t('catalog.column.offer') },
    {
      id: 'flavors',
      accessorFn: (row) => row.nutritionProfile?.flavors.join(', '),
      header: t('catalog.column.flavors'),
      enableColumnFilter: true,
    },
    {
      id: 'stock',
      accessorKey: 'stockStatus',
      header: t('catalog.column.stock'),
      enableColumnFilter: true,
    },
    {
      id: 'brand',
      accessorFn: (row) => row.brand.name,
      header: t('catalog.column.brand'),
      enableColumnFilter: true,
    },
    { id: 'packaging', accessorKey: 'packagingDisplay', header: t('catalog.column.packaging') },
    { id: 'mass', accessorKey: 'netMass', header: t('catalog.column.mass') },
    {
      id: 'tags',
      accessorFn: (row) => row.tags.map((tag) => tag.name).join(', '),
      header: t('catalog.column.tags'),
    },
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
    initialState: { columnFilters: defaultFilters() },
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
  watch([scenario, benefits, activeSlug], resetPage, { deep: true })
  onScopeDispose(() => clearTimeout(timer))

  function chosen(id: string): string[] {
    const value: unknown = debouncedFilters.value.find((filter) => filter.id === id)?.value
    return Array.isArray(value) ? value.filter((name) => typeof name === 'string') : []
  }
  function bound(index: number): number | null {
    const value = chosen('concentration')[index]
    return value ? Number(value) : null
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
        stock: chosen('stock'),
        concentrationMin: bound(0),
        concentrationMax: bound(1),
        sortBy: SORT_KEYS[sort?.id ?? 'pricePerActive'] ?? 'price_per_active',
        sortDir: sort?.desc ? 'desc' : 'asc',
        scenario: scenario.value || null,
        active: activeSlug.value || null,
        coupon: benefits.value.includes('coupon'),
        cashback: benefits.value.includes('cashback'),
        points: benefits.value.includes('points'),
      },
    }
  })
  const filtersActive = computed(
    () =>
      Boolean(globalFilter.value) ||
      JSON.stringify(columnFilters.value) !== JSON.stringify(defaultFilters()),
  )

  function clearFilters() {
    clearTimeout(timer)
    table.setGlobalFilter('')
    columnFilters.value = defaultFilters()
    debouncedSearch.value = ''
    debouncedFilters.value = defaultFilters()
    resetPage()
  }

  return {
    table,
    rows,
    pageInfo,
    activeName,
    activeSlug,
    scenario,
    benefits,
    variables,
    filtersActive,
    clearFilters,
  }
}
