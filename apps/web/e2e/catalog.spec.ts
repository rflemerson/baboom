import { expect, test, type Page, type Route } from '@playwright/test'

type Product = {
  id: number
  name: string
  packagingDisplay: string
  netMass: string
  price: string
  pricePerActive: string
  concentration: string
  totalActive: string
  externalLink: string
  brand: { name: string }
  category: { name: string }
  tags: Array<{ name: string }>
}

const PRODUCTS: Product[] = [
  {
    id: 1,
    name: 'Whey Prime 900g',
    packagingDisplay: 'Refill Package',
    netMass: '900',
    price: '129.90',
    pricePerActive: '0.14',
    concentration: '80',
    totalActive: '720',
    externalLink: 'https://example.com/whey-prime',
    brand: { name: 'dux' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Whey' }, { name: 'High Protein' }],
  },
  {
    id: 2,
    name: 'Whey Core 1kg',
    packagingDisplay: 'Container Package',
    netMass: '1000',
    price: '149.90',
    pricePerActive: '0.16',
    concentration: '78',
    totalActive: '780',
    externalLink: 'https://example.com/whey-core',
    brand: { name: 'black skull' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Whey' }],
  },
  {
    id: 3,
    name: 'Isolate Gold 1kg',
    packagingDisplay: 'Container Package',
    netMass: '1000',
    price: '219.90',
    pricePerActive: '0.22',
    concentration: '86',
    totalActive: '860',
    externalLink: 'https://example.com/isolate-gold',
    brand: { name: 'integralmedica' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Isolate' }],
  },
  {
    id: 4,
    name: 'Creatine Pure 300g',
    packagingDisplay: 'Container Package',
    netMass: '300',
    price: '89.90',
    pricePerActive: '0.30',
    concentration: '0',
    totalActive: '0',
    externalLink: 'https://example.com/creatine-pure',
    brand: { name: 'dux' },
    category: { name: 'Creatine' },
    tags: [{ name: 'Creatine' }],
  },
  {
    id: 5,
    name: 'Night Casein 900g',
    packagingDisplay: 'Refill Package',
    netMass: '900',
    price: '159.90',
    pricePerActive: '0.18',
    concentration: '74',
    totalActive: '666',
    externalLink: 'https://example.com/night-casein',
    brand: { name: 'black skull' },
    category: { name: 'Casein' },
    tags: [{ name: 'Slow Release' }],
  },
  {
    id: 6,
    name: 'Protein Blend 2kg',
    packagingDisplay: 'Container Package',
    netMass: '2000',
    price: '239.90',
    pricePerActive: '0.12',
    concentration: '70',
    totalActive: '1400',
    externalLink: 'https://example.com/protein-blend',
    brand: { name: 'max titanium' },
    category: { name: 'Protein Blend' },
    tags: [{ name: 'Blend' }],
  },
  {
    id: 7,
    name: 'Iso Hydro 900g',
    packagingDisplay: 'Refill Package',
    netMass: '900',
    price: '249.90',
    pricePerActive: '0.28',
    concentration: '90',
    totalActive: '810',
    externalLink: 'https://example.com/iso-hydro',
    brand: { name: 'dux' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Hydrolyzed' }],
  },
  {
    id: 8,
    name: 'Whey Budget 900g',
    packagingDisplay: 'Refill Package',
    netMass: '900',
    price: '99.90',
    pricePerActive: '0.11',
    concentration: '68',
    totalActive: '612',
    externalLink: 'https://example.com/whey-budget',
    brand: { name: 'max titanium' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Budget' }],
  },
  {
    id: 9,
    name: 'Pre Rush 300g',
    packagingDisplay: 'Container Package',
    netMass: '300',
    price: '109.90',
    pricePerActive: '0.37',
    concentration: '0',
    totalActive: '0',
    externalLink: 'https://example.com/pre-rush',
    brand: { name: 'black skull' },
    category: { name: 'Pre Workout' },
    tags: [{ name: 'Energy' }],
  },
  {
    id: 10,
    name: 'Mass Gainer 3kg',
    packagingDisplay: 'Bag Package',
    netMass: '3000',
    price: '199.90',
    pricePerActive: '0.07',
    concentration: '24',
    totalActive: '720',
    externalLink: 'https://example.com/mass-gainer',
    brand: { name: 'integralmedica' },
    category: { name: 'Mass Gainer' },
    tags: [{ name: 'Calories' }],
  },
  {
    id: 11,
    name: 'Egg Protein 1kg',
    packagingDisplay: 'Container Package',
    netMass: '1000',
    price: '179.90',
    pricePerActive: '0.19',
    concentration: '72',
    totalActive: '720',
    externalLink: 'https://example.com/egg-protein',
    brand: { name: 'max titanium' },
    category: { name: 'Egg Protein' },
    tags: [{ name: 'Albumin' }],
  },
  {
    id: 12,
    name: 'Peanut Butter 1kg',
    packagingDisplay: 'Container Package',
    netMass: '1000',
    price: '39.90',
    pricePerActive: '0.04',
    concentration: '0',
    totalActive: '250',
    externalLink: 'https://example.com/peanut-butter',
    brand: { name: 'growth' },
    category: { name: 'Snacks' },
    tags: [{ name: 'Peanut' }],
  },
  {
    id: 13,
    name: 'Bar Box 12x',
    packagingDisplay: 'Box Package',
    netMass: '600',
    price: '69.90',
    pricePerActive: '0.12',
    concentration: '20',
    totalActive: '120',
    externalLink: 'https://example.com/bar-box',
    brand: { name: 'bold' },
    category: { name: 'Protein Bars' },
    tags: [{ name: 'Snack' }],
  },
  {
    id: 14,
    name: 'Whey Gone 900g',
    packagingDisplay: 'Refill Package',
    netMass: '900',
    price: '99.90',
    pricePerActive: '0.13',
    concentration: '80',
    totalActive: '720',
    externalLink: 'https://example.com/whey-gone',
    brand: { name: 'dux' },
    category: { name: 'Whey Protein' },
    tags: [],
  },
]

const FLAVORS = ['Chocolate', 'Baunilha', 'Morango']

function flavorOf(product: Product) {
  return FLAVORS[product.id % FLAVORS.length] ?? 'Chocolate'
}

// One product is sold out: the default "in stock" filter hides it.
const SOLD_OUT = 'Whey Gone 900g'

function stockOf(product: Product) {
  return product.name === SOLD_OUT ? 'out_of_stock' : 'in_stock'
}

function readNumber(product: Product, key: string) {
  const values: Record<string, string> = {
    price: product.price,
    total_active: product.totalActive,
    concentration: product.concentration,
  }
  return Number(values[key] ?? product.pricePerActive)
}

async function fulfillCatalog(route: Route) {
  const url = new URL(route.request().url())
  const params = url.searchParams
  const chosen = (name: string) => params.getAll(name)
  const [brands, flavors, categories] = [chosen('brand'), chosen('flavor'), chosen('category')]
  const stock = chosen('stock')
  const sortBy = params.get('sort_by') ?? 'price_per_active'
  const direction = params.get('sort_dir') === 'desc' ? -1 : 1
  const perPage = Number(params.get('per_page') ?? 12)
  const filtered = PRODUCTS.filter(
    (product) =>
      (!brands.length || brands.includes(product.brand.name)) &&
      (!flavors.length || flavors.includes(flavorOf(product))) &&
      (!categories.length || categories.includes(product.category.name)) &&
      (!stock.length || stock.includes(stockOf(product))),
  ).sort((left, right) => (readNumber(left, sortBy) - readNumber(right, sortBy)) * direction)
  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage))
  const currentPage = Math.min(Number(params.get('page') ?? 1), totalPages)
  const start = (currentPage - 1) * perPage
  await route.fulfill({
    json: {
      active: { slug: 'protein', name: 'Proteína' },
      massUnit: 'g',
      market: { country: 'BR', currency: 'BRL' },
      scenario: { key: 'normal', version: 1 },
      pageInfo: {
        currentPage,
        perPage,
        totalPages,
        totalCount: filtered.length,
        hasPreviousPage: currentPage > 1,
        hasNextPage: currentPage < totalPages,
      },
      items: filtered.slice(start, start + perPage).map((product) => ({
        ...product,
        currency: 'BRL',
        nutritionProfile: {
          id: product.id,
          nutritionFactsId: product.id,
          flavors: [flavorOf(product)],
        },
        couponCodes: [],
        cashback: null,
        routeInstructions: null,
      })),
    },
  })
}

async function fulfillFilters(route: Route) {
  const unique = (values: string[]) =>
    [...new Set(values)].sort().map((name) => ({ name, label: name }))
  await route.fulfill({
    json: {
      brands: unique(PRODUCTS.map((product) => product.brand.name)),
      flavors: unique(FLAVORS),
      categories: unique(PRODUCTS.map((product) => product.category.name)),
    },
  })
}

async function fulfillAlerts(route: Route) {
  const body = route.request().postDataJSON() as { email?: string }
  const email = typeof body.email === 'string' ? body.email : ''
  const alreadySubscribed = email.toLowerCase() === 'already@subscribed.com'
  await route.fulfill({
    json: {
      success: !alreadySubscribed,
      alreadySubscribed,
      email,
      errors: alreadySubscribed ? [] : null,
    },
  })
}

async function setupApiMock(page: Page) {
  await page.route('**/api/catalog/products/**', fulfillCatalog)
  await page.route('**/api/catalog/filters/', fulfillFilters)
  await page.route('**/api/alerts/subscribe/', fulfillAlerts)
}

function catalogRequest(page: Page, matches: (params: URLSearchParams) => boolean) {
  return page.waitForRequest((request) => {
    const url = new URL(request.url())
    return url.pathname === '/api/catalog/products/' && matches(url.searchParams)
  })
}

async function choose(page: Page, label: string, option: string) {
  await page.locator(`summary[aria-label="${label}"]`).click()
  await page.getByRole('button', { name: option, exact: true }).click()
}

test.beforeEach(async ({ page }) => {
  await setupApiMock(page)
})

test.describe('desktop', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('loads the catalog and paginates through results', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByText('13 produtos')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Whey Budget 900g' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Ir para a próxima página' })).toBeVisible()

    await choose(page, 'Resultados por página', '24 / página')
    await expect(page.getByRole('button', { name: 'Ir para a próxima página' })).toHaveCount(0)

    await choose(page, 'Resultados por página', '12 / página')
    await page.getByRole('button', { name: 'Ir para a próxima página' }).click()
    await expect(page.getByText('Página 2 de 2')).toBeVisible()
  })

  test('filters by brand, flavor and category, and clears them', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('13 produtos')).toBeVisible()

    await page.locator('summary', { hasText: 'Filtros' }).click()
    await choose(page, 'Filtrar por', 'Marca')
    const byBrand = catalogRequest(page, (params) => params.getAll('brand').includes('dux'))
    await page.getByRole('checkbox', { name: 'dux', exact: true }).check()
    await byBrand
    await expect(page.getByRole('heading', { name: 'Whey Prime 900g' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Isolate Gold 1kg' })).toHaveCount(0)

    await choose(page, 'Filtrar por', 'Categoria')
    const byCategory = catalogRequest(
      page,
      (params) => params.get('category') === 'Creatine' && params.get('brand') === 'dux',
    )
    await page.getByRole('checkbox', { name: 'Creatine', exact: true }).check()
    await byCategory
    await expect(page.getByRole('heading', { name: 'Creatine Pure 300g' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Whey Prime 900g' })).toHaveCount(0)

    await page.getByRole('button', { name: 'Limpar filtros', exact: true }).click()
    await expect(page.getByText('13 produtos')).toBeVisible()
  })

  test('lists only products in stock until sold-out ones are asked for', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('13 produtos')).toBeVisible()
    await expect(page.getByRole('heading', { name: SOLD_OUT })).toHaveCount(0)

    await page.locator('summary', { hasText: 'Filtros' }).click()
    const withSoldOut = catalogRequest(page, (params) =>
      params.getAll('stock').includes('out_of_stock'),
    )
    await page.getByRole('checkbox', { name: 'Sem estoque', exact: true }).check()
    await withSoldOut
    await expect(page.getByText('14 produtos')).toBeVisible()
  })

  test('shows an empty state when no product matches', async ({ page }) => {
    await page.goto('/')
    await page.locator('summary', { hasText: 'Filtros' }).click()
    await choose(page, 'Filtrar por', 'Marca')
    await page.getByRole('checkbox', { name: 'bold', exact: true }).check()
    // "bold" sells only Baunilha: with Chocolate too, nothing is left.
    await choose(page, 'Filtrar por', 'Sabor')
    await page.getByRole('checkbox', { name: 'Chocolate', exact: true }).check()
    await page.keyboard.press('Escape')

    const emptyState = page
      .locator('section')
      .filter({ hasText: 'Tente mudar ou limpar os filtros.' })
    await expect(emptyState).toBeVisible()
    await emptyState.getByRole('button', { name: 'Limpar filtros' }).click()
    await expect(page.getByText('13 produtos')).toBeVisible()
  })

  test('sorts through the API from the column header', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('table')).toBeVisible()
    const sortRequest = catalogRequest(
      page,
      (params) => params.get('sort_by') === 'price' && params.get('sort_dir') === 'asc',
    )
    await page.getByRole('button', { name: 'Ordenar por Preço', exact: true }).click()
    await sortRequest
    await expect(
      page.getByRole('columnheader', { name: 'Ordenar por Preço', exact: true }),
    ).toHaveAttribute('aria-sort', 'ascending')
  })

  test('shows and hides columns without fetching another page', async ({ page }, testInfo) => {
    const requests: string[] = []
    page.on('request', (request) => {
      if (new URL(request.url()).pathname === '/api/catalog/products/') requests.push(request.url())
    })
    await page.goto('/')
    await expect(page.getByRole('table')).toBeVisible()
    const initialRequests = requests.length
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
    await page.screenshot({ path: testInfo.outputPath('catalog-desktop.png'), fullPage: true })

    await expect(page.getByRole('columnheader', { name: 'Marca', exact: true })).toHaveCount(0)
    await page.locator('summary', { hasText: 'Colunas' }).click()
    await page.getByRole('checkbox', { name: 'Marca', exact: true }).check()
    await expect(page.getByRole('columnheader', { name: 'Marca', exact: true })).toBeVisible()
    await page.getByRole('checkbox', { name: 'Marca', exact: true }).uncheck()
    await expect(page.getByRole('columnheader', { name: 'Marca', exact: true })).toHaveCount(0)
    expect(requests).toHaveLength(initialRequests)

    await page.getByRole('table').click({ position: { x: 5, y: 5 } })
    await expect(page.getByRole('checkbox', { name: 'Marca', exact: true })).toBeHidden()
  })

  test('subscribes alerts and handles a duplicate email', async ({ page }) => {
    await page.goto('/')

    await page.getByRole('button', { name: 'Abrir alertas' }).click()
    await page.getByLabel('E-mail').fill('new@example.com')
    await page.getByRole('button', { name: 'Inscrever', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Inscrição feita!' })).toBeVisible()
    await page.getByRole('button', { name: 'Inscrever outro e-mail' }).click()

    await page.getByLabel('E-mail').fill('already@subscribed.com')
    await page.getByRole('button', { name: 'Inscrever', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Já inscrito' })).toBeVisible()
  })
})

test.describe('mobile', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('lists cards, sorts from the select and switches theme', async ({ page }, testInfo) => {
    await page.goto('/')
    const card = page.getByTestId(/^catalog-card-/).first()
    await expect(card).toBeVisible()
    await expect(page.getByRole('table')).toBeHidden()
    await expect(card.getByRole('link', { name: /^Ver oferta de / })).toBeVisible()
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)

    const sortRequest = catalogRequest(
      page,
      (params) => params.get('sort_by') === 'concentration' && params.get('sort_dir') === 'desc',
    )
    await choose(page, 'Ordenar por', 'Maior concentração')
    await sortRequest
    await expect(page.getByTestId(/^catalog-card-/).first()).toContainText('Iso Hydro 900g')

    await page.getByRole('button', { name: 'Mudar para o tema escuro' }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await page.screenshot({ path: testInfo.outputPath('catalog-mobile-dark.png'), fullPage: true })
  })
})
