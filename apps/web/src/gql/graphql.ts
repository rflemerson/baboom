/* eslint-disable @typescript-eslint/no-explicit-any */
import type { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core'
export type Maybe<T> = T | null
export type InputMaybe<T> = T | null | undefined
export type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] }
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]?: Maybe<T[SubKey]> }
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]: Maybe<T[SubKey]> }
export type MakeEmpty<T extends { [key: string]: unknown }, K extends keyof T> = {
  [_ in K]?: never
}
export type Incremental<T> =
  | T
  | { [P in keyof T]?: P extends ' $fragmentName' | '__typename' ? T[P] : never }
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string }
  String: { input: string; output: string }
  Boolean: { input: boolean; output: boolean }
  Int: { input: number; output: number }
  Float: { input: number; output: number }
  /** Date with time (isoformat) */
  DateTime: { input: any; output: any }
  /** Decimal (fixed-point) */
  Decimal: { input: any; output: any }
}

export type AlertSubscriptionResult = {
  __typename?: 'AlertSubscriptionResult'
  alreadySubscribed: Scalars['Boolean']['output']
  email?: Maybe<Scalars['String']['output']>
  errors?: Maybe<Array<ValidationError>>
  success: Scalars['Boolean']['output']
}

export type BrandType = {
  __typename?: 'BrandType'
  displayName: Scalars['String']['output']
  id: Scalars['ID']['output']
  name: Scalars['String']['output']
}

export type CatalogPageInfo = {
  __typename?: 'CatalogPageInfo'
  currentPage: Scalars['Int']['output']
  hasNextPage: Scalars['Boolean']['output']
  hasPreviousPage: Scalars['Boolean']['output']
  perPage: Scalars['Int']['output']
  totalCount: Scalars['Int']['output']
  totalPages: Scalars['Int']['output']
}

export type CatalogProductType = {
  __typename?: 'CatalogProductType'
  brand: BrandType
  category?: Maybe<CategoryType>
  concentration?: Maybe<Scalars['Decimal']['output']>
  externalLink?: Maybe<Scalars['String']['output']>
  id: Scalars['Int']['output']
  isPublished: Scalars['Boolean']['output']
  lastPrice?: Maybe<Scalars['Decimal']['output']>
  name: Scalars['String']['output']
  packaging: Scalars['String']['output']
  packagingDisplay: Scalars['String']['output']
  pricePerGram?: Maybe<Scalars['Decimal']['output']>
  tags: Array<TagType>
  totalProtein?: Maybe<Scalars['Decimal']['output']>
  weight: Scalars['Int']['output']
}

export type CatalogProductsFiltersInput = {
  brand?: InputMaybe<Scalars['String']['input']>
  concentrationMax?: InputMaybe<Scalars['Float']['input']>
  concentrationMin?: InputMaybe<Scalars['Float']['input']>
  page?: Scalars['Int']['input']
  perPage?: Scalars['Int']['input']
  priceMax?: InputMaybe<Scalars['Float']['input']>
  priceMin?: InputMaybe<Scalars['Float']['input']>
  pricePerGramMax?: InputMaybe<Scalars['Float']['input']>
  pricePerGramMin?: InputMaybe<Scalars['Float']['input']>
  search?: InputMaybe<Scalars['String']['input']>
  sortBy?: Scalars['String']['input']
  sortDir?: Scalars['String']['input']
}

export type CatalogProductsResult = {
  __typename?: 'CatalogProductsResult'
  items: Array<CatalogProductType>
  pageInfo: CatalogPageInfo
}

export type CategoryType = {
  __typename?: 'CategoryType'
  description: Scalars['String']['output']
  id: Scalars['ID']['output']
  name: Scalars['String']['output']
}

export type FlavorType = {
  __typename?: 'FlavorType'
  id: Scalars['ID']['output']
  name: Scalars['String']['output']
}

export type MicronutrientInput = {
  name: Scalars['String']['input']
  unit?: Scalars['String']['input']
  value: Scalars['Float']['input']
}

export type MicronutrientType = {
  __typename?: 'MicronutrientType'
  id: Scalars['ID']['output']
  name: Scalars['String']['output']
  unit: Scalars['String']['output']
  value: Scalars['Decimal']['output']
}

export type Mutation = {
  __typename?: 'Mutation'
  checkoutScrapedItem?: Maybe<ScrapedItemType>
  createProduct: ProductResult
  discardScrapedItem: Scalars['Boolean']['output']
  ensureScrapedItemSourcePage?: Maybe<ScrapedItemType>
  reportScrapedItemError: Scalars['Boolean']['output']
  subscribeAlerts: AlertSubscriptionResult
  updateProductContent: ProductResult
  updateScrapedItemData?: Maybe<ScrapedItemType>
  upsertScrapedItemVariant?: Maybe<ScrapedItemType>
}

