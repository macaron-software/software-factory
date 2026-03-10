"""
Database migrations and initialization for the platform.
Supports dual backend: SQLite (local) / PostgreSQL (production).
Backend selected via DATABASE_URL env var.
"""

from pathlib import Path

from ..config import DB_PATH
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
    conn = _init_pg()
    _log.info("DB (PostgreSQL) schema v%s ready", _SCHEMA_VERSION)
    return conn


def _init_pg():
    """Initialize PostgreSQL schema.

    Uses a PostgreSQL advisory lock (id=20260301) so that when multiple nodes
    start simultaneously they serialize schema migrations instead of racing.
    """
    import logging as _logging

    _log = _logging.getLogger(__name__)
    conn = get_connection()
    # Acquire exclusive advisory lock — serialize migrations across nodes.
    # Use a 30s lock_timeout so we never block forever if a prior process crashed
    # mid-migration and left a zombie PG session holding the lock.
    try:
        conn.execute("SET lock_timeout = '30s'")
        conn.execute("SELECT pg_advisory_lock(20260301)")
        conn.execute("SET lock_timeout = '0'")  # reset
        _log.info("DB migration: advisory lock acquired")
    except Exception:
        pass  # non-fatal if advisory locks not supported

    try:
        schema = SCHEMA_PG_PATH.read_text()
        conn.executescript(schema)
        conn.commit()
        _migrate_pg(conn)
    finally:
        try:
            conn.execute("SELECT pg_advisory_unlock(20260301)")
        except Exception:
            pass
    return conn


