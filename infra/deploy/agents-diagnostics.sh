#!/usr/bin/env sh
set -eu

compose_file="${COMPOSE_FILE:-docker-compose.agents.yml}"

echo "== agents compose ps =="
docker compose -f "$compose_file" ps || true

webserver_container="$(docker compose -f "$compose_file" ps -q dagster-webserver || true)"
if [ -n "$webserver_container" ]; then
  echo "== dagster webserver health =="
  docker inspect "$webserver_container" --format "{{json .State.Health}}" || true

  echo "== dagster webserver logs =="
  docker logs --tail="${DEPLOY_LOG_LINES:-200}" "$webserver_container" || true
fi

daemon_container="$(docker compose -f "$compose_file" ps -q dagster-daemon || true)"
if [ -n "$daemon_container" ]; then
  echo "== dagster daemon logs =="
  docker logs --tail="${DEPLOY_LOG_LINES:-200}" "$daemon_container" || true
fi
