# COMPLETE UI AUDIT REPORT
## Platform/Web Application

---

## 1. ROUTES OVERVIEW

### Navigation Structure (from base.html)
**Sidebar Navigation with Role-Based Visibility:**

#### Simple UI (Minimal Navigation)
- **Home** → `/` (Home page)
- **Projects** → `/projects` (Projects page)
- **Sessions** → `/sessions` (Live Sessions)
- **Teams** → `/art` (ART/Agents/Organisation SAFe)
- **Metrics** → `/metrics` (Metrics & Ops)
- **Users** → `/rbac` (Admin only - Users & Roles)

#### Full UI (Role-Based Navigation)
1. **Cockpit** → `/cockpit` (Core dashboard)
2. **Home** → `/` 
3. **Portfolio/Dashboard** → `/portfolio` (DSI Board, Vue Métier)
4. **Backlog** → `/backlog` (Product, Idéation) - Multiple roles
5. **PI Board** → `/pi` (Program Increment, Epics) - Multiple roles
6. **Workflows** → `/workflows` (Patterns) - Multiple roles
7. **Projects** → `/projects` - Multiple roles
8. **Sessions** → `/sessions` (Live) - Multiple roles
9. **Teams** → `/art` - Multiple roles
10. **Metrics** → `/metrics` (Ops) - Multiple roles

---

## 2. ALL ROUTES BY MODULE (84 HTML Routes + 241 APIs = 325 Total)

### A. **pages.py** (4,158 lines) - Core Pages
**HTML Pages:**
- GET `/robots.txt` → robots_txt
- GET `/login` → login.html
- GET `/privacy` → privacy.html
- GET `/onboarding` → onboarding.html
- GET `/setup` → setup.html
- GET `/` → home.html
- GET `/cockpit` → cockpit.html (13 sections - see Section 4)
- GET `/dashboard` → dashboard.html
- GET `/portfolio` → portfolio.html
- GET `/backlog?tab=` → backlog.html
- GET `/pi` → pi_board.html (Program Increment board)
- GET `/workflows?tab=templates` → workflows.html
- GET `/workflows/list` → workflow graph visualization
- GET `/workflows/evolution` → evolution tracking
- GET `/workflows/improvement` → improvement cycles
- GET `/workflows/improvement/cycles/{project_id}` → cycle details

**APIs (Improvement Cycle):**
- POST `/api/improvement/start/{project_id}` - Start cycle
- POST `/api/improvement/stop/{project_id}` - Stop cycle
- POST `/api/improvement/rollback/{project_id}` - Rollback
- POST `/api/improvement/experiment` - Record experiment
- POST `/api/improvement/inject-cycle` - Inject cycle
- GET `/api/improvement/screenshot/{project_id}/{cycle_num}` - Screenshot
- POST `/api/improvement/backfill/{project_id}` - Backfill
- GET `/api/improvement/project/{project_id}` - Project state

---

### B. **projects.py** (3,987 lines) - Project Management
**HTML Pages:**
- GET `/projects` → projects.html (Projects list)
- GET `/projects/{project_id}/hub` → project_hub.html
- GET `/projects/{project_id}/product` → project_product.html
- GET `/projects/{project_id}/overview` → project_overview.html
- GET `/projects/{project_id}` → project_detail.html
- GET `/projects/{project_id}/board` → project_board_page.html
- GET `/projects/{project_id}/workspace` → project_workspace.html

**APIs (Projects):**
- GET `/api/projects` - List all projects (JSON)
- POST `/api/projects` - Create project
- GET `/api/projects/{project_id}/phase` - Get phase
- POST `/api/projects/{project_id}/phase` - Set phase
- GET `/api/projects/{project_id}/gate` - Gate check
- GET `/api/projects/{project_id}/health` - Health metrics
- GET `/api/projects/{project_id}/missions/suggest` - Mission suggestions
- POST `/api/projects/{project_id}/scaffold` - Scaffold project
- GET `/api/projects/{project_id}/git-status` - Git status
- POST `/api/projects/{project_id}/vision` - Update vision
- POST `/api/projects/{project_id}/chat` - Chat endpoint
- POST `/api/projects/{project_id}/conversations` - Create conversation
- POST `/api/projects/{project_id}/chat/stream` - Stream chat
- POST `/api/projects/{project_id}/heal` - Heal project
- GET `/api/projects/{project_id}/workspace/*` - Workspace endpoints (9 variants)

