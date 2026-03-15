import { graphql } from '@/gql'
import type { CatalogProductsQueryVariables } from '@/gql/graphql'

export const DEFAULT_CATALOG_PRODUCTS_VARIABLES: CatalogProductsQueryVariables = {
  page: 1,
  perPage: 12,
}

export const CATALOG_PRODUCTS_QUERY = graphql(`
  query CatalogProducts($page: Int!, $perPage: Int!) {
    catalogProducts(page: $page, perPage: $perPage) {
      pageInfo {
        currentPage
        perPage
        totalPages
        totalCount
        hasPreviousPage
        hasNextPage
      }
      items {
        id
        name
        packagingDisplay
        weight
        lastPrice
        pricePerGram
        concentration
        totalProtein
        externalLink
        brand {
          name
        }
        category {
          name
        }
        tags {
          name
        }
      }
    }
  }
`
)
