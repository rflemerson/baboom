import { computed, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/composables/useCatalogQuery', () => ({
  useCatalogQuery: vi.fn(),
}))

import { useCatalogQuery } from '@/composables/useCatalogQuery'
import CatalogView from './CatalogView.vue'

describe('CatalogView', () => {
  it('renders the catalog heading and the fetched item', () => {
    vi.mocked(useCatalogQuery).mockReturnValue({
      error: computed(() => null),
      loading: computed(() => false),
      pageInfo: computed(() => ({
        currentPage: 1,
        perPage: 12,
        totalPages: 1,
        totalCount: 1,
        hasPreviousPage: false,
        hasNextPage: false,
      })),
      products: computed(() => [
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
      ]),
      result: ref(undefined),
    })

    const wrapper = mount(CatalogView)

    expect(wrapper.text()).toContain('Public catalog')
    expect(wrapper.text()).toContain('100% Whey Concentrado 900g')
  })
})