**Workspace Endpoints:**
- GET `/api/projects/{project_id}/workspace/tool-calls`
- GET `/api/projects/{project_id}/workspace/run`
- GET `/api/projects/{project_id}/workspace/live`
- GET `/api/projects/{project_id}/workspace/metrics`
- GET `/api/projects/{project_id}/workspace/progress`
- GET `/api/projects/{project_id}/workspace/messages`
- GET `/api/projects/{project_id}/workspace/files`
- GET `/api/projects/{project_id}/workspace/file`
- POST `/api/projects/{project_id}/workspace/file/save`
- GET `/api/projects/{project_id}/workspace/diff`
- GET `/api/projects/{project_id}/workspace/docker`

**Screen/Annotation APIs:**
- POST `/api/projects/{project_id}/wireframe` - Create wireframe
- GET `/api/projects/{project_id}/screens` - List screens
- GET `/api/projects/{project_id}/screens/{screen_id}/svg` - Screen SVG
- DELETE `/api/projects/{project_id}/screens/{screen_id}` - Delete screen
- GET `/api/projects/{project_id}/annotations` - List annotations
- POST `/api/projects/{project_id}/annotations` - Create annotation
- PATCH `/api/projects/{project_id}/annotations/{ann_id}` - Update annotation
- DELETE `/api/projects/{project_id}/annotations/{ann_id}` - Delete annotation
- GET `/api/projects/{project_id}/annotations/export` - Export
- POST `/api/projects/{project_id}/annotations/fix-all` - Auto-fix
- GET `/api/projects/{project_id}/screens/{screen_id}/traceability` - Traceability

---

### C. **sessions.py** (1,365 lines) - Agent Sessions
**HTML Pages:**
- GET `/sessions` → sessions.html
- GET `/sessions/new` → new_session.html
- GET `/sessions/{session_id}/live` → session_live.html
- GET `/sessions/{session_id}` → session page

**APIs (Sessions):**
- POST `/api/sessions` - Create session
- POST `/api/sessions/{session_id}/messages` - Send message
- GET `/api/sessions/{session_id}/messages` - Poll messages
- GET `/api/sessions/{session_id}/messages/json` - Messages (JSON)
- POST `/api/sessions/{session_id}/stop` - Stop session
- POST `/api/sessions/{session_id}/resume` - Resume session
- POST `/api/sessions/{session_id}/run-pattern` - Run pattern
- DELETE `/api/sessions/{session_id}` - Delete session
- POST `/api/sessions/{session_id}/agents/start` - Start agents
- POST `/api/sessions/{session_id}/agents/stop` - Stop agents
- POST `/api/sessions/{session_id}/agents/{agent_id}/message` - Send to agent
- POST `/api/sessions/{session_id}/conversation` - Start conversation
- GET `/api/sessions/{session_id}/checkpoints` - Checkpoints
- GET `/api/sessions/{session_id}/sse` - Server-sent events
- GET `/api/sessions/{session_id}/stream` - Stream endpoint

---

### D. **agents.py** (1,079 lines) - Agent Management
**HTML Pages:**
- GET `/agents` → agents.html
- GET `/agents/new` → agent_new.html
- GET `/agents/{agent_id}/edit` → agent_edit.html
- GET `/patterns` → patterns.html
- GET `/patterns/list` → patterns_list.html
- GET `/patterns/new` → pattern_new.html
- GET `/patterns/{pattern_id}/edit` → pattern_edit.html
- GET `/skills` → skills.html
- GET `/skills/{skill_id}` → skill_detail.html
- GET `/mcps` → mcps.html (Model Context Protocol servers)
- GET `/org` → org.html (Organization tree)

**APIs (Agents):**
- GET `/api/agents` - List agents (JSON)
- POST `/api/agents` - Create agent
- POST `/api/agents/{agent_id}` - Update agent
- DELETE `/api/agents/{agent_id}` - Delete agent
- GET `/api/agents/{agent_id}/details` - Agent details

