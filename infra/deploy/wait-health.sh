#!/usr/bin/env sh
set -eu

service="${1:?usage: wait-health.sh <container-name> [attempts] [sleep-seconds]}"
attempts="${2:-30}"
sleep_seconds="${3:-10}"

echo "== Waiting for ${service} health =="

attempt=1
while [ "$attempt" -le "$attempts" ]; do
  status="$(
    docker inspect "$service" \
      --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" \
      2>/dev/null || true
  )"

  echo "${service} health attempt ${attempt}/${attempts}: ${status:-not-created}"

  if [ "$status" = "healthy" ]; then
    exit 0
  fi

  attempt=$((attempt + 1))
  sleep "$sleep_seconds"
done

echo "::error::${service} did not become healthy within $((attempts * sleep_seconds)) seconds"
docker inspect "$service" --format "{{json .State.Health}}" || true
docker logs --tail="${DEPLOY_LOG_LINES:-200}" "$service" || true
exit 1
