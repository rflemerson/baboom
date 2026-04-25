#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ROOT_DIR:-/home/ubuntu/app/baboom}"
REGISTRY="${REGISTRY:?REGISTRY is required}"
IMAGE_OWNER="${IMAGE_OWNER:?IMAGE_OWNER is required}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.agents.yml}"
DAGSTER_STORAGE_PATH="${DAGSTER_STORAGE_PATH:-/opt/baboom/dagster}"

cd "$ROOT_DIR"

on_error() {
  status="$?"
  echo "::error::Agents deploy failed with exit code ${status}"
  COMPOSE_FILE="$COMPOSE_FILE" ./infra/deploy/agents-diagnostics.sh
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

export AGENTS_IMAGE="${REGISTRY}/${IMAGE_OWNER}/baboom-agents:${image_tag}"
export DAGSTER_STORAGE_PATH
export AGENTS_API_URL="${AGENTS_API_URL:-https://baboom.com.br/graphql/}"
export AGENTS_HTTP_RETRIES="${AGENTS_HTTP_RETRIES:-3}"
export AGENTS_HTTP_RETRY_BACKOFF="${AGENTS_HTTP_RETRY_BACKOFF:-0.6}"
export AGENTS_IMAGE_FILTER_ENABLED="${AGENTS_IMAGE_FILTER_ENABLED:-true}"
export AGENTS_IMAGE_FILTER_STRIP_QUERY_FOR_DEDUPE="${AGENTS_IMAGE_FILTER_STRIP_QUERY_FOR_DEDUPE:-true}"
export AGENTS_IMAGE_FILTER_MAX_IMAGES="${AGENTS_IMAGE_FILTER_MAX_IMAGES:-0}"
export AGENTS_IMAGE_FILTER_EXCLUDE_KEYWORDS="${AGENTS_IMAGE_FILTER_EXCLUDE_KEYWORDS:-logo,icon,placeholder,sprite,swatch,avatar,badge,favicon,caveira}"
export AGENTS_SENTRY_DSN="${AGENTS_SENTRY_DSN:-}"
export AGENTS_SENTRY_ENVIRONMENT="${AGENTS_SENTRY_ENVIRONMENT:-production}"
export AGENTS_SENTRY_TRACES_SAMPLE_RATE="${AGENTS_SENTRY_TRACES_SAMPLE_RATE:-0.0}"
export AGENTS_SENTRY_SEND_DEFAULT_PII="${AGENTS_SENTRY_SEND_DEFAULT_PII:-false}"

echo "Deploying agents commit: ${short_sha}"
echo "Agents image: ${AGENTS_IMAGE}"
echo "Dagster storage path: ${DAGSTER_STORAGE_PATH}"

if [ -n "${GHCR_TOKEN:-}" ] && [ -n "${GHCR_USER:-}" ]; then
  echo "== Logging in to GHCR =="
  printf "%s\n" "$GHCR_TOKEN" | docker login "$REGISTRY" -u "$GHCR_USER" --password-stdin
fi

echo "== Preparing persistent Dagster directories =="
sudo mkdir -p "$DAGSTER_STORAGE_PATH"
sudo chown -R 10001:10001 "$DAGSTER_STORAGE_PATH"

echo "== Pulling immutable agents image =="
docker compose -f "$COMPOSE_FILE" pull dagster-code-server dagster-webserver dagster-daemon

echo "== Starting Dagster services =="
docker compose -f "$COMPOSE_FILE" up -d --no-build dagster-code-server dagster-webserver dagster-daemon

webserver_container="$(docker compose -f "$COMPOSE_FILE" ps -q dagster-webserver)"
./infra/deploy/wait-health.sh "$webserver_container" "${DAGSTER_HEALTH_ATTEMPTS:-30}" "${DAGSTER_HEALTH_INTERVAL:-10}"

echo "== Pruning unused images =="
docker image prune -f

echo "== Final agents compose state =="
docker compose -f "$COMPOSE_FILE" ps