**APIs (Patterns):**
- POST `/api/patterns` - Create pattern
- POST `/api/patterns/{pattern_id}` - Update pattern
- DELETE `/api/patterns/{pattern_id}` - Delete pattern
- POST `/api/patterns/recommend` - Pattern recommendations
- GET `/api/analytics/patterns/ab` - A/B test analytics

**APIs (Skills):**
- GET `/api/llm/providers` - LLM providers
- POST `/api/skills/reload` - Reload skills
- POST `/api/admin/skills/update` - Update skill file
- POST `/api/skills/github/add` - Add GitHub source
- POST `/api/skills/github/sync` - Sync GitHub
- POST `/api/skills/github/remove` - Remove GitHub source
- GET `/api/skills/stocktake` - Skills inventory

**APIs (MCPs):**
- POST `/api/mcps/{mcp_id}/start` - Start MCP
- POST `/api/mcps/{mcp_id}/stop` - Stop MCP
- POST `/api/mcps/{mcp_id}/test` - Test MCP
- POST `/api/mcps/{mcp_id}/call` - Call MCP
- GET `/api/mcps/status` - MCP status

**APIs (Organization):**
- GET `/api/org/tree` - Organization tree

---

### E. **analytics.py** (1,218 lines) - Metrics & Analytics
**HTML Pages:**
- GET `/metrics` → metrics.html
- GET `/metrics/tab/dora` → _partial_dora.html
- GET `/metrics/tab/quality` → _partial_quality.html
- GET `/metrics/tab/analytics` → _partial_analytics.html
- GET `/metrics/tab/monitoring` → _partial_monitoring.html
- GET `/metrics/tab/pipeline` → _partial_pipeline.html
- GET `/metrics/tab/knowledge` → _partial_knowledge.html
- GET `/metrics/tab/ops` → _partial_ops.html
- GET `/teams` → teams.html
- GET `/teams/partial` → _partial_teams.html

**APIs:**
- GET `/api/metrics/dora/{project_id}` - DORA metrics
- GET `/api/metrics/prometheus` - Prometheus metrics
- GET `/api/metrics/burndown/{epic_id}` - Burndown chart
- POST `/api/quality/scan/{project_id}` - Quality scan
- GET `/api/version` - Version info

---

### F. **wiki_content.py** (5,875 lines) - Wiki & Content
**Core Features:** Largest module - handles wiki pages, content, history

**HTML/Content Routes:** (Numerous wiki-related templates)

---

### G. **workflows.py** (1,775 lines) - Workflow Management
**HTML Pages:**
- GET `/workflows` - Workflows list
- GET `/workflows/list` - Alternative list view
- GET `/workflows/evolution` - Evolution tracking

---

### H. **ideation.py** (1,084 lines) - Ideation & Brainstorming
**HTML Pages:**
- GET `/ideation` → ideation.html
- GET `/ideation/history` → ideation_history.html
- GET `/generate` → generate.html

---

### I. **cto.py** (1,189 lines) - CTO Panel & Architecture
**HTML Pages:**
- GET `/cto` → cto_panel.html
- GET `/metier` → metier.html (Métier board)
- GET `/dsi` → dsi.html (DSI board)
- GET `/dsi_workflow` → dsi_workflow.html

---

### J. **auth.py** (636 lines) - Authentication

**APIs:**
- GET `/setup` - Setup page
- GET `/api/auth/demo-login` - Demo login
- POST `/api/auth/login` - User login
- POST `/api/auth/register` - User registration (admin only)
- POST `/api/auth/refresh` - Token refresh
- POST `/api/auth/logout` - Logout
- GET `/api/auth/me` - Current user
- GET `/api/auth/list-users` - List users (admin)
- GET `/api/auth/users/{user_id}` - Get user
- POST `/api/auth/users/{user_id}` - Update user
- DELETE `/api/auth/users/{user_id}` - Delete user
- POST `/api/auth/users/{user_id}/project-role` - Set project role
- DELETE `/api/auth/users/{user_id}/project-role` - Remove project role
- POST `/api/auth/forgot-password` - Forgot password
- POST `/api/auth/verify-reset` - Verify reset code
- POST `/api/auth/reset-password` - Reset password
- POST `/api/auth/export-data` - Export user data
- DELETE `/api/auth/delete-account` - Delete account

