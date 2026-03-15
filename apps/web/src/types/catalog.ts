import type { CatalogProductsQuery, CatalogProductsQueryVariables } from '@/gql/graphql'

export type CatalogProductsResponse = CatalogProductsQuery
export type CatalogProductsVariables = CatalogProductsQueryVariables
export type CatalogPageInfo = CatalogProductsQuery['catalogProducts']['pageInfo']
export type CatalogProduct = CatalogProductsQuery['catalogProducts']['items'][number]
