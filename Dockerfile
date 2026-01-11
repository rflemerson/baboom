# ============================================
# Stage 1: Build Tailwind CSS with DaisyUI
# ============================================
FROM debian:bookworm-slim AS css-builder

WORKDIR /build

RUN apt-get update && apt-get install -y curl bash && rm -rf /var/lib/apt/lists/*
RUN curl -sL daisyui.com/fast | bash

COPY . .

RUN cd static/css && ./tailwindcss -i input.css -o output.css --minify

# ============================================
# Stage 2: Python Application
# ============================================
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    gettext \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY . /app/
RUN pip install --no-cache-dir .

COPY --from=css-builder /build/static/css/output.css /app/static/css/output.css

RUN python manage.py compilemessages --ignore=.venv || true
RUN python manage.py collectstatic --noinput

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn --bind 0.0.0.0:8000 --workers 3 --access-logfile - baboom.wsgi:application"]