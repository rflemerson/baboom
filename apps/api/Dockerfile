FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_WORKERS=2
ENV GUNICORN_TIMEOUT=120
ARG DJANGO_SECRET_KEY=build-only-secret-key

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -g appuser -m -d /home/appuser appuser

COPY apps/api/ /app/
RUN pip install --no-cache-dir . \
    && (DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY python manage.py compilemessages --ignore=.venv || true) \
    && chown -R appuser:appuser /app

EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /app/media /app/staticfiles && chown -R appuser:appuser /app/media /app/staticfiles && su appuser -s /bin/sh -c 'python manage.py migrate && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - baboom.wsgi:application'"]
