import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useQuery } from '@vue/apollo-composable'

import { CatalogProductsDocument } from '@/gql/graphql'
import type { CatalogPageInfo, CatalogProduct, CatalogProductsVariables } from '@/types/catalog'

export function useCatalogQuery(variables: MaybeRefOrGetter<CatalogProductsVariables>) {
  const { result, loading, error, refetch } = useQuery(
    CatalogProductsDocument,
    () => toValue(variables),
  )

  const pageInfo = computed<CatalogPageInfo | null>(
    () => result.value?.catalogProducts.pageInfo ?? null,
  )

  const products = computed<CatalogProduct[]>(() => result.value?.catalogProducts.items ?? [])

  return {
    error,
    loading,
    pageInfo,
    products,
    refetch,
    result,
  }
}