export type MutationCheckoutScrapedItemArgs = {
  force?: Scalars['Boolean']['input']
  targetItemId?: InputMaybe<Scalars['Int']['input']>
}

export type MutationCreateProductArgs = {
  data: ProductInput
}

export type MutationDiscardScrapedItemArgs = {
  itemId: Scalars['Int']['input']
  reason: Scalars['String']['input']
}

export type MutationEnsureScrapedItemSourcePageArgs = {
  itemId: Scalars['Int']['input']
  storeSlug: Scalars['String']['input']
  url: Scalars['String']['input']
}

export type MutationReportScrapedItemErrorArgs = {
  isFatal?: Scalars['Boolean']['input']
  itemId: Scalars['Int']['input']
  message: Scalars['String']['input']
}

export type MutationSubscribeAlertsArgs = {
  email: Scalars['String']['input']
}

export type MutationUpdateProductContentArgs = {
  data: ProductContentUpdateInput
  productId: Scalars['Int']['input']
}

export type MutationUpdateScrapedItemDataArgs = {
  itemId: Scalars['Int']['input']
  name?: InputMaybe<Scalars['String']['input']>
  sourcePageUrl?: InputMaybe<Scalars['String']['input']>
  storeSlug?: InputMaybe<Scalars['String']['input']>
}

export type MutationUpsertScrapedItemVariantArgs = {
  externalId: Scalars['String']['input']
  name: Scalars['String']['input']
  originItemId: Scalars['Int']['input']
  pageUrl: Scalars['String']['input']
  price?: InputMaybe<Scalars['Float']['input']>
  stockStatus?: InputMaybe<Scalars['String']['input']>
  storeSlug: Scalars['String']['input']
}

export type NutritionFactsInput = {
  addedSugars?: Scalars['Float']['input']
  carbohydrates: Scalars['Float']['input']
  description?: InputMaybe<Scalars['String']['input']>
  dietaryFiber?: Scalars['Float']['input']
  energyKcal: Scalars['Int']['input']
  micronutrients?: InputMaybe<Array<MicronutrientInput>>
  proteins: Scalars['Float']['input']
  saturatedFats?: Scalars['Float']['input']
  servingSizeGrams: Scalars['Float']['input']
  sodium?: Scalars['Float']['input']
  totalFats: Scalars['Float']['input']
  totalSugars?: Scalars['Float']['input']
  transFats?: Scalars['Float']['input']
}

export type NutritionFactsType = {
  __typename?: 'NutritionFactsType'
  addedSugars: Scalars['Decimal']['output']
  carbohydrates: Scalars['Decimal']['output']
  description: Scalars['String']['output']
  dietaryFiber: Scalars['Decimal']['output']
  energyKcal: Scalars['Int']['output']
  id: Scalars['ID']['output']
  micronutrients: Array<MicronutrientType>
  proteins: Scalars['Decimal']['output']
  saturatedFats: Scalars['Decimal']['output']
  servingSizeGrams: Scalars['Decimal']['output']
  sodium: Scalars['Decimal']['output']
  totalFats: Scalars['Decimal']['output']
  totalSugars: Scalars['Decimal']['output']
  transFats: Scalars['Decimal']['output']
}

export enum PackagingEnum {
  Bar = 'BAR',
  Container = 'CONTAINER',
  Other = 'OTHER',
  Refill = 'REFILL',
}

export type ProductComponentInput = {
  name: Scalars['String']['input']
  packagingHint?: InputMaybe<Scalars['String']['input']>
  quantity?: Scalars['Int']['input']
  weightHint?: InputMaybe<Scalars['Int']['input']>
}

/** Input for updating product content only */
export type ProductContentUpdateInput = {
  categoryName?: InputMaybe<Scalars['String']['input']>
  categoryPath?: InputMaybe<Array<Scalars['String']['input']>>
  description?: InputMaybe<Scalars['String']['input']>
  name?: InputMaybe<Scalars['String']['input']>
  packaging?: InputMaybe<PackagingEnum>
  tagPaths?: InputMaybe<Array<TagPathInput>>
  tags?: InputMaybe<Array<Scalars['String']['input']>>
}

