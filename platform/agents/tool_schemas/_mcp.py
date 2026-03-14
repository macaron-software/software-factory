"""Tool schema definitions — sub-module of platform/agents/tool_schemas/.

WHY: tool_schemas.py grew to 3313L containing 6 large schema functions.
Split into sub-modules by category for readability without breaking any callers
(package __init__.py re-exports all public symbols).
"""
from __future__ import annotations
# Ref: feat-agents-list
def _mcp_schemas() -> list[dict]:
    """MCP tool schemas (LRM, Figma, Solaris, GitHub, JIRA)."""
    return [
        # ── MCP: LRM tools (project knowledge) ──
        {
            "type": "function",
            "function": {
                "name": "lrm_locate",
                "description": "Find files in the project matching a pattern or description via LRM server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Pattern or description (e.g. 'auth middleware', '*.test.ts')",
                        },
                        "scope": {
                            "type": "string",
                            "description": "Limit search scope (e.g. 'src/', 'tests/')",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_summarize",
                "description": "Get a summary of a file or directory from the LRM server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File or directory path to summarize",
                        },
                        "focus": {
                            "type": "string",
                            "description": "What to focus on (e.g. 'API endpoints', 'data model')",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_conventions",
                "description": "Get coding conventions for a domain (rust, typescript, svelte, python).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain: rust, typescript, svelte, python, kotlin, swift",
                        },
                    },
                    "required": ["domain"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_examples",
                "description": "Get code examples from the project (tests, implementations, API patterns).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Example type: test, implementation, api, model",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Domain filter (e.g. 'auth', 'api')",
                        },
                    },
                    "required": ["type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_build",
                "description": "Run build, test, or lint commands via the LRM server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Command type: build, test, lint, check",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Target domain (e.g. 'backend', 'frontend')",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_context",
                "description": "Get project context via RAG: vision, architecture, data_model, api_surface, conventions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Context category: vision, architecture, data_model, api_surface, conventions, all",
                        },
                    },
                    "required": ["category"],
                },
            },
        },
        # ── MCP: Component Gallery (60 UI components, 2600+ DS implementations) ──
        {
            "type": "function",
            "function": {
                "name": "lrm_component_gallery_list",
                "description": "List all 60 UI components from The Component Gallery: accordion, alert, avatar, badge, button, card, carousel, checkbox, combobox, datepicker, drawer, modal, pagination, select, skeleton, spinner, table, tabs, toast, tooltip, tree-view... each cross-referenced across 50+ Design Systems.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_component_gallery_get",
                "description": "Get full documentation for a UI component: description, all aliases used across design systems, N implementations with DS name + URL + tech stack. Also includes semantic HTML markup, ARIA patterns, CSS when available. Use before implementing any UI component.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component slug: accordion, alert, avatar, badge, button, card, carousel, checkbox, combobox, datepicker, drawer, dropdown-menu, empty-state, footer, form, header, icon, modal, navigation, pagination, popover, progress-bar, radio-button, rating, search-input, select, separator, skeleton, slider, spinner, stepper, table, tabs, text-input, textarea, toast, toggle, tooltip, tree-view, visually-hidden...",
                        },
                        "tech": {
                            "type": "string",
                            "description": "Filter by tech: React, Vue, Angular, CSS, Web Components, Svelte, etc.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max implementations (default 20)",
                        },
                    },
                    "required": ["component"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_component_gallery_search",
                "description": "Full-text search across all 60 UI components and their aliases. Use to discover which components relate to a concept (e.g. 'loading', 'navigation', 'error', 'notification').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search terms (component name, concept, alias)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_component_gallery_ds",
                "description": "Get all components from a specific Design System and how they name them. Useful to align with a target DS vocabulary (e.g. Material Design, Carbon, Atlassian, Ant Design, Spectrum, Primer, Fluent).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ds_name": {
                            "type": "string",
                            "description": "Design system name (partial ok): Material, Carbon, Atlassian, Ant Design, Spectrum, Primer, Fluent, Chakra, MUI, Radix, shadcn...",
                        },
                    },
                    "required": ["ds_name"],
                },
            },
        },
        # ── MCP: Architecture Guidelines (Confluence / GitLab Wiki / Markdown) ──
        {
            "type": "function",
            "function": {
                "name": "lrm_guidelines_summary",
                "description": "Get the architecture/tech guidelines summary for the current project: required tech stack, forbidden libs/patterns, standards. Always call before generating code to ensure compliance with DSI/org rules.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project ID (defaults to current project)",
                        },
                        "role": {
                            "type": "string",
                            "description": "Agent role: dev, architecture, security, frontend",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_guidelines_search",
                "description": "Search the org/project architecture guidelines wiki for rules, decisions, or guidance on a specific topic (e.g. 'auth', 'database choice', 'API standards', 'logging').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search terms"},
                        "project": {"type": "string", "description": "Project ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 5)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_guidelines_get",
                "description": "Get full content of a specific architecture guideline page by title.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Page title (partial match ok)",
                        },
                        "project": {"type": "string", "description": "Project ID"},
                        "page_id": {
                            "type": "string",
                            "description": "Exact page ID (alternative to title)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_guidelines_stack",
                "description": "Get required tech stack for the project by topic (backend, frontend, database, auth, infra, security). Use before choosing technologies to ensure DSI compliance.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project ID"},
                        "topic": {
                            "type": "string",
                            "description": "Filter by topic: backend, frontend, database, auth, infra, security, quality",
                        },
                    },
                },
            },
        },
        # ── LRM: Confluence & Jira ──
        {
            "type": "function",
            "function": {
                "name": "lrm_confluence_search",
                "description": "Search Confluence wiki pages (full-text). Use to find architecture docs, ADRs, conventions, or project specs in the company knowledge base.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keywords"},
                        "space": {
                            "type": "string",
                            "description": "Confluence space key (default: IAN)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default: 10)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_confluence_read",
                "description": "Read a Confluence page content by title or page ID. Use to get full architecture specs, conventions, or design decisions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Page title to find",
                        },
                        "page_id": {
                            "type": "string",
                            "description": "Confluence page ID (alternative to title)",
                        },
                        "space": {
                            "type": "string",
                            "description": "Space key (default: IAN)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_jira_search",
                "description": "Search Jira issues via JQL or keywords. Use to find tickets, bugs, epics or user stories linked to the current project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "JQL query or plain text keywords",
                        },
                        "project": {
                            "type": "string",
                            "description": "Jira project key (optional filter)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default: 20)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        # ── MCP: Figma (design system) ──
        {
            "type": "function",
            "function": {
                "name": "figma_get_node",
                "description": "Get a Figma component node with its properties, variants, and styles.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma file key"},
                        "node_id": {
                            "type": "string",
                            "description": "Node ID (e.g. '37:1201')",
                        },
                    },
                    "required": ["file_key", "node_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "figma_get_styles",
                "description": "Get design tokens (colors, typography, spacing) from a Figma file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma file key"},
                    },
                    "required": ["file_key"],
                },
            },
        },
        # ── MCP: Solaris (WCAG/design system validation) ──
        {
            "type": "function",
            "function": {
                "name": "solaris_wcag",
                "description": "Get WCAG accessibility pattern for a component (accordion, button, tabs, checkbox, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "WCAG pattern: accordion, button, tabs, checkbox, dialog, radio-group, switch, link",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "solaris_component",
                "description": "Get Figma component details: variants, properties, dimensions, colors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component name (e.g. 'button', 'badge', 'accordion')",
                        },
                    },
                    "required": ["component"],
                },
            },
        },
        # ── MCP: GitHub ──
        {
            "type": "function",
            "function": {
                "name": "github_issues",
                "description": "List or search issues in a GitHub repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "state": {
                            "type": "string",
                            "description": "Filter: open, closed, all",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query for issue titles/body",
                        },
                    },
                    "required": ["owner", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_prs",
                "description": "List pull requests in a GitHub repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "state": {
                            "type": "string",
                            "description": "Filter: open, closed, all",
                        },
                    },
                    "required": ["owner", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_code_search",
                "description": "Search code across GitHub repositories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Code search query (e.g. 'function handleAuth language:typescript')",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_actions",
                "description": "List workflow runs and their status for a GitHub repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "status": {
                            "type": "string",
                            "description": "Filter: completed, in_progress, queued",
                        },
                    },
                    "required": ["owner", "repo"],
                },
            },
        },
        # ── MCP: JIRA (needs JIRA_URL + JIRA_TOKEN or ~/.config/factory/jira.key) ──
        {
            "type": "function",
            "function": {
                "name": "jira_search",
                "description": "Search Jira issues using JQL query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "jql": {
                            "type": "string",
                            "description": "JQL query (e.g. 'project=LPDATA AND status=\"En Cours\"')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max results (default 20)",
                        },
                    },
                    "required": ["jql"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_create",
                "description": "Create a Jira issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project key (default: LPDATA)",
                        },
                        "summary": {"type": "string", "description": "Issue title"},
                        "type": {
                            "type": "string",
                            "description": "Issue type: User Story, Feature, Anomalie (AGILE), etc.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Issue description",
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority name (optional)",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Labels (optional)",
                        },
                    },
                    "required": ["summary"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_update",
                "description": "Update fields on an existing Jira issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_key": {
                            "type": "string",
                            "description": "Issue key (e.g. LPDATA-123)",
                        },
                        "fields": {
                            "type": "object",
                            "description": "Fields to update: summary, description, priority, labels, assignee",
                        },
                    },
                    "required": ["issue_key", "fields"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_transition",
                "description": "Move a Jira issue to a new status (e.g. 'En Cours', 'Terminé').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_key": {
                            "type": "string",
                            "description": "Issue key (e.g. LPDATA-123)",
                        },
                        "transition": {
                            "type": "string",
                            "description": "Target transition name",
                        },
                    },
                    "required": ["issue_key", "transition"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_board_issues",
                "description": "List all issues from a Jira Agile board (default: BAC A SABLE IA board 8680).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "board_id": {
                            "type": "integer",
                            "description": "Board ID (default 8680)",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max results (default 50)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_add_comment",
                "description": "Add a comment to a Jira issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_key": {
                            "type": "string",
                            "description": "Issue key (e.g. LPDATA-123)",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Comment body text",
                        },
                    },
                    "required": ["issue_key", "comment"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_sync_from_platform",
                "description": "Push platform mission tasks/stories to Jira as issues.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mission_id": {
                            "type": "string",
                            "description": "Platform mission ID to sync",
                        },
                        "board_id": {
                            "type": "integer",
                            "description": "Target Jira board ID (default 8680)",
                        },
                    },
                    "required": ["mission_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confluence_read",
                "description": "Read a Confluence page content by title or ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space": {
                            "type": "string",
                            "description": "Confluence space key",
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title to search",
                        },
                        "page_id": {
                            "type": "string",
                            "description": "Page ID (alternative to title)",
                        },
                    },
                },
            },
        },
    ]


