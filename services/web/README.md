# Web Service (Django + Scrapers)

This service owns:

- Django HTTP app
- Scraper orchestration and admin UI controls
- Celery worker/beat for scraper scheduling

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r services/web/requirements.txt
```

## Run

```bash
python manage.py runserver
celery -A baboom worker -l info
celery -A baboom beat -l info
```

## Env

Copy `services/web/.env.example` and configure values for your environment.