def _migrate(conn):
    """Run incremental migrations. Safe to call multiple times."""
    _migrate_pg(conn)


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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            "ALTER TABLE epics ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'functional'"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE epics ADD COLUMN IF NOT EXISTS active_phases_json TEXT DEFAULT '[]'"
        )
    except Exception:
        pass
    # Backfill: mark auto-provisioned system missions as category='system'
    try:
        conn.execute(
            "UPDATE epics SET category='system' WHERE type IN ('program','security','debt') AND config_json LIKE '%auto_provisioned%' AND category='functional'"
        )
        conn.execute(
            "UPDATE epics SET category='system' WHERE name LIKE 'Self-Healing %' AND config_json LIKE '%auto_heal%' AND category='functional'"
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    try:
        conn.execute(
            "ALTER TABLE phase_outcomes ADD COLUMN IF NOT EXISTS ab_group TEXT DEFAULT ''"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE phase_outcomes ADD COLUMN IF NOT EXISTS rejection_count INTEGER DEFAULT 0"
        )
    except Exception:
        pass
    # AgeMem: memory op counts per pattern run — feeds memory RL stage training
    try:
        conn.execute(
            "ALTER TABLE phase_outcomes ADD COLUMN IF NOT EXISTS mem_store_count INTEGER DEFAULT 0"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE phase_outcomes ADD COLUMN IF NOT EXISTS mem_retrieve_count INTEGER DEFAULT 0"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE phase_outcomes ADD COLUMN IF NOT EXISTS mem_prune_count INTEGER DEFAULT 0"
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
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
    # epic_runs: missing columns added post-launch (added 2026-03)
    for col, defn in [
        ("resume_attempts", "INTEGER DEFAULT 0"),
        ("last_resume_at", "TEXT"),
        ("human_input_required", "INTEGER DEFAULT 0"),
        ("llm_cost_usd", "DOUBLE PRECISION DEFAULT 0.0"),
        # pattern_type: which orchestration pattern ran for this epic (added 2026-03)
        ("pattern_type", "TEXT DEFAULT ''"),
        # context_json: epic run context (added 2026-03)
        ("context_json", "TEXT DEFAULT '{}'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE epic_runs ADD COLUMN IF NOT EXISTS {col} {defn}")
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
    # RTK compression stats — tracks token savings from rtk-wrapped commands (added 2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rtk_compression_stats (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            original_tokens INTEGER NOT NULL DEFAULT 0,
            compressed_tokens INTEGER NOT NULL DEFAULT 0,
            savings_pct REAL NOT NULL DEFAULT 0,
            provider TEXT DEFAULT 'git',
            cmd_prefix TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rtk_ts ON rtk_compression_stats(ts)")
    _bump_schema_version(conn, _SCHEMA_VERSION)
    # memory_project / memory_global: access tracking columns (added 2026-03)
    for col, defn in [
        ("access_count", "INTEGER DEFAULT 0"),
        ("last_read_at", "TIMESTAMP"),
        ("agent_role", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE memory_project ADD COLUMN IF NOT EXISTS {col} {defn}"
            )
        except Exception:
            pass
        try:
            conn.execute(
                f"ALTER TABLE memory_global ADD COLUMN IF NOT EXISTS {col} {defn}"
            )
        except Exception:
            pass
    # support_tickets: rename epic_id → mission_id (added 2026-03)
    try:
        conn.execute("ALTER TABLE support_tickets RENAME COLUMN epic_id TO mission_id")
    except Exception:
        pass  # already renamed or doesn't exist
    # confluence_pages: create with correct schema (added 2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS confluence_pages (
            mission_id TEXT NOT NULL,
            tab TEXT NOT NULL,
            confluence_page_id TEXT NOT NULL,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (mission_id, tab)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_confluence_mission ON confluence_pages(mission_id)"
    )
    # team_fitness: unique constraint needed for ON CONFLICT (added 2026-03)
    try:
        conn.execute(
            "ALTER TABLE team_fitness ADD CONSTRAINT team_fitness_agent_pattern_tech_phase_key UNIQUE(agent_id, pattern_id, technology, phase_type)"
        )
    except Exception:
        pass  # already exists
    try:
        conn.execute(
            "ALTER TABLE team_fitness_history ADD CONSTRAINT team_fitness_history_key UNIQUE(agent_id, pattern_id, technology, phase_type, snapshot_date)"
        )
    except Exception:
        pass  # already exists

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

    # ── platform_nodes: cluster node registry + heartbeat ──────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_nodes (
            node_id TEXT PRIMARY KEY,
            role TEXT NOT NULL DEFAULT 'slave',
            mode TEXT NOT NULL DEFAULT 'slave',
            url TEXT NOT NULL DEFAULT '',
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'online',
            cpu_pct DOUBLE PRECISION DEFAULT 0,
            mem_pct DOUBLE PRECISION DEFAULT 0,
            version TEXT DEFAULT '',
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pnodes_status ON platform_nodes(status)"
    )
    # Projects: starred + container_url (added 2026-03)
    try:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS starred BOOLEAN DEFAULT FALSE"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS container_url TEXT DEFAULT ''"
        )
    except Exception:
        pass
    # Projects: is_protected (added 2026-03)
    try:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_protected BOOLEAN DEFAULT FALSE"
        )
    except Exception:
        pass

    # Hook system (2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hook_registrations (
            id TEXT PRIMARY KEY,
            hook_type TEXT NOT NULL,
            handler_name TEXT NOT NULL,
            agent_id TEXT,
            priority INTEGER DEFAULT 0,
            enabled BOOLEAN DEFAULT TRUE,
            can_block BOOLEAN DEFAULT FALSE,
            required_role TEXT,
            config_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hook_log (
            id TEXT PRIMARY KEY,
            hook_type TEXT,
            handler_name TEXT,
            agent_id TEXT,
            session_id TEXT,
            tool_name TEXT,
            blocked BOOLEAN DEFAULT FALSE,
            message TEXT,
            duration_ms INTEGER,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Performance indexes (added 2026-03-08) ────────────────────────────────
    # phase_outcomes: engine reads AVG(duration_s) WHERE pattern_id=? on every phase
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_pattern ON phase_outcomes(pattern_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_created ON phase_outcomes(created_at DESC)"
    )
    # epic_runs: cockpit queries by created_at (24h/7d windows) + engine UPDATE by session_id
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_epic_runs_created ON epic_runs(created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_epic_runs_session ON epic_runs(session_id)"
    )
    # epic_runs: combined status + created_at for cockpit failure counts
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_epic_runs_status_created ON epic_runs(status, created_at DESC)"
    )
    # team_fitness_history: boards query WHERE technology=? and WHERE technology=? AND phase_type=?
    # existing idx_tfh_key starts with agent_id — unusable for tech-only filter
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tfh_technology ON team_fitness_history(technology, phase_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tfh_snapshot ON team_fitness_history(snapshot_date DESC)"
    )
    # team_okr: UPDATE WHERE technology=? AND kpi_name=?  / ORDER BY team_key, kpi_name
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tokr_tech ON team_okr(technology, kpi_name)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tokr_teamkey ON team_okr(team_key)")
    # agent_assignments: WHERE project_id=? (only agent_id is PK — no index on project_id)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_asgn_project ON agent_assignments(project_id)"
    )
    # agent_scores: composite for WHERE agent_id=? AND epic_id=? queries in selection.py
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ascores_agent_epic ON agent_scores(agent_id, epic_id)"
    )
    # messages: cockpit query WHERE from_agent NOT IN (...) AND timestamp >= NOW()-1h
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_from_ts ON messages(from_agent, timestamp DESC)"
    )
    # llm_traces: combined session+created_at for per-session trace lookups
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_llt_session_created ON llm_traces(session_id, created_at DESC)"
    )
    # rl_experience: training reads latest N rows — PK covers ORDER BY id DESC; add created_at for purge
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rl_exp_created ON rl_experience(created_at DESC)"
    )
    # admin_audit_log: composite for resource lookups (table created later in this migration)
    if _pg_table_exists(conn, "admin_audit_log"):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_aal_resource ON admin_audit_log(resource_type, resource_id)"
        )
    # tool_calls: combined (agent_id, timestamp) for agent activity windows
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_toolcalls_agent_ts ON tool_calls(agent_id, timestamp DESC)"
    )

    _seed_sf_patterns(conn)
    conn.commit()


