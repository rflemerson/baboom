import { ref } from 'vue'

import type { CatalogFilterOptions } from '@/types/catalog'

const filtersUrl = '/api/catalog/filters/'

/** Load the brands, flavors and categories the catalog can be filtered by. */
export function useCatalogFilterOptions() {
  const options = ref<CatalogFilterOptions>({ brands: [], flavors: [], categories: [] })
  fetch(filtersUrl, { headers: { Accept: 'application/json' } })
    .then((response) => (response.ok ? response.json() : null))
    .then((payload: CatalogFilterOptions | null) => {
      if (payload) options.value = payload
    })
    .catch(() => undefined)
  return { options }
}
