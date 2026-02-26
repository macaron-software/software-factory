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
    if _USE_PG:
        return _init_pg()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)

    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    conn.commit()
    return conn


def _init_pg():
    """Initialize PostgreSQL schema."""
    conn = get_connection()
    schema = SCHEMA_PG_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evprop_wf ON evolution_proposals(base_wf_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evprop_status ON evolution_proposals(status)")

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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rl_exp_mission ON rl_experience(mission_id)")

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

    # Add cost_usd to llm_traces if not present
    try:
        conn.execute("ALTER TABLE llm_traces ADD COLUMN cost_usd REAL DEFAULT 0.0")
    except Exception:
        pass

def _migrate_pg(conn):
    """PostgreSQL incremental migrations (safe ALTER TABLE IF NOT EXISTS)."""
    # PG schema_pg.sql already includes all columns, but for future migrations:
    pass


def get_db(db_path: Path = DB_PATH):
    """Get a database connection. Returns SQLite or PostgreSQL adapter."""
    if _USE_PG:
        conn = get_connection()
        return conn

    if not db_path.exists():
        return init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
