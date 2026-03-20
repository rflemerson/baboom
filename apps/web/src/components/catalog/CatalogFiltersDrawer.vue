<script setup lang="ts">
import { ref, watch } from 'vue'

import BaseModal from '@/components/ui/BaseModal.vue'

const props = defineProps<{
  brand: string
  concentrationMax: number | null
  concentrationMin: number | null
  modelValue: boolean
  priceMax: number | null
  priceMin: number | null
  pricePerGramMax: number | null
  pricePerGramMin: number | null
}>()

const emit = defineEmits<{
  apply: [
    payload: {
      brand: string
      concentrationMax: number | null
      concentrationMin: number | null
      priceMax: number | null
      priceMin: number | null
      pricePerGramMax: number | null
      pricePerGramMin: number | null
    },
  ]
  clear: []
  'update:modelValue': [value: boolean]
}>()

const draftBrand = ref('')
const draftPriceMin = ref<number | null>(null)
const draftPriceMax = ref<number | null>(null)
const draftPricePerGramMin = ref<number | null>(null)
const draftPricePerGramMax = ref<number | null>(null)
const draftConcentrationMin = ref<number | null>(null)
const draftConcentrationMax = ref<number | null>(null)

function syncDrafts() {
  draftBrand.value = props.brand
  draftPriceMin.value = props.priceMin
  draftPriceMax.value = props.priceMax
  draftPricePerGramMin.value = props.pricePerGramMin
  draftPricePerGramMax.value = props.pricePerGramMax
  draftConcentrationMin.value = props.concentrationMin
  draftConcentrationMax.value = props.concentrationMax
}

watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) {
      syncDrafts()
    }
  },
  { immediate: true },
)

function parseNumber(value: string) {
  return value === '' ? null : Number(value)
}

function applyFilters() {
  emit('apply', {
    brand: draftBrand.value,
    concentrationMax: draftConcentrationMax.value,
    concentrationMin: draftConcentrationMin.value,
    priceMax: draftPriceMax.value,
    priceMin: draftPriceMin.value,
    pricePerGramMax: draftPricePerGramMax.value,
    pricePerGramMin: draftPricePerGramMin.value,
  })
  emit('update:modelValue', false)
}

function clearDrafts() {
  draftBrand.value = ''
  draftPriceMin.value = null
  draftPriceMax.value = null
  draftPricePerGramMin.value = null
  draftPricePerGramMax.value = null
  draftConcentrationMin.value = null
  draftConcentrationMax.value = null
  emit('clear')
  emit('update:modelValue', false)
}

const titleId = 'catalog-filters-drawer-title'
</script>

<template>
  <BaseModal
    :aria-labelledby="titleId"
    container-class="justify-end"
    initial-focus='input[type="text"]'
    :model-value="modelValue"
    panel-class="app-drawer flex h-full w-full flex-col sm:max-w-md"
    @update:modelValue="emit('update:modelValue', $event)"
  >
    <aside class="flex h-full w-full flex-col">
      <header
        class="app-drawer__header flex items-center justify-between border-b px-4 py-4 sm:px-6 sm:py-5"
      >
        <div>
          <p class="app-eyebrow">Catalog filters</p>
          <h2 :id="titleId" class="mt-2 text-xl font-semibold">Refine results</h2>
        </div>
        <button
          type="button"
          class="app-button app-button--ghost app-button--control"
          @click="emit('update:modelValue', false)"
        >
          Close
        </button>
      </header>

      <div class="flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:space-y-6 sm:px-6 sm:py-6">
        <section class="app-drawer__section rounded-2xl p-4">
          <label class="flex flex-col gap-2">
            <span class="app-section-title">Brand</span>
            <input
              :value="draftBrand"
              type="text"
              placeholder="Filter by brand"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="draftBrand = ($event.target as HTMLInputElement).value"
            />
          </label>
        </section>

        <section class="app-drawer__section space-y-3 rounded-2xl p-4">
          <p class="app-section-title">Price range</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="draftPriceMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="draftPriceMin = parseNumber(($event.target as HTMLInputElement).value)"
            />
            <input
              :value="draftPriceMax ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Max"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="draftPriceMax = parseNumber(($event.target as HTMLInputElement).value)"
            />
          </div>
        </section>

        <section class="app-drawer__section space-y-3 rounded-2xl p-4">
          <p class="app-section-title">Price per gram</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="draftPricePerGramMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="draftPricePerGramMin = parseNumber(($event.target as HTMLInputElement).value)"
            />
            <input
              :value="draftPricePerGramMax ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Max"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="draftPricePerGramMax = parseNumber(($event.target as HTMLInputElement).value)"
            />
          </div>
        </section>

        <section class="app-drawer__section space-y-3 rounded-2xl p-4">
          <p class="app-section-title">Concentration</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="draftConcentrationMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                draftConcentrationMin = parseNumber(($event.target as HTMLInputElement).value)
              "
            />
            <input
              :value="draftConcentrationMax ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Max"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                draftConcentrationMax = parseNumber(($event.target as HTMLInputElement).value)
              "
            />
          </div>
        </section>
      </div>

      <footer
        class="app-drawer__footer flex flex-col gap-3 border-t px-4 py-4 sm:flex-row sm:px-6 sm:py-5"
      >
        <button
          type="button"
          class="app-button app-button--secondary app-button--control flex-1"
          @click="clearDrafts"
        >
          Clear
        </button>
        <button
          type="button"
          class="app-button app-button--primary app-button--control flex-1"
          @click="applyFilters"
        >
          Apply filters
        </button>
      </footer>
    </aside>
  </BaseModal>
</template>
