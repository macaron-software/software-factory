# MCP Platform — Software Factory Control

MCP server exposing Software Factory platform operations as tools for AI agents.

## Tools (20)

| Tool | Description |
|------|-------------|
| `sf_platform_status` | Platform overview: agents/projects/missions counts, active work |
| `sf_list_agents` | List agents with filters: role, art, safe_level, limit |
| `sf_get_agent` | Full agent details + recent sessions |
| `sf_create_agent` | Create a new agent |
| `sf_list_projects` | List projects, optional status filter |
| `sf_get_project` | Project details + recent missions |
| `sf_create_project` | Create a new project |
| `sf_get_project_health` | Project phase gate + mission completion metrics |
| `sf_list_missions` | List missions, filter by project/status |
| `sf_get_mission` | Mission details + runs |
| `sf_create_mission` | Create a mission for a project |
| `sf_delete_mission` | Delete a mission |
| `sf_list_sessions` | List agent sessions |
| `sf_get_session` | Session details + messages |
| `sf_create_session` | Run a task with a specific agent |
| `sf_list_workflows` | List available automation workflows |
| `sf_list_arts` | List ARTs and agent teams |
| `sf_get_metrics` | LLM usage metrics (cost, tokens, calls) |
| `sf_reload_agents` | Hot-reload agents from YAML without restart |
| `sf_search` | Full-text search across agents/projects/missions |

## Usage

```bash
# Stdio mode (for Claude Desktop / Copilot)
python -m mcp_platform.server

# Test mode
python -m mcp_platform.server --test

# With custom API URL
SF_PLATFORM_URL=http://localhost:8099 python -m mcp_platform.server
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "sf-platform": {
      "command": "python3",
      "args": ["-m", "mcp_platform.server"],
      "cwd": "/path/to/_MACARON-SOFTWARE",
      "env": {
        "SF_PLATFORM_URL": "http://127.0.0.1:8099"
      }
    }
  }
}
```

## Architecture

- **Reads**: direct SQLite DB access (fast, no auth)
- **Writes**: REST API calls to `SF_PLATFORM_URL` (proper validation)
- **Protocol**: MCP stdio (JSON-RPC 2.0), compatible with Claude Desktop, Copilot, any MCP client
