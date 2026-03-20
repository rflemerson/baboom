import { expect, test, type Page, type Route } from '@playwright/test'

type Product = {
  id: number
  name: string
  packagingDisplay: string
  weight: number
  lastPrice: string
  pricePerGram: string
  concentration: string
  totalProtein: string
  externalLink: string
  brand: { name: string }
  category: { name: string }
  tags: Array<{ name: string }>
}

type CatalogVariables = {
  page: number
  perPage: number
  search?: string | null
  brand?: string | null
  priceMin?: number | null
  priceMax?: number | null
  pricePerGramMin?: number | null
  pricePerGramMax?: number | null
  concentrationMin?: number | null
  concentrationMax?: number | null
  sortBy: string
  sortDir: string
}

const PRODUCTS: Product[] = [
  {
    id: 1,
    name: 'Whey Prime 900g',
    packagingDisplay: 'Refill Package',
    weight: 900,
    lastPrice: '129.90',
    pricePerGram: '0.14',
    concentration: '80',
    totalProtein: '720',
    externalLink: 'https://example.com/whey-prime',
    brand: { name: 'dux' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Whey' }, { name: 'High Protein' }],
  },
  {
    id: 2,
    name: 'Whey Core 1kg',
    packagingDisplay: 'Container Package',
    weight: 1000,
    lastPrice: '149.90',
    pricePerGram: '0.16',
    concentration: '78',
    totalProtein: '780',
    externalLink: 'https://example.com/whey-core',
    brand: { name: 'black skull' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Whey' }],
  },
  {
    id: 3,
    name: 'Isolate Gold 1kg',
    packagingDisplay: 'Container Package',
    weight: 1000,
    lastPrice: '219.90',
    pricePerGram: '0.22',
    concentration: '86',
    totalProtein: '860',
    externalLink: 'https://example.com/isolate-gold',
    brand: { name: 'integralmedica' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Isolate' }],
  },
  {
    id: 4,
    name: 'Creatine Pure 300g',
    packagingDisplay: 'Container Package',
    weight: 300,
    lastPrice: '89.90',
    pricePerGram: '0.30',
    concentration: '0',
    totalProtein: '0',
    externalLink: 'https://example.com/creatine-pure',
    brand: { name: 'dux' },
    category: { name: 'Creatine' },
    tags: [{ name: 'Creatine' }],
  },
  {
    id: 5,
    name: 'Night Casein 900g',
    packagingDisplay: 'Refill Package',
    weight: 900,
    lastPrice: '159.90',
    pricePerGram: '0.18',
    concentration: '74',
    totalProtein: '666',
    externalLink: 'https://example.com/night-casein',
    brand: { name: 'black skull' },
    category: { name: 'Casein' },
    tags: [{ name: 'Slow Release' }],
  },
  {
    id: 6,
    name: 'Protein Blend 2kg',
    packagingDisplay: 'Container Package',
    weight: 2000,
    lastPrice: '239.90',
    pricePerGram: '0.12',
    concentration: '70',
    totalProtein: '1400',
    externalLink: 'https://example.com/protein-blend',
    brand: { name: 'max titanium' },
    category: { name: 'Protein Blend' },
    tags: [{ name: 'Blend' }],
  },
  {
    id: 7,
    name: 'Iso Hydro 900g',
    packagingDisplay: 'Refill Package',
    weight: 900,
    lastPrice: '249.90',
    pricePerGram: '0.28',
    concentration: '90',
    totalProtein: '810',
    externalLink: 'https://example.com/iso-hydro',
    brand: { name: 'dux' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Hydrolyzed' }],
  },
  {
    id: 8,
    name: 'Whey Budget 900g',
    packagingDisplay: 'Refill Package',
    weight: 900,
    lastPrice: '99.90',
    pricePerGram: '0.11',
    concentration: '68',
    totalProtein: '612',
    externalLink: 'https://example.com/whey-budget',
    brand: { name: 'max titanium' },
    category: { name: 'Whey Protein' },
    tags: [{ name: 'Budget' }],
  },
  {
    id: 9,
    name: 'Pre Rush 300g',
    packagingDisplay: 'Container Package',
    weight: 300,
    lastPrice: '109.90',
    pricePerGram: '0.37',
    concentration: '0',
    totalProtein: '0',
    externalLink: 'https://example.com/pre-rush',
    brand: { name: 'black skull' },
    category: { name: 'Pre Workout' },
    tags: [{ name: 'Energy' }],
  },
  {
    id: 10,
    name: 'Mass Gainer 3kg',
    packagingDisplay: 'Bag Package',
    weight: 3000,
    lastPrice: '199.90',
    pricePerGram: '0.07',
    concentration: '24',
    totalProtein: '720',
    externalLink: 'https://example.com/mass-gainer',
    brand: { name: 'integralmedica' },
    category: { name: 'Mass Gainer' },
    tags: [{ name: 'Calories' }],
  },
  {
    id: 11,
    name: 'Egg Protein 1kg',
    packagingDisplay: 'Container Package',
    weight: 1000,
    lastPrice: '179.90',
    pricePerGram: '0.19',
    concentration: '72',
    totalProtein: '720',
    externalLink: 'https://example.com/egg-protein',
    brand: { name: 'max titanium' },
    category: { name: 'Egg Protein' },
    tags: [{ name: 'Albumin' }],
  },
  {
    id: 12,
    name: 'Peanut Butter 1kg',
    packagingDisplay: 'Container Package',
    weight: 1000,
    lastPrice: '39.90',
    pricePerGram: '0.04',
    concentration: '0',
    totalProtein: '250',
    externalLink: 'https://example.com/peanut-butter',
    brand: { name: 'growth' },
    category: { name: 'Snacks' },
    tags: [{ name: 'Peanut' }],
  },
  {
    id: 13,
    name: 'Bar Box 12x',
    packagingDisplay: 'Box Package',
    weight: 600,
    lastPrice: '69.90',
    pricePerGram: '0.12',
    concentration: '20',
    totalProtein: '120',
    externalLink: 'https://example.com/bar-box',
    brand: { name: 'bold' },
    category: { name: 'Protein Bars' },
    tags: [{ name: 'Snack' }],
  },
]

function normalize(value: string | null | undefined) {
  return value?.trim().toLowerCase() ?? ''
}

function sortProducts(products: Product[], sortBy: string, sortDir: string) {
  const direction = sortDir === 'desc' ? -1 : 1

  const readNumber = (product: Product, key: string) => {
    switch (key) {
      case 'last_price':
        return Number(product.lastPrice)
      case 'price_per_gram':
        return Number(product.pricePerGram)
      case 'total_protein':
        return Number(product.totalProtein)
      case 'concentration':
        return Number(product.concentration)
      default:
        return Number(product.pricePerGram)
    }
  }

  return [...products].sort((left, right) => {
    return (readNumber(left, sortBy) - readNumber(right, sortBy)) * direction
  })
}

function filterProducts(variables: CatalogVariables) {
  const search = normalize(variables.search)
  const brand = normalize(variables.brand)

  const filtered = PRODUCTS.filter((product) => {
    return (
      matchesSearch(product, search) &&
      matchesBrand(product, brand) &&
      matchesNumericRange(Number(product.lastPrice), variables.priceMin, variables.priceMax) &&
      matchesNumericRange(
        Number(product.pricePerGram),
        variables.pricePerGramMin,
        variables.pricePerGramMax,
      ) &&
      matchesNumericRange(
        Number(product.concentration),
        variables.concentrationMin,
        variables.concentrationMax,
      )
    )
  })

  const sorted = sortProducts(filtered, variables.sortBy, variables.sortDir)
  const totalCount = sorted.length
  const totalPages = Math.max(1, Math.ceil(totalCount / variables.perPage))
  const currentPage = Math.min(variables.page, totalPages)
  const start = (currentPage - 1) * variables.perPage
  const items = sorted.slice(start, start + variables.perPage)

  return {
    catalogProducts: {
      pageInfo: {
        currentPage,
        perPage: variables.perPage,
        totalPages,
        totalCount,
        hasPreviousPage: currentPage > 1,
        hasNextPage: currentPage < totalPages,
      },
      items,
    },
  }
}

function matchesSearch(product: Product, search: string) {
  if (!search) {
    return true
  }

  const haystack = [
    product.name,
    product.brand.name,
    product.category.name,
    ...product.tags.map((tag) => tag.name),
  ]
    .join(' ')
    .toLowerCase()

  return haystack.includes(search)
}

function matchesBrand(product: Product, brand: string) {
  return !brand || product.brand.name.toLowerCase().includes(brand)
}

function matchesNumericRange(value: number, min?: number | null, max?: number | null) {
  if (min != null && value < min) {
    return false
  }
  if (max != null && value > max) {
    return false
  }
  return true
}

async function fulfillGraphql(route: Route) {
  const request = route.request()
  const body = request.postDataJSON() as {
    operationName?: string
    query?: string
    variables?: Record<string, unknown>
  }

  if (body.operationName === 'CatalogProducts') {
    const payload = filterProducts(body.variables as CatalogVariables)
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ data: payload }),
    })
    return
  }

  if (body.operationName === 'SubscribeAlerts') {
    const email = typeof body.variables?.email === 'string' ? body.variables.email : ''
    const alreadySubscribed = email.toLowerCase() === 'already@subscribed.com'

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          subscribeAlerts: alreadySubscribed
            ? {
                success: false,
                alreadySubscribed: true,
                email,
                errors: [],
              }
            : {
                success: true,
                alreadySubscribed: false,
                email,
                errors: [],
              },
        },
      }),
    })
    return
  }

  await route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({
      errors: [{ message: `Unhandled GraphQL operation: ${body.operationName ?? 'unknown'}` }],
    }),
  })
}

