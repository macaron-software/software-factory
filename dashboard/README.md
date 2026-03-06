# Software Factory Dashboard

Lightweight monitoring dashboard for the Software Factory platform.

## 🎯 Overview

Web interface to monitor projects, tasks, daemons, and deployments across multiple environments (Azure, OVH, Local).

**Tech Stack:** FastAPI + Jinja2 + HTMX + Tailwind CSS

## 🚀 Quick Start

### Installation

```bash
# From Software Factory root
cd _SOFTWARE_FACTORY/dashboard

# Install dependencies (inherits from platform)
pip install -r ../platform/requirements.txt

# Or standalone
pip install fastapi uvicorn jinja2 pyyaml
```

### Running

```bash
# Method 1: Python module
python3 -m dashboard.server

# Method 2: Direct execution
python3 server.py

# Method 3: Via factory CLI (if available)
factory dashboard
```

**Access:** http://localhost:8080

## 📊 Features

### 1. Project Monitoring
- List all projects with statistics
- View project details and metrics
- Track tasks per project
- Real-time log streaming (SSE)

### 2. Environment Status
- Monitor remote environments (Azure, OVH)
- Check deployment status (online/offline)
- SSH connectivity checks
- Version comparison (local vs remote)

### 3. Daemon Management
- Start/stop daemons remotely
- Monitor daemon status
- PID tracking

### 4. RTK Integration
- Token savings statistics
- Command history
- Efficiency metrics (60-90% token reduction)

## 🔧 Configuration

### Environment Variables

```bash
# Server configuration
DASHBOARD_PORT=8080              # Server port (default: 8080)
DASHBOARD_HOST=0.0.0.0          # Bind host (default: 127.0.0.1)
DASHBOARD_DEBUG=false           # Debug mode (default: false)

# Database
DASHBOARD_DB_PATH=/path/to/db   # SQLite database path (default: ../data/factory.db)

# RTK Integration
RTK_DB_PATH=/path/to/rtk.db     # RTK history database (auto-detected)

# Logging
DASHBOARD_LOG_LEVEL=INFO        # Log level (default: WARNING)
```

### Configuration File

Projects are configured via YAML files in `../projects/*.yaml`:

```yaml
name: my-project
repository: https://github.com/user/repo
environments:
  - name: production
    url: https://prod.example.com
    ssh_host: prod.example.com
  - name: staging
    url: https://staging.example.com
```

## 🌐 API Endpoints

### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project details |
| GET | `/api/stats` | Global statistics |
| GET | `/api/metrics/{id}` | Project metrics |
| GET | `/api/deploy/status` | Deployment status |
| GET | `/api/daemons` | List daemons |
| POST | `/api/daemons/{id}/{daemon}/start` | Start daemon |
| POST | `/api/daemons/{id}/{daemon}/stop` | Stop daemon |
| GET | `/api/tasks` | List tasks |
| GET | `/api/logs/{id}/stream` | Stream logs (SSE) |
| GET | `/health` | Health check |

### Web Pages

| Path | Description |
|------|-------------|
| `/` | Main dashboard |
| `/live` | Real-time monitoring |
| `/project/{id}` | Project details |
| `/tasks` | Task management |

## 🧪 Development

### Local Development

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run with auto-reload
uvicorn server:app --reload --port 8080

# Run tests
pytest tests/

# Check code quality
ruff check .
```

### Project Structure

```
dashboard/
├── server.py           # FastAPI application (977 lines)
├── templates/          # Jinja2 templates
│   ├── base.html      # Base layout
│   ├── index.html     # Dashboard home
│   ├── live.html      # Real-time view
│   ├── project.html   # Project details
│   └── tasks.html     # Task list
├── static/            # Static assets
│   └── agentic_patterns.html
└── tests/             # Unit tests (TODO)
```

## 🐳 Docker

### Standalone Deployment

```bash
# Build image
docker build -t sf-dashboard .

# Run container
docker run -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e DASHBOARD_PORT=8080 \
  sf-dashboard
```

### Docker Compose

```yaml
version: '3.8'
services:
  dashboard:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ../data:/app/data
      - ../projects:/app/projects
    environment:
      - DASHBOARD_PORT=8080
```

## 📈 Monitoring

### Health Check

```bash
curl http://localhost:8080/health
# Response: {"status": "healthy", "version": "1.0.0"}
```

### Metrics

- Project count
- Active tasks
- Daemon status
- Environment health
- RTK token savings

## 🔒 Security

### Current Setup
- Local development only (127.0.0.1)
- No authentication (internal use)
- No rate limiting

### Production Recommendations
1. Add authentication (JWT/OAuth)
2. Enable HTTPS
3. Add rate limiting
4. Restrict CORS
5. Validate all inputs

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Find process
lsof -i :8080

# Kill process
kill -9 <PID>
```

### Database Not Found

```bash
# Check path
ls -la ../data/factory.db

# Create if missing
python3 -c "import sqlite3; sqlite3.connect('../data/factory.db')"
```

### Templates Not Found

```bash
# Check working directory
cd dashboard/

# Verify templates
ls -la templates/
```

## 📚 Dependencies

**Core:**
- fastapi>=0.104
- uvicorn[standard]>=0.24
- jinja2>=3.1
- pyyaml>=6.0
- aiohttp>=3.8

**Optional:**
- opentelemetry-* (monitoring)
- prometheus-client (metrics)

## 🤝 Contributing

This is an internal tool for Software Factory monitoring. For contributions:

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Test with `rtk` commands to save tokens

## 📄 License

Part of Software Factory - AGPL-3.0

## 🔗 Related

- [Software Factory Platform](../platform/) - Main platform
- [RTK](https://github.com/rtk-ai/rtk) - Token optimization
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [HTMX](https://htmx.org/) - Dynamic HTML