---

### K. **API Modules** (24 API-only modules in `/routes/api/`)

| Module | Endpoints | Purpose |
|--------|-----------|---------|
| **agent_bench.py** | 4 | Agent benchmarking |
| **analytics.py** | 7 | Analytics dashboard data |
| **api_keys.py** | 3 | API key management |
| **cockpit.py** | 1 | Cockpit summary data |
| **dashboard.py** | 10 | Dashboard data (KPIs, missions, features, sprints, etc.) |
| **deploy_targets.py** | 7 | Deployment target management |
| **events.py** | 2 | Event statistics |
| **guidelines.py** | 4 | Guidelines management |
| **health.py** | 10 | System health & monitoring |
| **hooks.py** | 6 | Webhook management |
| **incidents.py** | 7 | Incident & autoheal management |
| **instincts.py** | 6 | Instinct management & evolution |
| **integrations.py** | 9 | Third-party integrations (Jira, etc.) |
| **knowledge.py** | 2 | Knowledge base endpoints |
| **llm.py** | 10 | LLM routing & provider management |
| **memory.py** | 8 | Vector memory & search |
| **modules.py** | 4 | Module management |
| **partials.py** | 9 | HTML partials for dynamic loading |
| **patterns.py** | 2 | Pattern recommendations |
| **push.py** | 4 | Push notifications |
| **rbac.py** | 4 | Role-based access control |
| **screens.py** | 11 | Screen & annotation management |
| **search.py** | 12 | Search, retrospectives, workspaces |
| **settings.py** | 4 | System settings |
| **simplify.py** | 1 | Simplification service |
| **skill_eval.py** | 5 | Skill evaluation |
| **tasks.py** | 2 | Task management |
| **team_bench.py** | 4 | Team benchmarking |
| **teams.py** | 12 | Team management & OKR |
| **traceability.py** | 2 | Traceability |
| **webhooks.py** | 7 | Webhook configuration |

---

## 3. ALL HTML TEMPLATES (126 total)

### Main Pages (Base Templates)
```
base.html                  # Main layout wrapper
base_partial.html          # Partial layout
home.html                  # Home/dashboard
login.html                 # Login page
privacy.html               # Privacy policy
onboarding.html            # Onboarding flow
setup.html                 # Initial setup
```

### Core Application Pages
```
cockpit.html               # Operational cockpit (13 sections)
dashboard.html             # Main dashboard
portfolio.html             # Portfolio view
backlog.html               # Product backlog
pi_board.html              # Program Increment board
workflows.html             # Workflow templates & patterns
workflow_edit.html         # Workflow editor
workflow_graph.html        # Workflow visualization
```

### Project Management
```
projects.html              # Projects list
project_hub.html           # Project hub/overview
project_detail.html        # Project details
project_board_page.html    # Project board
project_overview.html      # Project overview
project_product.html       # Project product view
project_workspace.html     # Project workspace
```

### Agent/Skill/Pattern Management
```
agents.html                # Agents list
agent_new.html             # Create agent
agent_edit.html            # Edit agent
agent_chat.html            # Agent chat interface
agent_world.html           # Agent world/environment
patterns.html              # Patterns library
pattern_edit.html          # Pattern editor
skills.html                # Skills directory
mcps.html                  # MCP servers
org.html                   # Organization structure
```

### Session Management
```
sessions.html              # Sessions list
session_live.html          # Live session view
new_session.html           # Create new session
conversation.html          # Conversation view
```

### Analytics & Monitoring
```
metrics.html               # Metrics dashboard
metrics_unified.html       # Unified metrics view
metrics_modules.html       # Module metrics
dora_dashboard.html        # DORA metrics
quality.html               # Quality metrics
monitoring.html            # System monitoring
ops.html                   # Operations view
teams.html                 # Team analytics
```

### Content & Wiki
```
wiki_page.html             # Wiki page view
_partial_wiki.html         # Wiki sidebar
_partial_wiki_page.html    # Wiki page partial
```

