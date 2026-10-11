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

test('choosing the best price ranks by the price paid now', async ({ page }) => {
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
  await expect(page.getByRole('table').getByText('R$ 99,88')).toBeVisible()
  await expect(
    page.getByRole('columnheader', { name: 'Ordenar por Preço', exact: true }),
  ).toBeVisible()

  await chooseScenario(page, 'Melhor preço')

  await expect(page.getByRole('table').getByText('R$ 89,90')).toBeVisible()
  await expect(page.getByRole('table').getByText('Pagando com Pix')).toBeVisible()
  await expect(
    page.getByRole('table').getByText('A página da loja pode abrir a oferta de outro vendedor.'),
  ).toBeVisible()
  expect(scenarios).toContain('best')
})

test('the best price with a coupon says which coupon to use', async ({ page }) => {
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
            couponCodes: ['SYNTH20'],
            cashback: { amount: '8.00', currency: 'BRL' },
            routeInstructions: null,
          },
        ],
      },
    })
  })

  await page.goto('/')
  await chooseScenario(page, 'Melhor preço')

  await expect(page.getByRole('table').getByText('Use o cupom SYNTH20')).toBeVisible()
  await expect(page.getByRole('table').getByText('Pagando com Pix')).toBeVisible()
  await expect(page.getByRole('table').getByText('+ R$ 8,00 de cashback')).toBeVisible()
  await expect(page.getByRole('table').getByText('R$ 79,90')).toBeVisible()
})

test('a market without projections hides the best price and never asks for it', async ({
  page,
}) => {
  const scenarios: Array<string | null> = []
  await page.route('**/api/catalog/products/**', async (route: Route) => {
    scenarios.push(new URL(route.request().url()).searchParams.get('scenario'))
    await route.fulfill({
      json: {
        active: { slug: 'protein', name: 'Protein' },
        massUnit: 'g',
        market: { country: 'BR', currency: 'BRL' },
        scenario: { key: 'current', version: null },
        pageInfo: PAGE_INFO,
        items: [product('99.88', null, true)],
      },
    })
  })

  await page.goto('/')
  await expect(page.getByRole('table').getByText('R$ 99,88')).toBeVisible()

  await page.locator(`summary[aria-label="${SCENARIO}"]`).click()
  await expect(scenarioMenu(page).getByRole('button')).toHaveText(['Preço normal'])
  await page.getByRole('button', { name: 'Ordenar por Preço', exact: true }).click()
  await expect(page.getByRole('table').getByText('R$ 99,88')).toBeVisible()
  expect(scenarios.every((scenario) => scenario === null)).toBe(true)
})
