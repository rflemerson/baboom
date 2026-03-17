# GraphQL Code Generator

## What it does

- Generates TypeScript-safe GraphQL documents and operation types from the schema plus your queries and mutations.
- Removes most manual `Response` / `Variables` typing.
- Works with Vue and `@vue/apollo-composable` through the `client` preset.

## Current project setup

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
  documents: ['src/**/*.{ts,vue,graphql}', '!src/gql/**/*'],
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

Preferred structure in this repo:

```text
src/graphql/
├── mutations/
│   └── alerts.graphql
└── queries/
    └── catalog.graphql
```

Then import the generated document from `src/gql/graphql.ts`:

```ts
import { CatalogProductsDocument } from '@/gql/graphql'
```

Then in the composable:

```ts
const { result } = useQuery(CatalogProductsDocument, { page: 1, perPage: 12 })
```

The query result and variables become typed automatically.

## Project guidance

- Keep generated code in `src/gql/`.
- Do not hand-edit generated files.
- Prefer `.graphql` files for operations even though Codegen currently scans `ts`, `vue`, and `graphql`; the broader glob is there for compatibility, not as the preferred authoring style.
- Prefer generated typed documents over handwritten response/variables types.
- Keep GraphQL variables in composables and pass them explicitly into `useQuery` / `useMutation`.
- Regenerate after schema or operation changes with `npm run graphql-codegen`.

## Sources

- Codegen React/Vue guide: https://the-guild.dev/graphql/codegen/docs/guides/react-vue
- `client` preset: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client
- `schema` field config: https://the-guild.dev/graphql/codegen/docs/config-reference/schema-field
- `documents` field config: https://the-guild.dev/graphql/codegen/docs/config-reference/documents-field
- Apollo Codegen guidance: https://www.apollographql.com/docs/deploy-preview/e0e8a8504a18a502cb40/react/development-testing/graphql-codegen
