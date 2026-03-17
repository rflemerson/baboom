# API Security

## Core expectations

- Keep `SecurityMiddleware`, CSRF middleware, and frame protection active.
- Configure `ALLOWED_HOSTS` strictly in production.
- Sanitize logs; never log secrets, API keys, or sensitive personal data.

## Deployment rules

- Do not bake `.env` files or secrets into images.
- Prefer non-root runtime users in containers.
- Keep TLS and secure cookie settings explicit in production settings.

## Data handling

- Prefer least-privilege database credentials.
- Keep GraphQL permissions explicit and easy to audit.
