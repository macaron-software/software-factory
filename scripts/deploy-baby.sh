#!/bin/bash
# deploy-baby.sh — Deploy SF-Baby on OVH VPS
# Run from /opt/software-factory on the OVH VPS
#
# First-time setup:  ./scripts/deploy-baby.sh setup
# Deploy/update:     ./scripts/deploy-baby.sh deploy
# Status:            ./scripts/deploy-baby.sh status
# Logs:              ./scripts/deploy-baby.sh logs
set -e

COMPOSE="docker compose -f docker-compose.yml -f docker-compose-baby.yml"
DOMAIN="sf-baby.macaron-software.com"

cd /opt/software-factory

case "${1:-deploy}" in
  setup)
    echo "=== SF-Baby first-time setup ==="

    # 1. Create .env.baby if missing
    if [ ! -f .env.baby ]; then
      cat > .env.baby <<'EOF'
# SF-Baby — MiniMax M2.5
MINIMAX_API_KEY=REPLACE_WITH_YOUR_KEY
PG_USER=macaron
PG_PASSWORD=macaron_pg_ovh_2024
MACARON_API_KEY=baby-sf-key
SF_DEMO_EMAIL=admin@demo.local
SF_DEMO_PASSWORD=demo123
SANDBOX_ENABLED=true
LANDLOCK_ENABLED=auto
EOF
      echo "[setup] Created .env.baby — edit with your MiniMax key, then re-run setup"
      exit 1
    fi

    # 2. Create slot directories
    echo "[setup] Creating slot directories..."
    mkdir -p slots/baby-ui slots/baby-factory

    # 3. Copy platform code to baby slots
    echo "[setup] Copying platform to baby slots..."
    ACTIVE=$(cat active-slot 2>/dev/null || echo "blue")
    if [ -d "slots/$ACTIVE" ]; then
      cp -r "slots/$ACTIVE/." slots/baby-ui/
      cp -r "slots/$ACTIVE/." slots/baby-factory/
      echo "[setup] Copied from $ACTIVE slot"
    fi

    # 4. Copy docker-compose-baby.yml overlay
    if [ ! -f docker-compose-baby.yml ]; then
      cp platform/deploy/docker-compose-baby.yml docker-compose-baby.yml
      echo "[setup] Copied docker-compose-baby.yml"
    fi

    # 5. Create database
    echo "[setup] Creating macaron_baby database..."
    CONTAINER=$(docker ps --format '{{.Names}}' | grep postgres | head -1)
    docker exec "$CONTAINER" psql -U macaron -tc \
      "SELECT 1 FROM pg_database WHERE datname='macaron_baby'" | grep -q 1 || \
    docker exec "$CONTAINER" createdb -U macaron macaron_baby
    echo "[setup] Database macaron_baby ready"

    # 6. Build image
    echo "[setup] Building Docker image..."
    $COMPOSE build baby-ui

    # 7. Start services
    echo "[setup] Starting baby-ui + baby-factory..."
    $COMPOSE up -d baby-ui baby-factory

    # 8. Wait for health
    echo "[setup] Waiting for baby-ui on port 8093..."
    for i in $(seq 1 30); do
      if curl -sf http://localhost:8093/api/health >/dev/null 2>&1; then
        echo "[setup] baby-ui healthy after $((i*2))s"
        break
      fi
      sleep 2
    done

    # 9. Install nginx vhost
    echo "[setup] Installing nginx vhost..."
    sudo cp platform/deploy/nginx-baby.conf /etc/nginx/sites-available/sf-baby.macaron-software.com

    # 10. SSL certificate (must have DNS first)
    echo "[setup] Requesting SSL certificate for $DOMAIN..."
    if sudo certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@macaron-software.com 2>/dev/null; then
      echo "[setup] SSL certificate obtained"
    else
      echo "[setup] SSL failed — add DNS A record for $DOMAIN → $(curl -s ifconfig.me) first"
      echo "[setup] Then run: sudo certbot certonly --nginx -d $DOMAIN"
      echo "[setup] Setting up HTTP-only nginx for now..."
      # Temp HTTP-only config
      sudo tee /etc/nginx/sites-available/sf-baby.macaron-software.com > /dev/null <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://localhost:8093;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
    fi

    # 11. Enable site + reload nginx
    sudo ln -sf /etc/nginx/sites-available/sf-baby.macaron-software.com /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    echo "[setup] nginx reloaded"

    echo ""
    echo "=== SF-Baby setup complete ==="
    echo "  URL:     https://$DOMAIN (or http:// if SSL pending)"
    echo "  UI port: 8093"
    echo "  Factory: 8094"
    echo "  DB:      macaron_baby"
    echo "  LLM:     MiniMax M2.5"
    echo ""
    ;;

  deploy)
    echo "=== SF-Baby deploy ==="
    $COMPOSE build baby-ui baby-factory
    echo "[deploy] Swapping containers..."
    $COMPOSE up -d --no-build --force-recreate baby-ui baby-factory
    echo "[deploy] Waiting for health..."
    for i in $(seq 1 30); do
      if curl -sf http://localhost:8093/api/health >/dev/null 2>&1; then
        echo "[deploy] baby-ui healthy after $((i*2))s"
        exit 0
      fi
      sleep 2
    done
    echo "[deploy] WARNING: not healthy after 60s"
    docker logs software-factory-baby-ui-1 --tail 20 2>&1
    exit 1
    ;;

  status)
    echo "=== SF-Baby status ==="
    $COMPOSE ps baby-ui baby-factory 2>/dev/null
    echo ""
    curl -sf http://localhost:8093/api/health 2>/dev/null && echo "UI:      healthy" || echo "UI:      down"
    curl -sf http://localhost:8094/api/health 2>/dev/null && echo "Factory: healthy" || echo "Factory: down"
    ;;

  logs)
    docker logs software-factory-baby-ui-1 --tail 50 2>&1
    ;;

  stop)
    echo "Stopping SF-Baby..."
    $COMPOSE stop baby-ui baby-factory
    ;;

  *)
    echo "Usage: $0 {setup|deploy|status|logs|stop}"
    exit 1
    ;;
esac
