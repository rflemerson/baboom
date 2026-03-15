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
    panel-class="flex h-full w-full max-w-md flex-col border-l"
    @update:modelValue="emit('update:modelValue', $event)"
  >
    <aside class="flex h-full w-full flex-col">
      <header
        class="flex items-center justify-between px-6 py-5"
        style="border-bottom: 1px solid var(--app-border)"
      >
        <div>
          <p class="app-eyebrow">Catalog filters</p>
          <h2 :id="titleId" class="mt-2 text-xl font-semibold">Refine results</h2>
        </div>
        <button
          type="button"
          class="app-button app-button--ghost rounded-xl px-3 py-2 text-sm"
          @click="emit('update:modelValue', false)"
        >
          Close
        </button>
      </header>

      <div class="flex-1 space-y-6 overflow-y-auto px-6 py-6">
        <label class="flex flex-col gap-2">
          <span class="app-copy-soft text-xs tracking-[0.24em] uppercase">Brand</span>
          <input
            :value="brand"
            type="text"
            placeholder="Filter by brand"
            class="app-input rounded-xl px-4 py-3 text-sm"
            @input="emit('update:brand', ($event.target as HTMLInputElement).value)"
          />
        </label>

        <div class="space-y-3">
          <p class="app-copy-soft text-xs tracking-[0.24em] uppercase">Price range</p>
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
        </div>

        <div class="space-y-3">
          <p class="app-copy-soft text-xs tracking-[0.24em] uppercase">Price per gram</p>
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
        </div>

        <div class="space-y-3">
          <p class="app-copy-soft text-xs tracking-[0.24em] uppercase">Concentration</p>
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
        </div>
      </div>

      <footer class="flex gap-3 px-6 py-5" style="border-top: 1px solid var(--app-border)">
        <button
          type="button"
          class="app-button app-button--secondary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="emit('clear')"
        >
          Clear
        </button>
        <button
          type="button"
          class="app-button app-button--primary flex-1 rounded-xl px-4 py-3 text-sm"
          @click="applyFilters"
        >
          Apply filters
        </button>
      </footer>
    </aside>
  </BaseModal>
</template>
