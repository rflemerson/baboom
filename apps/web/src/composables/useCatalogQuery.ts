import { computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'

import {
  CATALOG_PRODUCTS_QUERY,
  DEFAULT_CATALOG_PRODUCTS_VARIABLES,
} from '@/graphql/queries/catalog'
import type { CatalogPageInfo, CatalogProduct } from '@/types/catalog'

export function useCatalogQuery() {
  const { result, loading, error } = useQuery(
    CATALOG_PRODUCTS_QUERY,
    DEFAULT_CATALOG_PRODUCTS_VARIABLES,
  )

  const pageInfo = computed<CatalogPageInfo | null>(
    () => result.value?.catalogProducts.pageInfo ?? null,
  )

  const products = computed<CatalogProduct[]>(
    () => result.value?.catalogProducts.items ?? [],
  )

  return {
    error,
    loading,
    pageInfo,
    products,
    result,
  }
}
