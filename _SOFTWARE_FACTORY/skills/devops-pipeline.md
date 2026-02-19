---
name: devops-pipeline
description: >
  Guides the agent through CI/CD pipeline design, Docker configuration, Nginx setup,
  health checks, monitoring, and deployment strategies. Use this skill when building
  or reviewing deployment infrastructure, container configurations, or operational
  tooling.
metadata:
  category: ops
  triggers:
    - "when user asks to set up CI/CD"
    - "when configuring Docker or containers"
    - "when setting up Nginx reverse proxy"
    - "when implementing health checks"
    - "when user asks about deployment or rollback strategies"
    - "when configuring monitoring or logging"
---

# DevOps Pipeline

This skill enables the agent to design and implement CI/CD pipelines, Docker configurations,
Nginx setups, health checks, monitoring, and deployment strategies.

## Use this skill when

- Setting up or improving CI/CD pipelines
- Writing Dockerfiles and docker-compose configurations
- Configuring Nginx as a reverse proxy
- Implementing health check endpoints
- Setting up logging and monitoring
- Designing deployment and rollback strategies

## Do not use this skill when

- Writing application code (use development skills)
- Doing security audits (use security-audit)
- Managing project tasks (use project-management)

## Instructions

### CI/CD Pipeline Design

#### GitHub Actions Workflow

```yaml
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck

  test:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: 'npm' }
      - run: npm ci
      - run: npm run test:ci
        env:
          DATABASE_URL: postgres://postgres:test@localhost:5432/test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage
          path: coverage/

  build:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - name: Deploy to production
        run: |
          # SSH and pull new image
          ssh ${{ secrets.DEPLOY_HOST }} << 'EOF'
            docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
            docker compose up -d --no-deps app
            # Wait for health check
            for i in $(seq 1 30); do
              if curl -sf http://localhost:3000/health; then
                echo "Deployment successful"
                exit 0
              fi
              sleep 2
            done
            echo "Health check failed, rolling back"
            docker compose rollback
            exit 1
          EOF
```

### Docker Multi-Stage Build

```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production=false

# Stage 2: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
RUN npm prune --production

# Stage 3: Production
FROM node:20-alpine AS runner
WORKDIR /app

# Security: non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 appuser

COPY --from=builder --chown=appuser:nodejs /app/dist ./dist
COPY --from=builder --chown=appuser:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=appuser:nodejs /app/package.json ./

USER appuser
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - '3000:3000'
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgres://app:${DB_PASSWORD}@db:5432/app
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'

  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U postgres']
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - '80:80'
      - '443:443'
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - app
    restart: unless-stopped

volumes:
  pgdata:
```

### Nginx Configuration

```nginx
upstream app_backend {
    server app:3000;
    keepalive 32;
}

server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self';" always;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1000;

    # Static files
    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass http://app_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    # Health check (no logging)
    location /health {
        proxy_pass http://app_backend;
        access_log off;
    }
}
```

### Health Check Endpoint

```typescript
// health.ts
app.get('/health', async (req, res) => {
  const checks = {
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
    checks: {
      database: 'unknown',
      redis: 'unknown',
    },
  };

  try {
    await db.query('SELECT 1');
    checks.checks.database = 'ok';
  } catch (e) {
    checks.checks.database = 'error';
    checks.status = 'degraded';
  }

  try {
    await redis.ping();
    checks.checks.redis = 'ok';
  } catch (e) {
    checks.checks.redis = 'error';
    checks.status = 'degraded';
  }

  const statusCode = checks.status === 'ok' ? 200 : 503;
  res.status(statusCode).json(checks);
});
```

### Graceful Shutdown

```typescript
const server = app.listen(3000);

async function gracefulShutdown(signal: string) {
  console.log(`Received ${signal}, starting graceful shutdown...`);

  // Stop accepting new connections
  server.close(() => {
    console.log('HTTP server closed');
  });

  // Wait for in-flight requests (max 30s)
  const timeout = setTimeout(() => {
    console.error('Forced shutdown after timeout');
    process.exit(1);
  }, 30000);

  try {
    await db.disconnect();
    await redis.quit();
    clearTimeout(timeout);
    console.log('Graceful shutdown complete');
    process.exit(0);
  } catch (err) {
    console.error('Error during shutdown:', err);
    process.exit(1);
  }
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

### Rollback Strategy

1. **Image tagging**: Every deploy uses a specific SHA tag
2. **Quick rollback**: `docker compose pull app && docker compose up -d app` with previous tag
3. **Database migrations**: Always write reversible migrations
4. **Feature flags**: Use flags to toggle features without redeploying
5. **Blue-green**: Run two versions, switch traffic via Nginx upstream

## Output Format

```
## Pipeline Review: [Project Name]
### CI Status
- Lint: ✅ | Test: ✅ | Build: ✅ | Deploy: ✅

### Infrastructure
- Container: [Docker config assessment]
- Reverse proxy: [Nginx assessment]
- Health checks: [Implementation status]
- Monitoring: [Tools and coverage]

### Recommendations
1. [Priority fix]
2. [Improvement]
```

## Anti-patterns

- **NEVER** deploy without health checks
- **NEVER** run containers as root
- **NEVER** store secrets in Docker images or Compose files
- **NEVER** skip graceful shutdown — it causes dropped requests
- **NEVER** deploy without rollback capability
- **NEVER** use `latest` tag in production — use specific SHAs
- **NEVER** skip CI steps to "deploy faster"
- **NEVER** ignore container resource limits — set memory and CPU
