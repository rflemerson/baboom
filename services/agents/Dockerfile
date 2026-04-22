FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DAGSTER_HOME=/opt/dagster/dagster_home

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -u 10001 -g appuser -m -d /home/appuser appuser \
    && mkdir -p "$DAGSTER_HOME"/storage "$DAGSTER_HOME"/compute_logs "$DAGSTER_HOME"/artifacts

COPY services/agents/ /app/
RUN pip install --no-cache-dir . \
    && chown -R appuser:appuser /app /opt/dagster

USER appuser
EXPOSE 3000

CMD ["dagster-webserver", "-m", "agents.definitions", "-h", "0.0.0.0", "-p", "3000"]
