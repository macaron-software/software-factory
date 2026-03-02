"""
Database migrations and initialization for the platform.
Supports dual backend: SQLite (local) / PostgreSQL (production).
Backend selected via DATABASE_URL env var.
"""

import sqlite3
from pathlib import Path

from ..config import DATA_DIR, DB_PATH
from .adapter import get_connection, is_postgresql

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
SCHEMA_PG_PATH = Path(__file__).parent / "schema_pg.sql"

_USE_PG = is_postgresql()

# Increment this when adding new migration blocks (SQLite or PG).
_SCHEMA_VERSION = 2


def get_schema_version() -> int:
    """Return the schema version recorded in the DB (0 if not yet tracked)."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def _bump_schema_version(conn, version: int) -> None:
    """Record the applied schema version (idempotent)."""
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,)
        )
    except Exception:
        pass


def _pg_column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a PostgreSQL table."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name=? AND column_name=?",
        (table, column),
    ).fetchone()
    return row is not None


def _pg_table_exists(conn, table: str) -> bool:
    """Check if a table exists in PostgreSQL."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name=?", (table,)
    ).fetchone()
    return row is not None


def init_db(db_path: Path = DB_PATH):
    """Initialize database with schema. Safe to call multiple times."""
    import logging as _logging

    _log = _logging.getLogger(__name__)
    if _USE_PG:
        conn = _init_pg()
        _log.info("DB (PostgreSQL) schema v%s ready", _SCHEMA_VERSION)
        return conn

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Recover from stale WAL left by a crashed previous process
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass

    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)

    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    conn.commit()
    _log.info("DB (SQLite) schema v%s ready", _SCHEMA_VERSION)
    return conn


def _init_pg():
    """Initialize PostgreSQL schema."""
    conn = get_connection()
    schema = SCHEMA_PG_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    _migrate_pg(conn)
    return conn


