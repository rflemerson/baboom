<script setup lang="ts">
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
</script>

<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm"
    @click.self="emit('update:modelValue', false)"
  >
    <aside
      class="flex h-full w-full max-w-md flex-col border-l border-white/10 bg-stone-950 text-white"
    >
      <header class="flex items-center justify-between border-b border-white/10 px-6 py-5">
        <div>
          <p class="text-xs tracking-[0.24em] text-orange-300 uppercase">Catalog filters</p>
          <h2 class="mt-2 text-xl font-semibold">Refine results</h2>
        </div>
        <button
          type="button"
          class="rounded-xl border border-white/10 px-3 py-2 text-sm transition hover:border-orange-400"
          @click="emit('update:modelValue', false)"
        >
          Close
        </button>
      </header>

      <div class="flex-1 space-y-6 overflow-y-auto px-6 py-6">
        <label class="flex flex-col gap-2">
          <span class="text-xs tracking-[0.24em] text-stone-400 uppercase">Brand</span>
          <input
            :value="brand"
            type="text"
            placeholder="Filter by brand"
            class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
            @input="emit('update:brand', ($event.target as HTMLInputElement).value)"
          />
        </label>

        <div class="space-y-3">
          <p class="text-xs tracking-[0.24em] text-stone-400 uppercase">Price range</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="priceMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
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
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
              @input="
                emit('update:priceMax', parseNumber(($event.target as HTMLInputElement).value))
              "
            />
          </div>
        </div>

        <div class="space-y-3">
          <p class="text-xs tracking-[0.24em] text-stone-400 uppercase">Price per gram</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="pricePerGramMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
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
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
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
          <p class="text-xs tracking-[0.24em] text-stone-400 uppercase">Concentration</p>
          <div class="grid grid-cols-2 gap-3">
            <input
              :value="concentrationMin ?? ''"
              type="number"
              min="0"
              step="0.01"
              placeholder="Min"
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
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
              class="rounded-xl border border-white/10 bg-stone-900 px-4 py-3 text-sm text-white transition outline-none focus:border-orange-400"
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

      <footer class="flex gap-3 border-t border-white/10 px-6 py-5">
        <button
          type="button"
          class="flex-1 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-stone-200 transition hover:border-white/30"
          @click="emit('clear')"
        >
          Clear
        </button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-orange-500 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-orange-400"
          @click="applyFilters"
        >
          Apply filters
        </button>
      </footer>
    </aside>
  </div>
</template>
