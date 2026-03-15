import { ApolloClient, HttpLink, InMemoryCache } from '@apollo/client/core'

const graphqlUrl = import.meta.env.VITE_GRAPHQL_URL || '/graphql/'
const apiKey = import.meta.env.VITE_GRAPHQL_API_KEY

const headers: Record<string, string> = {}

if (apiKey) {
  headers['X-API-KEY'] = apiKey
}

const link = new HttpLink({
  uri: graphqlUrl,
  headers,
})

export const apolloClient = new ApolloClient({
  link,
  cache: new InMemoryCache(),
})
