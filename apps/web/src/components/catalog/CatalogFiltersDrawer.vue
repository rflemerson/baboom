<script setup lang="ts">
import BaseModal from '@/components/ui/BaseModal.vue'

defineProps<{
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
  apply: []
  clear: []
  'update:brand': [value: string]
  'update:concentrationMax': [value: number | null]
  'update:concentrationMin': [value: number | null]
  'update:modelValue': [value: boolean]
  'update:priceMax': [value: number | null]
  'update:priceMin': [value: number | null]
  'update:pricePerGramMax': [value: number | null]
  'update:pricePerGramMin': [value: number | null]
}>()

function parseNumber(value: string) {
  return value === '' ? null : Number(value)
}

function applyFilters() {
  emit('apply')
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
    panel-class="app-drawer flex h-full w-full max-w-md flex-col"
    @update:modelValue="emit('update:modelValue', $event)"
  >
    <aside class="flex h-full w-full flex-col">
      <header
        class="app-drawer__header flex items-center justify-between border-b px-6 py-5"
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

      <div class="flex-1 space-y-6 overflow-y-auto px-6 py-6">
        <section class="app-drawer__section rounded-2xl p-4">
          <label class="flex flex-col gap-2">
            <span class="app-section-title">Brand</span>
            <input
              :value="brand"
              type="text"
              placeholder="Filter by brand"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="emit('update:brand', ($event.target as HTMLInputElement).value)"
            />
          </label>
        </section>

        <section class="app-drawer__section space-y-3 rounded-2xl p-4">
          <p class="app-section-title">Price range</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="priceMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                emit('update:priceMin', parseNumber(($event.target as HTMLInputElement).value))
              "
            />
            <input
              :value="priceMax ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Max"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                emit('update:priceMax', parseNumber(($event.target as HTMLInputElement).value))
              "
            />
          </div>
        </section>

        <section class="app-drawer__section space-y-3 rounded-2xl p-4">
          <p class="app-section-title">Price per gram</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="pricePerGramMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                emit(
                  'update:pricePerGramMin',
                  parseNumber(($event.target as HTMLInputElement).value),
                )
              "
            />
            <input
              :value="pricePerGramMax ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Max"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                emit(
                  'update:pricePerGramMax',
                  parseNumber(($event.target as HTMLInputElement).value),
                )
              "
            />
          </div>
        </section>

        <section class="app-drawer__section space-y-3 rounded-2xl p-4">
          <p class="app-section-title">Concentration</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="concentrationMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                emit(
                  'update:concentrationMin',
                  parseNumber(($event.target as HTMLInputElement).value),
                )
              "
            />
            <input
              :value="concentrationMax ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Max"
              class="app-input rounded-xl px-4 py-3 text-sm"
              @input="
                emit(
                  'update:concentrationMax',
                  parseNumber(($event.target as HTMLInputElement).value),
                )
              "
            />
          </div>
        </section>
      </div>

      <footer class="app-drawer__footer flex gap-3 border-t px-6 py-5">
        <button
          type="button"
          class="app-button app-button--secondary app-button--control flex-1"
          @click="emit('clear')"
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
