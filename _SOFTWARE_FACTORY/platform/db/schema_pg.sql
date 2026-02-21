-- Macaron Agent Platform — PostgreSQL Schema v3
-- Requires extensions: pgvector, pg_trgm, uuid-ossp

-- ============================================================================
-- WORKFLOWS (created at runtime by WorkflowStore)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    phases_json TEXT DEFAULT '[]',
    config_json TEXT DEFAULT '{}',
    icon TEXT DEFAULT 'workflow',
    is_builtin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PROJECTS (created at runtime by ProjectManager)
-- ============================================================================

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    factory_type TEXT DEFAULT 'standalone',
    domains_json TEXT DEFAULT '[]',
    vision TEXT DEFAULT '',
    values_json TEXT DEFAULT '[]',
    lead_agent_id TEXT DEFAULT '',
    agents_json TEXT DEFAULT '[]',
    active_pattern_id TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- AGENTS
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

-- ============================================================================
-- AGENT INSTANCES
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_instances (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    session_id TEXT,
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
-- MISSIONS
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
    completed_at TIMESTAMP,
    business_value REAL DEFAULT 0,
    time_criticality REAL DEFAULT 0,
    risk_reduction REAL DEFAULT 0,
    job_duration REAL DEFAULT 1,
    kanban_status TEXT DEFAULT 'funnel'
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
    completed_at TIMESTAMP,
    velocity INTEGER DEFAULT 0,
    planned_sp INTEGER DEFAULT 0
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
-- FEATURES
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

CREATE TABLE IF NOT EXISTS feature_deps (
    feature_id TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    dep_type TEXT DEFAULT 'blocked_by',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (feature_id, depends_on)
);

-- ============================================================================
-- SESSIONS
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
-- MESSAGES (with tsvector for full-text search instead of FTS5)
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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_agent);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_fts ON messages USING GIN(content_tsv);

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
-- MEMORY (4 layers — tsvector replaces FTS5, vector replaces numpy)
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_pattern (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    type TEXT DEFAULT 'context',
    author_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mempat_session ON memory_pattern(session_id);
CREATE INDEX IF NOT EXISTS idx_mempat_type ON memory_pattern(type);

CREATE TABLE IF NOT EXISTS memory_project (
    id SERIAL PRIMARY KEY,
    project_id TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(key, '') || ' ' || coalesce(value, ''))
    ) STORED,
    embedding vector(1536)
);
CREATE INDEX IF NOT EXISTS idx_memproj_project ON memory_project(project_id);
CREATE INDEX IF NOT EXISTS idx_memproj_category ON memory_project(category);
CREATE INDEX IF NOT EXISTS idx_memproj_fts ON memory_project USING GIN(search_tsv);
CREATE INDEX IF NOT EXISTS idx_memproj_vec ON memory_project USING ivfflat(embedding vector_cosine_ops) WITH (lists = 10);

CREATE TABLE IF NOT EXISTS memory_global (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    occurrences INTEGER DEFAULT 1,
    projects_json TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(key, '') || ' ' || coalesce(value, ''))
    ) STORED,
    embedding vector(1536)
);
CREATE INDEX IF NOT EXISTS idx_memglob_category ON memory_global(category);
CREATE INDEX IF NOT EXISTS idx_memglob_fts ON memory_global USING GIN(search_tsv);

-- ============================================================================
-- TOOL CALLS
-- ============================================================================

CREATE TABLE IF NOT EXISTS tool_calls (
    id SERIAL PRIMARY KEY,
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
-- IDEATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS ideation_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    status TEXT DEFAULT 'draft',
    mission_id TEXT DEFAULT '',
    project_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ideation_messages (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES ideation_sessions(id),
    type TEXT NOT NULL DEFAULT 'opportunity',
    text TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ideation_findings_session ON ideation_findings(session_id);

-- ============================================================================
-- RETROSPECTIVES
-- ============================================================================

CREATE TABLE IF NOT EXISTS retrospectives (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT 'session',
    scope_id TEXT DEFAULT '',
    successes TEXT DEFAULT '[]',
    failures TEXT DEFAULT '[]',
    lessons TEXT DEFAULT '[]',
    improvements TEXT DEFAULT '[]',
    metrics_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_retro_scope ON retrospectives(scope, scope_id);

-- ============================================================================
-- AGENT SCORES
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_scores (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    epic_id TEXT NOT NULL,
    accepted INTEGER DEFAULT 0,
    rejected INTEGER DEFAULT 0,
    iterations INTEGER DEFAULT 0,
    quality_score REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, epic_id)
);

-- ============================================================================
-- ORG TREE (SAFe)
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

-- ============================================================================
-- MISSION RUNS
-- ============================================================================

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_mission_runs_project ON mission_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_mission_runs_status ON mission_runs(status);

-- ============================================================================
-- PROGRAM INCREMENTS
-- ============================================================================

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
);
CREATE INDEX IF NOT EXISTS idx_pi_art ON program_increments(art_id);

-- ============================================================================
-- CONFLUENCE SYNC
-- ============================================================================

CREATE TABLE IF NOT EXISTS confluence_pages (
    mission_id TEXT NOT NULL,
    tab TEXT NOT NULL,
    confluence_page_id TEXT NOT NULL,
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (mission_id, tab)
);

-- ============================================================================
-- SUPPORT TICKETS
-- ============================================================================

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
);
CREATE INDEX IF NOT EXISTS idx_tickets_mission ON support_tickets(mission_id);

-- ============================================================================
-- PERFORMANCE INDEXES (missing from initial schema)
-- ============================================================================

-- Missions: sort by priority
CREATE INDEX IF NOT EXISTS idx_missions_wsjf ON missions(wsjf_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_missions_created ON missions(created_at);

-- Sessions: timeline queries
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);

-- Messages: heavy aggregation queries
CREATE INDEX IF NOT EXISTS idx_messages_session_from ON messages(session_id, from_agent);

-- Tool calls: subquery by session
CREATE INDEX IF NOT EXISTS idx_toolcalls_session ON tool_calls(session_id);

-- LLM traces: time-range queries + cost reports
CREATE INDEX IF NOT EXISTS idx_llm_traces_created ON llm_traces(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_traces_agent ON llm_traces(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_traces_provider ON llm_traces(provider, model);

-- Sprints: status queries
CREATE INDEX IF NOT EXISTS idx_sprints_status ON sprints(status);

-- Features: status board
CREATE INDEX IF NOT EXISTS idx_features_status ON features(status);

-- Incidents: open incident scan (auto-heal)
CREATE INDEX IF NOT EXISTS idx_incidents_status ON platform_incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON platform_incidents(severity);

-- Ideation: by project
CREATE INDEX IF NOT EXISTS idx_ideation_project ON ideation_sessions(project_id);

-- Artifacts: by type
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type);
