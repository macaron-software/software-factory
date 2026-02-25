# API Reference

Base URL: `http://<host>:<port>`  
Auth: Bearer token (`MACARON_API_KEY`). GET endpoints are public; mutations require auth.  
Format: dual JSON + form-data (auto-detected via `_parse_body`).  
Swagger: `/docs` (FastAPI auto-generated).

## Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List projects |

## Missions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/missions` | Create mission |
| POST | `/api/missions/{id}/start` | Start mission |
| POST | `/api/missions/{id}/run` | Run phase |
| POST | `/api/missions/{id}/wsjf` | Set WSJF scores |
| POST | `/api/missions/{id}/sprints` | Create sprint |
| POST | `/api/missions/{id}/validate` | Validate phase |
| GET | `/api/missions/{id}` | Get mission details |

## Epics / Features / Stories

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/epics/{id}/features` | Create feature under epic |
| POST | `/api/features/{id}/stories` | Create story under feature |
| POST | `/api/features/{id}/deps` | Add dependency |
| PATCH | `/api/features/{id}` | Update feature |
| PATCH | `/api/stories/{id}` | Update story |
| PATCH | `/api/tasks/{id}/status` | Update task status |
| PATCH | `/api/backlog/reorder` | Reorder backlog |
| DELETE | `/api/features/{id}/deps/{dep}` | Remove dependency |
| DELETE | `/api/sprints/{id}/stories/{id}` | Remove story from sprint |
| GET | `/api/sprints/{id}/available-stories` | List unassigned stories |
| GET | `/api/features/{id}/deps` | Get dependencies |

## Metrics & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/metrics/cycle-time` | Cycle time metrics |
| GET | `/api/releases/{project_id}` | Release history |
| GET | `/api/llm/stats` | LLM usage statistics |
| GET | `/api/llm/traces` | LLM call traces |
| GET | `/api/monitoring/live` | Live monitoring (SSE) |

## System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/agents` | List agents |
| GET | `/api/sessions` | List sessions |
| GET | `/api/mcps` | List MCP servers |
| GET | `/docs` | Swagger UI |

## SSE Streams

| Endpoint | Description |
|----------|-------------|
| `/api/missions/{id}/stream` | Mission execution events |
| `/api/monitoring/live` | System monitoring events |

## 🇫🇷 [Référence API (FR)](API-Reference‐FR) · 🇪🇸 [ES](API-Reference‐ES) · 🇩🇪 [DE](API-Reference‐DE)
