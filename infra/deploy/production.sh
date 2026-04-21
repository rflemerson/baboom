#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ROOT_DIR:-/home/ubuntu/app/baboom}"
REGISTRY="${REGISTRY:?REGISTRY is required}"
IMAGE_OWNER="${IMAGE_OWNER:?IMAGE_OWNER is required}"

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

echo "Deploying commit: ${short_sha}"
echo "API image: ${API_IMAGE}"
echo "Web image: ${WEB_IMAGE}"

if [ -n "${GHCR_TOKEN:-}" ] && [ -n "${GHCR_USER:-}" ]; then
  echo "== Logging in to GHCR =="
  printf "%s\n" "$GHCR_TOKEN" | docker login "$REGISTRY" -u "$GHCR_USER" --password-stdin
fi

echo "== Pulling immutable images =="
docker compose pull api web celery celery-beat redis

echo "== Starting web and API =="
docker compose up -d --no-build web api
./infra/deploy/wait-health.sh baboom-api-1 "${API_HEALTH_ATTEMPTS:-30}" "${API_HEALTH_INTERVAL:-10}"

echo "== Starting workers =="
docker compose up -d --no-build celery celery-beat

echo "== Reloading edge proxy =="
docker compose up -d --no-build --force-recreate --no-deps nginx

echo "== Pruning unused images =="
docker image prune -f

echo "== Final compose state =="
docker compose ps
