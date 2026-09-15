#!/usr/bin/env sh
set -eu

# Runs on either machine, so it reports whatever baboom containers exist here
# rather than assuming the web machine's services.
echo "== containers =="
docker ps -a --filter "name=baboom" --format "table {{.Names}}\t{{.Status}}" || true

if docker inspect baboom-api-1 >/dev/null 2>&1; then
  echo "== api health =="
  docker inspect baboom-api-1 --format "{{json .State.Health}}" || true
fi

for name in $(docker ps -a --filter "name=baboom" --format "{{.Names}}"); do
  echo "== ${name} logs =="
  docker logs --tail="${DEPLOY_LOG_LINES:-100}" "$name" || true
done
