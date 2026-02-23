-- Macaron Agent Platform - Database Schema v3
-- SQLite with FTS5 for full-text search

-- ============================================================================
-- AGENTS (definitions + instances)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'worker',
    description TEXT DEFAULT '',
    system_prompt TEXT DEFAULT '',
    provider TEXT DEFAULT 'anthropic',
    model TEXT DEFAULT 'MiniMax-M2.5',
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    skills_json TEXT DEFAULT '[]',
    tools_json TEXT DEFAULT '[]',
    mcps_json TEXT DEFAULT '[]',
    permissions_json TEXT DEFAULT '{}',
    tags_json TEXT DEFAULT '[]',
    icon TEXT DEFAULT 'bot',
    color TEXT DEFAULT '#f78166',
    is_builtin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    avatar TEXT DEFAULT '',
    tagline TEXT DEFAULT '',
    persona TEXT DEFAULT '',
    motivation TEXT DEFAULT '',
    hierarchy_rank INTEGER DEFAULT 50
);

CREATE INDEX IF NOT EXISTS idx_agents_role ON agents(role);

-- Agent instances (running agents in a session)
CREATE TABLE IF NOT EXISTS agent_instances (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    session_id TEXT REFERENCES sessions(id),
    status TEXT DEFAULT 'idle',
    current_task TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_instances_session ON agent_instances(session_id);
CREATE INDEX IF NOT EXISTS idx_instances_agent ON agent_instances(agent_id);

-- ============================================================================
-- PATTERNS (workflow templates)
-- ============================================================================

CREATE TABLE IF NOT EXISTS patterns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT DEFAULT 'sequential',
    agents_json TEXT DEFAULT '[]',
    edges_json TEXT DEFAULT '[]',
    config_json TEXT DEFAULT '{}',
    memory_config_json TEXT DEFAULT '{}',
    icon TEXT DEFAULT 'workflow',
    is_builtin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SKILLS
-- ============================================================================

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    content TEXT DEFAULT '',
    source TEXT DEFAULT 'local',
    source_url TEXT DEFAULT '',
    tags_json TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- MCP SERVERS
-- ============================================================================

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
);

-- ============================================================================
-- MISSIONS (production pipeline: Mission → Sprint → Task)
-- ============================================================================

CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal TEXT DEFAULT '',
    status TEXT DEFAULT 'planning',
    type TEXT DEFAULT 'feature',
    workflow_id TEXT,
    parent_mission_id TEXT,
    wsjf_score REAL DEFAULT 0,
    created_by TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_missions_project ON missions(project_id);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);

CREATE TABLE IF NOT EXISTS sprints (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    number INTEGER NOT NULL DEFAULT 1,
    name TEXT DEFAULT '',
    goal TEXT DEFAULT '',
    status TEXT DEFAULT 'planning',
    retro_notes TEXT DEFAULT '',
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sprints_mission ON sprints(mission_id);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    sprint_id TEXT NOT NULL REFERENCES sprints(id),
    mission_id TEXT NOT NULL REFERENCES missions(id),
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT DEFAULT 'feature',
    domain TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    assigned_to TEXT,
    priority INTEGER DEFAULT 0,
    files_changed TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);
CREATE INDEX IF NOT EXISTS idx_tasks_mission ON tasks(mission_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

-- ============================================================================
-- FEATURES (PO backlog items — extracted from agent discussions)
-- ============================================================================

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
);

CREATE INDEX IF NOT EXISTS idx_features_epic ON features(epic_id);

-- ============================================================================
-- SESSIONS (legacy — kept for backward compatibility)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    pattern_id TEXT REFERENCES patterns(id),
    project_id TEXT,
    status TEXT DEFAULT 'planning',
    goal TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);

-- ============================================================================
-- MESSAGES (A2A + user)
-- ============================================================================

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    message_type TEXT DEFAULT 'inform',
    content TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    artifacts_json TEXT DEFAULT '[]',
    parent_id TEXT REFERENCES messages(id),
    priority INTEGER DEFAULT 5,
    requires_response INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_agent);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content, content=messages, content_rowid=rowid
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
END;

-- ============================================================================
-- ARTIFACTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    type TEXT DEFAULT 'code',
    name TEXT NOT NULL,
    content TEXT DEFAULT '',
    language TEXT,
    version INTEGER DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id);

-- ============================================================================
-- MEMORY (4 layers)
-- ============================================================================

-- Pattern memory (shared context within a workflow run)
CREATE TABLE IF NOT EXISTS memory_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    type TEXT DEFAULT 'context',
    author_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mempat_session ON memory_pattern(session_id);
CREATE INDEX IF NOT EXISTS idx_mempat_type ON memory_pattern(type);

