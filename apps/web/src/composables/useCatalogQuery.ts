import { computed, type MaybeRefOrGetter, ref, toValue, watch } from 'vue'

import type {
  CatalogPageInfo,
  CatalogProduct,
  CatalogProductsResponse,
  CatalogProductsVariables,
} from '@/types/catalog'

const catalogApiUrl = import.meta.env.VITE_CATALOG_API_URL || '/api/catalog/products/'

function appendOptionalParam(
  params: URLSearchParams,
  name: string,
  value: number | string | null | undefined,
) {
  if (value === null || value === undefined || value === '') {
    return
  }
  params.set(name, String(value))
}

function buildCatalogUrl(variables: CatalogProductsVariables) {
  const filters = variables.filters ?? {}
  const params = new URLSearchParams()

  appendOptionalParam(params, 'page', filters.page)
  appendOptionalParam(params, 'per_page', filters.perPage)
  appendOptionalParam(params, 'search', filters.search)
  appendOptionalParam(params, 'brand', filters.brand)
  appendOptionalParam(params, 'price_min', filters.priceMin)
  appendOptionalParam(params, 'price_max', filters.priceMax)
  appendOptionalParam(params, 'price_per_protein_gram_min', filters.pricePerProteinGramMin)
  appendOptionalParam(params, 'price_per_protein_gram_max', filters.pricePerProteinGramMax)
  appendOptionalParam(params, 'concentration_min', filters.concentrationMin)
  appendOptionalParam(params, 'concentration_max', filters.concentrationMax)
  appendOptionalParam(params, 'sort_by', filters.sortBy)
  appendOptionalParam(params, 'sort_dir', filters.sortDir)

  const queryString = params.toString()
  return queryString ? `${catalogApiUrl}?${queryString}` : catalogApiUrl
}

export function useCatalogQuery(variables: MaybeRefOrGetter<CatalogProductsVariables>) {
  const result = ref<CatalogProductsResponse | null>(null)
  const loading = ref(false)
  const error = ref<Error | null>(null)
  let requestId = 0

  async function fetchCatalog() {
    const currentRequestId = requestId + 1
    requestId = currentRequestId
    loading.value = true
    error.value = null

    try {
      const response = await fetch(buildCatalogUrl(toValue(variables)), {
        headers: {
          Accept: 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`Catalog request failed with status ${response.status}`)
      }

      const payload = (await response.json()) as CatalogProductsResponse
      if (currentRequestId === requestId) {
        result.value = payload
      }
    } catch (caughtError) {
      if (currentRequestId === requestId) {
        error.value =
          caughtError instanceof Error ? caughtError : new Error('Catalog request failed')
      }
    } finally {
      if (currentRequestId === requestId) {
        loading.value = false
      }
    }
  }

  watch(() => toValue(variables), fetchCatalog, { deep: true, immediate: true })

  const pageInfo = computed<CatalogPageInfo | null>(() => result.value?.pageInfo ?? null)

  const products = computed<CatalogProduct[]>(() => result.value?.items ?? [])

  return {
    error,
    loading,
    pageInfo,
    products,
    refetch: fetchCatalog,
    result,
  }
}