### Business/Strategic Views
```
backlog.html               # Product backlog
pi_board.html              # Program Increment
dsi.html                   # DSI board
dsi_workflow.html          # DSI workflow
portfolio.html             # Portfolio management
mercato.html               # Market view
metier.html                # Business metrics
product.html               # Product view
product_line.html          # Product line management
```

### Ideation & Innovation
```
ideation.html              # Ideation workspace
ideation_history.html      # Idea history
group_ideation.html        # Group brainstorming
mkt_ideation.html          # Market ideation
generate.html              # Content generation
```

### Mission Control
```
missions.html              # Missions list
mission_control.html       # Mission control panel
mission_control_list.html  # Mission list view
mission_detail.html        # Mission details
mission_start.html         # Start mission workflow
mission_replay.html        # Mission replay/history
```

### Configuration & Admin
```
rbac.html                  # Role/access control
admin_users.html           # User administration
settings.html              # System settings
notifications.html         # Notifications center
```

### System & Design
```
design_system.html         # Design system showcase
ac.html                    # Automation center
annotate.html              # Annotation tool
bricks.html                # Brick/component library
ceremonies.html            # Agile ceremonies
evals.html                 # Evaluations
marketplace.html           # Skills marketplace
memory.html                # Memory management
tool_builder.html          # Custom tool builder
toolbox.html               # Toolbox
workspace.html             # Workspace view
workspaces.html            # Workspaces list
```

### Partials (HTML Snippets for Dynamic Loading)
```
_partial_analytics.html    # Analytics partial
_partial_dora.html         # DORA metrics partial
_partial_knowledge.html    # Knowledge partial
_partial_monitoring.html   # Monitoring partial
_partial_ops.html          # Operations partial
_partial_pipeline.html     # Pipeline partial
_partial_quality.html      # Quality partial
_partial_teams.html        # Teams partial
_partial_tests.html        # Tests partial
```

---

## 4. COCKPIT DASHBOARD SECTIONS (13 Major Sections)

From `cockpit.html` structure:

1. **Pipeline Value Stream** - Development pipeline metrics
2. **Infrastructure 3-Column Layout** - System infrastructure status
3. **Projects + Activity Side-by-Side** - Project status and activity feed
4. **Architecture interne SF** - Internal Software Factory architecture
5. **Agents / Skills / Tools / Teams / Workflows / Workspace** - Core capability display
6. **Intégrations tierces** - Third-party integration status (6 integration boxes)
7. **Amélioration Continue (Continuous Improvement Loop)** - Process improvement with 5 pilot projects
8. **Self-Healing Architecture** - Auto-repair mechanisms
9. **Patterns Catalogue Graph** - Visual pattern library
10. **Memory Architecture** - Knowledge/memory system card
11. **Security & Isolation** - Security status and isolation controls
12. **Engineering Concepts Badge Cloud** - Technology/methodology badges
13. **Footer KPIs** - Key performance indicators dashboard

---

## 5. PAGE STATISTICS

| Metric | Count |
|--------|-------|
| **HTML Templates** | 126 |
| **HTML Routes (GET with HTMLResponse)** | 84 |
| **API Endpoints** | 241 |
| **Total Distinct Routes** | 325 |
| **Largest Route File** | wiki_content.py (5,875 lines) |
| **Second Largest** | pages.py (4,158 lines) |
| **Third Largest** | projects.py (3,987 lines) |

---

## 6. CSS FILES & SIZE

| File | Lines | Purpose |
|------|-------|---------|
| main.css | 2,199 | Core styling |
| mission-control.css | 3,160 | Mission control interface |
| components.css | 1,223 | Reusable components |
| agents.css | 1,508 | Agent interface |
| projects.css | 1,118 | Project pages |
| live.css | 1,336 | Live session styling |
| project_workspace.css | 1,077 | Workspace UI |
| ideation.css | 830 | Ideation interface |
| mercato.css | 271 | Market view |
| monitoring.css | 339 | Monitoring dashboard |
| mkt_ideation.css | 620 | Market ideation |
| **TOTAL** | **13,681** | **lines of CSS** |

---

## 7. JAVASCRIPT FILES