-- Project memory (persistent per-project knowledge)
CREATE TABLE IF NOT EXISTS memory_project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memproj_project ON memory_project(project_id);
CREATE INDEX IF NOT EXISTS idx_memproj_category ON memory_project(category);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_project_fts USING fts5(
    key, value, content=memory_project, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS memproj_ai AFTER INSERT ON memory_project BEGIN
    INSERT INTO memory_project_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS memproj_ad AFTER DELETE ON memory_project BEGIN
    INSERT INTO memory_project_fts(memory_project_fts, rowid, key, value) VALUES('delete', old.id, old.key, old.value);
END;

-- Global memory (cross-project learnings)
CREATE TABLE IF NOT EXISTS memory_global (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    occurrences INTEGER DEFAULT 1,
    projects_json TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memglob_category ON memory_global(category);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_global_fts USING fts5(
    key, value, content=memory_global, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS memglob_ai AFTER INSERT ON memory_global BEGIN
    INSERT INTO memory_global_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS memglob_ad AFTER DELETE ON memory_global BEGIN
    INSERT INTO memory_global_fts(memory_global_fts, rowid, key, value) VALUES('delete', old.id, old.key, old.value);
END;

-- ============================================================================
-- TOOL CALLS (audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    session_id TEXT,
    tool_name TEXT NOT NULL,
    parameters_json TEXT DEFAULT '{}',
    result_json TEXT DEFAULT '{}',
    success INTEGER DEFAULT 1,
    duration_ms INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_toolcalls_agent ON tool_calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_toolcalls_ts ON tool_calls(timestamp);

-- ============================================================================
-- SKILL GITHUB SOURCES
-- ============================================================================

CREATE TABLE IF NOT EXISTS skill_github_sources (
    repo TEXT PRIMARY KEY,
    path TEXT DEFAULT '',
    branch TEXT DEFAULT 'main',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- IDEATION SESSIONS (persistent brainstorming history)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ideation_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    status TEXT DEFAULT 'draft',          -- draft | analyzed | epic_created
    mission_id TEXT DEFAULT '',           -- FK → missions.id (when epic created)
    project_id TEXT DEFAULT '',           -- FK → projects.id (when project created)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ideation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES ideation_sessions(id),
    agent_id TEXT NOT NULL DEFAULT 'system',
    agent_name TEXT NOT NULL DEFAULT '',
    role TEXT DEFAULT '',
    target TEXT DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    color TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ideation_msgs_session ON ideation_messages(session_id);

CREATE TABLE IF NOT EXISTS ideation_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES ideation_sessions(id),
    type TEXT NOT NULL DEFAULT 'opportunity',   -- opportunity | risk | question | decision | feature
    text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_ideation_findings_session ON ideation_findings(session_id);

-- ── Retrospectives (self-improvement feedback loop) ──
CREATE TABLE IF NOT EXISTS retrospectives (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT 'session',  -- session | sprint | project | global
    scope_id TEXT DEFAULT '',               -- session_id, sprint_id, project_id
    successes TEXT DEFAULT '[]',            -- JSON array of success items
    failures TEXT DEFAULT '[]',             -- JSON array of failure items
    lessons TEXT DEFAULT '[]',              -- JSON array of lessons learned
    improvements TEXT DEFAULT '[]',         -- JSON array of suggested improvements
    metrics_json TEXT DEFAULT '{}',         -- metrics snapshot (duration, tokens, tool_calls)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_retro_scope ON retrospectives(scope, scope_id);

-- ============================================================================
-- ORG TREE (SAFe hierarchy: Portfolio → ART → Team)
-- ============================================================================

CREATE TABLE IF NOT EXISTS org_portfolios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    lead_agent_id TEXT DEFAULT '',
    budget_allocated REAL DEFAULT 0,
    budget_consumed REAL DEFAULT 0,
    fiscal_year INTEGER DEFAULT 2025,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS org_arts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    portfolio_id TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    lead_agent_id TEXT DEFAULT '',
    pi_cadence_weeks INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_arts_portfolio ON org_arts(portfolio_id);

CREATE TABLE IF NOT EXISTS org_teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    art_id TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    scrum_master_id TEXT DEFAULT '',
    capacity INTEGER DEFAULT 5,
    wip_limit INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_art ON org_teams(art_id);

CREATE TABLE IF NOT EXISTS org_team_members (
    team_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    PRIMARY KEY (team_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_agent ON org_team_members(agent_id);

-- Mission Control: lifecycle runs with phase tracking
CREATE TABLE IF NOT EXISTS mission_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_name TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    cdp_agent_id TEXT DEFAULT 'chef_de_programme',
    project_id TEXT DEFAULT '',
    workspace_path TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    current_phase TEXT DEFAULT '',
    phases_json TEXT DEFAULT '[]',
    brief TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_mission_runs_project ON mission_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_mission_runs_status ON mission_runs(status);

-- Custom AI Providers: User-configurable LLM providers
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
);

CREATE INDEX IF NOT EXISTS idx_custom_ai_enabled ON custom_ai_providers(enabled);