/** Input for creating a new product with all related data */
export type ProductInput = {
  /** Brand name (auto-created if not exists) */
  brandName: Scalars['String']['input']
  /** Deprecated: Use category_path */
  categoryName?: InputMaybe<Scalars['String']['input']>
  /** Hierarchical category path */
  categoryPath?: InputMaybe<Array<Scalars['String']['input']>>
  /** List of components if combo */
  components?: InputMaybe<Array<ProductComponentInput>>
  /** Marketing description */
  description?: InputMaybe<Scalars['String']['input']>
  /** Barcode */
  ean?: InputMaybe<Scalars['String']['input']>
  /** Is this a combo/kit product? */
  isCombo?: Scalars['Boolean']['input']
  /** Visible on public site */
  isPublished?: Scalars['Boolean']['input']
  /** Product display name */
  name: Scalars['String']['input']
  /** List of nutrient slugs claimed by source */
  nutrientClaims?: InputMaybe<Array<Scalars['String']['input']>>
  /** Nutrition profiles */
  nutrition?: InputMaybe<Array<ProductNutritionInput>>
  /** ID of the ScrapedItem that generated this product (to link/complete) */
  originScrapedItemId?: InputMaybe<Scalars['Int']['input']>
  /** Packaging type */
  packaging?: PackagingEnum
  /** Store links */
  stores?: InputMaybe<Array<ProductStoreInput>>
  /** Hierarchical tag paths */
  tagPaths?: InputMaybe<Array<TagPathInput>>
  /** Deprecated: Use tag_paths */
  tags?: InputMaybe<Array<Scalars['String']['input']>>
  /** Weight in grams */
  weight: Scalars['Int']['input']
}

export type ProductNutritionInput = {
  flavorNames?: InputMaybe<Array<Scalars['String']['input']>>
  nutritionFacts: NutritionFactsInput
}

export type ProductNutritionType = {
  __typename?: 'ProductNutritionType'
  flavors: Array<FlavorType>
  id: Scalars['ID']['output']
  nutritionFacts: NutritionFactsType
  product: ProductType
}

export type ProductPriceHistoryType = {
  __typename?: 'ProductPriceHistoryType'
  collectedAt: Scalars['DateTime']['output']
  id: Scalars['ID']['output']
  price: Scalars['Decimal']['output']
  stockStatus: Scalars['String']['output']
}

export type ProductResult = {
  __typename?: 'ProductResult'
  errors?: Maybe<Array<ValidationError>>
  product?: Maybe<ProductType>
}

export type ProductStoreInput = {
  affiliateLink?: InputMaybe<Scalars['String']['input']>
  externalId?: InputMaybe<Scalars['String']['input']>
  price: Scalars['Float']['input']
  productLink: Scalars['String']['input']
  stockStatus?: StockStatusEnum
  storeName: Scalars['String']['input']
}

export type ProductStoreType = {
  __typename?: 'ProductStoreType'
  affiliateLink: Scalars['String']['output']
  externalId: Scalars['String']['output']
  id: Scalars['ID']['output']
  priceHistory: Array<ProductPriceHistoryType>
  productLink: Scalars['String']['output']
  store: StoreType
}

export type ProductType = {
  __typename?: 'ProductType'
  brand: BrandType
  category?: Maybe<CategoryType>
  createdAt: Scalars['DateTime']['output']
  description: Scalars['String']['output']
  ean?: Maybe<Scalars['String']['output']>
  id: Scalars['ID']['output']
  isPublished: Scalars['Boolean']['output']
  lastEnrichedAt?: Maybe<Scalars['DateTime']['output']>
  name: Scalars['String']['output']
  nutritionProfiles: Array<ProductNutritionType>
  packaging: Scalars['String']['output']
  storeLinks: Array<ProductStoreType>
  tags: Array<TagType>
  updatedAt: Scalars['DateTime']['output']
  weight: Scalars['Int']['output']
}

export type Query = {
  __typename?: 'Query'
  catalogProducts: CatalogProductsResult
  categories: Array<CategoryType>
  hello: Scalars['String']['output']
  product?: Maybe<ProductType>
  products: Array<ProductType>
  scrapedItem?: Maybe<ScrapedItemType>
  tags: Array<TagType>
}

export type QueryCatalogProductsArgs = {
  filters?: InputMaybe<CatalogProductsFiltersInput>
}

export type QueryProductArgs = {
  productId: Scalars['Int']['input']
}

export type QueryProductsArgs = {
  limit?: Scalars['Int']['input']
  offset?: Scalars['Int']['input']
}

export type QueryScrapedItemArgs = {
  itemId: Scalars['Int']['input']
}

