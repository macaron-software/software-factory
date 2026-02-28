#!/bin/bash
# Setup nginx vhost + HTTPS cert for analytics.macaron-software.com
# Run this on OVH demo server once DNS A record is added:
#   analytics.macaron-software.com → 54.36.183.124
#
# Usage: sudo bash setup-analytics-nginx.sh

set -e

DOMAIN="analytics.macaron-software.com"
UMAMI_PORT="3001"

echo "=== Setting up nginx vhost for $DOMAIN ==="

# Create nginx vhost for HTTP (needed for certbot challenge)
cat > /etc/nginx/sites-available/$DOMAIN << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$UMAMI_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
nginx -t && systemctl reload nginx

echo "=== Running certbot for $DOMAIN ==="
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@macaron-software.com

echo "=== Enabling + starting fail2ban (if not running) ==="
systemctl enable fail2ban
systemctl start fail2ban
# Unban local admin IP if needed
fail2ban-client unban 185.185.208.46 2>/dev/null || true

echo "=== Done! Umami available at https://$DOMAIN ==="
echo "   Umami tracking: https://$DOMAIN/script.js"