| File | Purpose |
|------|---------|
| **agents.js** | Agent management interactions |
| **workspace.js** | Project workspace functionality |
| **sse.js** | Server-sent events handling |
| **htmx.min.js** | HTMX library (dynamic updates) |
| **codemirror6.min.js** | Code editor |
| **chart.umd.min.js** | Chart visualization |
| **sortable.min.js** | Drag-and-drop sorting |

---

## 8. ROLE-BASED NAVIGATION ACCESS

### Roles & Perspective Levels
- `admin` - Full access
- `overview` - Overview perspective
- `dsi` - DSI perspective
- `portfolio_manager` - Portfolio management
- `product_owner` - Product ownership
- `architect` - Architecture decisions
- `business_owner` - Business decisions
- `rte` - Release Train Engineer
- `scrum_master` - Scrum/Agile facilitation
- `qa_security` - QA and security
- `developer` - Development

### Conditional Menu Items Based on Role
- **Backlog**: `admin`, `overview`, `dsi`, `portfolio_manager`, `product_owner`, `architect`, `business_owner`
- **PI Board**: `admin`, `overview`, `dsi`, `portfolio_manager`, `rte`, `product_owner`, `scrum_master`, `architect`, `business_owner`
- **Workflows**: `admin`, `overview`, `dsi`, `rte`, `scrum_master`, `qa_security`
- **Projects**: `admin`, `overview`, `dsi`, `product_owner`, `developer`, `architect`, `qa_security`
- **Sessions**: `admin`, `overview`, `dsi`, `rte`, `product_owner`, `scrum_master`, `developer`, `qa_security`

---

## 9. KEY FEATURES SUMMARY

### User-Facing Pages & Data
1. **Cockpit** - Comprehensive operational dashboard with 13 sections
2. **Portfolio** - High-level strategic view
3. **Backlog** - Product backlog management with ideation
4. **PI Board** - Program increment planning
5. **Workflows** - Automation and pattern templates
6. **Projects** - Individual project workspaces with full IDE-like environment
7. **Sessions** - Agent session management and conversations
8. **Teams** - Team organization and OKR tracking
9. **Metrics** - DORA, quality, analytics, monitoring
10. **Memory** - Knowledge base and vector search
11. **Agents & Skills** - Agent and skill management
12. **MCPs** - Model Context Protocol servers
13. **Ideation** - Brainstorming and idea generation
14. **Mission Control** - Task execution and automation orchestration
15. **Admin** - User management, RBAC, settings

### Backend Capabilities
- **Real-time**: WebSockets, SSE (Server-Sent Events), streaming
- **AI Integration**: LLM routing, provider management
- **Automation**: Pattern execution, workflow orchestration
- **Monitoring**: Health checks, metrics collection, incident tracking
- **Knowledge**: Vector memory, search, ingestion
- **Integrations**: Jira, GitHub, monitoring systems, webhooks
- **Quality**: Code scanning, DORA metrics, burndown charts
- **Security**: RBAC, API keys, autoheal mechanisms

---

## 10. NAVIGATION FLOW

```
Login → Setup → Home/Cockpit
                ├─ Portfolio (Strategic)
                ├─ Backlog (Product)
                ├─ PI Board (Planning)
                ├─ Workflows (Automation)
                ├─ Projects (Development)
                │  └─ Workspace (IDE-like environment)
                ├─ Sessions (Agents/Chat)
                ├─ Metrics (Analytics)
                ├─ Teams (Organization)
                ├─ Agents (AI Agents)
                ├─ Ideation (Innovation)
                └─ Admin (Settings, Users, RBAC)
```

---

## CONCLUSION

This is a **comprehensive Enterprise AI/Software Factory platform** with:
- **84 distinct HTML pages** (UI views)
- **241 API endpoints** (backend services)
- **126 HTML template files**
- **13,681 lines of CSS**
- **11,713 lines of route code** (excluding wiki_content.py)
- **Role-based access control** across 11 different perspectives
- **Rich feature set**: Ideation, project management, agent orchestration, metrics, memory, automation
- **Real-time capabilities**: WebSockets, SSE, streaming responses
- **Enterprise integration**: Jira, GitHub, monitoring systems, webhooks
