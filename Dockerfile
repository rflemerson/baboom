FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    gettext \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY . /app/
RUN pip install --no-cache-dir .

RUN python manage.py compilemessages --ignore=.venv || true

RUN curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss-linux-x64 \
    && curl -sL https://unpkg.com/daisyui@latest/dist/index.mjs -o static/css/daisyui.mjs \
    && curl -sL https://unpkg.com/daisyui@latest/dist/theme.mjs -o static/css/daisyui-theme.mjs \
    && ./tailwindcss-linux-x64 -i static/css/input.css -o static/css/output.css --minify \
    && rm tailwindcss-linux-x64

RUN python manage.py collectstatic --noinput

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn --bind 0.0.0.0:8000 --workers 3 --access-logfile - baboom.wsgi:application"]