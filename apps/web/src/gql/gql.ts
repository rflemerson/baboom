/* eslint-disable */
import * as types from './graphql';
import type { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';

/**
 * Map of all GraphQL operations in the project.
 *
 * This map has several performance disadvantages:
 * 1. It is not tree-shakeable, so it will include all operations in the project.
 * 2. It is not minifiable, so the string of a GraphQL query will be multiple times inside the bundle.
 * 3. It does not support dead code elimination, so it will add unused operations.
 *
 * Therefore it is highly recommended to use the babel or swc plugin for production.
 * Learn more about it here: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client#reducing-bundle-size
 */
type Documents = {
    "mutation SubscribeAlerts($email: String!) {\n  subscribeAlerts(email: $email) {\n    success\n    alreadySubscribed\n    email\n    errors {\n      field\n      message\n    }\n  }\n}": typeof types.SubscribeAlertsDocument,
    "query CatalogProducts($page: Int!, $perPage: Int!, $search: String, $brand: String, $priceMin: Float, $priceMax: Float, $pricePerGramMin: Float, $pricePerGramMax: Float, $concentrationMin: Float, $concentrationMax: Float, $sortBy: String!, $sortDir: String!) {\n  catalogProducts(\n    page: $page\n    perPage: $perPage\n    search: $search\n    brand: $brand\n    priceMin: $priceMin\n    priceMax: $priceMax\n    pricePerGramMin: $pricePerGramMin\n    pricePerGramMax: $pricePerGramMax\n    concentrationMin: $concentrationMin\n    concentrationMax: $concentrationMax\n    sortBy: $sortBy\n    sortDir: $sortDir\n  ) {\n    pageInfo {\n      currentPage\n      perPage\n      totalPages\n      totalCount\n      hasPreviousPage\n      hasNextPage\n    }\n    items {\n      id\n      name\n      packagingDisplay\n      weight\n      lastPrice\n      pricePerGram\n      concentration\n      totalProtein\n      externalLink\n      brand {\n        name\n      }\n      category {\n        name\n      }\n      tags {\n        name\n      }\n    }\n  }\n}": typeof types.CatalogProductsDocument,
};
const documents: Documents = {
    "mutation SubscribeAlerts($email: String!) {\n  subscribeAlerts(email: $email) {\n    success\n    alreadySubscribed\n    email\n    errors {\n      field\n      message\n    }\n  }\n}": types.SubscribeAlertsDocument,
    "query CatalogProducts($page: Int!, $perPage: Int!, $search: String, $brand: String, $priceMin: Float, $priceMax: Float, $pricePerGramMin: Float, $pricePerGramMax: Float, $concentrationMin: Float, $concentrationMax: Float, $sortBy: String!, $sortDir: String!) {\n  catalogProducts(\n    page: $page\n    perPage: $perPage\n    search: $search\n    brand: $brand\n    priceMin: $priceMin\n    priceMax: $priceMax\n    pricePerGramMin: $pricePerGramMin\n    pricePerGramMax: $pricePerGramMax\n    concentrationMin: $concentrationMin\n    concentrationMax: $concentrationMax\n    sortBy: $sortBy\n    sortDir: $sortDir\n  ) {\n    pageInfo {\n      currentPage\n      perPage\n      totalPages\n      totalCount\n      hasPreviousPage\n      hasNextPage\n    }\n    items {\n      id\n      name\n      packagingDisplay\n      weight\n      lastPrice\n      pricePerGram\n      concentration\n      totalProtein\n      externalLink\n      brand {\n        name\n      }\n      category {\n        name\n      }\n      tags {\n        name\n      }\n    }\n  }\n}": types.CatalogProductsDocument,
};

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 *
 *
 * @example
 * ```ts
 * const query = graphql(`query GetUser($id: ID!) { user(id: $id) { name } }`);
 * ```
 *
 * The query argument is unknown!
 * Please regenerate the types.
 */
export function graphql(source: string): unknown;

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "mutation SubscribeAlerts($email: String!) {\n  subscribeAlerts(email: $email) {\n    success\n    alreadySubscribed\n    email\n    errors {\n      field\n      message\n    }\n  }\n}"): (typeof documents)["mutation SubscribeAlerts($email: String!) {\n  subscribeAlerts(email: $email) {\n    success\n    alreadySubscribed\n    email\n    errors {\n      field\n      message\n    }\n  }\n}"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "query CatalogProducts($page: Int!, $perPage: Int!, $search: String, $brand: String, $priceMin: Float, $priceMax: Float, $pricePerGramMin: Float, $pricePerGramMax: Float, $concentrationMin: Float, $concentrationMax: Float, $sortBy: String!, $sortDir: String!) {\n  catalogProducts(\n    page: $page\n    perPage: $perPage\n    search: $search\n    brand: $brand\n    priceMin: $priceMin\n    priceMax: $priceMax\n    pricePerGramMin: $pricePerGramMin\n    pricePerGramMax: $pricePerGramMax\n    concentrationMin: $concentrationMin\n    concentrationMax: $concentrationMax\n    sortBy: $sortBy\n    sortDir: $sortDir\n  ) {\n    pageInfo {\n      currentPage\n      perPage\n      totalPages\n      totalCount\n      hasPreviousPage\n      hasNextPage\n    }\n    items {\n      id\n      name\n      packagingDisplay\n      weight\n      lastPrice\n      pricePerGram\n      concentration\n      totalProtein\n      externalLink\n      brand {\n        name\n      }\n      category {\n        name\n      }\n      tags {\n        name\n      }\n    }\n  }\n}"): (typeof documents)["query CatalogProducts($page: Int!, $perPage: Int!, $search: String, $brand: String, $priceMin: Float, $priceMax: Float, $pricePerGramMin: Float, $pricePerGramMax: Float, $concentrationMin: Float, $concentrationMax: Float, $sortBy: String!, $sortDir: String!) {\n  catalogProducts(\n    page: $page\n    perPage: $perPage\n    search: $search\n    brand: $brand\n    priceMin: $priceMin\n    priceMax: $priceMax\n    pricePerGramMin: $pricePerGramMin\n    pricePerGramMax: $pricePerGramMax\n    concentrationMin: $concentrationMin\n    concentrationMax: $concentrationMax\n    sortBy: $sortBy\n    sortDir: $sortDir\n  ) {\n    pageInfo {\n      currentPage\n      perPage\n      totalPages\n      totalCount\n      hasPreviousPage\n      hasNextPage\n    }\n    items {\n      id\n      name\n      packagingDisplay\n      weight\n      lastPrice\n      pricePerGram\n      concentration\n      totalProtein\n      externalLink\n      brand {\n        name\n      }\n      category {\n        name\n      }\n      tags {\n        name\n      }\n    }\n  }\n}"];

export function graphql(source: string) {
  return (documents as any)[source] ?? {};
}

export type DocumentType<TDocumentNode extends DocumentNode<any, any>> = TDocumentNode extends DocumentNode<  infer TType,  any>  ? TType  : never;