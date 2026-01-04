FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Install python dependencies (global install is fine in container)
RUN pip install --no-cache-dir .

# Compile translations
RUN python manage.py compilemessages --ignore=.venv || true

# Collect static files
RUN python manage.py collectstatic --noinput

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Swtich to non-root user
USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "baboom.wsgi:application"]
