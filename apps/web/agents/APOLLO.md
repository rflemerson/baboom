# Apollo

## Role in this project

- Use Apollo Client with `@vue/apollo-composable`.
- Keep Apollo Client on the `3.x` line while using `@vue/apollo-composable@4.x`.
- Prefer pushing typed GraphQL documents into composables instead of calling Apollo directly from many components.

## Current project pattern

- Apollo setup lives in `src/graphql/client/apollo.ts`.
- The app provides the default client in `src/main.ts` with `DefaultApolloClient`.
- Components should consume GraphQL through composables such as `useCatalogQuery()`.

## Usage guidance

- Keep query/mutation documents in `src/graphql/`.
- Keep UI components dumb when possible; fetch in a composable or route-level view.
- Pass variables explicitly; avoid hidden global query state.
- Prefer one composable per feature area when the query has UI state attached.

## Sources

- Vue Apollo installation: https://apollo.vuejs.org/guide/installation.html
- Vue Apollo composable setup: https://apollo.vuejs.org/guide-composable/setup
- Vue Apollo queries: https://apollo.vuejs.org/guide-composable/query
