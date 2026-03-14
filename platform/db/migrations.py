"""
Database migrations and initialization for the platform.
Supports dual backend: SQLite (local) / PostgreSQL (production).
Backend selected via DATABASE_URL env var.
"""
# Ref: feat-settings

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
    if _USE_PG:
        conn = _init_pg()
        _log.info("DB (PostgreSQL) schema v%s ready", _SCHEMA_VERSION)
    else:
        conn = _init_sqlite(db_path)
        _log.info("DB (SQLite) schema v%s ready at %s", _SCHEMA_VERSION, db_path)
    return conn


def _init_pg():
    """Initialize PostgreSQL schema.

    Uses a PostgreSQL advisory lock (id=20260301) so that when multiple nodes
    start simultaneously they serialize schema migrations instead of racing.
    """
    import logging as _logging

    _log = _logging.getLogger(__name__)
    conn = get_connection()
    # Acquire exclusive advisory lock — other nodes block here until migration done
    try:
        conn.execute("SELECT pg_advisory_lock(20260301)")
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


def _init_sqlite(db_path: Path = DB_PATH):
    """Initialize SQLite database with schema."""
    import sqlite3

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    # Align SQLite with PG schema — add missing columns
    _add_missing_columns = [
        ("projects", "owner_id", "TEXT DEFAULT ''"),
        ("projects", "starred", "INTEGER DEFAULT 0"),
        ("projects", "container_url", "TEXT DEFAULT ''"),
    ]
    for table, col, typedef in _add_missing_columns:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass  # column already exists
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
    # epic_runs: missing columns added post-launch (added 2026-03)
    for col, defn in [
        ("resume_attempts", "INTEGER DEFAULT 0"),
        ("last_resume_at", "TEXT"),
        ("human_input_required", "INTEGER DEFAULT 0"),
        ("llm_cost_usd", "DOUBLE PRECISION DEFAULT 0.0"),
        ("cancel_reason", "TEXT"),
        ("started_at", "TIMESTAMP"),
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rtk_ts ON rtk_compression_stats(ts)"
    )
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
            last_seen TIMESTAMPTZ DEFAULT NOW(),
            status TEXT NOT NULL DEFAULT 'online',
            cpu_pct DOUBLE PRECISION DEFAULT 0,
            mem_pct DOUBLE PRECISION DEFAULT 0,
            version TEXT DEFAULT '',
            registered_at TIMESTAMPTZ DEFAULT NOW()
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

    conn.commit()

    # Acceptance criteria + User journeys tables (traceability chain, 2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS acceptance_criteria (
            id          TEXT PRIMARY KEY,
            feature_id  TEXT NOT NULL,
            story_id    TEXT DEFAULT '',
            title       TEXT NOT NULL DEFAULT '',
            given_text  TEXT NOT NULL DEFAULT '',
            when_text   TEXT NOT NULL DEFAULT '',
            then_text   TEXT NOT NULL DEFAULT '',
            and_text    TEXT DEFAULT '',
            status      TEXT DEFAULT 'pending',
            verified_by TEXT DEFAULT '',
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_feature ON acceptance_criteria(feature_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_story   ON acceptance_criteria(story_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_status  ON acceptance_criteria(status)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_journeys (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL,
            persona_id  TEXT DEFAULT '',
            title       TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            steps_json  TEXT DEFAULT '[]',
            pain_points TEXT DEFAULT '',
            opportunities TEXT DEFAULT '',
            status      TEXT DEFAULT 'draft',
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journey_project ON user_journeys(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journey_persona ON user_journeys(persona_id)")

    # --- Wiki pages: owner RBAC columns ---
    for col, default in [("owner", "NULL"), ("visibility", "'public'")]:
        try:
            conn.execute(f"ALTER TABLE wiki_pages ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS adversarial_events (
            id SERIAL PRIMARY KEY,
            run_id TEXT,
            agent_name TEXT,
            agent_role TEXT,
            check_type TEXT,
            score INTEGER DEFAULT 0,
            passed BOOLEAN DEFAULT TRUE,
            issues_json TEXT DEFAULT '[]',
            level TEXT DEFAULT 'L0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_adv_run_id ON adversarial_events(run_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_adv_check_type ON adversarial_events(check_type, created_at)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS code_traceability (
            id SERIAL PRIMARY KEY,
            run_id TEXT DEFAULT '',
            epic_id TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            user_story_id TEXT DEFAULT '',
            file_path TEXT NOT NULL,
            rationale TEXT DEFAULT '',
            ref_tag TEXT DEFAULT '',
            agent_name TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trace_file ON code_traceability(file_path)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trace_feature ON code_traceability(feature_id)
    """)

    # Add traceability columns to features and user_stories if missing
    for col, defn in [
        ("rationale", "TEXT DEFAULT ''"),
        ("why_text", "TEXT DEFAULT ''"),
        ("req_ref", "TEXT DEFAULT ''"),
        ("wsjf_score", "REAL DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE features ADD COLUMN IF NOT EXISTS {col} {defn}")
        except Exception:
            pass
    for col, defn in [
        ("rationale", "TEXT DEFAULT ''"),
        ("why_text", "TEXT DEFAULT ''"),
        ("req_ref", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE user_stories ADD COLUMN IF NOT EXISTS {col} {defn}")
        except Exception:
            pass

    # ── Legacy Items inventory (migration traceability) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS legacy_items (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id TEXT DEFAULT '',
            description TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            source_file TEXT DEFAULT '',
            source_line INTEGER DEFAULT 0,
            status TEXT DEFAULT 'identified',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_legacy_project ON legacy_items(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_legacy_type ON legacy_items(item_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_legacy_parent ON legacy_items(parent_id)")

    # ── Traceability links (bidirectional: legacy↔story↔code↔test) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traceability_links (
            id SERIAL PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            link_type TEXT NOT NULL,
            coverage_pct INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tlink_pair ON traceability_links(source_id, target_id, link_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tlink_source ON traceability_links(source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tlink_target ON traceability_links(target_id)")

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

    # Password reset codes table (added 2026-03)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_codes (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            attempts INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def get_db(db_path: Path = DB_PATH):
    """Get a database connection. Returns PostgreSQL adapter."""
    return get_connection()
