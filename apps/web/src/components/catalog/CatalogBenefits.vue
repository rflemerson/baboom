<script setup lang="ts">
import { computed, type Component } from 'vue'
import { BadgePercent, Coins, Info, Star, Ticket, Wallet } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import type { CatalogProduct } from '@/types/catalog'
import { formatMoney } from '@/utils/number'
import { paymentMethodLabel } from '@/utils/payment'

// What the price asks of the buyer (blue), then what comes back later.
const props = defineProps<{ product: CatalogProduct }>()
const { t } = useI18n()

interface Badge {
  key: string
  icon: Component
  label: string
  title: string
  tone: 'pay' | 'cashback' | 'points' | 'store'
}

function payBadges(product: CatalogProduct): Badge[] {
  const badges: Badge[] = (product.couponCodes ?? []).map((code) => ({
    key: `coupon:${code}`,
    icon: Ticket,
    label: code,
    title: t('catalog.notes.coupon', { code }),
    tone: 'pay',
  }))
  const method = paymentMethodLabel(product.paymentMethod)
  if (method) {
    badges.push({
      key: 'method',
      icon: Wallet,
      label: method,
      title: t('catalog.notes.payment', { method }),
      tone: 'pay',
    })
  }
  if (product.routeInstructions) {
    badges.push({
      key: 'route',
      icon: Info,
      label: t('catalog.notes.route'),
      title: product.routeInstructions,
      tone: 'pay',
    })
  }
  return badges
}

function receiveBadges(product: CatalogProduct): Badge[] {
  const badges: Badge[] = []
  if (product.cashback) {
    const amount = formatMoney(product.cashback.amount, product.cashback.currency)
    badges.push({
      key: 'cashback',
      icon: Coins,
      label: amount,
      title: t('catalog.notes.cashback', { amount }),
      tone: 'cashback',
    })
  }
  if (product.points) {
    badges.push({
      key: 'points',
      icon: Star,
      label: t('catalog.notes.pointsShort', { count: product.points }),
      title: t('catalog.notes.points', { count: product.points }, product.points),
      tone: 'points',
    })
  }
  return badges
}

const STORE_ICONS: Record<string, Component> = {
  coupon: Ticket,
  cashback: Coins,
  points: Star,
  promotion: BadgePercent,
}

// The store has it, but it is not in the price: shown last, apart.
function storeBadges(product: CatalogProduct): Badge[] {
  return (product.storePromotions ?? []).map((promotion, index) => ({
    key: `store:${index}`,
    icon: STORE_ICONS[promotion.kind] ?? BadgePercent,
    label: t(`catalog.notes.store.${promotion.kind}`),
    title: promotion.title || t(`catalog.notes.store.${promotion.kind}`),
    tone: 'store',
  }))
}

const badges = computed(() => [
  ...payBadges(props.product),
  ...receiveBadges(props.product),
  ...storeBadges(props.product),
])
</script>

<template>
  <ul v-if="badges.length" class="app-benefits" data-testid="benefits">
    <li
      v-for="badge in badges"
      :key="badge.key"
      class="app-benefits__badge"
      :class="`app-benefits__badge--${badge.tone}`"
      :title="badge.title"
    >
      <component :is="badge.icon" class="h-3 w-3 shrink-0" aria-hidden="true" />
      <span aria-hidden="true">{{ badge.label }}</span>
      <span class="sr-only">{{ badge.title }}</span>
    </li>
  </ul>
  <span v-else class="app-copy-soft">—</span>
</template>

<style scoped lang="scss">
.app-benefits {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
}

.app-benefits__badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 500;
  white-space: nowrap;
}

.app-benefits__badge--pay {
  background: var(--app-info-soft);
  color: var(--app-info);
}

.app-benefits__badge--cashback {
  background: var(--app-success-soft);
  color: var(--app-success);
}

.app-benefits__badge--store {
  border: 1px dashed var(--app-border-strong);
  color: var(--app-text-soft);
}

.app-benefits__badge--points {
  background: var(--app-points-soft);
  color: var(--app-points);
}
</style>
