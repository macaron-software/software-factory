"""Tool schema definitions — sub-module of platform/agents/tool_schemas/.

WHY: tool_schemas.py grew to 3313L containing 6 large schema functions.
Split into sub-modules by category for readability without breaking any callers
(package __init__.py re-exports all public symbols).
"""
from __future__ import annotations
def _build_schemas() -> list[dict]:
    """Build, test, and CI tool schemas."""
    return [
        # ── Build & Test tools ──
        {
            "type": "function",
            "function": {
                "name": "build",
                "description": "Run a build command in the project workspace. Use to compile, install dependencies, or run any build step. Returns stdout+stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Build command to run. Examples: 'pip install -r requirements.txt', 'npm install && npm run build', 'cargo build', 'make'",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "test",
                "description": "Run tests in the project workspace. Returns test output with pass/fail results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Test command to run. Examples: 'pytest -v', 'npm test', 'cargo test', 'python -m pytest tests/'",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "browser_screenshot",
                "description": "Take a real browser screenshot of a web page using Playwright headless. If no URL given, starts a local HTTP server on the workspace index.html. Use to verify UI rendering, check layout, detect visual bugs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to screenshot. Leave empty to auto-serve local index.html",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Screenshot filename (default: screenshot.png)",
                        },
                        "wait_ms": {
                            "type": "integer",
                            "description": "Wait time in ms after page load (default: 2000)",
                        },
                    },
                },
            },
        },
        # ── Fractal coding tool (sub-agent spawning) ──
        {
            "type": "function",
            "function": {
                "name": "fractal_code",
                "description": "Spawn a focused sub-agent to complete an atomic coding task. The sub-agent gets full tool access (code_write, code_read, code_edit, test, git_commit) and runs autonomously for up to 8 tool rounds. Use this to delegate specific implementation tasks: 'write the auth module with tests', 'create the API endpoint for users', 'add unit tests for calculator'. Returns a summary of files created/modified and test results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Detailed coding task. Be specific about: what files to create, what functions/classes, what tests. Example: 'Create src/auth.py with login(username, password) function and tests/test_auth.py with pytest tests for valid/invalid credentials'",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context: existing files, architecture decisions, tech stack, conventions",
                        },
                    },
                    "required": ["task"],
                },
            },
        },
        # ── Security scanning tools ──
        {
            "type": "function",
            "function": {
                "name": "sast_scan",
                "description": "Run static application security testing (SAST) on workspace code. Uses semgrep/bandit to detect vulnerabilities, injection flaws, and insecure patterns. Returns findings with severity, file, and line number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "Workspace root directory",
                        },
                        "path": {
                            "type": "string",
                            "description": "Subdirectory or file to scan (default: whole workspace)",
                        },
                    },
                    "required": ["cwd"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "dependency_audit",
                "description": "Audit project dependencies for known CVEs. Auto-detects package.json (npm), requirements.txt (pip), Cargo.toml (cargo). Returns vulnerability list with severity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "Project root directory with dependency files",
                        },
                    },
                    "required": ["cwd"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "secrets_scan",
                "description": "Scan workspace for hardcoded secrets (API keys, tokens, passwords, private keys). Deterministic grep-based detection. Ignores test fixtures and examples.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "Workspace root directory to scan",
                        },
                    },
                    "required": ["cwd"],
                },
            },
        },
        # ── Pentest / Offensive security tools ──
        {
            "type": "function",
            "function": {
                "name": "recon_portscan",
                "description": "nmap port scan — detect open ports and service versions on a target host.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Hostname or IP to scan",
                        },
                        "ports": {
                            "type": "string",
                            "description": "Port range, e.g. '1-1000' or '80,443,8080'",
                        },
                    },
                    "required": ["target"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recon_subdomain",
                "description": "Enumerate subdomains of a domain using subfinder (passive recon).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Target domain, e.g. example.com",
                        },
                    },
                    "required": ["domain"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recon_fingerprint",
                "description": "Identify tech stack, framework, CMS, server software on a URL using whatweb.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Target URL"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "pentest_fuzz_api",
                "description": "Fuzz API endpoints using schemathesis — finds 5xx errors, injection vectors in OpenAPI/GraphQL APIs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "API base URL"},
                        "schema": {
                            "type": "string",
                            "description": "Path to OpenAPI schema file or URL (default: /openapi.json)",
                        },
                        "max_examples": {
                            "type": "integer",
                            "description": "Max test cases per endpoint (default: 10)",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "pentest_inject",
                "description": "Test a URL parameter for SQL/command injection. Sends payloads and analyzes error responses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Target URL"},
                        "param": {
                            "type": "string",
                            "description": "Parameter name to test",
                        },
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST"],
                            "description": "HTTP method",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["sqli", "cmd", "ldap"],
                            "description": "Injection type",
                        },
                    },
                    "required": ["url", "param"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "pentest_auth",
                "description": "Test authentication bypass: default credentials, forced browsing, missing security headers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Target base URL"},
                        "auth_url": {
                            "type": "string",
                            "description": "Login endpoint URL",
                        },
                        "protected_url": {
                            "type": "string",
                            "description": "URL that should require authentication",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "pentest_ssrf",
                "description": "Test a URL parameter for Server-Side Request Forgery (SSRF). Probes internal addresses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Target URL"},
                        "param": {
                            "type": "string",
                            "description": "Parameter that accepts a URL (default: 'url')",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        # ── Ticket/Incident management tools ──
        {
            "type": "function",
            "function": {
                "name": "create_ticket",
                "description": "Create a support ticket or incident for TMA tracking. Persisted in platform DB.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Ticket title (concise)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the issue",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Severity level",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["bug", "incident", "improvement", "security"],
                            "description": "Ticket category",
                        },
                    },
                    "required": ["title", "description", "severity"],
                },
            },
        },
        # ── Local CI pipeline (fallback when no GitHub Actions) ──
        {
            "type": "function",
            "function": {
                "name": "local_ci",
                "description": "Run a local CI pipeline: install deps → build → lint → test → commit. Auto-detects stack (npm/pip/cargo). Use this when no remote CI is configured.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "Project workspace root directory",
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Steps to run: install, build, lint, test, commit (default: all)",
                        },
                        "commit_message": {
                            "type": "string",
                            "description": "Git commit message (if commit step included)",
                        },
                    },
                    "required": ["cwd"],
                },
            },
        },
        # ── Chaos & Load testing tools ──
        {
            "type": "function",
            "function": {
                "name": "chaos_test",
                "description": "Run chaos engineering test against a staging URL. Injects failures (process kill, network latency, memory pressure) and verifies recovery. Returns recovery time and health status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Staging URL to test"},
                        "scenario": {
                            "type": "string",
                            "enum": [
                                "kill_process",
                                "network_latency",
                                "memory_pressure",
                                "cpu_stress",
                            ],
                            "description": "Chaos scenario to run",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Max recovery time in seconds (default: 30)",
                        },
                    },
                    "required": ["url", "scenario"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tmc_load_test",
                "description": "Run load test (TMC) against a URL using k6. Returns p50/p95/p99 latency, throughput (rps), error rate. Scenarios: baseline (5 VUs), ramp_10x (50 VUs), spike (100 VUs).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to load test"},
                        "scenario": {
                            "type": "string",
                            "enum": ["baseline", "ramp_10x", "spike", "soak"],
                            "description": "Load scenario",
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Test duration in seconds (default: 30)",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "infra_check",
                "description": "Verify infrastructure health: HTTP endpoints, Docker containers, port availability. Returns structured health report.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to check (for site check)",
                        },
                        "checks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Checks to run: site, docker, ports",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Port to check (for ports check)",
                        },
                    },
                },
            },
        },
        # ── SI Blueprint tool ──
        {
            "type": "function",
            "function": {
                "name": "get_si_blueprint",
                "description": "Get the SI (Information System) blueprint for the project. Returns infrastructure specs: cloud provider, compute type, CI/CD, databases, monitoring, existing services, and deployment conventions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier",
                        },
                    },
                },
            },
        },
    ]


