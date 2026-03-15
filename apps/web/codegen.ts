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
