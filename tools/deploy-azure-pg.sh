#!/bin/bash
# deploy-azure-pg.sh — Run on Azure VM when SSH is accessible
# Usage: ssh macaron@4.233.64.30 "bash -s" < deploy-azure-pg.sh
set -e

cd /opt/macaron

echo "=== 1. Git pull ==="
git pull origin main 2>&1 | tail -5

echo "=== 2. Backup SQLite ==="
mkdir -p ~/az-backups
docker cp platform-platform-1:/app/data/platform.db ~/az-backups/platform-sqlite-az-$(date +%Y%m%d-%H%M%S).db 2>/dev/null \
  && echo "SQLite backed up" || echo "No SQLite in container"

echo "=== 3. Add PG vars to .env ==="
grep -q "^PG_USER=" .env || cat >> .env << 'ENVEOF'
PG_USER=macaron
PG_PASSWORD=macaron_pg_az_2024
PG_DB=macaron_platform
ENVEOF
echo "PG vars OK"

echo "=== 4. Start PG service ==="
docker compose -f platform/deploy/docker-compose-vm.yml up -d postgres 2>&1 | tail -5

echo "=== 5. Wait for PG ready ==="
for i in $(seq 1 30); do
  docker compose -f platform/deploy/docker-compose-vm.yml exec -T postgres \
    pg_isready -U macaron -d macaron_platform 2>/dev/null && echo "PG ready!" && break
  sleep 3; echo "waiting $i/30..."
done

echo "=== 6. Init PG schema ==="
docker run --rm \
  --network deploy_default \
  -v $(pwd):/app \
  -e PGPASSWORD='macaron_pg_az_2024' \
  postgres:16-alpine \
  psql -h postgres -U macaron -d macaron_platform -f /app/platform/db/schema_pg.sql 2>&1 | tail -5

echo "=== 7. Start PG proxy for migration ==="
docker run --rm -d --name pg-proxy-az \
  --network deploy_default \
  -p 5436:5432 \
  alpine/socat \
  TCP-LISTEN:5432,fork,reuseaddr TCP:deploy-postgres-1:5432

sleep 2

echo "=== 8. Install psycopg and migrate ==="
pip3 install psycopg[binary] psycopg-pool --break-system-packages -q 2>/dev/null || true

SQLITE_FILE=$(ls ~/az-backups/*.db | sort | tail -1)
DATABASE_URL="postgresql://macaron:macaron_pg_az_2024@localhost:5436/macaron_platform" \
SQLITE_PATH="$SQLITE_FILE" \
python3 tools/migrate_sqlite_to_pg.py 2>&1

docker stop pg-proxy-az 2>/dev/null || true

echo "=== 9. Rebuild platform with PG ==="
docker compose -f platform/deploy/docker-compose-vm.yml up --build -d 2>&1 | tail -10

echo "=== 10. Health check ==="
sleep 20
curl -s http://localhost:8090/api/health

echo ""
echo "=== Done! ==="