def _migrate(conn):
    """Run incremental migrations. Safe to call multiple times."""
    if _USE_PG:
        _migrate_pg(conn)
        return

    # SQLite migrations (unchanged)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)").fetchall()}
    if "avatar" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN avatar TEXT DEFAULT ''")
    if "tagline" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN tagline TEXT DEFAULT ''")
    if "motivation" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN motivation TEXT DEFAULT ''")

    try:
        im_cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(ideation_messages)").fetchall()
        }
        if im_cols and "role" not in im_cols:
            conn.execute(
                "ALTER TABLE ideation_messages ADD COLUMN role TEXT DEFAULT ''"
            )
        if im_cols and "target" not in im_cols:
            conn.execute(
                "ALTER TABLE ideation_messages ADD COLUMN target TEXT DEFAULT ''"
            )
    except Exception:
        pass

    try:
        m_cols = {r[1] for r in conn.execute("PRAGMA table_info(missions)").fetchall()}
        for col, default in [
            ("business_value", "0"),
            ("time_criticality", "0"),
            ("risk_reduction", "0"),
            ("job_duration", "1"),
        ]:
            if col not in m_cols:
                conn.execute(
                    f"ALTER TABLE missions ADD COLUMN {col} REAL DEFAULT {default}"
                )
    except Exception:
        pass

    try:
        mr_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(mission_runs)").fetchall()
        }
        if mr_cols and "workspace_path" not in mr_cols:
            conn.execute(
                "ALTER TABLE mission_runs ADD COLUMN workspace_path TEXT DEFAULT ''"
            )
        if mr_cols and "parent_mission_id" not in mr_cols:
            conn.execute(
                "ALTER TABLE mission_runs ADD COLUMN parent_mission_id TEXT DEFAULT ''"
            )
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            epic_id TEXT NOT NULL,
            accepted INTEGER DEFAULT 0,
            rejected INTEGER DEFAULT 0,
            iterations INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, epic_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS retrospectives (
            id TEXT PRIMARY KEY,
            scope TEXT DEFAULT 'epic',
            scope_id TEXT DEFAULT '',
            successes TEXT DEFAULT '[]',
            failures TEXT DEFAULT '[]',
            lessons TEXT DEFAULT '[]',
            improvements TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id TEXT PRIMARY KEY,
            epic_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            acceptance_criteria TEXT DEFAULT '',
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'backlog',
            story_points INTEGER DEFAULT 0,
            assigned_to TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_epic ON features(epic_id)")

    try:
        sp_cols = {r[1] for r in conn.execute("PRAGMA table_info(sprints)").fetchall()}
        if sp_cols:
            if "velocity" not in sp_cols:
                conn.execute(
                    "ALTER TABLE sprints ADD COLUMN velocity INTEGER DEFAULT 0"
                )
            if "planned_sp" not in sp_cols:
                conn.execute(
                    "ALTER TABLE sprints ADD COLUMN planned_sp INTEGER DEFAULT 0"
                )
    except Exception:
        pass

    try:
        m_cols2 = {r[1] for r in conn.execute("PRAGMA table_info(missions)").fetchall()}
        if m_cols2 and "kanban_status" not in m_cols2:
            conn.execute(
                "ALTER TABLE missions ADD COLUMN kanban_status TEXT DEFAULT 'funnel'"
            )
        if m_cols2 and "jira_key" not in m_cols2:
            conn.execute("ALTER TABLE missions ADD COLUMN jira_key TEXT")
    except Exception:
        pass

    try:
        f_cols = {r[1] for r in conn.execute("PRAGMA table_info(features)").fetchall()}
        if f_cols and "completed_at" not in f_cols:
            conn.execute("ALTER TABLE features ADD COLUMN completed_at TEXT")
        if f_cols and "jira_key" not in f_cols:
            conn.execute("ALTER TABLE features ADD COLUMN jira_key TEXT")
    except Exception:
        pass

    # jira_key on user_stories
    try:
        us_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(user_stories)").fetchall()
        }
        if us_cols and "jira_key" not in us_cols:
            conn.execute("ALTER TABLE user_stories ADD COLUMN jira_key TEXT")
    except Exception:
        pass

    # jira_key on tasks
    try:
        t_cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if t_cols and "jira_key" not in t_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN jira_key TEXT")
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS feature_deps (
            feature_id TEXT NOT NULL,
            depends_on TEXT NOT NULL,
            dep_type TEXT DEFAULT 'blocked_by',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (feature_id, depends_on)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS program_increments (
            id TEXT PRIMARY KEY,
            art_id TEXT DEFAULT '',
            number INTEGER DEFAULT 1,
            name TEXT DEFAULT '',
            goal TEXT DEFAULT '',
            status TEXT DEFAULT 'planning',
            start_date TEXT,
            end_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pi_art ON program_increments(art_id)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS confluence_pages (
            mission_id TEXT NOT NULL,
            tab TEXT NOT NULL,
            confluence_page_id TEXT NOT NULL,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (mission_id, tab)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            severity TEXT DEFAULT 'P3',
            category TEXT DEFAULT 'incident',
            status TEXT DEFAULT 'open',
            reporter TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            resolution TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tickets_mission ON support_tickets(mission_id)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_incidents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            severity TEXT DEFAULT 'P3',
            status TEXT DEFAULT 'open',
            source TEXT DEFAULT 'auto',
            error_type TEXT,
            error_detail TEXT,
            mission_id TEXT,
            agent_id TEXT,
            count INTEGER DEFAULT 1,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolution TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_status ON platform_incidents(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_severity ON platform_incidents(severity)"
    )

    # ── Performance indexes ──
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_missions_wsjf ON missions(wsjf_score DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_missions_created ON missions(created_at)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_type ON missions(type)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_missions_workflow ON missions(workflow_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_session_from ON messages(session_id, from_agent)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_toolcalls_session ON tool_calls(session_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sprints_status ON sprints(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_status ON features(status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ideation_project ON ideation_sessions(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ideation_status ON ideation_sessions(status)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mission_runs_parent ON mission_runs(parent_mission_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mission_runs_session ON mission_runs(session_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_created ON platform_incidents(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_scores_agent ON agent_scores(agent_id)"
    )

    # ── Integrations (plugin connectors) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS integrations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            config_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'disconnected',
            last_sync TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_integrations_type ON integrations(type)"
    )

    # ── Custom AI Providers ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_ai_providers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider_type TEXT NOT NULL DEFAULT 'openai-compatible',
            base_url TEXT NOT NULL,
            api_key_encrypted TEXT NOT NULL,
            default_model TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_custom_ai_enabled ON custom_ai_providers(enabled)"
    )

    # ── Notifications (in-app) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            url TEXT DEFAULT '',
            severity TEXT DEFAULT 'info',
            source TEXT DEFAULT '',
            ref_id TEXT DEFAULT '',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(is_read)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at DESC)"
    )

    # Seed default integrations if empty
    existing = conn.execute("SELECT COUNT(*) FROM integrations").fetchone()[0]
    if existing == 0:
        for integ in [
            (
                "jira",
                "Jira",
                "project_management",
                '{"url":"","project_key":"","mode":"import"}',
            ),
            (
                "confluence",
                "Confluence",
                "documentation",
                '{"url":"","space_key":"","auto_publish":["adr","retro"]}',
            ),
            ("xray", "Xray", "test_management", '{"url":"","test_plan_sync":true}'),
            (
                "sonarqube",
                "SonarQube",
                "quality",
                '{"url":"","project_key":"","quality_gate":true}',
            ),
            ("gitlab", "GitLab", "devops", '{"url":"","project_id":"","ci_sync":true}'),
            (
                "azure-devops",
                "Azure DevOps",
                "devops",
                '{"org":"","project":"","boards_sync":true}',
            ),
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO integrations (id, name, type, config_json) VALUES (?,?,?,?)",
                integ,
            )

    # ── Integrations: add category/icon/description/agent_roles columns (v2+) ──
    for col, typedef in [
        ("category", "TEXT DEFAULT 'devops'"),
        ("icon", "TEXT DEFAULT '🔌'"),
        ("description", "TEXT DEFAULT ''"),
        ("agent_roles", "TEXT DEFAULT '[]'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE integrations ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    # ── Seed extended integrations (30+ tools across all agent categories) ──
    _integ_extended = [
        # ── Dev & DevOps ──
        (
            "jira",
            "Jira",
            "project_management",
            "devops",
            "https://cdn.simpleicons.org/jira/white",
            "Jira is the industry-standard project management and issue tracking tool from Atlassian. Agents synchronize tasks and sprints bidirectionally: they create tickets from mission outcomes, update statuses, and read backlog items to align platform work with business priorities. Supports both Jira Cloud and Server.",
            '{"url":"","project_key":"","mode":"import"}',
            '["dev","qa","product","architecture","tma"]',
        ),
        (
            "confluence",
            "Confluence",
            "documentation",
            "devops",
            "https://cdn.simpleicons.org/confluence/white",
            "Confluence is Atlassian's team wiki and knowledge base platform. Agents read architecture guidelines, API contracts, and domain standards from Confluence spaces to automatically inject them into system prompts. Keeps agent context aligned with your latest internal documentation without manual copy-paste.",
            '{"url":"","space_key":"","auto_publish":["adr","retro"]}',
            '["dev","architecture","product","tma"]',
        ),
        (
            "gitlab",
            "GitLab",
            "devops",
            "devops",
            "https://cdn.simpleicons.org/gitlab/white",
            "GitLab is a complete DevOps platform with built-in CI/CD, issue tracking, and container registry. Agents can push code, trigger pipelines, open merge requests, and manage milestones directly. Ideal for self-hosted environments or enterprises with strict data residency requirements.",
            '{"url":"","project_id":"","ci_sync":true}',
            '["dev","architecture","security","qa"]',
        ),
        (
            "azure-devops",
            "Azure DevOps",
            "devops",
            "devops",
            "https://cdn.simpleicons.org/azuredevops/white",
            "Azure DevOps provides boards, repos, pipelines, and artifact feeds in one platform. Agents can read work items from boards, trigger build pipelines, and push results back as comments or status updates. Useful for Microsoft-stack teams using TFVC or Azure Pipelines.",
            '{"org":"","project":"","boards_sync":true}',
            '["dev","architecture","qa"]',
        ),
        (
            "sonarqube",
            "SonarQube",
            "quality",
            "devops",
            "https://cdn.simpleicons.org/sonarqube/white",
            "SonarQube is an open-source static analysis platform for continuous code quality. Agents submit code to SonarQube, read quality gate results, and automatically create fix tasks for blocker and critical issues. Integrates with the security and code-review agent roles.",
            '{"url":"","project_key":"","quality_gate":true}',
            '["dev","architecture","security","qa","reviewer"]',
        ),
        (
            "xray",
            "Xray",
            "test_management",
            "testing",
            "🧪",
            "Test plans, test runs, traceability to requirements.",
            '{"url":"","test_plan_sync":true}',
            '["qa","dev"]',
        ),
        # ── Communication & Alerting ──
        (
            "slack",
            "Slack",
            "communication",
            "communication",
            "https://cdn.simpleicons.org/slack/white",
            "Slack is the leading team messaging platform. Agents send mission completion alerts, error notifications, and progress updates to Slack channels or DMs. Configure per-agent role notification rules to keep teams informed without overwhelming them.",
            '{"webhook_url":"","channel":"#platform","notify_on":["mission_done","incident","deploy"]}',
            '["dev","qa","product","architecture","security","marketing","tma","tmc"]',
        ),
        (
            "teams",
            "Microsoft Teams",
            "communication",
            "communication",
            "https://cdn.simpleicons.org/microsoftteams/white",
            "Microsoft Teams is Microsoft's collaboration platform for chat, calls, and file sharing. Agents post mission summaries, critical alerts, and deployment results as adaptive card messages in Teams channels. Required for Azure-stack enterprises using Teams as the primary communication tool.",
            '{"webhook_url":"","channel":"","tenant_id":""}',
            '["dev","qa","product","architecture","tma","tmc"]',
        ),
        (
            "email-smtp",
            "Email / SMTP",
            "communication",
            "communication",
            "📧",
            "Send reports, alerts, and summaries by email.",
            '{"host":"","port":587,"user":"","from":"","tls":true}',
            '["dev","qa","product","marketing","tma","tmc","security"]',
        ),
        # ── Monitoring / Observability ──
        (
            "grafana",
            "Grafana",
            "monitoring",
            "monitoring",
            "https://cdn.simpleicons.org/grafana/white",
            "Grafana is the leading open-source observability platform for metrics, logs, and traces. Agents can query dashboards, read panel data, and annotate graphs with deployment events or mission outcomes. Essential for MCO agents monitoring production SLAs.",
            '{"url":"","api_key":"","org_id":1}',
            '["dev","architecture","tmc","security"]',
        ),
        (
            "datadog",
            "Datadog",
            "monitoring",
            "monitoring",
            "https://cdn.simpleicons.org/datadog/white",
            "Datadog is a cloud-scale observability platform combining metrics, APM, logs, and security. Agents use it to correlate deployment events with performance regressions, read SLO burn rates, and trigger automated rollback missions on anomaly detection.",
            '{"api_key":"","app_key":"","site":"datadoghq.eu"}',
            '["dev","architecture","tmc","security"]',
        ),
        (
            "sentry",
            "Sentry",
            "monitoring",
            "monitoring",
            "https://cdn.simpleicons.org/sentry/white",
            "Sentry is a real-time error and performance monitoring platform. Agents subscribe to Sentry issue feeds and automatically create TMA missions when new crashes exceed a threshold. Error stack traces are injected into fix agent prompts for faster root cause analysis.",
            '{"dsn":"","org":"","project":"","token":""}',
            '["dev","qa","tmc"]',
        ),
        (
            "pagerduty",
            "PagerDuty",
            "incident",
            "monitoring",
            "https://cdn.simpleicons.org/pagerduty/white",
            "PagerDuty is the incident management platform used by SRE and on-call teams. Agents can create incidents, add context notes, and resolve them automatically when fix missions succeed. Integrates with the MCO agent role for end-to-end automated incident response.",
            '{"api_key":"","service_id":"","escalation_policy":""}',
            '["dev","tmc","security","architecture"]',
        ),
        (
            "opsgenie",
            "OpsGenie",
            "incident",
            "monitoring",
            "🚒",
            "Alert management, on-call schedules, incident response.",
            '{"api_key":"","team":""}',
            '["dev","tmc","security"]',
        ),
        # ── Security ──
        (
            "snyk",
            "Snyk",
            "security",
            "security",
            "🛡️",
            "Dependency vulnerabilities, IaC security, container scanning.",
            '{"token":"","org_id":"","auto_fix":false}',
            '["security","dev","architecture"]',
        ),
        (
            "trivy",
            "Trivy",
            "security",
            "security",
            "🔍",
            "Container image and filesystem vulnerability scanner.",
            '{"server_url":"","severity":"CRITICAL,HIGH"}',
            '["security","dev"]',
        ),
        (
            "wiz",
            "Wiz",
            "security",
            "security",
            "🌪️",
            "Cloud security posture, CSPM, CWPP.",
            '{"api_endpoint":"","client_id":"","client_secret":""}',
            '["security","architecture"]',
        ),
        # ── ITSM / TMA / MCO ──
        (
            "servicenow",
            "ServiceNow",
            "itsm",
            "itsm",
            "https://cdn.simpleicons.org/servicenow/white",
            "ServiceNow is the enterprise ITSM platform used by large organizations for change, incident, and problem management. Agents create and update CMDB records, submit change requests with automated risk assessment, and read open incidents to prioritize platform work.",
            '{"instance":"","user":"","table":"incident"}',
            '["tma","tmc","product","architecture"]',
        ),
        (
            "glpi",
            "GLPI",
            "itsm",
            "itsm",
            "🖥️",
            "IT asset management, helpdesk tickets, inventory.",
            '{"url":"","app_token":"","user_token":""}',
            '["tma","tmc"]',
        ),
        (
            "freshservice",
            "Freshservice",
            "itsm",
            "itsm",
            "🎫",
            "IT service management, asset tracking, CMDB.",
            '{"domain":"","api_key":""}',
            '["tma","tmc","product"]',
        ),
        (
            "zendesk",
            "Zendesk",
            "itsm",
            "itsm",
            "https://cdn.simpleicons.org/zendesk/white",
            "Zendesk is the leading customer support platform. Agents analyze support ticket trends, auto-triage incoming requests, generate canned responses for common issues, and escalate complex cases to engineering missions for deeper investigation.",
            '{"subdomain":"","email":"","api_token":""}',
            '["tma","marketing","product"]',
        ),
        # ── Marketing & Analytics ──
        (
            "google-analytics",
            "Google Analytics",
            "analytics",
            "marketing",
            "https://cdn.simpleicons.org/googleanalytics/white",
            "Google Analytics tracks website traffic, conversion funnels, and user behavior. Marketing agents read GA4 data to analyze feature adoption, measure A/B test results, and generate weekly performance reports with actionable insights.",
            '{"property_id":"","view_id":"","service_account_json":""}',
            '["marketing","product"]',
        ),
        (
            "matomo",
            "Matomo",
            "analytics",
            "marketing",
            "https://cdn.simpleicons.org/matomo/white",
            "Matomo is the privacy-first open-source analytics platform, GDPR-compliant by design. Agents read traffic and event data to measure content performance and user journeys without third-party data sharing. Ideal for EU-regulated industries.",
            '{"url":"","token":"","site_id":1}',
            '["marketing","product"]',
        ),
        (
            "hubspot",
            "HubSpot",
            "crm",
            "marketing",
            "https://cdn.simpleicons.org/hubspot/white",
            "HubSpot is the all-in-one CRM, marketing, and sales platform. Agents enrich leads with analysis, trigger nurturing sequences based on user behavior, and generate pipeline health reports. Connects product outcomes to revenue metrics.",
            '{"api_key":"","portal_id":""}',
            '["marketing","product"]',
        ),
        (
            "mixpanel",
            "Mixpanel",
            "analytics",
            "marketing",
            "🔮",
            "Mixpanel is a product analytics platform focused on user behavior, A/B testing, and retention cohorts. Agents read Mixpanel reports to measure feature adoption, identify drop-off points in user funnels, and generate product health summaries for sprint retrospectives.",
            '{"project_token":"","secret":""}',
            '["marketing","product"]',
        ),
        # ── Cloud & Infra ──
        (
            "aws",
            "Amazon Web Services",
            "cloud",
            "infra",
            "https://cdn.simpleicons.org/amazonaws/white",
            "Amazon Web Services is the leading cloud platform with 200+ services. Agents can provision EC2 instances, manage S3 buckets, deploy Lambda functions, and read CloudWatch alarms to detect production issues. Required for teams hosting workloads on AWS.",
            '{"access_key_id":"","region":"eu-west-1","account_id":""}',
            '["dev","architecture","tmc","security"]',
        ),
        (
            "azure-cloud",
            "Microsoft Azure",
            "cloud",
            "infra",
            "https://cdn.simpleicons.org/microsoftazure/white",
            "Microsoft Azure is the enterprise cloud platform by Microsoft. Agents deploy to Azure App Service and AKS, read Azure Monitor metrics, manage Blob Storage, and integrate with Azure AD for identity-aware deployments. Required for Microsoft-stack teams.",
            '{"subscription_id":"","tenant_id":"","client_id":""}',
            '["dev","architecture","tmc","security"]',
        ),
        (
            "gcp",
            "Google Cloud Platform",
            "cloud",
            "infra",
            "https://cdn.simpleicons.org/googlecloud/white",
            "Google Cloud Platform offers GKE, Cloud Run, BigQuery, and Pub/Sub. Agents deploy containerized apps to Cloud Run, query BigQuery datasets for analytics, and publish/subscribe to Pub/Sub topics as part of data pipeline missions.",
            '{"project_id":"","service_account_json":""}',
            '["dev","architecture","tmc"]',
        ),
        (
            "docker-registry",
            "Docker Registry",
            "registry",
            "infra",
            "https://cdn.simpleicons.org/docker/white",
            "A Docker image registry (Docker Hub, Harbor, ECR, ACR, or GCR) stores and distributes container images. Agents push built images, pull base images, and read image manifests during CI/CD and deployment missions.",
            '{"url":"","username":"","type":"hub"}',
            '["dev","architecture"]',
        ),
        # ── Design ──
        (
            "figma",
            "Figma",
            "design",
            "design",
            "https://cdn.simpleicons.org/figma/white",
            "Figma is the leading collaborative design tool for product and UI teams. Agents read component specs, design tokens, and style guides via the Figma MCP to ensure generated code matches the design system exactly. Essential for front-end development missions.",
            '{"access_token":"","team_id":"","file_key":""}',
            '["ux","product","dev"]',
        ),
        (
            "storybook",
            "Storybook",
            "design",
            "design",
            "https://cdn.simpleicons.org/storybook/white",
            "Storybook is the open-source workshop for building and testing UI components in isolation. Agents can run visual regression tests, check accessibility with the a11y addon, and verify that generated components render correctly before committing.",
            '{"url":"","token":""}',
            '["ux","dev","qa"]',
        ),
        # ── Testing ──
        (
            "testrail",
            "TestRail",
            "test_management",
            "testing",
            "🧾",
            "TestRail is the enterprise test case management platform. Agents create test plans and suites from sprint requirements, link test runs to missions, and update test results automatically — keeping QA traceability aligned with automated execution.",
            '{"url":"","user":"","api_key":""}',
            '["qa","dev","product"]',
        ),
        (
            "browserstack",
            "BrowserStack",
            "test_management",
            "testing",
            "https://cdn.simpleicons.org/browserstack/white",
            "BrowserStack provides real device and browser testing infrastructure in the cloud. Agents trigger cross-browser and mobile test runs, read screenshot diffs, and flag UI regressions as part of QA missions without maintaining a local device lab.",
            '{"username":"","access_key":""}',
            '["qa","dev"]',
        ),
        # ── Architecture / Wiki Guidelines ──
        (
            "wiki-guidelines",
            "Architecture Guidelines (Wiki)",
            "knowledge",
            "architecture",
            "📐",
            "Architecture guidelines wiki provides organizational coding standards, API conventions, and security policies. When enabled, agents automatically inject relevant guidelines into their system prompts before generating code or architecture decisions. Supports Confluence and GitLab Wiki sources.",
            '{"source":"confluence","space":"","confluence_url":"","domain":"","auto_inject":true}',
            '["dev","architecture","security","reviewer","qa"]',
        ),
        # ── GitHub OSS Tools ──
        (
            "scrapy",
            "Scrapy",
            "github_tool",
            "testing",
            "https://avatars.githubusercontent.com/u/733635?s=48",
            "Scrapy is the most popular Python web scraping framework, with 50k+ GitHub stars. Agents schedule Scrapy crawls to harvest competitor documentation, product data, and public APIs for market intelligence missions. Also used for broken-link detection in QA missions.",
            '{"repo_url":"https://github.com/scrapy/scrapy","version":"latest"}',
            '["dev","qa","marketing","data"]',
        ),
        (
            "opensandbox",
            "OpenSandbox",
            "github_tool",
            "devops",
            "📦",
            "OpenSandbox by Alibaba provides secure, isolated sandboxes for executing untrusted code. Agents run generated code snippets, test scripts, and migration scripts inside sandboxes before applying them to production environments, eliminating execution risk.",
            '{"repo_url":"https://github.com/alibaba/OpenSandbox","version":"latest"}',
            '["dev","security","qa","architecture"]',
        ),
        (
            "locust",
            "Locust",
            "github_tool",
            "testing",
            "https://avatars.githubusercontent.com/u/70621?s=48",
            "Locust is a scalable Python load testing framework that simulates thousands of concurrent users. Agents write Locust scenarios to validate API response times, trigger ramp-up tests after deployments, and interpret throughput results to recommend infrastructure scaling.",
            '{"repo_url":"https://github.com/locustio/locust","version":"latest","target_url":""}',
            '["qa","dev","architecture"]',
        ),
        (
            "k6",
            "Grafana k6",
            "github_tool",
            "testing",
            "https://cdn.simpleicons.org/k6/white",
            "Grafana k6 is a modern JavaScript-based performance testing tool with CI-friendly output and built-in threshold assertions. Agents write k6 scenarios, run performance gates as part of sprint missions, and report p95/p99 latency metrics directly into mission results.",
            '{"repo_url":"https://github.com/grafana/k6","version":"latest","target_url":""}',
            '["qa","dev","architecture"]',
        ),
        (
            "trufflehog",
            "TruffleHog",
            "github_tool",
            "security",
            "https://avatars.githubusercontent.com/u/7197340?s=48",
            "TruffleHog scans Git history, branches, and CI environments for leaked secrets, API keys, and credentials with 700+ detectors. Security agents run TruffleHog scans on every pull request and flag leaked credentials for immediate rotation before merge.",
            '{"repo_url":"https://github.com/trufflesecurity/trufflehog","scan_depth":"100"}',
            '["security","dev","qa"]',
        ),
        (
            "semgrep",
            "Semgrep",
            "github_tool",
            "security",
            "https://cdn.simpleicons.org/semgrep/white",
            "Semgrep is a fast, lightweight static analysis engine with 2000+ ready-made rules for OWASP Top 10, secrets detection, and code quality across 30+ languages. Security agents run Semgrep on every code change and block deployments when critical security findings are detected.",
            '{"repo_url":"https://github.com/returntocorp/semgrep","ruleset":"auto"}',
            '["security","dev","qa","reviewer"]',
        ),
        (
            "checkov",
            "Checkov",
            "github_tool",
            "security",
            "✅",
            "Checkov is the leading open-source IaC security scanner supporting Terraform, CloudFormation, Kubernetes manifests, Dockerfiles, and Helm charts. Architecture and security agents run Checkov before every infrastructure deployment to catch misconfigurations before they reach production.",
            '{"repo_url":"https://github.com/bridgecrewio/checkov","framework":"terraform,kubernetes"}',
            '["security","architecture","dev"]',
        ),
        (
            "zap",
            "OWASP ZAP",
            "github_tool",
            "security",
            "https://cdn.simpleicons.org/owasp/white",
            "OWASP ZAP (Zed Attack Proxy) is the world's most widely used web application security scanner. Security agents run ZAP baseline and full active scans against staging environments, parse findings by severity, and create remediation missions for OWASP Top 10 vulnerabilities.",
            '{"repo_url":"https://github.com/zaproxy/zaproxy","target_url":"","scan_mode":"baseline"}',
            '["security","qa","dev"]',
        ),
        (
            "renovate",
            "Renovate",
            "github_tool",
            "devops",
            "https://cdn.simpleicons.org/renovatebot/white",
            "Renovate automatically opens pull requests to keep all project dependencies up to date across npm, pip, Maven, Gradle, Docker, and more. DevOps agents use it to enforce patch-level auto-merge policies and flag major version upgrades for human review in the sprint backlog.",
            '{"repo_url":"https://github.com/renovatebot/renovate","auto_merge":"patch"}',
            '["dev","architecture","security"]',
        ),
        (
            "semantic-release",
            "Semantic Release",
            "github_tool",
            "devops",
            "https://cdn.simpleicons.org/semanticrelease/white",
            "Semantic Release fully automates versioning and package publishing based on Conventional Commits. Agents trigger releases at the end of sprint missions, ensuring every deployment gets a proper changelog, Git tag, and published artifact without manual intervention.",
            '{"repo_url":"https://github.com/semantic-release/semantic-release","branch":"main"}',
            '["dev","architecture"]',
        ),
        (
            "hadolint",
            "Hadolint",
            "github_tool",
            "devops",
            "https://avatars.githubusercontent.com/u/20535571?s=48",
            "Hadolint is a Dockerfile linter that enforces best practices and security rules. Dev and security agents run Hadolint on every Dockerfile change to catch issues like pinning base image versions, avoiding RUN as root, and minimizing layer count before image builds.",
            '{"repo_url":"https://github.com/hadolint/hadolint"}',
            '["dev","security","architecture"]',
        ),
        (
            "mermaid",
            "Mermaid",
            "github_tool",
            "architecture",
            "https://cdn.simpleicons.org/mermaidjs/white",
            "Mermaid.js is the leading diagrams-as-code library for flowcharts, sequence diagrams, ER models, Gantt charts, and C4 architecture. Architecture agents generate Mermaid diagrams automatically in documentation and ADRs to keep visual representations in sync with code.",
            '{"repo_url":"https://github.com/mermaid-js/mermaid"}',
            '["architecture","dev","product"]',
        ),
        (
            "structurizr",
            "Structurizr",
            "github_tool",
            "architecture",
            "https://avatars.githubusercontent.com/u/18306521?s=48",
            "Structurizr implements Simon Brown's C4 model for software architecture documentation. Architecture agents generate system context, container, and component diagrams as code using the Structurizr DSL, then export them as SVG for inclusion in technical specs and ADRs.",
            '{"repo_url":"https://github.com/structurizr/structurizr-cli"}',
            '["architecture","dev"]',
        ),
        (
            "mkdocs-material",
            "MkDocs Material",
            "github_tool",
            "devops",
            "https://avatars.githubusercontent.com/u/9342239?s=48",
            "MkDocs with the Material theme is the most popular Python documentation site generator. Agents auto-generate and publish structured documentation sites from markdown files, including API references, runbooks, and architecture guides, as part of delivery missions.",
            '{"repo_url":"https://github.com/squidfunk/mkdocs-material","site_dir":"docs/site"}',
            '["dev","architecture","product"]',
        ),
        (
            "mlflow",
            "MLflow",
            "github_tool",
            "devops",
            "https://avatars.githubusercontent.com/u/43071452?s=48",
            "MLflow is the open-source platform for managing the full ML lifecycle: experiment tracking, model registry, and deployment. Data agents log LLM experiment runs, compare model versions, and register promoted models to the MLflow registry for reproducible deployments.",
            '{"repo_url":"https://github.com/mlflow/mlflow","tracking_uri":""}',
            '["dev","architecture","data"]',
        ),
        (
            "httpie",
            "HTTPie",
            "github_tool",
            "testing",
            "https://cdn.simpleicons.org/httpie/white",
            "HTTPie is a human-friendly HTTP client for testing and exploring REST APIs. Agents use HTTPie to interactively call and validate APIs during integration testing, document example requests in runbooks, and verify endpoint contracts as part of QA missions.",
            '{"repo_url":"https://github.com/httpie/cli"}',
            '["dev","qa","security"]',
        ),
    ]
    for row in _integ_extended:
        iid, name, itype, category, icon, desc, cfg, roles = row
        conn.execute(
            "INSERT OR IGNORE INTO integrations (id, name, type, category, icon, description, config_json, agent_roles) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (iid, name, itype, category, icon, desc, cfg, roles),
        )
        # Update category/icon/description for existing rows (in case seeded without them)
        conn.execute(
            "UPDATE integrations SET category=?, icon=?, description=?, agent_roles=? WHERE id=?",
            (category, icon, desc, roles, iid),
        )

    # Auth & RBAC tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'viewer',
            avatar TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            auth_provider TEXT DEFAULT 'local',
            provider_id TEXT DEFAULT '',
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_project_roles (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            granted_by TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, project_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            refresh_token_hash TEXT NOT NULL,
            user_agent TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usess_user ON user_sessions(user_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usess_expires ON user_sessions(expires_at)"
    )

    # ── Mercato: Agent Transfer Market ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_wallets (
            project_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 5000,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_assignments (
            agent_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assignment_type TEXT DEFAULT 'owned',
            loan_expires_at TIMESTAMP,
            loan_from_project TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aa_project ON agent_assignments(project_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mercato_listings (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            seller_project TEXT NOT NULL,
            listing_type TEXT DEFAULT 'transfer',
            asking_price INTEGER NOT NULL,
            loan_weeks INTEGER,
            buyout_clause INTEGER,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ml_status ON mercato_listings(status)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mercato_transfers (
            id TEXT PRIMARY KEY,
            listing_id TEXT,
            agent_id TEXT NOT NULL,
            from_project TEXT NOT NULL,
            to_project TEXT NOT NULL,
            transfer_type TEXT NOT NULL,
            price INTEGER NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mt_agent ON mercato_transfers(agent_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            reference_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tt_project ON token_transactions(project_id)"
    )

    # ── LLM Usage tracking ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            cost_estimate REAL DEFAULT 0,
            project_id TEXT,
            agent_id TEXT,
            session_id TEXT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_ts ON llm_usage(ts)")

    # ── Quality Metrics (v2.1) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            mission_id TEXT,
            session_id TEXT,
            phase_name TEXT,
            dimension TEXT NOT NULL,
            score REAL NOT NULL,
            details_json TEXT,
            tool_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add columns that may be missing from older schema versions
    for col, typedef in [
        ("mission_id", "TEXT"),
        ("session_id", "TEXT"),
        ("phase_name", "TEXT"),
        ("details_json", "TEXT"),
        ("tool_used", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]:
        try:
            conn.execute(f"ALTER TABLE quality_reports ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qr_project ON quality_reports(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qr_mission ON quality_reports(mission_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_ts ON quality_reports(created_at)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            mission_id TEXT,
            global_score REAL NOT NULL,
            breakdown_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for col, typedef in [
        ("mission_id", "TEXT"),
        ("breakdown_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]:
        try:
            conn.execute(f"ALTER TABLE quality_snapshots ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qs_project ON quality_snapshots(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qs_ts ON quality_snapshots(created_at)"
    )

    # ── Wiki pages ────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wiki_pages (
            slug TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            icon TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 100,
            parent_slug TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wiki_cat ON wiki_pages(category)")

    # ── Wiki translations (i18n content) ─────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wiki_translations (
            slug TEXT NOT NULL,
            lang TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (slug, lang)
        )
    """)

    # ── Evolution / GA tables ─────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_proposals (
            id TEXT PRIMARY KEY,
            base_wf_id TEXT NOT NULL,
            genome_json TEXT NOT NULL,
            fitness REAL DEFAULT 0.0,
            generation INTEGER DEFAULT 0,
            run_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_evprop_wf ON evolution_proposals(base_wf_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_evprop_status ON evolution_proposals(status)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_runs (
            id TEXT PRIMARY KEY,
            wf_id TEXT NOT NULL,
            generations INTEGER DEFAULT 0,
            best_fitness REAL DEFAULT 0.0,
            fitness_history_json TEXT DEFAULT '[]',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evrun_wf ON evolution_runs(wf_id)")

    # ── RL experience replay buffer ───────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rl_experience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state_json TEXT NOT NULL,
            action TEXT NOT NULL,
            reward REAL NOT NULL,
            next_state_json TEXT NOT NULL,
            mission_id TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rl_exp_mission ON rl_experience(mission_id)"
    )

    # ── Simulation runs log ───────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wf_id TEXT NOT NULL,
            n_runs INTEGER DEFAULT 0,
            rows_written INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── LLM cost rates ────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_cost_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_per_1k REAL DEFAULT 0.0,
            output_per_1k REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(provider, model)
        )
    """)
    for provider, model, inp, out in [
        ("azure-openai", "gpt-5-mini", 0.00015, 0.0006),
        ("azure-openai", "gpt-5.2", 0.005, 0.015),
        ("minimax", "MiniMax", 0.0002, 0.001),
    ]:
        conn.execute(
            "INSERT OR IGNORE INTO llm_cost_rates (provider, model, input_per_1k, output_per_1k) VALUES (?,?,?,?)",
            (provider, model, inp, out),
        )

    # ── Real execution analytics ──────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS phase_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            phase_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL DEFAULT 'sequential',
            agent_ids_json TEXT NOT NULL DEFAULT '[]',
            team_size INTEGER DEFAULT 1,
            success INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            rejection_count INTEGER DEFAULT 0,
            duration_secs REAL DEFAULT 0.0,
            complexity_tier TEXT DEFAULT 'simple',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_workflow ON phase_outcomes(workflow_id, pattern_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_phase ON phase_outcomes(phase_id, success)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_complexity ON phase_outcomes(complexity_tier, pattern_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_pair_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_a TEXT NOT NULL,
            agent_b TEXT NOT NULL,
            co_appearances INTEGER DEFAULT 0,
            joint_successes INTEGER DEFAULT 0,
            joint_quality_sum REAL DEFAULT 0.0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_a, agent_b)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aps_pair ON agent_pair_scores(agent_a, agent_b)"
    )

    # Add cost_usd to llm_traces if not present
    try:
        conn.execute("ALTER TABLE llm_traces ADD COLUMN cost_usd REAL DEFAULT 0.0")
    except Exception:
        pass

    # Add deduplication fields to platform_incidents if not present
    for col, typedef in [("count", "INTEGER"), ("last_seen_at", "TIMESTAMP")]:
        try:
            conn.execute(f"ALTER TABLE platform_incidents ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    # Backfill nulls after column addition
    try:
        conn.execute("UPDATE platform_incidents SET count=1 WHERE count IS NULL")
        conn.execute(
            "UPDATE platform_incidents SET last_seen_at=created_at WHERE last_seen_at IS NULL"
        )
    except Exception:
        pass

    # ── Darwin / Thompson / GA / RL tables ───────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_fitness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            fitness_score REAL DEFAULT 0.0,
            runs INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            avg_iterations REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            retired INTEGER DEFAULT 0,
            retired_at TIMESTAMP,
            pinned INTEGER DEFAULT 0,
            weight_multiplier REAL DEFAULT 1.0,
            UNIQUE(agent_id, pattern_id, technology, phase_type)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tf_context ON team_fitness(technology, phase_type)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_fitness_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            snapshot_date TEXT NOT NULL DEFAULT (date('now')),
            fitness_score REAL DEFAULT 0.0,
            runs INTEGER DEFAULT 0,
            generation INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, pattern_id, technology, phase_type, snapshot_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT,
            workflow_id TEXT,
            agent_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            selection_method TEXT DEFAULT 'thompson',
            score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_ab_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            agent_a TEXT NOT NULL,
            agent_b TEXT NOT NULL,
            wins_a INTEGER DEFAULT 0,
            wins_b INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            winner TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_okr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective TEXT NOT NULL,
            key_result TEXT NOT NULL,
            target REAL DEFAULT 0.0,
            current_value REAL DEFAULT 0.0,
            unit TEXT DEFAULT '%',
            period TEXT DEFAULT 'Q1-2026',
            status TEXT DEFAULT 'on_track',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_sqlite_tables(conn)
    _bump_schema_version(conn, _SCHEMA_VERSION)
    conn.commit()


def _ensure_sqlite_tables(conn) -> None:
    """Create SQLite-only tables that may be missing on older DBs."""
    # MCP server registry
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcps (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            command TEXT NOT NULL DEFAULT '',
            args_json TEXT DEFAULT '[]',
            env_json TEXT DEFAULT '{}',
            tools_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'stopped',
            is_builtin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Marketing ideation tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mkt_ideation_sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            prompt TEXT,
            status TEXT DEFAULT 'running',
            result_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mkt_ideation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES mkt_ideation_sessions(id) ON DELETE CASCADE,
            role TEXT DEFAULT 'assistant',
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Eval framework tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_datasets (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            agent_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            id TEXT PRIMARY KEY,
            dataset_id TEXT,
            prompt TEXT NOT NULL,
            expected_output TEXT,
            tags TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id TEXT PRIMARY KEY,
            dataset_id TEXT,
            agent_id TEXT,
            status TEXT DEFAULT 'pending',
            score_avg REAL,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            case_id TEXT,
            actual_output TEXT,
            score REAL,
            judge_feedback TEXT,
            latency_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Custom tools table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_tools (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Deploy targets registry
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deploy_targets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            driver TEXT NOT NULL DEFAULT 'docker_local',
            config_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'unknown',
            last_check TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_deploy_targets_driver ON deploy_targets(driver)"
    )
    # RTK compression stats
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rtk_compression_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            original_tokens INTEGER DEFAULT 0,
            compressed_tokens INTEGER DEFAULT 0,
            savings_pct REAL DEFAULT 0,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rtk_ts ON rtk_compression_stats(ts)")
    # Annotation Studio
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_screens (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            page_url TEXT DEFAULT '',
            svg_path TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_screens_project ON project_screens(project_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_annotations (
            id TEXT PRIMARY KEY,
            screen_id TEXT DEFAULT '',
            project_id TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'comment',
            selector TEXT DEFAULT '',
            element_text TEXT DEFAULT '',
            x_pct REAL DEFAULT 0,
            y_pct REAL DEFAULT 0,
            w_pct REAL DEFAULT 0,
            h_pct REAL DEFAULT 0,
            from_x_pct REAL DEFAULT 0,
            from_y_pct REAL DEFAULT 0,
            to_x_pct REAL DEFAULT 0,
            to_y_pct REAL DEFAULT 0,
            page_url TEXT DEFAULT '',
            viewport_w INTEGER DEFAULT 1280,
            viewport_h INTEGER DEFAULT 800,
            quoted_text TEXT DEFAULT '',
            computed_css TEXT DEFAULT '',
            react_tree TEXT DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            seq_num INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ann_project ON project_annotations(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ann_screen ON project_annotations(screen_id)")
    # Seed RTK integration
    conn.execute("""
        INSERT OR IGNORE INTO integrations (id, name, type, category, icon, description, enabled, status, config_json, agent_roles)
        VALUES (
            'rtk-compression',
            'RTK Prompt Compression',
            'platform',
            'platform',
            '🗜️',
            'RTK-inspired prompt compressor: reduces tokens sent to LLMs by normalizing whitespace, truncating long code blocks, and summarizing old conversation history. Saves 40-70% tokens per call.',
            1,
            'connected',
            '{"threshold_tokens": 12000, "max_msg_tokens": 3000, "history_keep_recent": 4}',
            '[]'
        )
    """)
    conn.commit()


def _migrate_pg(conn):
    """PostgreSQL incremental migrations (safe ALTER TABLE IF NOT EXISTS)."""
    # Marketing ideation tables (added 2026-02)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mkt_ideation_sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            prompt TEXT,
            status TEXT DEFAULT 'active',
            project_id TEXT,
            mission_id TEXT,
            marketing_plan TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mkt_ideation_messages (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES mkt_ideation_sessions(id) ON DELETE CASCADE,
            agent_id TEXT,
            agent_name TEXT,
            content TEXT,
            color TEXT,
            avatar_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mkt_ideation_msgs_session ON mkt_ideation_messages(session_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mkt_ideation_findings (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES mkt_ideation_sessions(id) ON DELETE CASCADE,
            type TEXT,
            text TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mkt_ideation_findings_session ON mkt_ideation_findings(session_id)"
    )
    # MCP server registry (added 2026-02)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcps (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            command TEXT NOT NULL,
            args_json TEXT DEFAULT '[]',
            env_json TEXT DEFAULT '{}',
            tools_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'stopped',
            is_builtin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Projects: lifecycle phases (added 2026-02)
    try:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS current_phase TEXT DEFAULT ''"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS phases_json TEXT DEFAULT '[]'"
        )
    except Exception:
        pass
    # Missions: category + active_phases (added 2026-02)
    try:
        conn.execute(
            "ALTER TABLE missions ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'functional'"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE missions ADD COLUMN IF NOT EXISTS active_phases_json TEXT DEFAULT '[]'"
        )
    except Exception:
        pass
    # Backfill: mark auto-provisioned system missions as category='system'
    try:
        conn.execute(
            "UPDATE missions SET category='system' WHERE type IN ('program','security','debt') AND config_json LIKE '%auto_provisioned%' AND category='functional'"
        )
        conn.execute(
            "UPDATE missions SET category='system' WHERE name LIKE 'Self-Healing %' AND config_json LIKE '%auto_heal%' AND category='functional'"
        )
    except Exception:
        pass
    # GA/RL empirical data tables (added 2026-02)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS phase_outcomes (
            id SERIAL PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            phase_id TEXT NOT NULL,
            agent_ids TEXT NOT NULL,
            team_size INTEGER DEFAULT 1,
            success INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            duration_s REAL DEFAULT 0.0,
            complexity_tier TEXT DEFAULT 'simple',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_workflow ON phase_outcomes(workflow_id, pattern_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_phase ON phase_outcomes(phase_id, success)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_complexity ON phase_outcomes(complexity_tier, pattern_id)"
    )
    try:
        conn.execute(
            "ALTER TABLE phase_outcomes ADD COLUMN IF NOT EXISTS complexity_tier TEXT DEFAULT 'simple'"
        )
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_pair_scores (
            id SERIAL PRIMARY KEY,
            agent_a TEXT NOT NULL,
            agent_b TEXT NOT NULL,
            co_appearances INTEGER DEFAULT 0,
            joint_successes INTEGER DEFAULT 0,
            joint_quality_sum REAL DEFAULT 0.0,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(agent_a, agent_b)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aps_pair ON agent_pair_scores(agent_a, agent_b)"
    )
    # Deploy targets registry (PG)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deploy_targets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            driver TEXT NOT NULL DEFAULT 'docker_local',
            config_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'unknown',
            last_check TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_deploy_targets_driver ON deploy_targets(driver)"
    )
    # mission_runs: missing columns added post-launch (added 2026-03)
    for col, defn in [
        ("resume_attempts", "INTEGER DEFAULT 0"),
        ("last_resume_at", "TEXT"),
        ("human_input_required", "INTEGER DEFAULT 0"),
        ("llm_cost_usd", "DOUBLE PRECISION DEFAULT 0.0"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE mission_runs ADD COLUMN IF NOT EXISTS {col} {defn}"
            )
        except Exception:
            pass
    # platform_incidents: deduplication fields (added 2026-03)
    for col, defn in [
        ("count", "INTEGER DEFAULT 1"),
        ("last_seen_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE platform_incidents ADD COLUMN IF NOT EXISTS {col} {defn}"
            )
        except Exception:
            pass
    # platform_settings: key-value store for runtime config (added 2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Quality metrics tables (added 2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_reports (
            id SERIAL PRIMARY KEY,
            project_id TEXT NOT NULL,
            mission_id TEXT,
            session_id TEXT,
            dimension TEXT NOT NULL,
            score REAL NOT NULL,
            details_json TEXT DEFAULT '{}',
            tool_used TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qr_project ON quality_reports(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qr_mission ON quality_reports(mission_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_ts ON quality_reports(created_at)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_snapshots (
            id SERIAL PRIMARY KEY,
            project_id TEXT NOT NULL,
            mission_id TEXT,
            global_score REAL NOT NULL,
            breakdown_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qs_project ON quality_snapshots(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_qs_ts ON quality_snapshots(created_at)"
    )
    _bump_schema_version(conn, _SCHEMA_VERSION)

    # ── GitHub OSS tool integrations ──
    # Ensure columns exist first (SQLite path added them in _migrate)
    for col, typ in [
        ("category", "TEXT"),
        ("icon", "TEXT"),
        ("description", "TEXT"),
        ("agent_roles", "TEXT"),
        ("enabled", "INTEGER DEFAULT 0"),
    ]:
        conn.execute(f"ALTER TABLE integrations ADD COLUMN IF NOT EXISTS {col} {typ}")
    _github_tools = [
        (
            "scrapy",
            "Scrapy",
            "github_tool",
            "testing",
            "https://avatars.githubusercontent.com/u/733635?s=48",
            "Scrapy is the most popular Python web scraping framework, with 50k+ GitHub stars. Agents schedule Scrapy crawls to harvest competitor documentation, product data, and public APIs for market intelligence missions. Also used for broken-link detection in QA missions.",
            '{"repo_url":"https://github.com/scrapy/scrapy","version":"latest"}',
            '["dev","qa","marketing","data"]',
        ),
        (
            "opensandbox",
            "OpenSandbox",
            "github_tool",
            "devops",
            "📦",
            "OpenSandbox by Alibaba provides secure, isolated sandboxes for executing untrusted code. Agents run generated code snippets, test scripts, and migration scripts inside sandboxes before applying them to production environments, eliminating execution risk.",
            '{"repo_url":"https://github.com/alibaba/OpenSandbox","version":"latest"}',
            '["dev","security","qa","architecture"]',
        ),
        (
            "locust",
            "Locust",
            "github_tool",
            "testing",
            "https://avatars.githubusercontent.com/u/70621?s=48",
            "Locust is a scalable Python load testing framework that simulates thousands of concurrent users. Agents write Locust scenarios to validate API response times, trigger ramp-up tests after deployments, and interpret throughput results to recommend infrastructure scaling.",
            '{"repo_url":"https://github.com/locustio/locust","version":"latest","target_url":""}',
            '["qa","dev","architecture"]',
        ),
        (
            "k6",
            "Grafana k6",
            "github_tool",
            "testing",
            "https://cdn.simpleicons.org/k6/white",
            "Grafana k6 is a modern JavaScript-based performance testing tool with CI-friendly output and built-in threshold assertions. Agents write k6 scenarios, run performance gates as part of sprint missions, and report p95/p99 latency metrics directly into mission results.",
            '{"repo_url":"https://github.com/grafana/k6","version":"latest","target_url":""}',
            '["qa","dev","architecture"]',
        ),
        (
            "trufflehog",
            "TruffleHog",
            "github_tool",
            "security",
            "https://avatars.githubusercontent.com/u/7197340?s=48",
            "TruffleHog scans Git history, branches, and CI environments for leaked secrets, API keys, and credentials with 700+ detectors. Security agents run TruffleHog scans on every pull request and flag leaked credentials for immediate rotation before merge.",
            '{"repo_url":"https://github.com/trufflesecurity/trufflehog","scan_depth":"100"}',
            '["security","dev","qa"]',
        ),
        (
            "semgrep",
            "Semgrep",
            "github_tool",
            "security",
            "https://cdn.simpleicons.org/semgrep/white",
            "Semgrep is a fast, lightweight static analysis engine with 2000+ ready-made rules for OWASP Top 10, secrets detection, and code quality across 30+ languages. Security agents run Semgrep on every code change and block deployments when critical security findings are detected.",
            '{"repo_url":"https://github.com/returntocorp/semgrep","ruleset":"auto"}',
            '["security","dev","qa","reviewer"]',
        ),
        (
            "checkov",
            "Checkov",
            "github_tool",
            "security",
            "✅",
            "Checkov is the leading open-source IaC security scanner supporting Terraform, CloudFormation, Kubernetes manifests, Dockerfiles, and Helm charts. Architecture and security agents run Checkov before every infrastructure deployment to catch misconfigurations before they reach production.",
            '{"repo_url":"https://github.com/bridgecrewio/checkov","framework":"terraform,kubernetes"}',
            '["security","architecture","dev"]',
        ),
        (
            "zap",
            "OWASP ZAP",
            "github_tool",
            "security",
            "https://cdn.simpleicons.org/owasp/white",
            "OWASP ZAP (Zed Attack Proxy) is the world's most widely used web application security scanner. Security agents run ZAP baseline and full active scans against staging environments, parse findings by severity, and create remediation missions for OWASP Top 10 vulnerabilities.",
            '{"repo_url":"https://github.com/zaproxy/zaproxy","target_url":"","scan_mode":"baseline"}',
            '["security","qa","dev"]',
        ),
        (
            "renovate",
            "Renovate",
            "github_tool",
            "devops",
            "https://cdn.simpleicons.org/renovatebot/white",
            "Renovate automatically opens pull requests to keep all project dependencies up to date across npm, pip, Maven, Gradle, Docker, and more. DevOps agents use it to enforce patch-level auto-merge policies and flag major version upgrades for human review in the sprint backlog.",
            '{"repo_url":"https://github.com/renovatebot/renovate","auto_merge":"patch"}',
            '["dev","architecture","security"]',
        ),
        (
            "semantic-release",
            "Semantic Release",
            "github_tool",
            "devops",
            "https://cdn.simpleicons.org/semanticrelease/white",
            "Semantic Release fully automates versioning and package publishing based on Conventional Commits. Agents trigger releases at the end of sprint missions, ensuring every deployment gets a proper changelog, Git tag, and published artifact without manual intervention.",
            '{"repo_url":"https://github.com/semantic-release/semantic-release","branch":"main"}',
            '["dev","architecture"]',
        ),
        (
            "hadolint",
            "Hadolint",
            "github_tool",
            "devops",
            "https://avatars.githubusercontent.com/u/20535571?s=48",
            "Hadolint is a Dockerfile linter that enforces best practices and security rules. Dev and security agents run Hadolint on every Dockerfile change to catch issues like pinning base image versions, avoiding RUN as root, and minimizing layer count before image builds.",
            '{"repo_url":"https://github.com/hadolint/hadolint"}',
            '["dev","security","architecture"]',
        ),
        (
            "mermaid",
            "Mermaid",
            "github_tool",
            "architecture",
            "https://cdn.simpleicons.org/mermaidjs/white",
            "Mermaid.js is the leading diagrams-as-code library for flowcharts, sequence diagrams, ER models, Gantt charts, and C4 architecture. Architecture agents generate Mermaid diagrams automatically in documentation and ADRs to keep visual representations in sync with code.",
            '{"repo_url":"https://github.com/mermaid-js/mermaid"}',
            '["architecture","dev","product"]',
        ),
        (
            "structurizr",
            "Structurizr",
            "github_tool",
            "architecture",
            "https://avatars.githubusercontent.com/u/18306521?s=48",
            "Structurizr implements Simon Brown's C4 model for software architecture documentation. Architecture agents generate system context, container, and component diagrams as code using the Structurizr DSL, then export them as SVG for inclusion in technical specs and ADRs.",
            '{"repo_url":"https://github.com/structurizr/structurizr-cli"}',
            '["architecture","dev"]',
        ),
        (
            "mkdocs-material",
            "MkDocs Material",
            "github_tool",
            "devops",
            "https://avatars.githubusercontent.com/u/9342239?s=48",
            "MkDocs with the Material theme is the most popular Python documentation site generator. Agents auto-generate and publish structured documentation sites from markdown files, including API references, runbooks, and architecture guides, as part of delivery missions.",
            '{"repo_url":"https://github.com/squidfunk/mkdocs-material","site_dir":"docs/site"}',
            '["dev","architecture","product"]',
        ),
        (
            "mlflow",
            "MLflow",
            "github_tool",
            "devops",
            "https://avatars.githubusercontent.com/u/43071452?s=48",
            "MLflow is the open-source platform for managing the full ML lifecycle: experiment tracking, model registry, and deployment. Data agents log LLM experiment runs, compare model versions, and register promoted models to the MLflow registry for reproducible deployments.",
            '{"repo_url":"https://github.com/mlflow/mlflow","tracking_uri":""}',
            '["dev","architecture","data"]',
        ),
        (
            "httpie",
            "HTTPie",
            "github_tool",
            "testing",
            "https://cdn.simpleicons.org/httpie/white",
            "HTTPie is a human-friendly HTTP client for testing and exploring REST APIs. Agents use HTTPie to interactively call and validate APIs during integration testing, document example requests in runbooks, and verify endpoint contracts as part of QA missions.",
            '{"repo_url":"https://github.com/httpie/cli"}',
            '["dev","qa","security"]',
        ),
    ]
    for iid, name, itype, category, icon, desc, cfg, roles in _github_tools:
        conn.execute(
            "INSERT OR IGNORE INTO integrations (id, name, type, category, icon, description, config_json, agent_roles) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (iid, name, itype, category, icon, desc, cfg, roles),
        )

    # ── user_project_roles (RBAC per-project) ──────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_project_roles (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, project_id)
        )
    """)

    conn.commit()


def _ensure_darwin_tables(conn) -> None:
    """Create Darwin/adaptive-AI tables if missing (called for existing DBs)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_fitness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            fitness_score REAL DEFAULT 0.0,
            runs INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            avg_iterations REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            retired INTEGER DEFAULT 0,
            retired_at TIMESTAMP,
            pinned INTEGER DEFAULT 0,
            weight_multiplier REAL DEFAULT 1.0,
            UNIQUE(agent_id, pattern_id, technology, phase_type)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tf_context ON team_fitness(technology, phase_type)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_fitness_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            snapshot_date TEXT NOT NULL DEFAULT (date('now')),
            fitness_score REAL DEFAULT 0.0,
            runs INTEGER DEFAULT 0,
            generation INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, pattern_id, technology, phase_type, snapshot_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT,
            workflow_id TEXT,
            agent_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            selection_method TEXT DEFAULT 'thompson',
            score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_ab_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            technology TEXT NOT NULL DEFAULT 'generic',
            phase_type TEXT NOT NULL DEFAULT 'generic',
            agent_a TEXT NOT NULL,
            agent_b TEXT NOT NULL,
            wins_a INTEGER DEFAULT 0,
            wins_b INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            winner TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_okr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective TEXT NOT NULL,
            key_result TEXT NOT NULL,
            target REAL DEFAULT 0.0,
            current_value REAL DEFAULT 0.0,
            unit TEXT DEFAULT '%',
            period TEXT DEFAULT 'Q1-2026',
            status TEXT DEFAULT 'on_track',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Real execution data: phase_outcomes for empirical GA fitness
    conn.execute("""
        CREATE TABLE IF NOT EXISTS phase_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            phase_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL DEFAULT 'sequential',
            agent_ids_json TEXT NOT NULL DEFAULT '[]',
            team_size INTEGER DEFAULT 1,
            success INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            rejection_count INTEGER DEFAULT 0,
            duration_secs REAL DEFAULT 0.0,
            complexity_tier TEXT DEFAULT 'simple',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_workflow ON phase_outcomes(workflow_id, pattern_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_phase ON phase_outcomes(phase_id, success)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_complexity ON phase_outcomes(complexity_tier, pattern_id)"
    )

    # Migrate existing phase_outcomes: add complexity_tier if missing
    try:
        po_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(phase_outcomes)").fetchall()
        }
        if po_cols and "complexity_tier" not in po_cols:
            conn.execute(
                "ALTER TABLE phase_outcomes ADD COLUMN complexity_tier TEXT DEFAULT 'simple'"
            )
    except Exception:
        pass

    # Agent pair chemistry: how well each pair of agents works together
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_pair_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_a TEXT NOT NULL,
            agent_b TEXT NOT NULL,
            co_appearances INTEGER DEFAULT 0,
            joint_successes INTEGER DEFAULT 0,
            joint_quality_sum REAL DEFAULT 0.0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_a, agent_b)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aps_pair ON agent_pair_scores(agent_a, agent_b)"
    )

    # Migrations: category + active_phases on missions
    try:
        m_cols3 = {r[1] for r in conn.execute("PRAGMA table_info(missions)").fetchall()}
        if m_cols3 and "category" not in m_cols3:
            conn.execute(
                "ALTER TABLE missions ADD COLUMN category TEXT DEFAULT 'functional'"
            )
        if m_cols3 and "active_phases_json" not in m_cols3:
            conn.execute(
                "ALTER TABLE missions ADD COLUMN active_phases_json TEXT DEFAULT '[]'"
            )
    except Exception:
        pass

    # Migration: add user_id to ideation_sessions for per-user space isolation
    try:
        is_cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(ideation_sessions)").fetchall()
        }
        if is_cols and "user_id" not in is_cols:
            conn.execute(
                "ALTER TABLE ideation_sessions ADD COLUMN user_id TEXT DEFAULT ''"
            )
    except Exception:
        pass

    # RTK compression stats
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rtk_compression_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            original_tokens INTEGER DEFAULT 0,
            compressed_tokens INTEGER DEFAULT 0,
            savings_pct REAL DEFAULT 0,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rtk_ts ON rtk_compression_stats(ts)")
    # Annotation Studio
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_screens (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            page_url TEXT DEFAULT '',
            svg_path TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_screens_project ON project_screens(project_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_annotations (
            id TEXT PRIMARY KEY,
            screen_id TEXT DEFAULT '',
            project_id TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'comment',
            selector TEXT DEFAULT '',
            element_text TEXT DEFAULT '',
            x_pct REAL DEFAULT 0,
            y_pct REAL DEFAULT 0,
            w_pct REAL DEFAULT 0,
            h_pct REAL DEFAULT 0,
            from_x_pct REAL DEFAULT 0,
            from_y_pct REAL DEFAULT 0,
            to_x_pct REAL DEFAULT 0,
            to_y_pct REAL DEFAULT 0,
            page_url TEXT DEFAULT '',
            viewport_w INTEGER DEFAULT 1280,
            viewport_h INTEGER DEFAULT 800,
            quoted_text TEXT DEFAULT '',
            computed_css TEXT DEFAULT '',
            react_tree TEXT DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            seq_num INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ann_project ON project_annotations(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ann_screen ON project_annotations(screen_id)")
    # Seed RTK integration
    conn.execute("""
        INSERT OR IGNORE INTO integrations (id, name, type, category, icon, description, enabled, status, config_json, agent_roles)
        VALUES (
            'rtk-compression',
            'RTK Prompt Compression',
            'platform',
            'platform',
            '🗜️',
            'RTK-inspired prompt compressor: reduces tokens sent to LLMs by normalizing whitespace, truncating long code blocks, and summarizing old conversation history. Saves 40-70% tokens per call.',
            1,
            'connected',
            '{"threshold_tokens": 12000, "max_msg_tokens": 3000, "history_keep_recent": 4}',
            '[]'
        )
    """)

    conn.commit()


def get_db(db_path: Path = DB_PATH):
    """Get a database connection. Returns SQLite or PostgreSQL adapter."""
    if _USE_PG:
        conn = get_connection()
        return conn

    if not db_path.exists():
        return init_db(db_path)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Ensure Darwin tables exist on existing DBs (idempotent)
    try:
        conn.execute("SELECT COUNT(*) FROM team_fitness")
    except Exception:
        _ensure_darwin_tables(conn)
    return conn
