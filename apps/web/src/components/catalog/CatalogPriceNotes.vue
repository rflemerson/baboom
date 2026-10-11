<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { CatalogProduct } from '@/types/catalog'
import { formatMoney } from '@/utils/number'
import { paymentMethodLabel } from '@/utils/payment'

const { t } = useI18n()

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
  <ul v-if="hasNotes" class="app-copy-muted mt-1 grid gap-1 text-xs" data-testid="price-notes">
    <li v-for="code in product.couponCodes ?? []" :key="code">
      {{ t('catalog.notes.coupon', { code }) }}
    </li>
    <li v-if="method">{{ t('catalog.notes.payment', { method }) }}</li>
    <li v-if="cashback">{{ t('catalog.notes.cashback', { amount: cashback }) }}</li>
    <li v-if="product.routeInstructions">{{ product.routeInstructions }}</li>
  </ul>
</template>
