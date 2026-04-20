import { describe, expect, it, vi } from 'vitest'

import { useCatalogQuery } from './useCatalogQuery'

describe('useCatalogQuery', () => {
  it('maps products and page info from the REST response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
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
              pricePerProteinGram: '0.18',
              concentration: '80',
              totalProtein: '720',
              externalLink: 'https://example.com/whey',
              brand: { name: 'max-titanium' },
              category: { name: 'Whey Protein' },
              tags: [{ name: 'Whey' }],
            },
          ],
        }),
      }),
    )

    const { loading, pageInfo, products } = useCatalogQuery({
      filters: {
        page: 1,
        perPage: 12,
        search: null,
        sortBy: 'price_per_protein_gram',
        sortDir: 'asc',
      },
    })

    await vi.waitFor(() => {
      expect(loading.value).toBe(false)
      expect(pageInfo.value?.totalCount).toBe(15)
      expect(products.value).toHaveLength(1)
    })
    expect(products.value[0]?.name).toBe('100% Whey Concentrado 900g')
  })
})
