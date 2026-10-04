import { describe, expect, it, vi } from 'vitest'

import { useCatalogQuery } from './useCatalogQuery'

describe('useCatalogQuery', () => {
  it('maps products and page info from the REST response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          active: { slug: 'protein', name: 'Protein' },
          massUnit: 'g',
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
              netMass: '900',
              price: '129.90',
              pricePerActive: '0.18',
              concentration: '80',
              totalActive: '720',
              externalLink: 'https://example.com/whey',
              brand: { name: 'max-titanium' },
              category: { name: 'Whey Protein' },
              tags: [{ name: 'Whey' }],
            },
          ],
        }),
      }),
    )

    const { active, loading, massUnit, pageInfo, products } = useCatalogQuery({
      filters: {
        page: 1,
        perPage: 12,
        search: null,
        sortBy: 'price_per_active',
        sortDir: 'asc',
      },
    })

    await vi.waitFor(() => {
      expect(loading.value).toBe(false)
      expect(pageInfo.value?.totalCount).toBe(15)
      expect(products.value).toHaveLength(1)
    })
    expect(products.value[0]?.name).toBe('100% Whey Concentrado 900g')
    expect(active.value?.slug).toBe('protein')
    expect(massUnit.value).toBe('g')
  })

  it('sends the chosen pricing scenario', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        active: null,
        massUnit: 'g',
        scenario: { key: 'best', version: 1 },
        pageInfo: {
          currentPage: 1,
          perPage: 12,
          totalPages: 0,
          totalCount: 0,
          hasPreviousPage: false,
          hasNextPage: false,
        },
        items: [],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { loading } = useCatalogQuery({ filters: { page: 1, scenario: 'best' } })

    await vi.waitFor(() => expect(loading.value).toBe(false))
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('scenario=best')
  })

  it('stops asking for a scenario once the market answers with the current price', async () => {
    const payload = (key: string) => ({
      ok: true,
      json: vi.fn().mockResolvedValue({
        active: null,
        massUnit: 'g',
        scenario: { key, version: null },
        pageInfo: {
          currentPage: 1,
          perPage: 12,
          totalPages: 0,
          totalCount: 0,
          hasPreviousPage: false,
          hasNextPage: false,
        },
        items: [],
      }),
    })
    const fetchMock = vi.fn().mockResolvedValue(payload('current'))
    vi.stubGlobal('fetch', fetchMock)

    const { loading, refetch, scenarioAvailable } = useCatalogQuery({
      filters: { page: 1, scenario: 'best' },
    })

    await vi.waitFor(() => expect(loading.value).toBe(false))
    expect(scenarioAvailable.value).toBe(false)
    await refetch()
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('scenario=best')
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain('scenario')

    fetchMock.mockResolvedValue(payload('normal'))
    await refetch()
    expect(scenarioAvailable.value).toBe(true)
  })
})
