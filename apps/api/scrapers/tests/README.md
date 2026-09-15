Scraper tests mirror the application modules:

- `normalizers/` covers platform payload transformations.
- `crawler/` covers shared scheduling, middleware, pipelines, and platform
  spider callbacks with in-memory responses.
- `services/` covers scraper persistence workflows.
- `commands/` covers explicit operator commands.
- `test_tasks.py` and `test_checks.py` cover Celery task and system-check
  behavior.

All tests use Django's runner from `apps/api`:

```bash
DJANGO_SECRET_KEY=test-only-local .venv/bin/python manage.py test
DJANGO_SECRET_KEY=test-only-local .venv/bin/coverage run manage.py test
.venv/bin/coverage report
```

Real store verification is intentionally outside the suite. Run
`manage.py verify_scraper_stores` manually when network access is intended; it
uses the same monitor workflow as Celery and therefore persists the crawl,
creates a `ScraperRun`, and reconciles offers absent from a successful run.
