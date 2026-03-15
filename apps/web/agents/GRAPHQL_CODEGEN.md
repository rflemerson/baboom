# GraphQL Code Generator

## What it does

- Generates TypeScript-safe GraphQL documents and operation types from the schema plus your queries and mutations.
- Removes most manual `Response` / `Variables` typing.
- Works with Vue and `@vue/apollo-composable` through the `client` preset.

## Recommended setup for this project

Install:

```bash
cd apps/web
npm install --save-dev @graphql-codegen/cli @graphql-codegen/client-preset @parcel/watcher
```

Create `apps/web/codegen.ts`:

```ts
import type { CodegenConfig } from '@graphql-codegen/cli'

const graphqlUrl = process.env.CODEGEN_SCHEMA_URL ?? 'http://127.0.0.1:8000/graphql/'
const apiKey = process.env.CODEGEN_API_KEY

const config: CodegenConfig = {
  schema: apiKey
    ? [
        {
          [graphqlUrl]: {
            headers: {
              'X-API-KEY': apiKey,
            },
          },
        },
      ]
    : graphqlUrl,
  documents: ['src/**/*.{ts,vue}', '!src/gql/**/*'],
  ignoreNoDocuments: true,
  generates: {
    './src/gql/': {
      preset: 'client',
      config: {
        useTypeImports: true,
      },
    },
  },
}

export default config
```

Add scripts to `apps/web/package.json`:

```json
{
  "scripts": {
    "graphql-codegen": "graphql-codegen",
    "graphql-codegen:watch": "graphql-codegen --watch"
  }
}
```

Then run:

```bash
cd apps/web
CODEGEN_API_KEY=your-local-api-key npm run graphql-codegen
```

## How to use it in Vue

Instead of importing `gql` from Apollo directly, use the generated helper:

```ts
import { graphql } from '@/gql'

export const catalogProductsQuery = graphql(`
  query CatalogProducts($page: Int!, $perPage: Int!) {
    catalogProducts(page: $page, perPage: $perPage) {
      pageInfo {
        currentPage
        perPage
        totalPages
        totalCount
      }
      items {
        id
        name
      }
    }
  }
`)
```

Then in the composable:

```ts
const { result } = useQuery(catalogProductsQuery, { page: 1, perPage: 12 })
```

The query result and variables become typed automatically.

## Recommendation for this repo

- Add Codegen after the catalog query and alert mutation shapes settle a bit more.
- Use the `client` preset first.
- Keep generated code in `src/gql/`.
- Do not hand-edit generated files.
- Prefer generated typed documents over handwritten response/variables types once Codegen is enabled.

## Sources

- Codegen React/Vue guide: https://the-guild.dev/graphql/codegen/docs/guides/react-vue
- `client` preset: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client
- `schema` field config: https://the-guild.dev/graphql/codegen/docs/config-reference/schema-field
- `documents` field config: https://the-guild.dev/graphql/codegen/docs/config-reference/documents-field
- Apollo Codegen guidance: https://www.apollographql.com/docs/deploy-preview/e0e8a8504a18a502cb40/react/development-testing/graphql-codegen