async function setupGraphqlMock(page: Page) {
  await page.route('**/graphql/', fulfillGraphql)
}

test.beforeEach(async ({ page }) => {
  await setupGraphqlMock(page)
})

test('loads the catalog and paginates through results', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByText('13 products')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Whey Budget 900g' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Go to next page' })).toBeVisible()

  await page.getByLabel('Results per page').selectOption('24')

  await expect(page.getByRole('button', { name: 'Go to next page' })).toHaveCount(0)

  await page.getByLabel('Results per page').selectOption('12')
  await page.getByRole('button', { name: 'Go to next page' }).click()

  await expect(page.getByText('Page 2 of 2')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Pre Rush 300g' })).toBeVisible()
})

test('supports view toggle, search, filters, and clearing filters', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('View mode: Grid view').click()
  await expect(page.getByLabel('View mode: List view')).toBeVisible()

  await page.getByLabel('Search catalog').fill('creatine')
  await expect(page.getByRole('heading', { name: 'Creatine Pure 300g' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Go to next page' })).toHaveCount(0)

  await page.getByLabel('Clear filters').click()
  await expect(page.getByText('13 products')).toBeVisible()

  await page.getByLabel('Open filters').click()
  await page.getByLabel('Brand').fill('dux')
  await page.getByRole('button', { name: 'Apply filters' }).click()

  await expect(page.getByRole('heading', { name: 'Whey Prime 900g' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Iso Hydro 900g' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Whey Budget 900g' })).toHaveCount(0)

  await page.getByLabel('Clear filters').click()
  await expect(page.getByText('13 products')).toBeVisible()
})

test('shows product-like empty state after restrictive filters', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('Open filters').click()
  await page.getByPlaceholder('Min').first().fill('999')
  await page.getByRole('button', { name: 'Apply filters' }).click()

  const emptyState = page
    .getByRole('heading', { name: 'No products matched this search' })
    .locator('xpath=ancestor::section[1]')

  await expect(emptyState).toBeVisible()
  await emptyState.getByRole('button', { name: 'Clear filters' }).click()

  await expect(page.getByText('13 products')).toBeVisible()
})

test('subscribes alerts and handles duplicate email', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('button', { name: 'Open alerts' }).click()
  await page.getByLabel('Email').fill('new@example.com')
  await page.getByRole('button', { name: 'Subscribe' }).click()

  await expect(page.getByRole('heading', { name: "You're Subscribed!" })).toBeVisible()
  await page.getByRole('button', { name: 'Subscribe another email' }).click()

  await page.getByLabel('Email').fill('already@subscribed.com')
  await page.getByRole('button', { name: 'Subscribe' }).click()

  await expect(page.getByRole('heading', { name: 'Already Subscribed' })).toBeVisible()
})
