#!/bin/bash
# Zero-downtime deploy: build image FIRST, then swap container
set -e
cd /opt/macaron

COMPOSE="docker compose --env-file .env -f platform/deploy/docker-compose-vm.yml"

echo "[deploy] Building new image (old container stays running)..."
$COMPOSE build platform

echo "[deploy] Swapping container (fast restart)..."
$COMPOSE up -d --no-build --force-recreate platform

echo "[deploy] Waiting for healthy..."
for i in $(seq 1 30); do
    STATUS=$(docker inspect deploy-platform-1 --format='{{.State.Health.Status}}' 2>/dev/null || echo "missing")
    if [ "$STATUS" = "healthy" ]; then
        echo "[deploy] Platform healthy after ${i}s"
        exit 0
    fi
    sleep 2
done

echo "[deploy] WARNING: not healthy after 60s, check logs:"
docker logs deploy-platform-1 --tail 10 2>&1
exit 1
