# Software Factory

> Multi-project Software Factory based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

## Overview

Software Factory is an autonomous code analysis and generation system that:

- **Analyzes** projects using Claude Opus 4.5 (Brain)
- **Generates** code using MiniMax M2.1 TDD workers (Wiggums)
- **Validates** code quality via adversarial gate
- **Decomposes** large tasks using FRACTAL algorithm
- **Supports** multiple projects via YAML configuration

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 RLM BRAIN (Claude Opus 4.5)                                 │
│  Vision LEAN + Project Analysis + Task Generation               │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  QUEUE 1: TDD       │      │  QUEUE 2: DEPLOY    │
│  MiniMax M2.1 × 50  │      │  MiniMax M2.1 × 10  │
│                     │      │                     │
│  TDD Cycle:         │      │  Pipeline:          │
│  1. FRACTAL check   │      │  1. Build           │
│  2. RED (test)      │      │  2. Staging         │
│  3. GREEN (code)    │      │  3. E2E smoke       │
│  4. VERIFY          │      │  4. Prod            │
│  5. ADVERSARIAL     │      │  5. Rollback        │
│  6. COMMIT          │      │                     │
└─────────────────────┘      └─────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔴 ADVERSARIAL GATE (Configurable per project)                 │
│  Core: test.skip, @ts-ignore, TODO, STUB                        │
│  Custom: project-specific patterns from YAML                    │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone
cd /Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY

# Install
pip install -e .

# Create LLM config
factory init --llm-config
# Edit ~/.config/factory/llm.yaml

# Set API keys
export ANTHROPIC_API_KEY="..."
export MINIMAX_API_KEY="..."
```

## Quick Start

```bash
# List projects
factory projects

# Run Brain analysis
factory ppz brain run

# Start TDD workers
factory ppz wiggum -w 50

# Check status
factory status --all
```

## Project Configuration

Projects are defined in `projects/*.yaml`:

```yaml
project:
  name: my-project
  root_path: /path/to/project
  vision_doc: CLAUDE.md

domains:
  typescript:
    paths: [src/]
    extensions: [.ts, .tsx]
    build_cmd: npm run build
    test_cmd: npm run test

deploy:
  strategy: blue-green
  auto_prod: true

fractal:
  max_files: 5
  max_loc: 400

adversarial:
  threshold: 5
  custom_patterns:
    - pattern: 'dangerous_function'
      score: 5
      message: "Dangerous function detected"
```

## CLI Commands

```bash
# Brain commands
factory <project> brain run              # Full analysis
factory <project> brain run -q "focus"   # With focus
factory <project> brain status           # Show status

# Wiggum TDD workers
factory <project> wiggum                 # 50 workers daemon
factory <project> wiggum -w 100          # 100 workers
factory <project> wiggum --once          # Single task

# Status
factory status                           # Current project
factory status --all                     # All projects
```

## Directory Structure

```
_SOFTWARE_FACTORY/
├── core/                    # Core framework
│   ├── brain.py             # RLM Brain (Claude Opus 4.5)
│   ├── wiggum_tdd.py        # TDD workers (MiniMax M2.1)
│   ├── task_store.py        # SQLite + zlib storage
│   ├── project_registry.py  # YAML config loader
│   ├── adversarial.py       # Quality gate
│   ├── fractal.py           # Task decomposition
│   └── llm_client.py        # LLM client
│
├── mcp_lrm/                 # MCP server for agents
│   ├── server.py            # MCP protocol handler
│   └── exclusions.py        # File exclusion rules
│
├── projects/                # Project configs
│   ├── ppz.yaml
│   ├── solaris.yaml
│   └── veligo.yaml
│
├── cli/                     # CLI
│   └── factory.py
│
└── data/                    # Runtime data
    ├── factory.db           # SQLite database
    └── logs/
```

## Requirements

- Python 3.10+
- `claude` CLI (for Brain)
- `opencode` CLI (for Wiggums)
- API keys:
  - `ANTHROPIC_API_KEY` (Claude)
  - `MINIMAX_API_KEY` (MiniMax M2.1)

## License

MIT
