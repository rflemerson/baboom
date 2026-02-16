---
description: Security Best Practices (OWASP)
alwaysApply: true
applyTo: "**"
---

# Security Reference (OWASP)

- [Docker Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [Django Security](https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html)
- [Database Security](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)

## Docker Security

### Golden Rules
1.  **Run as Non-Root**: Never run container processes as `root`. Define a user (e.g., `appuser`) in your `Dockerfile`.
2.  **No Secrets in Images**: Never `COPY .env` or bake secrets into layers. Use environment variables at runtime.
3.  **Vulnerability Scanning**: Scan images regularly (Trivy, Snyk).
4.  **Least Privilege**: Drop capabilities (`--cap-drop=all`) and prevent privilege escalation (`--security-opt=no-new-privileges`).
5.  **Filesystem**: Use read-only filesystems where possible for app code.

## Django Security

### Settings (Production)
Enforce these in `settings/production.py`:
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'  # Prevent Clickjacking
```

### Middleware
Ensure these are active:
-   `SecurityMiddleware` (Top of list)
-   `CsrfViewMiddleware`
-   `XFrameOptionsMiddleware`

### CSRF Protection
-   Always use `{% csrf_token %}` in POST forms.
-   For HTMX, ensure the CSRF token is passed in headers (handled by `document.body` config in `AGENTS.md` context or base template).

## Frontend & XSS

### Templates
-   **Auto-Escaping**: Django handles this by default.
-   **`|safe` Filter**: **DANGER**. Never use `|safe` on user-provided content. Only use on trusted, static strings.
-   **JSON Injection**: Use `{{ my_var|json_script:"my-id" }}` to pass data to JS safely. Do NOT use `var x = "{{ my_var }}"`.

### Content Security Policy (CSP)
-   Implement `django-csp`.
-   Restrict `script-src` to self and trusted domains (e.g., Alpine/HTMX CDNs if used).

## Database Security

### Access Control
-   **Least Privilege**: The DB user for the app should ONLY have `SELECT`, `INSERT`, `UPDATE`, `DELETE`.
    -   No `DROP`, `ALTER`, or `TRUNCATE`.
-   **Isolation**: Use separate credentials for Read Replicas vs Write.
-   **Encryption**: Use SSL connections (`sslmode=require`).

## General Hardening
1.  **Dependencies**: Keep `pyproject.toml` updated. `safety` check runs in pre-commit.
2.  **Logging**: Sanitize logs. Never log passwords, API keys, or PII.
3.  **Allowed Hosts**: Configure `ALLOWED_HOSTS` strictly in production.
