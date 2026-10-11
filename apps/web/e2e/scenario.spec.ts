import { expect, test, type Page, type Route } from '@playwright/test'

const PAGE_INFO = {
  currentPage: 1,
  perPage: 12,
  totalPages: 1,
  totalCount: 1,
  hasPreviousPage: false,
  hasNextPage: false,
}

function product(price: string, paymentMethod: string | null, linkSelectsSeller: boolean) {
  return {
    id: 1,
    name: 'Soy Protein Natural 1 kg',
    packagingDisplay: 'Refill Package',
    netMass: '1000',
    price,
    currency: 'BRL',
    paymentMethod,
    linkSelectsSeller,
    pricePerActive: '0.10',
    concentration: '86.7',
    totalActive: '866.67',
    externalLink: 'https://example.com/soy',
    brand: { name: 'Growth Supplements' },
    category: { name: 'Soja' },
    tags: [],
  }
}

const SCENARIO = 'Preço que o catálogo compara'

function scenarioMenu(page: Page) {
  return page.locator('details').filter({ has: page.locator(`summary[aria-label="${SCENARIO}"]`) })
}

async function chooseScenario(page: Page, option: string) {
  await page.locator(`summary[aria-label="${SCENARIO}"]`).click()
  await scenarioMenu(page).getByRole('button', { name: option, exact: true }).click()
}

test.use({ viewport: { width: 1280, height: 900 } })

test('the best price leads; the catalog price is one choice away', async ({ page }) => {
  const scenarios: Array<string | null> = []
  await page.route('**/api/catalog/products/**', async (route: Route) => {
    const url = new URL(route.request().url())
    const scenario = url.searchParams.get('scenario')
    scenarios.push(scenario)
    const best = scenario === 'best'
    await route.fulfill({
      json: {
        active: { slug: 'protein', name: 'Protein' },
        massUnit: 'g',
        market: { country: 'BR', currency: 'BRL' },
        scenario: best ? { key: 'best', version: 1 } : { key: 'normal', version: 1 },
        pageInfo: PAGE_INFO,
        items: [best ? product('89.90', 'pix', false) : product('99.88', null, true)],
      },
    })
  })

  await page.goto('/')
  await expect(page.getByRole('table').getByText('R$ 89,90')).toBeVisible()
  await expect(page.getByRole('table').getByText('Pagando com Pix')).toBeVisible()
  await expect(
    page.getByRole('table').getByText('A página da loja pode abrir a oferta de outro vendedor.'),
  ).toBeVisible()
  expect(scenarios[0]).toBe('best')

  await chooseScenario(page, 'Preço de catálogo')

  await expect(page.getByRole('table').getByText('R$ 99,88')).toBeVisible()
  await expect(
    page.getByRole('columnheader', { name: 'Ordenar por Preço', exact: true }),
  ).toBeVisible()
  expect(scenarios.at(-1)).toBe('normal')
})

test('the benefits column lists the coupon, the payment method and the cashback', async ({
  page,
}) => {
  await page.route('**/api/catalog/products/**', async (route: Route) => {
    await route.fulfill({
      json: {
        active: { slug: 'protein', name: 'Protein' },
        massUnit: 'g',
        market: { country: 'BR', currency: 'BRL' },
        scenario: { key: 'best', version: 1 },
        pageInfo: PAGE_INFO,
        items: [
          {
            ...product('79.90', 'pix', true),
            listPrice: '99.90',
            couponCodes: ['SYNTH20'],
            cashback: { amount: '8.00', currency: 'BRL' },
            routeInstructions: null,
            storePromotions: [{ title: 'Cupons de influenciadores', kind: 'coupon' }],
          },
        ],
      },
    })
  })

  await page.goto('/')

  const table = page.getByRole('table')
  await expect(table.getByRole('columnheader', { name: 'Benefícios' })).toBeVisible()
  await expect(table.getByTestId('benefits')).toContainText('SYNTH20')
  await expect(table.getByTestId('benefits')).toContainText('Pix')
  await expect(table.getByTestId('benefits')).toContainText('R$ 8,00')
  await expect(table.getByTestId('benefits')).toContainText('Cupom na loja')
  await expect(table.getByTitle('Cupons de influenciadores')).toBeVisible()
  await expect(table.getByText('R$ 79,90')).toBeVisible()
  await expect(table.locator('s')).toHaveText('R$ 99,90')
})
