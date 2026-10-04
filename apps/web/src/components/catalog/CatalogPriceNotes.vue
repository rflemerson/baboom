<script setup lang="ts">
import { computed } from 'vue'

import type { CatalogProduct } from '@/types/catalog'
import { formatMoney } from '@/utils/number'
import { paymentMethodLabel } from '@/utils/payment'

const props = defineProps<{
  product: CatalogProduct
}>()

const method = computed(() => paymentMethodLabel(props.product.paymentMethod))
const cashback = computed(() =>
  props.product.cashback
    ? formatMoney(props.product.cashback.amount, props.product.cashback.currency)
    : null,
)
const hasNotes = computed(
  () =>
    Boolean(props.product.couponCodes?.length) ||
    method.value !== null ||
    cashback.value !== null ||
    Boolean(props.product.routeInstructions),
)
</script>

<template>
  <ul v-if="hasNotes" class="app-copy-muted mt-3 grid gap-1 text-xs" data-testid="price-notes">
    <li v-for="code in product.couponCodes ?? []" :key="code">Use o cupom {{ code }}</li>
    <li v-if="method">Pagando com {{ method }}</li>
    <li v-if="cashback">+ {{ cashback }} de cashback</li>
    <li v-if="product.routeInstructions">{{ product.routeInstructions }}</li>
  </ul>
</template>
