"""
Project Context Extractor - RAG "Big Picture" for Brain

Extracts and structures project knowledge into 10 categories:
1. VISION - Roadmap, features, priorities
2. ARCHITECTURE - Patterns, layers, modules
3. STRUCTURE - File organization, conventions
4. DATA_MODEL - Schemas, entities, relations
5. API_SURFACE - Endpoints, signatures, contracts
6. CONVENTIONS - Style guide, patterns, standards
7. DEPENDENCIES - Libs, services, versions
8. STATE - Tasks, errors, debt, coverage
9. HISTORY - Recent commits, hot files
10. DOMAIN - Business glossary, rules

Usage:
    context = ProjectContext("ppz")
    context.refresh()  # Analyze project
    summary = context.get_summary()  # For brain prompt
    relevant = context.query("authentication patterns")  # RAG search
"""

import os
import re
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore


@dataclass
class ContextCategory:
    """Single category of project context."""
    name: str
    description: str
    content: str
    keywords: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProjectContextData:
    """Complete project context."""
    project_id: str
    vision: ContextCategory = None
    architecture: ContextCategory = None
    structure: ContextCategory = None
    data_model: ContextCategory = None
    api_surface: ContextCategory = None
    conventions: ContextCategory = None
    dependencies: ContextCategory = None
    state: ContextCategory = None
    history: ContextCategory = None
    domain: ContextCategory = None

    def to_dict(self) -> Dict:
        return {k: asdict(v) if v else None for k, v in asdict(self).items()}


