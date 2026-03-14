# Observability, API, Data, DR — Deep Skill
# Production readiness for SF Platform

## WHEN TO ACTIVATE
Setting up monitoring, designing APIs, handling data lifecycle, planning disaster recovery,
or any production infrastructure work.

---

## OBSERVABILITY — OTEL + Metrics + Alerts

### OpenTelemetry Integration
```python
# Traces: distributed request tracking
from opentelemetry import trace
tracer = trace.get_tracer("sf-platform")

with tracer.start_as_current_span("mission.execute") as span:
    span.set_attribute("mission.id", mission_id)
    span.set_attribute("mission.phase", phase_name)
    span.set_attribute("agent.id", agent_id)
    result = execute_phase(...)
    span.set_attribute("phase.status", result.status)
```

### Key Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `mission.duration_seconds` | Histogram | Total mission execution time |
| `phase.duration_seconds` | Histogram | Per-phase execution time |
| `agent.execution_count` | Counter | Agent invocations |
| `adversarial.reject_count` | Counter | Adversarial rejections by check type |
| `llm.request_duration` | Histogram | LLM API latency per provider |
| `llm.token_usage` | Counter | Token consumption per provider/model |
| `llm.fallback_count` | Counter | Provider fallback events |
| `tool.execution_count` | Counter | Tool calls per tool type |
| `quality.score` | Gauge | Quality score per project |
| `traceability.coverage_pct` | Gauge | Traceability coverage per project |

### Alerting Rules
```yaml
# Critical — page immediately
- alert: MissionStuck
  expr: mission_duration_seconds > 7200  # 2h
  severity: critical
  
- alert: LLMAllProvidersFailing
  expr: llm_fallback_count > 10 in 5m
  severity: critical

- alert: HighAdversarialRejectRate
  expr: rate(adversarial_reject_count[10m]) > 0.8
  severity: warning

- alert: DatabaseConnectionExhausted
  expr: pg_active_connections > pg_max_connections * 0.9
  severity: critical

# Warning — investigate
- alert: QualityScoreDropped
  expr: quality_score < 0.5
  severity: warning

- alert: TraceabilityCoveragelow
  expr: traceability_coverage_pct < 0.6
  severity: warning
```

### Health Endpoints
- `GET /api/health` — DB + Redis connectivity, response time
- `GET /api/ready` — Returns 503 during drain (for nginx proxy_next_upstream)
- `GET /api/metrics` — Prometheus-format metrics export

---

## API — OpenAPI Spec + Versioning + Rate Limits

### OpenAPI Standards
```yaml
openapi: 3.1.0
info:
  title: SF Platform API
  version: 2.0.0
  description: Multi-agent orchestration platform API
servers:
  - url: https://api.sf.macaron-software.com/api
    description: Production
```

### Versioning Strategy
- URL-based: `/api/v2/missions/` (breaking changes)
- Header-based: `Accept: application/vnd.sf.v2+json` (content negotiation)
- Current: v1 (implicit), v2 when breaking changes needed
- Deprecation: 6-month notice with `Sunset` header + docs

### Rate Limits
| Endpoint Category | Limit | Window | Scope |
|-------------------|-------|--------|-------|
| Auth (login/register) | 5 | 1 min | IP + account |
| API Read | 60 | 1 min | User |
| API Write | 30 | 1 min | User |
| LLM-heavy (missions) | 5 | 1 min | User |
| Webhooks | 100 | 1 min | IP |
| Health/Ready | unlimited | - | - |

Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
429 response with `Retry-After` header.

### API Documentation
- Auto-generated from FastAPI routes (Swagger UI at `/docs`)
- Structured error responses: `{"error": "message", "code": "ERR_CODE", "details": {...}}`
- Authentication: JWT Bearer token in `Authorization` header

---

## DATA — GDPR Lifecycle + Backup/Restore

### GDPR Data Lifecycle
```
Collection → Processing → Storage → Retention → Deletion
    ↓           ↓           ↓          ↓           ↓
  Consent    Purpose      Encrypt    Policy     Purge
  Minimize   Audit log    Access     30/90/365  Verify
  Notice     Lawful base  Backup     Review     Certify
```

### Data Classification
| Level | Examples | Retention | Encryption |
|-------|----------|-----------|------------|
| Public | Docs, skills, patterns | Indefinite | At rest |
| Internal | Agent configs, workflows | 2 years | At rest + transit |
| Confidential | User data, sessions | 90 days | At rest + transit + field |
| Restricted | Auth tokens, secrets | 30 days | HSM + field-level |

### Right to Erasure (GDPR Art. 17)
```python
async def gdpr_delete_user(user_id: str):
    # 1. Delete personal data
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    # 2. Anonymize audit logs (keep structure)
    db.execute("UPDATE admin_audit_log SET user_id = 'DELETED' WHERE user_id = ?", (user_id,))
    # 3. Delete sessions
    db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    # 4. Delete from backups (within retention window)
    schedule_backup_purge(user_id)
    # 5. Log the deletion (without PII)
    log_audit("gdpr_erasure", {"user_ref": hash(user_id)})
```

### Backup Strategy
```
Continuous: PG WAL streaming → standby (RPO ~0)
Hourly:     pg_dump --format=custom → S3/Object storage
Daily:      Full backup + verify restore
Weekly:     Cross-region replication check
Monthly:    Restore drill (test full recovery)
```

### Backup Retention
- Hourly: 48 hours
- Daily: 30 days
- Weekly: 90 days
- Monthly: 1 year

---

## DR — RTO/RPO + Failover

### Recovery Targets
| Tier | RTO | RPO | Examples |
|------|-----|-----|----------|
| Critical | 15 min | 0 (sync) | Auth, DB, API gateway |
| Important | 1 hour | 5 min | Mission execution, SSE |
| Standard | 4 hours | 1 hour | Analytics, evolution, traceability sweep |
| Low | 24 hours | 24 hours | Skill health, Darwin tournament |

### Failover Architecture
```
                    ┌─────────────┐
                    │  nginx LB   │ (n2: 40.89.174.75)
                    │ health check │
                    └──────┬──────┘
                    ┌──────┴──────┐
              ┌─────┴─────┐ ┌─────┴─────┐
              │  Node 1   │ │  Node 2   │
              │ (primary) │ │ (standby) │
              │ :8090     │ │ :8090     │
              └─────┬─────┘ └─────┬─────┘
                    └──────┬──────┘
              ┌────────────┴────────────┐
              │   PG16 + Redis7 (n3)   │
              │   WAL streaming        │
              │   10.0.1.6             │
              └────────────────────────┘
```

### Failover Procedures
1. **Node failure**: nginx `proxy_next_upstream http_503` auto-routes
2. **DB failure**: Promote standby, update connection strings, verify WAL
3. **Full site failure**: DNS failover to OVH (blue-green), restore from backup
4. **LLM provider failure**: Auto-fallback chain (azure→minimax→local)

### Blue-Green Deployment
```bash
# Current: blue active, green standby
# Deploy to green:
rsync -avz platform/ green:/opt/software-factory/slots/green/
# Health check green:
curl green:8090/api/health
# Switch nginx upstream:
sed -i 's/blue/green/' /etc/nginx/conf.d/upstream.conf
nginx -s reload
# Rollback if needed: switch back to blue
```

### DR Testing Schedule
- Weekly: Health probe verification
- Monthly: Single node failover drill
- Quarterly: Full DR drill (DB restore + app recovery)
- Annually: Cross-region failover test
