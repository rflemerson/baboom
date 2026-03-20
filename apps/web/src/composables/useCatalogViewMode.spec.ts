import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { useCatalogViewMode } from './useCatalogViewMode'

describe('useCatalogViewMode', () => {
  it('persists the selected view mode to localStorage', async () => {
    const { setViewMode, viewMode } = useCatalogViewMode()

    setViewMode('list')
    await nextTick()

    expect(viewMode.value).toBe('list')
    expect(globalThis.localStorage.getItem('baboom.catalog.viewMode')).toBe('list')
  })
})