class ProjectContext:
    """
    Extracts and manages project context for brain analysis.
    Stores in SQLite with FTS5 for fast search.
    """

    DB_PATH = Path(__file__).parent.parent / "data" / "project_context.db"

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project = get_project(project_id)
        self.task_store = TaskStore()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite with FTS5 for full-text search."""
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.DB_PATH) as conn:
            # Main context table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context (
                    project_id TEXT,
                    category TEXT,
                    name TEXT,
                    description TEXT,
                    content TEXT,
                    keywords TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (project_id, category)
                )
            """)

            # FTS5 virtual table for search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS context_fts USING fts5(
                    project_id,
                    category,
                    content,
                    keywords,
                    content='context',
                    content_rowid='rowid'
                )
            """)

            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS context_ai AFTER INSERT ON context BEGIN
                    INSERT INTO context_fts(rowid, project_id, category, content, keywords)
                    VALUES (new.rowid, new.project_id, new.category, new.content, new.keywords);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS context_ad AFTER DELETE ON context BEGIN
                    INSERT INTO context_fts(context_fts, rowid, project_id, category, content, keywords)
                    VALUES('delete', old.rowid, old.project_id, old.category, old.content, old.keywords);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS context_au AFTER UPDATE ON context BEGIN
                    INSERT INTO context_fts(context_fts, rowid, project_id, category, content, keywords)
                    VALUES('delete', old.rowid, old.project_id, old.category, old.content, old.keywords);
                    INSERT INTO context_fts(rowid, project_id, category, content, keywords)
                    VALUES (new.rowid, new.project_id, new.category, new.content, new.keywords);
                END
            """)
            conn.commit()

    def refresh(self, categories: List[str] = None):
        """
        Refresh project context by analyzing the codebase.

        Args:
            categories: Specific categories to refresh (default: all)
        """
        all_categories = [
            'vision', 'architecture', 'structure', 'data_model',
            'api_surface', 'conventions', 'dependencies', 'state',
            'history', 'domain'
        ]

        to_refresh = categories or all_categories

        for category in to_refresh:
            print(f"[CONTEXT] Extracting {category}...")
            extractor = getattr(self, f'_extract_{category}', None)
            if extractor:
                try:
                    ctx = extractor()
                    if ctx:
                        self._save_category(ctx)
                        print(f"[CONTEXT] {category}: {len(ctx.content)} chars, {len(ctx.keywords)} keywords")
                except Exception as e:
                    print(f"[CONTEXT] Error extracting {category}: {e}")

    def _save_category(self, ctx: ContextCategory):
        """Save a category to the database."""
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO context
                (project_id, category, name, description, content, keywords, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.project_id,
                ctx.name.lower(),
                ctx.name,
                ctx.description,
                ctx.content,
                json.dumps(ctx.keywords),
                ctx.updated_at
            ))
            conn.commit()

    def get_category(self, category: str) -> Optional[ContextCategory]:
        """Get a specific category from the database."""
        with sqlite3.connect(self.DB_PATH) as conn:
            row = conn.execute("""
                SELECT name, description, content, keywords, updated_at
                FROM context WHERE project_id = ? AND category = ?
            """, (self.project_id, category.lower())).fetchone()

            if row:
                return ContextCategory(
                    name=row[0],
                    description=row[1],
                    content=row[2],
                    keywords=json.loads(row[3]) if row[3] else [],
                    updated_at=row[4]
                )
        return None

    def query(self, search_query: str, limit: int = 5) -> List[Dict]:
        """
        Search project context using FTS5.

        Args:
            search_query: Search terms
            limit: Max results

        Returns:
            List of matching context snippets with category and relevance
        """
        with sqlite3.connect(self.DB_PATH) as conn:
            # FTS5 search with ranking
            results = conn.execute("""
                SELECT category, content, keywords,
                       bm25(context_fts) as rank
                FROM context_fts
                WHERE project_id = ? AND context_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (self.project_id, search_query, limit)).fetchall()

            return [
                {
                    'category': r[0],
                    'content': r[1][:500] + '...' if len(r[1]) > 500 else r[1],
                    'keywords': json.loads(r[2]) if r[2] else [],
                    'relevance': -r[3]  # BM25 returns negative scores
                }
                for r in results
            ]

    def get_summary(self, max_chars: int = 15000) -> str:
        """
        Get a structured summary of project context for brain prompt.
        Fits within token limits while providing comprehensive overview.
        """
        sections = []
        char_budget = max_chars

        # Priority order for brain context
        priority = [
            ('vision', 2000),
            ('architecture', 2500),
            ('structure', 1500),
            ('conventions', 1500),
            ('data_model', 2000),
            ('api_surface', 1500),
            ('state', 1500),
            ('dependencies', 1000),
            ('history', 1000),
            ('domain', 1000),
        ]

        for category, budget in priority:
            if char_budget <= 0:
                break

            ctx = self.get_category(category)
            if ctx and ctx.content:
                content = ctx.content[:min(budget, char_budget)]
                if len(ctx.content) > budget:
                    content += "\n... (truncated)"

                sections.append(f"""
### {ctx.name.upper()}
{ctx.description}

{content}
""")
                char_budget -= len(sections[-1])

        return f"""# PROJECT CONTEXT: {self.project_id.upper()}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{''.join(sections)}
"""

    # ═══════════════════════════════════════════════════════════════════════
    # EXTRACTORS - One per category
    # ═══════════════════════════════════════════════════════════════════════

    def _extract_vision(self) -> ContextCategory:
        """Extract vision from CLAUDE.md, ROADMAP.md, etc."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # Vision documents to check
        vision_files = [
            'CLAUDE.md', 'VISION.md', 'ROADMAP.md', 'README.md',
            'PLATFORM_FEATURES.md', 'PROJECT_ROADMAP.md',
            'docs/VISION.md', 'docs/ROADMAP.md'
        ]

        for vf in vision_files:
            path = root / vf
            if path.exists():
                try:
                    text = path.read_text()[:5000]
                    content_parts.append(f"## {vf}\n{text}")
                    # Extract keywords (headings, capitalized terms)
                    keywords.extend(re.findall(r'^#+\s+(.+)$', text, re.MULTILINE))
                except:
                    pass

        # Also check project config for vision_doc
        if self.project.vision_doc:
            vd_path = root / self.project.vision_doc
            if vd_path.exists() and str(vd_path) not in [str(root/vf) for vf in vision_files]:
                try:
                    text = vd_path.read_text()[:5000]
                    content_parts.append(f"## {self.project.vision_doc}\n{text}")
                except:
                    pass

        return ContextCategory(
            name="Vision",
            description="Product roadmap, planned features, business priorities",
            content="\n\n".join(content_parts) or "No vision documents found",
            keywords=list(set(keywords))[:50]
        )

    def _extract_architecture(self) -> ContextCategory:
        """Extract architecture patterns from code structure."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # Architecture documents
        arch_files = [
            'ARCHITECTURE.md', 'docs/ARCHITECTURE.md', 'docs/architecture.md',
            'DESIGN.md', 'docs/DESIGN.md'
        ]

        for af in arch_files:
            path = root / af
            if path.exists():
                try:
                    text = path.read_text()[:3000]
                    content_parts.append(f"## {af}\n{text}")
                except:
                    pass

        # Detect patterns from code structure
        patterns_detected = []

        # Check for common architectural patterns
        if (root / 'src' / 'domain').exists() or (root / 'domain').exists():
            patterns_detected.append("Clean Architecture / DDD (domain layer detected)")
        if (root / 'src' / 'infrastructure').exists() or (root / 'infra').exists():
            patterns_detected.append("Infrastructure layer detected")
        if (root / 'src' / 'application').exists() or (root / 'app').exists():
            patterns_detected.append("Application layer detected")
        if (root / 'handlers').exists() or (root / 'controllers').exists():
            patterns_detected.append("MVC/Handler pattern detected")
        if (root / 'crates').exists():
            patterns_detected.append("Rust workspace with multiple crates")
        if (root / 'packages').exists() or (root / 'libs').exists():
            patterns_detected.append("Monorepo with packages/libs")

        # Detect module structure
        modules = []
        for domain_name, domain_config in self.project.domains.items():
            for path_pattern in domain_config.get('paths', []):
                domain_path = root / path_pattern.rstrip('/')
                if domain_path.exists() and domain_path.is_dir():
                    subdirs = [d.name for d in domain_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
                    if subdirs:
                        modules.append(f"- {domain_name}: {', '.join(subdirs[:10])}")

        if patterns_detected:
            content_parts.append("## Detected Patterns\n" + "\n".join(f"- {p}" for p in patterns_detected))

        if modules:
            content_parts.append("## Modules by Domain\n" + "\n".join(modules))

        keywords = patterns_detected + [m.split(':')[0].strip('- ') for m in modules]

        return ContextCategory(
            name="Architecture",
            description="Architectural patterns, layers, module organization",
            content="\n\n".join(content_parts) or "No architecture info detected",
            keywords=keywords
        )

    def _extract_structure(self) -> ContextCategory:
        """Extract file/folder structure."""
        root = Path(self.project.root_path)

        # Generate tree (max depth 3, exclude common)
        exclude = {'.git', 'node_modules', 'target', '__pycache__', '.cache',
                   'build', 'dist', '.next', 'venv', '.venv', 'vendor'}

        def tree(path: Path, prefix: str = "", depth: int = 0, max_depth: int = 3) -> List[str]:
            if depth > max_depth:
                return []

            lines = []
            try:
                entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
                entries = [e for e in entries if e.name not in exclude and not e.name.startswith('.')]

                for i, entry in enumerate(entries[:20]):  # Limit per level
                    is_last = i == len(entries[:20]) - 1
                    connector = "└── " if is_last else "├── "

                    if entry.is_dir():
                        lines.append(f"{prefix}{connector}{entry.name}/")
                        extension = "    " if is_last else "│   "
                        lines.extend(tree(entry, prefix + extension, depth + 1, max_depth))
                    else:
                        lines.append(f"{prefix}{connector}{entry.name}")

                if len(entries) > 20:
                    lines.append(f"{prefix}... and {len(entries) - 20} more")

            except PermissionError:
                pass

            return lines

        tree_output = tree(root)

        # Count files by extension
        ext_counts = {}
        for f in root.rglob('*'):
            if f.is_file() and not any(ex in str(f) for ex in exclude):
                ext = f.suffix.lower() or '(no ext)'
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:15]

        content = f"""## Project Root
{self.project.root_path}

## Directory Tree
```
{chr(10).join(tree_output[:100])}
```

## File Types
{chr(10).join(f"- {ext}: {count} files" for ext, count in top_exts)}

## Domains Configured
{chr(10).join(f"- {name}: {', '.join(cfg.get('paths', []))}" for name, cfg in self.project.domains.items())}
"""

        return ContextCategory(
            name="Structure",
            description="File and folder organization, project layout",
            content=content,
            keywords=[ext for ext, _ in top_exts] + list(self.project.domains.keys())
        )

    def _extract_data_model(self) -> ContextCategory:
        """Extract data models from schemas, proto, types."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # Proto files
        protos = list(root.rglob('*.proto'))[:10]
        if protos:
            proto_content = []
            for p in protos:
                try:
                    text = p.read_text()
                    # Extract message definitions
                    messages = re.findall(r'message\s+(\w+)\s*\{[^}]+\}', text, re.DOTALL)
                    if messages:
                        proto_content.append(f"### {p.name}\n```proto\n{text[:1500]}\n```")
                        keywords.extend([m for m in re.findall(r'message\s+(\w+)', text)])
                except:
                    pass
            if proto_content:
                content_parts.append("## Protobuf Schemas\n" + "\n".join(proto_content[:5]))

        # TypeScript types
        type_files = list(root.rglob('**/types.ts')) + list(root.rglob('**/types/*.ts'))
        if type_files:
            type_content = []
            for tf in type_files[:5]:
                try:
                    text = tf.read_text()[:2000]
                    type_content.append(f"### {tf.relative_to(root)}\n```typescript\n{text}\n```")
                    keywords.extend(re.findall(r'(?:interface|type|enum)\s+(\w+)', text))
                except:
                    pass
            if type_content:
                content_parts.append("## TypeScript Types\n" + "\n".join(type_content))

        # Rust structs (models)
        model_files = list(root.rglob('**/models.rs')) + list(root.rglob('**/model.rs'))
        if model_files:
            model_content = []
            for mf in model_files[:5]:
                try:
                    text = mf.read_text()[:2000]
                    model_content.append(f"### {mf.relative_to(root)}\n```rust\n{text}\n```")
                    keywords.extend(re.findall(r'(?:struct|enum)\s+(\w+)', text))
                except:
                    pass
            if model_content:
                content_parts.append("## Rust Models\n" + "\n".join(model_content))

        # SQL migrations
        migrations = sorted(root.rglob('*.sql'))[-5:]  # Last 5 migrations
        if migrations:
            mig_content = []
            for m in migrations:
                try:
                    text = m.read_text()[:1000]
                    mig_content.append(f"### {m.name}\n```sql\n{text}\n```")
                    # Extract table names
                    keywords.extend(re.findall(r'(?:CREATE|ALTER)\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', text, re.I))
                except:
                    pass
            if mig_content:
                content_parts.append("## Recent Migrations\n" + "\n".join(mig_content))

        return ContextCategory(
            name="data_model",
            description="Database schemas, protobuf definitions, type definitions",
            content="\n\n".join(content_parts) or "No data models found",
            keywords=list(set(keywords))[:50]
        )

    def _extract_api_surface(self) -> ContextCategory:
        """Extract API endpoints and public interfaces."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # OpenAPI/Swagger
        openapi_files = list(root.rglob('openapi.yaml')) + list(root.rglob('openapi.json')) + list(root.rglob('swagger.*'))
        for oaf in openapi_files[:2]:
            try:
                text = oaf.read_text()[:3000]
                content_parts.append(f"## OpenAPI: {oaf.name}\n```yaml\n{text}\n```")
            except:
                pass

        # Extract routes from Rust handlers
        handler_files = list(root.rglob('**/handlers.rs')) + list(root.rglob('**/routes.rs'))
        routes = []
        for hf in handler_files[:5]:
            try:
                text = hf.read_text()
                # Extract route definitions
                route_matches = re.findall(r'(?:#\[(?:get|post|put|delete|patch)\("([^"]+)"\)\])|(?:\.route\("([^"]+)")', text, re.I)
                for match in route_matches:
                    route = match[0] or match[1]
                    if route:
                        routes.append(route)
            except:
                pass

        if routes:
            content_parts.append("## API Routes Detected\n" + "\n".join(f"- {r}" for r in sorted(set(routes))[:30]))
            keywords.extend(routes)

        # gRPC services from proto
        grpc_services = []
        for proto in root.rglob('*.proto'):
            try:
                text = proto.read_text()
                services = re.findall(r'service\s+(\w+)\s*\{([^}]+)\}', text, re.DOTALL)
                for svc_name, svc_body in services:
                    rpcs = re.findall(r'rpc\s+(\w+)', svc_body)
                    grpc_services.append(f"- {svc_name}: {', '.join(rpcs)}")
                    keywords.append(svc_name)
                    keywords.extend(rpcs)
            except:
                pass

        if grpc_services:
            content_parts.append("## gRPC Services\n" + "\n".join(grpc_services))

        return ContextCategory(
            name="api_surface",
            description="REST endpoints, gRPC services, public interfaces",
            content="\n\n".join(content_parts) or "No API surface detected",
            keywords=list(set(keywords))[:50]
        )

    def _extract_conventions(self) -> ContextCategory:
        """Extract coding conventions from config files and examples."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # Linter configs
        config_files = {
            '.eslintrc': 'ESLint',
            '.eslintrc.js': 'ESLint',
            '.prettierrc': 'Prettier',
            'rustfmt.toml': 'Rustfmt',
            '.clippy.toml': 'Clippy',
            'pyproject.toml': 'Python',
            'tsconfig.json': 'TypeScript',
        }

        for cfg, name in config_files.items():
            path = root / cfg
            if path.exists():
                try:
                    text = path.read_text()[:1000]
                    content_parts.append(f"## {name} Config ({cfg})\n```\n{text}\n```")
                    keywords.append(name)
                except:
                    pass

        # Extract from project YAML config
        if self.project.domains:
            domain_conventions = []
            for name, cfg in self.project.domains.items():
                conv = []
                if cfg.get('build_cmd'):
                    conv.append(f"Build: `{cfg['build_cmd']}`")
                if cfg.get('test_cmd'):
                    conv.append(f"Test: `{cfg['test_cmd']}`")
                if cfg.get('lint_cmd'):
                    conv.append(f"Lint: `{cfg['lint_cmd']}`")
                if conv:
                    domain_conventions.append(f"### {name}\n" + "\n".join(conv))

            if domain_conventions:
                content_parts.append("## Domain Commands\n" + "\n".join(domain_conventions))

        # Common patterns from existing code (sample)
        patterns = []

        # Check error handling style
        rs_files = list(root.rglob('*.rs'))[:5]
        for rf in rs_files:
            try:
                text = rf.read_text()
                if 'anyhow::' in text or 'anyhow::Result' in text:
                    patterns.append("Error handling: anyhow")
                if 'thiserror::' in text:
                    patterns.append("Error handling: thiserror")
                if '#[tokio::main]' in text:
                    patterns.append("Async runtime: tokio")
                break
            except:
                pass

        if patterns:
            content_parts.append("## Detected Patterns\n" + "\n".join(f"- {p}" for p in set(patterns)))

        return ContextCategory(
            name="Conventions",
            description="Coding style, linter configs, project standards",
            content="\n\n".join(content_parts) or "No conventions detected",
            keywords=keywords
        )

    def _extract_dependencies(self) -> ContextCategory:
        """Extract dependencies from package managers."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # Cargo.toml (Rust)
        cargo_files = list(root.rglob('Cargo.toml'))[:3]
        for cf in cargo_files:
            try:
                text = cf.read_text()
                # Extract dependencies section
                deps_match = re.search(r'\[dependencies\](.*?)(?:\[|\Z)', text, re.DOTALL)
                if deps_match:
                    deps = re.findall(r'^(\w[\w-]*)\s*=', deps_match.group(1), re.MULTILINE)
                    content_parts.append(f"## Rust ({cf.relative_to(root)})\n" +
                                        "\n".join(f"- {d}" for d in deps[:20]))
                    keywords.extend(deps[:20])
            except:
                pass

        # package.json (Node)
        pkg_files = list(root.rglob('package.json'))[:3]
        for pf in pkg_files:
            try:
                data = json.loads(pf.read_text())
                deps = list(data.get('dependencies', {}).keys())[:15]
                dev_deps = list(data.get('devDependencies', {}).keys())[:10]
                if deps or dev_deps:
                    content_parts.append(f"## Node ({pf.relative_to(root)})\n" +
                                        "Dependencies: " + ", ".join(deps) + "\n" +
                                        "DevDeps: " + ", ".join(dev_deps))
                    keywords.extend(deps)
            except:
                pass

        # requirements.txt / pyproject.toml (Python)
        req_file = root / 'requirements.txt'
        if req_file.exists():
            try:
                text = req_file.read_text()
                deps = re.findall(r'^([\w-]+)', text, re.MULTILINE)
                content_parts.append("## Python (requirements.txt)\n" +
                                    "\n".join(f"- {d}" for d in deps[:20]))
                keywords.extend(deps[:20])
            except:
                pass

        return ContextCategory(
            name="Dependencies",
            description="External libraries, frameworks, services",
            content="\n\n".join(content_parts) or "No dependencies found",
            keywords=list(set(keywords))[:50]
        )

    def _extract_state(self) -> ContextCategory:
        """Extract current project state from tasks, errors, etc."""
        content_parts = []
        keywords = []

        # Task statistics
        stats = self.task_store.get_stats(self.project_id)
        if stats:
            content_parts.append(f"""## Task Statistics
- Total tasks: {stats.get('total', 0)}
- Pending: {stats.get('pending', 0)}
- In Progress: {stats.get('tdd_in_progress', 0)}
- Deployed: {stats.get('deployed', 0)}
- Failed: {stats.get('tdd_failed', 0) + stats.get('build_failed', 0)}
""")

        # Recent failures
        with sqlite3.connect(self.task_store.db_path) as conn:
            failures = conn.execute("""
                SELECT type, description, status
                FROM tasks
                WHERE project_id = ? AND status LIKE '%failed'
                ORDER BY updated_at DESC
                LIMIT 10
            """, (self.project_id,)).fetchall()

            if failures:
                content_parts.append("## Recent Failures\n" +
                    "\n".join(f"- [{f[0]}] {f[1][:60]}... ({f[2]})" for f in failures))
                keywords.extend([f[0] for f in failures])

        # Tech debt (TODOs, FIXMEs)
        root = Path(self.project.root_path)
        todos = []
        for ext in ['*.rs', '*.ts', '*.py', '*.swift', '*.kt']:
            for f in list(root.rglob(ext))[:50]:
                try:
                    text = f.read_text()
                    matches = re.findall(r'(?:TODO|FIXME|HACK|XXX)[:!]?\s*(.{0,60})', text, re.I)
                    for m in matches[:3]:
                        todos.append(f"- {f.name}: {m.strip()}")
                except:
                    pass

        if todos:
            content_parts.append("## Tech Debt (TODOs/FIXMEs)\n" + "\n".join(todos[:20]))

        return ContextCategory(
            name="State",
            description="Current project state: tasks, errors, tech debt",
            content="\n\n".join(content_parts) or "No state info available",
            keywords=keywords
        )

    def _extract_history(self) -> ContextCategory:
        """Extract recent git history."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        try:
            # Recent commits
            result = subprocess.run(
                ['git', 'log', '--oneline', '-20', '--no-merges'],
                cwd=root, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                commits = result.stdout.strip()
                content_parts.append(f"## Recent Commits\n```\n{commits}\n```")
                # Extract keywords from commit messages
                keywords.extend(re.findall(r'\b(?:feat|fix|refactor|test|docs|chore)\b', commits, re.I))

            # Recently modified files
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD~20', 'HEAD'],
                cwd=root, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                files = result.stdout.strip().split('\n')[:20]
                if files and files[0]:
                    content_parts.append("## Recently Modified Files\n" +
                        "\n".join(f"- {f}" for f in files))

            # Hot files (most commits)
            result = subprocess.run(
                ['git', 'log', '--name-only', '--pretty=format:', '-100'],
                cwd=root, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                files = [f for f in result.stdout.strip().split('\n') if f]
                from collections import Counter
                hot = Counter(files).most_common(10)
                if hot:
                    content_parts.append("## Hot Files (most changes)\n" +
                        "\n".join(f"- {f}: {c} changes" for f, c in hot))
                    keywords.extend([f.split('/')[-1] for f, _ in hot])

        except Exception as e:
            content_parts.append(f"Git analysis failed: {e}")

        return ContextCategory(
            name="History",
            description="Recent commits, modified files, change patterns",
            content="\n\n".join(content_parts) or "No git history available",
            keywords=keywords
        )

    def _extract_domain(self) -> ContextCategory:
        """Extract domain/business knowledge."""
        content_parts = []
        keywords = []

        root = Path(self.project.root_path)

        # Look for glossary/domain docs
        domain_files = [
            'GLOSSARY.md', 'docs/GLOSSARY.md', 'DOMAIN.md', 'docs/DOMAIN.md',
            'BUSINESS_RULES.md', 'docs/business-rules.md'
        ]

        for df in domain_files:
            path = root / df
            if path.exists():
                try:
                    text = path.read_text()[:3000]
                    content_parts.append(f"## {df}\n{text}")
                    # Extract defined terms
                    keywords.extend(re.findall(r'^\*\*(\w+)\*\*', text, re.MULTILINE))
                except:
                    pass

        # Extract from code comments (domain terms)
        domain_terms = set()
        for ext in ['*.rs', '*.ts']:
            for f in list(root.rglob(ext))[:20]:
                try:
                    text = f.read_text()
                    # Look for domain-specific comments
                    comments = re.findall(r'///?\s*(.+)', text)
                    for c in comments:
                        # Extract capitalized terms (likely domain concepts)
                        terms = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', c)
                        domain_terms.update(terms)
                except:
                    pass

        if domain_terms:
            content_parts.append("## Domain Terms (from code)\n" +
                ", ".join(sorted(domain_terms)[:30]))
            keywords.extend(list(domain_terms)[:30])

        # Project-specific info from config
        if self.project.display_name:
            content_parts.insert(0, f"## Project: {self.project.display_name}")

        return ContextCategory(
            name="Domain",
            description="Business glossary, domain concepts, rules",
            content="\n\n".join(content_parts) or "No domain knowledge found",
            keywords=keywords
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Project Context Extractor")
    parser.add_argument("project", help="Project ID")
    parser.add_argument("--refresh", action="store_true", help="Refresh all categories")
    parser.add_argument("--category", "-c", help="Refresh specific category")
    parser.add_argument("--summary", action="store_true", help="Print summary")
    parser.add_argument("--query", "-q", help="Search context")

    args = parser.parse_args()

    ctx = ProjectContext(args.project)

    if args.refresh or args.category:
        categories = [args.category] if args.category else None
        ctx.refresh(categories)

    if args.summary:
        print(ctx.get_summary())

    if args.query:
        results = ctx.query(args.query)
        for r in results:
            print(f"\n[{r['category']}] (relevance: {r['relevance']:.2f})")
            print(r['content'])