export type ScrapedItemType = {
  __typename?: 'ScrapedItemType'
  externalId: Scalars['String']['output']
  id: Scalars['ID']['output']
  linkedProductId?: Maybe<Scalars['Int']['output']>
  name: Scalars['String']['output']
  price?: Maybe<Scalars['Decimal']['output']>
  productLink: Scalars['String']['output']
  productStoreId?: Maybe<Scalars['Int']['output']>
  sourcePageContentType: Scalars['String']['output']
  sourcePageId?: Maybe<Scalars['Int']['output']>
  sourcePageRawContent: Scalars['String']['output']
  sourcePageUrl: Scalars['String']['output']
  status: Scalars['String']['output']
  stockStatus: Scalars['String']['output']
  storeName: Scalars['String']['output']
  storeSlug: Scalars['String']['output']
}

export enum StockStatusEnum {
  Available = 'AVAILABLE',
  LastUnits = 'LAST_UNITS',
  OutOfStock = 'OUT_OF_STOCK',
}

export type StoreType = {
  __typename?: 'StoreType'
  displayName: Scalars['String']['output']
  id: Scalars['ID']['output']
  name: Scalars['String']['output']
}

export type TagPathInput = {
  path: Array<Scalars['String']['input']>
}

export type TagType = {
  __typename?: 'TagType'
  id: Scalars['ID']['output']
  name: Scalars['String']['output']
}

export type ValidationError = {
  __typename?: 'ValidationError'
  field: Scalars['String']['output']
  message: Scalars['String']['output']
}

export type SubscribeAlertsMutationVariables = Exact<{
  email: Scalars['String']['input']
}>

export type SubscribeAlertsMutation = {
  __typename?: 'Mutation'
  subscribeAlerts: {
    __typename?: 'AlertSubscriptionResult'
    success: boolean
    alreadySubscribed: boolean
    email?: string | null
    errors?: Array<{ __typename?: 'ValidationError'; field: string; message: string }> | null
  }
}

export type CatalogProductsQueryVariables = Exact<{
  filters?: InputMaybe<CatalogProductsFiltersInput>
}>

export type CatalogProductsQuery = {
  __typename?: 'Query'
  catalogProducts: {
    __typename?: 'CatalogProductsResult'
    pageInfo: {
      __typename?: 'CatalogPageInfo'
      currentPage: number
      perPage: number
      totalPages: number
      totalCount: number
      hasPreviousPage: boolean
      hasNextPage: boolean
    }
    items: Array<{
      __typename?: 'CatalogProductType'
      id: number
      name: string
      packagingDisplay: string
      weight: number
      lastPrice?: any | null
      pricePerGram?: any | null
      concentration?: any | null
      totalProtein?: any | null
      externalLink?: string | null
      brand: { __typename?: 'BrandType'; name: string }
      category?: { __typename?: 'CategoryType'; name: string } | null
      tags: Array<{ __typename?: 'TagType'; name: string }>
    }>
  }
}

export const SubscribeAlertsDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'mutation',
      name: { kind: 'Name', value: 'SubscribeAlerts' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: { kind: 'Variable', name: { kind: 'Name', value: 'email' } },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'String' } },
          },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'subscribeAlerts' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'email' },
                value: { kind: 'Variable', name: { kind: 'Name', value: 'email' } },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                { kind: 'Field', name: { kind: 'Name', value: 'success' } },
                { kind: 'Field', name: { kind: 'Name', value: 'alreadySubscribed' } },
                { kind: 'Field', name: { kind: 'Name', value: 'email' } },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'errors' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'field' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'message' } },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<SubscribeAlertsMutation, SubscribeAlertsMutationVariables>
export const CatalogProductsDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'query',
      name: { kind: 'Name', value: 'CatalogProducts' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: { kind: 'Variable', name: { kind: 'Name', value: 'filters' } },
          type: { kind: 'NamedType', name: { kind: 'Name', value: 'CatalogProductsFiltersInput' } },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'catalogProducts' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'filters' },
                value: { kind: 'Variable', name: { kind: 'Name', value: 'filters' } },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'pageInfo' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'currentPage' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'perPage' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'totalPages' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'totalCount' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'hasPreviousPage' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'hasNextPage' } },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'items' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'name' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'packagingDisplay' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'weight' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'lastPrice' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'pricePerGram' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'concentration' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'totalProtein' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'externalLink' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'brand' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [{ kind: 'Field', name: { kind: 'Name', value: 'name' } }],
                        },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'category' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [{ kind: 'Field', name: { kind: 'Name', value: 'name' } }],
                        },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'tags' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [{ kind: 'Field', name: { kind: 'Name', value: 'name' } }],
                        },
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<CatalogProductsQuery, CatalogProductsQueryVariables>