def _seed_sf_patterns(conn) -> None:
    """Seed 5 pattern epics + 39 pattern features into the factory (self-SF) project.
    Added 2026-03-08 — ref: pattern observability + AgeMem (arXiv:2601.01885).
    Uses ON CONFLICT DO NOTHING so safe to re-run on existing DBs.
    """
    epics = [
        (
            "pat-orch",
            "factory",
            "Orchestration Patterns — SF Platform",
            "18 patterns moteur: sequential, parallel, hierarchical, loop, debate, router, aggregator, wave, fractal_*, backprop_merge, HITL, adversarial-cascade, saga, sf-tdd, map-reduce, blackboard, swarm, solo-chat",
            9,
            9,
        ),
        (
            "pat-learn",
            "factory",
            "Learning Patterns — SF Platform",
            "5 patterns apprentissage: InstinctObserver, ConsolidateAgent, EvolutionScheduler (GA), RLPolicy (Q-learning + MemoryRLPolicy AgeMem), evolve_instincts hook",
            8,
            8,
        ),
        (
            "pat-qs",
            "factory",
            "Quality & Safety Patterns — SF Platform",
            "4 patterns qualité/sécurité: AdversarialGuard (Swiss Cheese), Guardrails, HookSystem (ECC lifecycle), SkillStocktake",
            9,
            9,
        ),
        (
            "pat-mem",
            "factory",
            "Memory Patterns — SF Platform",
            "8 patterns mémoire: MemoryManager 4-layer, AgeMem mem-1/2/3 (arXiv:2601.01885), VectorMemory, MemoryCompactor, InboxWatcher, QueryAgent",
            8,
            8,
        ),
        (
            "pat-ops",
            "factory",
            "Ops Patterns — SF Platform",
            "4 patterns ops: AutoHeal, ChaosEndurance, EnduranceWatchdog, A2A Bus (LF A2A v1.0)",
            7,
            7,
        ),
    ]
    for epic_id, project_id, name, desc, bv, wsjf in epics:
        conn.execute(
            """
            INSERT INTO epics (id, project_id, name, description, status, business_value, wsjf_score, created_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?, NOW())
            ON CONFLICT (id) DO NOTHING
        """,
            (epic_id, project_id, name, desc, bv, wsjf),
        )

    # (epic_id, feature_id, name, description, acceptance_criteria, priority, story_points)
    features = [
        # pat-orch (18)
        (
            "pat-orch",
            "fp-sequential",
            "Pattern: Sequential (Pipeline)",
            "Agents chaînés, output de chacun → input du suivant. Implémentation: engine.py run_sequential(). Cas: feature-sprint, cicd-pipeline.",
            "GIVEN un workflow séquentiel WHEN lancé THEN chaque phase reçoit le contexte précédent · output final = output dernière phase",
            1,
            3,
        ),
        (
            "pat-orch",
            "fp-parallel",
            "Pattern: Parallel (Fan-out)",
            "N agents en parallèle, résultats mergés. Implémentation: patterns/impls/parallel.py. Cas: research multi-source, code review multi-facettes.",
            "GIVEN N branches WHEN lancées THEN exécution concurrente · merge de tous les résultats",
            2,
            3,
        ),
        (
            "pat-orch",
            "fp-hierarchical",
            "Pattern: Hierarchical",
            "PM agent délègue à des spécialistes. Implémentation: patterns/impls/hierarchical.py. Cascade top-down avec synthèse remontante.",
            "GIVEN 1 PM + N specialists WHEN PM reçoit tâche THEN délègue · chaque specialist rend compte · PM synthétise",
            2,
            5,
        ),
        (
            "pat-orch",
            "fp-loop",
            "Pattern: Loop (Adversarial Pair)",
            "Writer/Reviewer itèrent jusqu'à approbation ou max_iter. Implémentation: patterns/impls/loop.py. Sprint DB record créé par itération.",
            "GIVEN writer + reviewer WHEN launched THEN iterates · sprint record créé/cloturé · approval ou max_iter exit",
            2,
            5,
        ),
        (
            "pat-orch",
            "fp-debate",
            "Pattern: Débat (Network)",
            "N agents débattent, vote majoritaire ou consensus. Implémentation: patterns/impls/debate.py. Cas: ideation 5 agents.",
            "GIVEN N agents WHEN debate launched THEN rounds de débat · vote final · position gagnante retournée",
            2,
            5,
        ),
        (
            "pat-orch",
            "fp-router",
            "Pattern: Router",
            "Routage dynamique selon contenu/contexte. Implémentation: patterns/impls/router.py. pub-sub variant pour event-driven.",
            "GIVEN input + routing rules WHEN message arrives THEN correct agent selected · routing logged · fallback si no match",
            2,
            3,
        ),
        (
            "pat-orch",
            "fp-aggregator",
            "Pattern: Agrégateur",
            "Fan-out vers N agents, merge des résultats. Consensus variant = vote majoritaire. Implémentation: patterns/impls/aggregator.py.",
            "GIVEN N agents WHEN all complete THEN results merged · consensus vote computed si activé",
            3,
            3,
        ),
        (
            "pat-orch",
            "fp-wave",
            "Pattern: Wave",
            "Phases parallèles avec barrière de synchronisation entre chaque wave. Implémentation: patterns/impls/wave.py.",
            "GIVEN wave config WHEN launched THEN parallel agents per wave · sync barrier before next wave · results accumulated",
            3,
            5,
        ),
        (
            "pat-orch",
            "fp-fractal-stories",
            "Pattern: Fractal Stories",
            "Décomposition épic → features → user stories. Implémentation: patterns/impls/fractal_stories.py.",
            "GIVEN epic WHEN fractal-stories launched THEN features + user stories générés · AC définis · points estimés",
            2,
            5,
        ),
        (
            "pat-orch",
            "fp-fractal-tests",
            "Pattern: Fractal Tests",
            "Suite de tests fractale: BDD GIVEN/WHEN/THEN. Implémentation: patterns/impls/fractal_tests.py.",
            "GIVEN codebase WHEN fractal-tests launched THEN unit + integration + e2e generated · coverage estimé",
            3,
            5,
        ),
        (
            "pat-orch",
            "fp-fractal-qa",
            "Pattern: Fractal QA",
            "Décomposition QA fractale: test plans → test suites → cas de test. Implémentation: patterns/impls/fractal_qa.py.",
            "GIVEN feature WHEN fractal-qa launched THEN hierarchical test decomposition · QA agent at each level",
            2,
            8,
        ),
        (
            "pat-orch",
            "fp-fractal-worktree",
            "Pattern: Fractal Worktree",
            "Workspace Git isolé par nœud fractal. Implémentation: patterns/impls/fractal_worktree.py.",
            "GIVEN fractal task WHEN launched THEN git worktree isolé créé · each node works in isolation · merge final",
            2,
            8,
        ),
        (
            "pat-orch",
            "fp-backprop",
            "Pattern: Backpropagation Merge",
            "Résolution de conflits par backprop entre agents. Implémentation: patterns/impls/backprop_merge.py.",
            "GIVEN N outputs with conflicts WHEN backprop THEN conflicts resolved · merged output coherent",
            3,
            8,
        ),
        (
            "pat-orch",
            "fp-hitl",
            "Pattern: Human-in-the-Loop",
            "Gate humain: GO/NOGO avant poursuite. Implémentation: patterns/impls/human_in_the_loop.py. HITL_TIMEOUT configurable.",
            "GIVEN workflow avec HITL gate WHEN reached THEN pause · notif envoyée · wait human decision · timeout auto-GO si configuré",
            1,
            3,
        ),
        (
            "pat-orch",
            "fp-adv-cascade",
            "Pattern: Adversarial Cascade",
            "Cascade d'agents adversariaux: chacun challenge le précédent. Implémentation: patterns/impls/adversarial_cascade.py.",
            "GIVEN N adversarial agents WHEN cascade THEN each challenges previous · final output survives all challenges",
            2,
            5,
        ),
        (
            "pat-orch",
            "fp-saga",
            "Pattern: Checkpoint / Saga",
            "Rollback sur échec via checkpoints. Implémentation: patterns/impls/saga.py.",
            "GIVEN multi-step workflow WHEN failure THEN compensating actions run · state restored to last checkpoint",
            2,
            8,
        ),
        (
            "pat-orch",
            "fp-sf-tdd",
            "Pattern: SF TDD Pipeline",
            "Pipeline TDD SF: RED → GREEN → REFACTOR + CI/CD. Implémentation: patterns/impls/sf_tdd.py + feature-sprint.yaml.",
            "GIVEN feature WHEN sf-tdd launched THEN failing tests → implementation → passing tests → review · sprint record created",
            1,
            13,
        ),
        (
            "pat-orch",
            "fp-supervisor-retry",
            "Pattern: Supervisor Retry",
            "Supervisor relance un agent en cas d'échec, avec correction de prompt. Implémentation: patterns/impls/loop.py (variant).",
            "GIVEN agent + supervisor WHEN failure THEN supervisor corrects + retries · max 3 retries · quality score propagé",
            3,
            3,
        ),
        # pat-learn (5)
        (
            "pat-learn",
            "fp-instinct-obs",
            "Pattern: InstinctObserver",
            "Observer post-session: extrait instincts comportementaux depuis logs. hooks/instinct_observer.py. On: post_session.",
            "GIVEN session terminée WHEN observer runs THEN insights extraits · instinct_insights table populated",
            2,
            5,
        ),
        (
            "pat-learn",
            "fp-consolidate",
            "Pattern: ConsolidateAgent",
            "Consolide instincts en YAML skill amélioré. agents/consolidate.py. Appelé par EvolutionScheduler.",
            "GIVEN instinct_insights WHEN consolidate THEN skill YAML updated · version incrémentée · quality_score computed",
            2,
            5,
        ),
        (
            "pat-learn",
            "fp-ga-evolution",
            "Pattern: EvolutionScheduler (GA)",
            "Genetic Algorithm sur prompts/skills: mutation + crossover + selection. agents/evolution.py. POST /api/darwin/evolve.",
            "GIVEN skill pool WHEN GA run THEN mutations générées · fitness evaluated · best kept · POST /api/darwin/seed",
            2,
            8,
        ),
        (
            "pat-learn",
            "fp-rl-policy",
            "Pattern: RLPolicy (Q-learning)",
            "Q-table tabular pour sélection pattern optimal. agents/rl_policy.py. Feedback: session quality_score. + MemoryRLPolicy 3-stage (AgeMem).",
            "GIVEN session outcome WHEN update THEN Q-table updated · next pattern recommendation améliorée · mem-3 stages 1→2→3",
            2,
            8,
        ),
        (
            "pat-learn",
            "fp-evolve-hook",
            "Pattern: evolve_instincts hook",
            "Hook post_session qui déclenche automatiquement l'évolution des instincts. hooks/lifecycle.py.",
            "GIVEN session end WHEN hook fires THEN instinct observer run · consolidation triggered si threshold atteint",
            3,
            3,
        ),
        # pat-qs (4)
        (
            "pat-qs",
            "fp-adv-guard",
            "Pattern: AdversarialGuard (Swiss Cheese)",
            "Vérification adversariale avant memory_store. engine.py::_execute_node() before store. Swiss Cheese: chaque couche rattrape ce que la précédente laisse passer.",
            "GIVEN agent output WHEN AdversarialGuard activated THEN hallucination/injection checked · blocked si flagged · logged",
            1,
            5,
        ),
        (
            "pat-qs",
            "fp-guardrails",
            "Pattern: Guardrails",
            "Content filter: PII, prompt injection, toxicity. hooks/guardrails.py. Pre-agent et post-agent gates.",
            "GIVEN any agent message WHEN guardrail runs THEN PII detected/masked · injection blocked · toxicity filtered · AC_SCORE impact",
            1,
            5,
        ),
        (
            "pat-qs",
            "fp-hook-system",
            "Pattern: HookSystem (ECC)",
            "Event-driven hooks: pre_agent, post_agent, pre_phase, post_phase, post_session, veto. hooks/lifecycle.py. ECC = Error Correction Code.",
            "GIVEN workflow run WHEN hooks registered THEN each lifecycle event fires correct hooks · veto stops execution · hooks chainable",
            2,
            8,
        ),
        (
            "pat-qs",
            "fp-skill-stocktake",
            "Pattern: SkillStocktake",
            "Audit automatique des skills: version check, eval harness (deterministic + LLM-judge). instincts.py::run_skill_eval(). Version frontmatter requis.",
            "GIVEN skill YAML WHEN stocktake THEN version présente · deterministic checks run · LLM-judge optionnel · score retourné",
            2,
            5,
        ),
        # pat-mem (8)
        (
            "pat-mem",
            "fp-mem-manager",
            "Pattern: MemoryManager 4-layer",
            "4 couches: session(ephemeral) · pattern(run) · project(persistent) · global(cross-project). manager.py. _serialize_row() datetime+Decimal safe (PG compat).",
            "GIVEN agent execution WHEN memory used THEN correct layer targeted · project_get() retourne bien filtrés · _serialize_row() no TypeError",
            1,
            8,
        ),
        (
            "pat-mem",
            "fp-agemem-1",
            "Pattern: AgeMem mem-1 (explicit tools)",
            "memory_store / memory_retrieve / memory_prune exposés comme tools explicites dans ExecutionContext. prompt_builder: auto-inject role-scoped mem si ctx vide. Ref: arXiv:2601.01885.",
            "GIVEN agent with project_id WHEN no project_context THEN role-scoped mem auto-retrieved via project_get() · mem tools available in tool schemas",
            1,
            8,
        ),
        (
            "pat-mem",
            "fp-agemem-2",
            "Pattern: AgeMem mem-2 (phase_outcomes tracking)",
            "_make_memory_op_counter(run) dans engine.py: on_tool_call hook incrémente mem_store_count / mem_retrieve_count / mem_prune_count. 15 colonnes dans phase_outcomes. Ref: arXiv:2601.01885.",
            "GIVEN pattern run WHEN memory tools called THEN counters incrémentés · 3 cols dans phase_outcomes · stats disponibles via /api/rl/memory/stats",
            1,
            5,
        ),
        (
            "pat-mem",
            "fp-agemem-3",
            "Pattern: AgeMem mem-3 (MemoryRLPolicy)",
            "3-stage progressive RL (Q-table tabular): stage-1=LTM quality, stage-2=STM efficiency, stage-3=joint. agents/rl_policy.py::MemoryRLPolicy. POST /api/rl/memory/train. Ref: arXiv:2601.01885.",
            "GIVEN phase_outcomes data WHEN train_stage(N) called THEN Q-table updated · stage 1→2→3 progressif · recommend_memory_ops() retourne action",
            1,
            8,
        ),
        (
            "pat-mem",
            "fp-vector-mem",
            "Pattern: VectorMemory",
            "Embeddings OpenAI-compat + cosine similarity search. memory/vectors.py. Fallback FTS5/tsvector si pas de provider.",
            "GIVEN query WHEN vector search THEN cosine sim ranking · fallback FTS5 si no embedding provider · results merged",
            2,
            5,
        ),
        (
            "pat-mem",
            "fp-compactor",
            "Pattern: MemoryCompactor",
            "Nightly 03:00: prune stale (NOW()-INTERVAL PG), compress oversized (>2000 chars), dedup global (HAVING COUNT(*)), re-score relevance. memory/compactor.py.",
            "GIVEN memory tables WHEN compaction THEN stale pruned · oversized compressed · duplicates merged · scores recalculated · 0 errors",
            2,
            5,
        ),
        (
            "pat-mem",
            "fp-inbox",
            "Pattern: InboxWatcher (AOMA)",
            "Poll ./inbox/ toutes les 10s, LLM extract → memory_global. POST /api/memory/ingest. Source: Google Always-On Memory Agent pattern.",
            "GIVEN file in inbox/ WHEN watcher runs THEN LLM extracts facts · stored in memory_global · file moved to processed/",
            3,
            3,
        ),
        (
            "pat-mem",
            "fp-query-agent",
            "Pattern: QueryAgent",
            "GET /api/memory/query?q= : recherche multi-layer + LLM synthesis. Citations [MEM-N]/[INST-N]. memory/api.py.",
            "GIVEN query string WHEN GET /api/memory/query THEN all layers searched · results ranked · LLM synthesizes · citations incluses",
            2,
            5,
        ),
        # pat-ops (4)
        (
            "pat-ops",
            "fp-autoheal",
            "Pattern: AutoHeal",
            "Scan platform_incidents toutes les 60s, groupe par error_type, lance epic TMA auto: diagnose→fix→verify→close. ops/auto_heal.py.",
            "GIVEN incident in platform_incidents WHEN autoheal scan THEN epic TMA lancé · agents assignés · ticket clos si fix validé",
            1,
            8,
        ),
        (
            "pat-ops",
            "fp-chaos",
            "Pattern: ChaosEndurance",
            "Chaos monkey: scenarios VM1/VM2/MODULES aléatoires 2-6h, MTTR mesuré. 80% infra + 20% modules. ops/chaos_endurance.py.",
            "GIVEN running platform WHEN chaos scenario fires THEN platform survives · MTTR < 5min · chaos_runs table populated · alert si MTTR > seuil",
            2,
            8,
        ),
        (
            "pat-ops",
            "fp-watchdog",
            "Pattern: EnduranceWatchdog",
            "Toutes les 60s: stalls >15min → retry, zombies → kill, disk >90% → cleanup, LLM health probe, rapport daily. ops/endurance_watchdog.py.",
            "GIVEN running platform WHEN watchdog scan THEN stalls detected · zombies killed · disk cleaned si > 90% · daily report generated",
            1,
            5,
        ),
        (
            "pat-ops",
            "fp-a2a-bus",
            "Pattern: A2A Bus",
            "Pub/sub agent-to-agent: queues par agent + DB persistence + SSE bridge. Redis pub/sub optionnel. PG NOTIFY/LISTEN cross-node. a2a/bus.py. Linux Foundation A2A v1.0.",
            "GIVEN N agents WHEN message published THEN correct subscriber receives · DB persistence garantie · SSE bridge live · cross-node si Redis/PG NOTIFY",
            1,
            8,
        ),
    ]
    for epic_id, feat_id, name, desc, ac, priority, sp in features:
        conn.execute(
            """
            INSERT INTO features (id, epic_id, name, description, acceptance_criteria, priority, status, story_points, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'done', ?, NOW())
            ON CONFLICT (id) DO NOTHING
        """,
            (feat_id, epic_id, name, desc, ac, priority, sp),
        )


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
                "ALTER TABLE epics ADD COLUMN category TEXT DEFAULT 'functional'"
            )
        if m_cols3 and "active_phases_json" not in m_cols3:
            conn.execute(
                "ALTER TABLE epics ADD COLUMN active_phases_json TEXT DEFAULT '[]'"
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
            feature_id TEXT DEFAULT '',
            mission_id TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_screens_project ON project_screens(project_id)"
    )
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ann_project ON project_annotations(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ann_screen ON project_annotations(screen_id)"
    )
    # Error monitoring: signatures + mutes (ported from airweave-ai/error-monitoring-agent, MIT)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS error_signatures (
            signature TEXT PRIMARY KEY,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_alerted TIMESTAMP,
            times_seen INTEGER DEFAULT 1,
            last_severity TEXT,
            last_status TEXT,
            last_summary TEXT,
            linked_mission_id TEXT,
            linked_ticket_url TEXT,
            linked_ticket_status TEXT,
            muted_until TIMESTAMP,
            muted_by TEXT,
            mute_reason TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_errsig_last_seen ON error_signatures(last_seen)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS error_mutes (
            signature TEXT PRIMARY KEY,
            muted_until TIMESTAMP NOT NULL,
            muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            muted_by TEXT,
            reason TEXT,
            duration_hours INTEGER
        )
    """)

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

    # Seed Image Generation provider integrations
    for img_integ in [
        (
            "image-gen-falai",
            "fal.ai — Flux",
            "image-gen",
            "ai-llm",
            "🌊",
            "Flux.1 via fal.ai. Best quality for backgrounds, concept art, general game assets. ~$0.05/image. Set FAL_KEY.",
            '{"env_key": "FAL_KEY", "base_url": "https://fal.run", "models": ["fal-ai/flux-pro", "fal-ai/flux/dev", "fal-ai/flux/schnell"]}',
        ),
        (
            "image-gen-pixellab",
            "PixelLab",
            "image-gen",
            "ai-llm",
            "🎮",
            "Purpose-built pixel art API: sprites, tilesets, animations, sprite sheets. Set PIXELLAB_API_KEY.",
            '{"env_key": "PIXELLAB_API_KEY", "base_url": "https://api.pixellab.ai/v1", "models": ["pixelart"]}',
        ),
        (
            "image-gen-gemini-image",
            "Gemini Image — Nano Banana",
            "image-gen",
            "ai-llm",
            "🍌",
            "Gemini 2.5 Flash Image (aka Nano Banana). Generates UI mockups and screen flows from text prompts. Attach output to Claude/Gemini prompt to implement. Reuses GEMINI_API_KEY.",
            '{"env_key": "GEMINI_API_KEY", "base_url": "https://generativelanguage.googleapis.com/v1beta", "models": ["gemini-2.5-flash", "imagen-3.0-generate-002"]}',
        ),
        (
            "image-gen-replicate",
            "Replicate",
            "image-gen",
            "ai-llm",
            "🔁",
            "Access to all open image models (Flux, SDXL, custom LoRAs). Good for style-consistent asset libraries. Set REPLICATE_API_TOKEN.",
            '{"env_key": "REPLICATE_API_TOKEN", "base_url": "https://api.replicate.com/v1", "models": ["black-forest-labs/flux-1.1-pro", "stability-ai/sdxl"]}',
        ),
        (
            "image-gen-mflux",
            "mflux — Apple Silicon",
            "image-gen",
            "ai-llm",
            "🍎",
            "Local FLUX image generation on Apple Silicon (M1/M2/M3/M4) via MLX. No API key needed — runs fully offline. Install: pip install mflux. macOS only.",
            '{"local": true, "models": ["flux-schnell", "flux-dev"], "requires": "Apple Silicon + macOS"}',
        ),
    ]:
        conn.execute(
            """
            INSERT OR IGNORE INTO integrations (id, name, type, category, icon, description, enabled, status, config_json, agent_roles)
            VALUES (?, ?, ?, ?, ?, ?, 0, 'disconnected', ?, '[]')
        """,
            img_integ,
        )

    conn.commit()

    # GAEngine: evolution_proposals schema fix (added 2026-03)
    # The original evolution_proposals table was created with column names that
    # diverged from the GAEngine _save_proposal() code (genome_json vs mutated_config,
    # fitness vs fitness_score). Added missing columns here so evolve_all() can persist
    # proposals to DB. Source: platform/agents/evolution.py _save_proposal().
    # Also dropped NOT NULL on legacy columns (workflow_id, mutated_config) to allow
    # the new column-based INSERT without breaking existing schema.
    conn.execute(
        "ALTER TABLE evolution_proposals ADD COLUMN IF NOT EXISTS genome_json TEXT"
    )
    conn.execute(
        "ALTER TABLE evolution_proposals ADD COLUMN IF NOT EXISTS fitness REAL DEFAULT 0.0"
    )
    conn.execute("ALTER TABLE evolution_proposals ADD COLUMN IF NOT EXISTS run_id TEXT")
    conn.execute("ALTER TABLE evolution_runs ADD COLUMN IF NOT EXISTS wf_id TEXT")
    conn.execute(
        "ALTER TABLE evolution_runs ADD COLUMN IF NOT EXISTS generations INT DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE evolution_runs ADD COLUMN IF NOT EXISTS fitness_history_json TEXT"
    )
    # Drop legacy NOT NULL constraints — old code populated mutated_config/workflow_id,
    # new code uses genome_json/wf_id. Both columns coexist; constraint removed so INSERT
    # doesn't fail when only the new column is populated.
    conn.execute("ALTER TABLE evolution_runs ALTER COLUMN workflow_id DROP NOT NULL")
    conn.execute(
        "ALTER TABLE evolution_proposals ALTER COLUMN mutated_config DROP NOT NULL"
    )
    # agents.project_id FK (added 2026-03) — links ft-* project agents back to their project
    # Rationale: needed for project-scoped agent queries (ADR-0009 project isolation).
    conn.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS project_id TEXT")

    # Hook system (2026-03) — pre/post tool hooks with RBAC
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hook_registrations (
            id TEXT PRIMARY KEY,
            hook_type TEXT NOT NULL,
            handler_name TEXT NOT NULL,
            agent_id TEXT,
            priority INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            can_block INTEGER DEFAULT 0,
            required_role TEXT,
            config_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hook_log (
            id TEXT PRIMARY KEY,
            hook_type TEXT,
            handler_name TEXT,
            agent_id TEXT,
            session_id TEXT,
            tool_name TEXT,
            blocked INTEGER DEFAULT 0,
            message TEXT,
            duration_ms INTEGER,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Instinct system — ECC continuous-learning-v2 adapted for server-side
    # SOURCE: https://github.com/affaan-m/everything-claude-code/tree/main/skills/continuous-learning-v2
    # WHY: Atomic learned behaviors extracted from sessions, with confidence scoring and project scoping.
    #      Allows agents to evolve skills from observed patterns rather than manual curation.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS instinct_observations (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            session_id TEXT,
            project_id TEXT,
            tool_name TEXT,
            args_json TEXT DEFAULT '{}',
            outcome TEXT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS instinct_insights (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            instinct_ids TEXT NOT NULL,
            summary TEXT NOT NULL,
            domains TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_insights_type ON instinct_insights(type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_insights_conf ON instinct_insights(confidence DESC)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS instincts (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            project_id TEXT,
            trigger TEXT NOT NULL,
            action TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            domain TEXT DEFAULT 'general',
            scope TEXT DEFAULT 'project',
            evidence_json TEXT DEFAULT '[]',
            source TEXT DEFAULT 'session-observation',
            evolved_into TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ECC — external module integration entry
    # SOURCE: https://github.com/affaan-m/everything-claude-code
    # WHY: Allow admins to toggle ECC-inspired features on/off without code changes.
    conn.execute("""
        INSERT OR IGNORE INTO integrations (id, name, type, category, icon, description, enabled, status, config_json, agent_roles)
        VALUES (
            'ecc-everything-claude',
            'Everything Claude Code (ECC)',
            'external',
            'platform',
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
            'ECC-inspired features: instinct system (continuous learning from sessions), skill-stocktake auditor, hook profiles. Source: github.com/affaan-m/everything-claude-code',
            1,
            'connected',
            '{"repo": "https://github.com/affaan-m/everything-claude-code", "features": ["instinct-observer", "skill-stocktake", "quality-gate", "pre-compact"], "hook_profile": "standard", "observer_enabled": true, "min_observations": 10}',
            '["ac-architect", "platform"]'
        )
    """)

    # Agent-specific hook assignments (seeded defaults)
    # SOURCE: ECC hooks.json — maps agent roles to appropriate hook types
    # WHY: security agents watch PRE_TOOL (can potentially block), QA runs quality-gate,
    #      ac-architect + ac-codex run instinct observer to accumulate learning.
    for _agent, _htype, _hname, _can_block, _role in [
        # AC agents: instinct observer fires at SESSION_END
        ("ac-architect", "session_end", "instinct_observer", 0, None),
        ("ac-codex", "session_end", "instinct_observer", 0, None),
        # QA agents: quality gate fires POST_TOOL
        ("qa-security", "post_tool", "quality_gate", 0, "quality"),
        ("ciso", "post_tool", "quality_gate", 0, "security"),
        # Security agents: PRE_TOOL hook (non-blocking by default — security-critic decides)
        ("security-critic", "pre_tool", "security_scan_noop", 0, "security"),
        ("security-architect", "pre_tool", "security_scan_noop", 0, "security"),
    ]:
        conn.execute(
            """
            INSERT OR IGNORE INTO hook_registrations
            (id, hook_type, handler_name, agent_id, priority, enabled, can_block, required_role, config_json)
            VALUES (?,?,?,?,?,1,?,?,?)
        """,
            (
                f"builtin-{_agent}-{_htype}",
                _htype,
                _hname,
                _agent,
                5,
                _can_block,
                _role,
                "{}",
            ),
        )

    # Security audit log — used by security/audit.py and agents/guardrails.py
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id SERIAL PRIMARY KEY,
            actor TEXT,
            action TEXT,
            resource_type TEXT,
            resource_id TEXT,
            detail TEXT,
            ip TEXT,
            user_agent TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT,
            actor_id TEXT,
            target_type TEXT,
            target_id TEXT,
            severity TEXT,
            blocked BOOLEAN DEFAULT false,
            context_json TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aal_timestamp ON admin_audit_log(timestamp DESC)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_aal_actor ON admin_audit_log(actor)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aal_event_type ON admin_audit_log(event_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aal_resource ON admin_audit_log(resource_type, resource_id)"
    )

    conn.commit()


def get_db(db_path: Path = DB_PATH):
    """Get a database connection. Returns PostgreSQL adapter."""
    return get_connection()
