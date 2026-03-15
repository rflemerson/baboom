FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY services/agents/ /app/
RUN pip install --no-cache-dir .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 3000

CMD ["dagster", "dev", "-m", "agents.definitions", "-h", "0.0.0.0", "-p", "3000"]
