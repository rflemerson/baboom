import { ref } from 'vue'

import type { CatalogFilterOptions } from '@/types/catalog'

const filtersUrl = '/api/catalog/filters/'

// One request per page load, shared by the toolbar and the filters menu.
const options = ref<CatalogFilterOptions>({ actives: [], brands: [], flavors: [], categories: [] })
let loading: Promise<void> | null = null

/** Load the actives, brands, flavors and categories the catalog offers. */
export function useCatalogFilterOptions() {
  loading ??= fetch(filtersUrl, { headers: { Accept: 'application/json' } })
    .then((response) => (response.ok ? response.json() : null))
    .then((payload: CatalogFilterOptions | null) => {
      if (payload) options.value = payload
    })
    .catch(() => {
      loading = null
    })
  return { options }
}
