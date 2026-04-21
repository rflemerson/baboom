#!/usr/bin/env sh
set -eu

echo "== docker compose ps =="
docker compose ps || true

echo "== api health =="
docker inspect baboom-api-1 --format "{{json .State.Health}}" || true

echo "== api logs =="
docker logs --tail="${DEPLOY_LOG_LINES:-200}" baboom-api-1 || true

echo "== web logs =="
docker logs --tail="${DEPLOY_LOG_LINES:-100}" baboom-web-1 || true

echo "== nginx logs =="
docker logs --tail="${DEPLOY_LOG_LINES:-100}" baboom_nginx || true
