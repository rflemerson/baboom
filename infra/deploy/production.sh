#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ROOT_DIR:-/home/ubuntu/app/baboom}"
REGISTRY="${REGISTRY:?REGISTRY is required}"
IMAGE_OWNER="${IMAGE_OWNER:?IMAGE_OWNER is required}"
# web: nginx, web, API and postgres. worker: celery, beat and redis.
DEPLOY_ROLE="${DEPLOY_ROLE:?DEPLOY_ROLE must be web or worker}"

cd "$ROOT_DIR"

on_error() {
  status="$?"
  echo "::error::Deploy failed with exit code ${status}"
  ./infra/deploy/diagnostics.sh
  exit "$status"
}
trap on_error ERR

if [ "${DEPLOY_SKIP_GIT_UPDATE:-0}" != "1" ]; then
  echo "== Updating repository =="
  git pull --ff-only origin main
fi

commit_sha="$(git rev-parse HEAD)"
short_sha="$(git rev-parse --short HEAD)"
image_tag="sha-${commit_sha}"

export API_IMAGE="${REGISTRY}/${IMAGE_OWNER}/baboom-api:${image_tag}"
export WEB_IMAGE="${REGISTRY}/${IMAGE_OWNER}/baboom-web:${image_tag}"
# Written by the deploy workflow over stdin, so the signing key never
# appears in a command line.
if [ -f .env.oauth ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env.oauth
  set +a
fi

export SENTRY_DSN="${SENTRY_DSN:-}"
export SENTRY_TRACES_SAMPLE_RATE="${SENTRY_TRACES_SAMPLE_RATE:-0.0}"
export SENTRY_SEND_DEFAULT_PII="${SENTRY_SEND_DEFAULT_PII:-false}"
export SENTRY_MONITOR_CELERY_BEAT="${SENTRY_MONITOR_CELERY_BEAT:-false}"

echo "Deploying commit: ${short_sha}"
echo "API image: ${API_IMAGE}"
echo "Web image: ${WEB_IMAGE}"

if [ -n "${GHCR_TOKEN:-}" ] && [ -n "${GHCR_USER:-}" ]; then
  echo "== Logging in to GHCR =="
  printf "%s\n" "$GHCR_TOKEN" | docker login "$REGISTRY" -u "$GHCR_USER" --password-stdin
fi

case "$DEPLOY_ROLE" in
  web)
    DB_PRIVATE_BIND="${DB_PRIVATE_BIND:?DB_PRIVATE_BIND is required on the web machine}"
    export DB_PRIVATE_BIND
    compose() { docker compose -f docker-compose.yml -f docker-compose.web.yml "$@"; }

    echo "== Pulling immutable images =="
    compose pull api web

    echo "== Starting database, web and API =="
    compose up -d --no-build db web api
    ./infra/deploy/wait-health.sh baboom-api-1 "${API_HEALTH_ATTEMPTS:-30}" "${API_HEALTH_INTERVAL:-10}"

    if [ -n "${CATALOG_OPERATOR_USERNAME:-}" ]; then
      echo "== Ensuring the catalog operator =="
      compose exec -T \
        -e CATALOG_OPERATOR_PASSWORD="${CATALOG_OPERATOR_PASSWORD:-}" \
        api python manage.py ensure_catalog_operator \
          --username "${CATALOG_OPERATOR_USERNAME}" \
          --email "${CATALOG_OPERATOR_EMAIL:-}"
    fi

    # Background work lives on the worker machine. A beat left running here
    # would schedule every crawl twice.
    echo "== Removing background services from this machine =="
    compose rm -sf celery celery-beat redis

    echo "== Reloading edge proxy =="
    compose up -d --no-build --force-recreate --no-deps nginx
    ;;
  worker)
    compose() { docker compose -f docker-compose.worker.yml "$@"; }

    echo "== Pulling immutable images =="
    compose pull celery celery-beat redis

    echo "== Starting background services =="
    compose up -d --no-build redis celery celery-beat
    ;;
  *)
    echo "::error::Unknown DEPLOY_ROLE: ${DEPLOY_ROLE}"
    exit 1
    ;;
esac

echo "== Pruning unused images =="
docker image prune -f

echo "== Final compose state =="
compose ps
