import type { Ref } from 'vue'
import { computed, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import type { UseQueryReturn } from '@vue/apollo-composable'
import type { CatalogProductsQuery, CatalogProductsQueryVariables } from '@/gql/graphql'

const { mockUseQuery } = vi.hoisted(() => ({
  mockUseQuery:
    vi.fn<
      (...args: unknown[]) => UseQueryReturn<CatalogProductsQuery, CatalogProductsQueryVariables>
    >(),
}))

vi.mock('@vue/apollo-composable', () => ({
  useQuery: mockUseQuery,
}))

import { useCatalogQuery } from './useCatalogQuery'

function createUseQueryReturn(
  overrides: Partial<UseQueryReturn<CatalogProductsQuery, CatalogProductsQueryVariables>>,
): UseQueryReturn<CatalogProductsQuery, CatalogProductsQueryVariables> {
  return {
    result: ref(undefined),
    loading: ref(false),
    networkStatus: ref(undefined),
    error: computed(() => null),
    start: vi.fn(),
    stop: vi.fn(),
    restart: vi.fn(),
    forceDisabled: ref(false),
    document: ref(null),
    variables: ref(undefined) as Ref<CatalogProductsQueryVariables | undefined>,
    options: {},
    query: ref(null),
    refetch: vi.fn(),
    fetchMore: vi.fn(),
    updateQuery: vi.fn(),
    subscribeToMore: vi.fn(),
    onResult: vi.fn(() => ({ off: vi.fn() })),
    onError: vi.fn(() => ({ off: vi.fn() })),
    ...overrides,
  }
}

describe('useCatalogQuery', () => {
  it('maps products and page info from the GraphQL response', () => {
    mockUseQuery.mockImplementation(() =>
      createUseQueryReturn({
        result: ref({
          catalogProducts: {
            pageInfo: {
              currentPage: 1,
              perPage: 12,
              totalPages: 2,
              totalCount: 15,
              hasPreviousPage: false,
              hasNextPage: true,
            },
            items: [
              {
                id: 1,
                name: '100% Whey Concentrado 900g',
                packagingDisplay: 'Refill Package',
                weight: 900,
                lastPrice: '129.90',
                pricePerGram: '0.18',
                concentration: '80',
                totalProtein: '720',
                externalLink: 'https://example.com/whey',
                brand: { name: 'max-titanium' },
                category: { name: 'Whey Protein' },
                tags: [{ name: 'Whey' }],
              },
            ],
          },
        }),
        loading: ref(false),
        error: computed(() => null),
      }),
    )

    const { loading, pageInfo, products } = useCatalogQuery({
      page: 1,
      perPage: 12,
      search: null,
      sortBy: 'price_per_gram',
      sortDir: 'asc',
    })

    expect(loading.value).toBe(false)
    expect(pageInfo.value?.totalCount).toBe(15)
    expect(products.value).toHaveLength(1)
    expect(products.value[0]?.name).toBe('100% Whey Concentrado 900g')
  })
})
