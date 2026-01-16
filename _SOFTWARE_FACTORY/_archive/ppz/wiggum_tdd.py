#!/usr/bin/env python3 -u
"""
Wiggum TDD - Parallel TDD Agents with Fractal Decomposition
==========================================================

Architecture fractale:
- Tâches > seuils → décomposition automatique en sous-tâches
- Seuils: MAX_FILES=5, MAX_LOC=400, MAX_ITEMS=10
- Sous-tâches héritent du parent_task_id

TDD Pipeline per agent:
1. ANALYZE: Évalue la complexité (fractal check)
2. RED:     Si simple → écrit test qui échoue
3. GREEN:   Écrit le fix
4. VERIFY:  Run test → DOIT passer
5. SUCCESS: Mark complete → ready for adversarial

Usage:
    ppz wiggum                       # 50 agents daemon (default)
    ppz wiggum tdd --workers 100     # 100 agents
    ppz wiggum tdd --once            # 1 task
    ppz wiggum tdd --task TASK_ID    # Specific task
    ppz wiggum tdd --use-store       # Use SQLite store instead of JSON

Prérequis:
    - opencode installé: npm install -g opencode
    - MiniMax configuré: ~/.config/opencode/opencode.json
    - Clé MiniMax coding (payante mais pas cher): https://platform.minimax.io

IMPORTANT: PAS de Claude CLI (trop coûteux en tokens)
           PAS de ollama (trop lent pour TDD parallèle)
"""

import asyncio
import json
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import tempfile
import shutil

# Import adversarial gate
from adversarial import AdversarialAgent

# Setup
RLM_DIR = Path(__file__).parent
POPINZ_ROOT = Path("/Users/sylvain/_POPINZ/popinz-dev")
RUST_DIR = POPINZ_ROOT / "popinz-v2-rust"
TESTS_DIR = POPINZ_ROOT / "popinz-tests"

# Files
BACKLOG_FILE = RLM_DIR / "backlog_tasks.json"
LOG_DIR = RLM_DIR / "logs"

# Config
DEFAULT_WORKERS = 50
AGENT_TIMEOUT = 3600  # 1 hour per task

# Fractal thresholds (au-delà, on décompose)
FRACTAL_THRESHOLDS = {
    "max_files": 5,        # Max 5 fichiers par tâche
    "max_loc": 400,        # Max 400 lignes de code à modifier
    "max_items": 10,       # Max 10 items (routes, actions, etc.)
    "max_complexity": 3,   # Max 3 domaines (DB + API + UI = 3)
}

# Ensure directories
LOG_DIR.mkdir(exist_ok=True)


def log(msg: str, level: str = "INFO", worker_id: int = 0):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"[W{worker_id:02d}]" if worker_id else "[TDD]"
    emoji = {"INFO": "", "WARN": "⚠️", "ERROR": "❌", "FRACTAL": "🔀"}.get(level, "")
    print(f"[{ts}] {prefix} [{level}] {emoji} {msg}", flush=True)


def load_backlog() -> dict:
    if BACKLOG_FILE.exists():
        return json.loads(BACKLOG_FILE.read_text())
    return {"tasks": [], "updated": None}


# Max retries for adversarial_failed tasks
MAX_ADVERSARIAL_RETRIES = 5


def get_pending_tasks(limit: int = 50, include_retries: bool = True) -> list:
    """Get pending tasks sorted by WSJF priority.

    Also includes adversarial_failed tasks that can be retried (retry_count < MAX_ADVERSARIAL_RETRIES).
    """
    data = load_backlog()
    tasks = data.get("tasks", [])

    # Get pending tasks
    pending = [t for t in tasks if t.get("status") == "pending"]

    # Also get adversarial_failed tasks that can be retried
    if include_retries:
        retryable = [
            t for t in tasks
            if t.get("status") == "adversarial_failed"
            and t.get("retry_count", 0) < MAX_ADVERSARIAL_RETRIES
        ]
        # Mark them as pending with incremented retry_count
        for t in retryable:
            t["_is_retry"] = True
        pending.extend(retryable)

    pending.sort(key=lambda t: -t.get("wsjf_score", t.get("priority", 0)))
    return pending[:limit]


def mark_task_status(task_id: str, status: str, **kwargs):
    """Update task status (thread-safe with file locking)"""
    import fcntl

    with open(BACKLOG_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)
            for t in data.get("tasks", []):
                if t.get("id") == task_id:
                    t["status"] = status
                    t["updated_at"] = datetime.now().isoformat()
                    for k, v in kwargs.items():
                        t[k] = v
                    break
            data["updated"] = datetime.now().isoformat()
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def add_subtasks(parent_id: str, subtasks: List[dict]):
    """Add subtasks to backlog (fractal decomposition)"""
    import fcntl

    with open(BACKLOG_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)

            # Mark parent as decomposed
            for t in data.get("tasks", []):
                if t.get("id") == parent_id:
                    t["status"] = "decomposed"
                    t["subtask_ids"] = [st["id"] for st in subtasks]
                    t["updated_at"] = datetime.now().isoformat()
                    break

            # Add subtasks
            data["tasks"].extend(subtasks)
            data["updated"] = datetime.now().isoformat()

            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    log(f"Decomposed {parent_id} into {len(subtasks)} subtasks", "FRACTAL")


def run_adversarial_gate(task: dict, worker_id: int) -> Tuple[bool, str]:
    """
    Run adversarial check on task files.
    Returns (approved, feedback).
    """
    agent = AdversarialAgent()
    files = task.get("files", [])
    file_path = task.get("file_path")
    domain = task.get("domain", "rust")

    # Determine file type from domain
    file_type_map = {
        "rust": "rust",
        "typescript": "typescript",
        "e2e": "typescript",
        "php": "php",
    }
    file_type = file_type_map.get(domain, "rust")

    # Collect files to check
    files_to_check = []
    if file_path:
        full_path = POPINZ_ROOT / file_path
        if full_path.exists():
            files_to_check.append(full_path)

    for f in files:
        full_path = POPINZ_ROOT / f
        if full_path.exists():
            files_to_check.append(full_path)

    if not files_to_check:
        log(f"No files to check for adversarial gate", "WARN", worker_id)
        return True, ""

    # Run adversarial check on each file
    total_score = 0
    all_issues = []

    for fpath in files_to_check:
        try:
            code = fpath.read_text(encoding='utf-8', errors='ignore')
            result = agent.check_code(code, file_type=file_type)
            total_score += result.get("score", 0)
            all_issues.extend(result.get("issues", []))
        except Exception as e:
            log(f"Error reading {fpath}: {e}", "ERROR", worker_id)

    approved = total_score < agent.REJECT_THRESHOLD

    if approved:
        log(f"✅ Adversarial APPROVED (score={total_score})", "GATE", worker_id)
        return True, ""
    else:
        feedback = f"Adversarial REJECTED (score={total_score}):\n"
        for issue in all_issues[:5]:
            feedback += f"  - {issue.get('rule')}: {issue.get('message')} (line {issue.get('line')})\n"
        log(f"❌ Adversarial REJECTED (score={total_score})", "GATE", worker_id)
        return False, feedback


@dataclass
class TDDResult:
    """Result of a TDD cycle"""
    task_id: str
    success: bool = False
    decomposed: bool = False
    subtask_ids: List[str] = field(default_factory=list)
    test_file: Optional[str] = None
    files_modified: List[str] = field(default_factory=list)
    error: Optional[str] = None
    agent_output: str = ""
    attempt: int = 1


@dataclass
class FractalAnalysis:
    """Analysis result for fractal decomposition"""
    should_decompose: bool = False
    reason: str = ""
    estimated_files: int = 0
    estimated_loc: int = 0
    estimated_items: int = 0
    complexity_score: int = 0
    suggested_splits: List[dict] = field(default_factory=list)


def analyze_for_fractal(task: dict) -> FractalAnalysis:
    """
    Analyze if task should be decomposed (fractalized).
    Returns analysis with suggested splits if too complex.
    """
    analysis = FractalAnalysis()

    files = task.get("files", [])
    file_content = task.get("file_content", "")
    description = task.get("description", "")
    domain = task.get("domain", "unknown")
    task_type = task.get("type", "fix")

    # REQUIREMENT tasks always need decomposition
    if task_type == "requirement":
        analysis.should_decompose = True
        analysis.reason = "requirement-type task (mega-task)"
        analysis.complexity_score = 10

        # Expand directories to actual source files
        expanded_files = []
        for f in files:
            path = POPINZ_ROOT / f
            if path.is_dir():
                # Get all source files in directory
                for ext in ["*.swift", "*.kt", "*.rs", "*.ts", "*.tsx", "*.php", "*.py"]:
                    expanded_files.extend([str(p.relative_to(POPINZ_ROOT)) for p in path.rglob(ext)])
            elif path.exists():
                expanded_files.append(f)

        if expanded_files:
            files = expanded_files[:50]  # Limit to 50 files max for decomposition
            analysis.estimated_files = len(expanded_files)
        else:
            analysis.estimated_files = max(20, task.get("file_count", 20))

        analysis.suggested_splits = generate_splits_for_requirement(task, expanded_files)
        return analysis

    # Count files
    analysis.estimated_files = len(files)

    # Estimate LOC from file_content
    if file_content:
        analysis.estimated_loc = len(file_content.split('\n'))

    # Count items (routes, actions, methods to implement)
    items_patterns = [
        r'route.*?(?:GET|POST|PUT|DELETE)',  # Routes
        r'fn\s+\w+',                          # Rust functions
        r'function\s+\w+',                    # JS/TS functions
        r'def\s+\w+',                         # Python functions
        r'test\s*\(',                         # Test cases
        r'describe\s*\(',                     # Test suites
    ]
    item_count = 0
    content_to_check = file_content + description
    for pattern in items_patterns:
        item_count += len(re.findall(pattern, content_to_check, re.IGNORECASE))
    analysis.estimated_items = item_count

    # Complexity: count domains involved
    domains_involved = set()
    domain_keywords = {
        "db": ["sql", "database", "migration", "table", "column", "query"],
        "api": ["endpoint", "route", "controller", "handler", "grpc", "rest"],
        "ui": ["view", "component", "template", "frontend", "css", "html"],
        "test": ["test", "spec", "playwright", "vitest", "phpunit"],
    }
    desc_lower = description.lower()
    for d, keywords in domain_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            domains_involved.add(d)
    analysis.complexity_score = len(domains_involved)

    # Check thresholds
    thresholds = FRACTAL_THRESHOLDS
    reasons = []

    if analysis.estimated_files > thresholds["max_files"]:
        reasons.append(f"files={analysis.estimated_files}>{thresholds['max_files']}")

    if analysis.estimated_loc > thresholds["max_loc"]:
        reasons.append(f"loc={analysis.estimated_loc}>{thresholds['max_loc']}")

    if analysis.estimated_items > thresholds["max_items"]:
        reasons.append(f"items={analysis.estimated_items}>{thresholds['max_items']}")

    if analysis.complexity_score > thresholds["max_complexity"]:
        reasons.append(f"complexity={analysis.complexity_score}>{thresholds['max_complexity']}")

    if reasons:
        analysis.should_decompose = True
        analysis.reason = ", ".join(reasons)

        # Generate suggested splits
        analysis.suggested_splits = generate_splits(task, analysis)

    return analysis


def generate_splits_for_requirement(task: dict, expanded_files: List[str]) -> List[dict]:
    """
    Generate subtasks for a requirement-type mega-task.
    Groups files by directory/module for parallel processing.
    """
    splits = []
    task_id = task.get("id", "unknown")
    description = task.get("description", "")
    context = task.get("context", {})

    # Group files by top-level directory
    file_groups = {}
    for f in expanded_files:
        parts = f.split("/")
        if len(parts) >= 2:
            group_key = f"{parts[0]}/{parts[1]}"  # e.g., "popinz-mobile-ios/Appel"
        else:
            group_key = parts[0]

        if group_key not in file_groups:
            file_groups[group_key] = []
        file_groups[group_key].append(f)

    # Create subtask for each group (max 20 subtasks)
    for i, (group, group_files) in enumerate(list(file_groups.items())[:20]):
        # Determine subtask domain from file extensions
        subtask_domain = "mobile"
        if any(f.endswith(".swift") for f in group_files):
            subtask_domain = "ios"
        elif any(f.endswith(".kt") for f in group_files):
            subtask_domain = "android"
        elif any(f.endswith(".rs") for f in group_files):
            subtask_domain = "rust"
        elif any(f.endswith((".ts", ".tsx")) for f in group_files):
            subtask_domain = "typescript"

        subtask = {
            "id": f"{task_id}-{i+1:02d}-{Path(group).name[:15]}",
            "type": "implementation",
            "domain": subtask_domain,
            "description": f"[{i+1}/{len(file_groups)}] {description} - Module: {group}",
            "files": group_files[:10],  # Max 10 files per subtask
            "file_path": group_files[0] if group_files else None,
            "parent_task_id": task_id,
            "status": "pending",
            "wsjf_score": 4.0,  # Higher priority for requirement subtasks
            "context": {
                **context,
                "module": group,
                "file_count": len(group_files),
            },
            "created_at": datetime.now().isoformat(),
        }
        splits.append(subtask)

    # If no groups created, create generic subtasks
    if not splits:
        for i, phase in enumerate(["setup", "core", "ui", "tests", "integration"]):
            subtask = {
                "id": f"{task_id}-phase{i+1}-{phase}",
                "type": "implementation",
                "domain": task.get("domain", "mobile"),
                "description": f"[Phase {i+1}/5] {description} - {phase.title()}",
                "files": [],
                "parent_task_id": task_id,
                "status": "pending",
                "wsjf_score": 4.0,
                "context": {**context, "phase": phase},
                "created_at": datetime.now().isoformat(),
            }
            splits.append(subtask)

    return splits


def generate_splits(task: dict, analysis: FractalAnalysis) -> List[dict]:
    """Generate subtasks for a task that needs decomposition"""
    splits = []
    task_id = task.get("id", "unknown")
    domain = task.get("domain", "unknown")
    files = task.get("files", [])
    description = task.get("description", "")

    # Strategy 1: Split by files
    if len(files) > FRACTAL_THRESHOLDS["max_files"]:
        # Group files by directory or type
        for i, file_path in enumerate(files):
            subtask = {
                "id": f"{task_id}-file{i+1:02d}",
                "type": task.get("type", "fix"),
                "domain": domain,
                "description": f"[Subtask {i+1}/{len(files)}] {description} - File: {Path(file_path).name}",
                "files": [file_path],
                "parent_task_id": task_id,
                "status": "pending",
                "wsjf_score": task.get("wsjf_score", 0) + 0.1,  # Slightly higher priority
                "created_at": datetime.now().isoformat(),
            }

            # Copy enrichment data for this specific file
            if task.get("file_content"):
                subtask["file_content"] = task["file_content"]
            if task.get("conventions"):
                subtask["conventions"] = task["conventions"]
            if task.get("test_example"):
                subtask["test_example"] = task["test_example"]

            splits.append(subtask)

    # Strategy 2: Split by domain (if multi-domain)
    elif analysis.complexity_score > FRACTAL_THRESHOLDS["max_complexity"]:
        domains = ["db", "api", "ui", "test"]
        desc_lower = description.lower()

        for d in domains:
            domain_keywords = {
                "db": ["database", "migration", "table", "sql"],
                "api": ["endpoint", "route", "controller", "api"],
                "ui": ["view", "component", "template", "frontend"],
                "test": ["test", "spec", "e2e"],
            }

            if any(kw in desc_lower for kw in domain_keywords.get(d, [])):
                subtask = {
                    "id": f"{task_id}-{d}",
                    "type": task.get("type", "fix"),
                    "domain": d if d != "test" else domain,
                    "description": f"[{d.upper()} layer] {description}",
                    "files": files,
                    "parent_task_id": task_id,
                    "status": "pending",
                    "wsjf_score": task.get("wsjf_score", 0) + 0.1,
                    "created_at": datetime.now().isoformat(),
                }
                splits.append(subtask)

    # Strategy 3: Split into chunks (default)
    else:
        chunk_size = max(1, analysis.estimated_items // 3)
        for i in range(3):
            subtask = {
                "id": f"{task_id}-part{i+1}",
                "type": task.get("type", "fix"),
                "domain": domain,
                "description": f"[Part {i+1}/3] {description}",
                "files": files,
                "parent_task_id": task_id,
                "status": "pending",
                "wsjf_score": task.get("wsjf_score", 0) + 0.1,
                "created_at": datetime.now().isoformat(),
            }

            # Copy enrichment
            for key in ["file_content", "conventions", "test_example", "error_context"]:
                if task.get(key):
                    subtask[key] = task[key]

            splits.append(subtask)

    return splits


def build_agent_prompt(task: dict, include_fractal_check: bool = True) -> str:
    """
    Build the prompt for the opencode agent.
    Include fractal awareness and TDD cycle instructions.
    """
    task_id = task.get("id", "unknown")
    domain = task.get("domain", "unknown")
    description = task.get("description", "")
    files = task.get("files", [])
    file_path = files[0] if files else ""
    parent_id = task.get("parent_task_id")

    # Get enriched context
    file_content = task.get("file_content", "")
    imports = task.get("imports", [])
    types_defined = task.get("types_defined", [])
    error_context = task.get("error_context", {})
    test_example = task.get("test_example", "")
    conventions = task.get("conventions", {})

    # Check if this is a retry (adversarial_failed task being retried)
    is_retry = task.get("_is_retry", False)
    retry_count = task.get("retry_count", 0)
    adversarial_feedback = task.get("adversarial_feedback", "")

    # ADVERSARIAL RULES - Always prepended to all prompts
    adversarial_rules = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                         🚨 ADVERSARIAL GATE RULES 🚨                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Ton code sera vérifié par une gate adversarial. Ces patterns = REJET:        ║
║                                                                              ║
║ INTERDIT (5 points = REJET IMMÉDIAT):                                        ║
║   ❌ test.skip()           → Utilise: test.skip(IS_STAGING, 'raison')        ║
║   ❌ describe.skip()       → Utilise: describe.skip(condition)               ║
║   ❌ it.skip()             → Utilise: test.skip(condition)                   ║
║                                                                              ║
║ INTERDIT (2 points chacun):                                                  ║
║   ❌ : any                 → Utilise le vrai type ou générique <T>           ║
║   ❌ as any                → Utilise le vrai type                            ║
║   ❌ @ts-ignore            → Corrige l'erreur TypeScript                     ║
║   ❌ @ts-expect-error      → Corrige l'erreur TypeScript                     ║
║                                                                              ║
║ WARNING (1 point chacun):                                                    ║
║   ⚠️  TODO / FIXME         → Supprime ou implémente                          ║
║   ⚠️  .unwrap() (Rust)     → Utilise ? ou .expect("msg")                     ║
║                                                                              ║
║ Score >= 5 points = CODE REJETÉ par la gate                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

    # Add retry context if this is a retry
    retry_context = ""
    if is_retry and adversarial_feedback:
        retry_context = f"""
⚠️ ATTENTION: RETRY #{retry_count + 1} - Cette tâche a été REJETÉE par la gate adversarial !
RAISON DU REJET: {adversarial_feedback}

Tu DOIS corriger les violations ci-dessus. Si tu refais les mêmes erreurs, la tâche échouera à nouveau.
"""

    # Fractal context
    fractal_context = ""
    if parent_id:
        fractal_context = f"\n⚠️ Cette tâche est une SOUS-TÂCHE de {parent_id}. Focus uniquement sur ton périmètre.\n"

    if include_fractal_check:
        fractal_context += """
RÈGLE FRACTALE:
Si la tâche te semble trop large (>5 fichiers, >400 LOC, >10 éléments), dis:
"FRACTAL: Cette tâche nécessite une décomposition"
Et liste les sous-tâches suggérées. Je créerai les sous-tâches.
"""

    # Build prompt based on domain
    if domain == "e2e":
        return f"""{adversarial_rules}
{retry_context}
Tu es un agent Wiggum TDD. Ta mission: corriger cette tâche E2E avec un VRAI cycle TDD.
{fractal_context}
TÂCHE: {task_id}
DESCRIPTION: {description}
FICHIER: {file_path}
ERREUR: {error_context.get('message', 'N/A') if isinstance(error_context, dict) else 'N/A'}

CONVENTIONS DU PROJET:
- Framework: {conventions.get('framework', 'Playwright TypeScript') if isinstance(conventions, dict) else 'Playwright TypeScript'}
- Structure: {conventions.get('structure', 'test.describe > test > expect') if isinstance(conventions, dict) else 'test.describe > test > expect'}
- CRITIQUE: {conventions.get('skip_pattern', 'JAMAIS de test.skip() nu - utilise test.skip(IS_STAGING, "raison")') if isinstance(conventions, dict) else 'JAMAIS de test.skip() nu'}

CONTENU ACTUEL DU FICHIER:
```typescript
{file_content[:4000] if file_content else "Utilise Read pour lire le fichier"}
```

{f"EXEMPLE DE BON TEST:{chr(10)}```typescript{chr(10)}{test_example[:1500]}{chr(10)}```" if test_example else ""}

ÉTAPES TDD:
1. Lis le fichier avec Read si pas déjà fait
2. Corrige le code (supprime test.skip/test.only ou ajoute condition IS_STAGING)
3. Écris le fichier corrigé avec Write
4. Lance le test: npx playwright test {Path(file_path).name} --reporter=list
5. Si le test passe, dis "TDD SUCCESS"
6. Si le test échoue, corrige et réessaie (max 3 fois)

RÈGLES:
- JAMAIS de test.skip() sans condition
- Si skip nécessaire: test.skip(IS_STAGING, 'Feature not on staging')
- Définis IS_STAGING si absent: const IS_STAGING = BASE_URL.includes('staging')
"""

    elif domain in ["rust", "api-saas", "api-central", "api-registrations"]:
        return f"""{adversarial_rules}
{retry_context}
Tu es un agent Wiggum TDD. Ta mission: corriger cette tâche Rust avec un VRAI cycle TDD.
{fractal_context}
TÂCHE: {task_id}
DESCRIPTION: {description}
FICHIER: {file_path}
ERREUR: {error_context.get('message', 'N/A') if isinstance(error_context, dict) else 'N/A'}

CONVENTIONS:
- Error handling: {conventions.get('error_handling', 'Use ? operator, avoid unwrap()') if isinstance(conventions, dict) else 'Use ? operator'}
- Testing: {conventions.get('testing', '#[cfg(test)] mod tests') if isinstance(conventions, dict) else '#[cfg(test)] mod tests'}
- Async: {conventions.get('async', 'tokio runtime') if isinstance(conventions, dict) else 'tokio runtime'}

TYPES DÉFINIS: {', '.join(types_defined) if types_defined else 'N/A'}
IMPORTS: {', '.join(imports[:10]) if imports else 'N/A'}

CONTENU ACTUEL:
```rust
{file_content[:4000] if file_content else "Utilise Read pour lire le fichier"}
```

{f"EXEMPLE DE TEST:{chr(10)}```rust{chr(10)}{test_example[:1500]}{chr(10)}```" if test_example else ""}

ÉTAPES TDD:
1. Lis le fichier
2. Ajoute un test #[test] qui vérifie le fix
3. Écris le fix
4. Lance: cargo test --package <crate> -- --nocapture
5. Si test passe, dis "TDD SUCCESS"

RÈGLES:
- Pas de unwrap() - utilise ? ou expect()
- Pas de todo!() ou unimplemented!()
"""

    elif domain == "typescript":
        return f"""{adversarial_rules}
{retry_context}
Tu es un agent Wiggum TDD. Ta mission: corriger cette tâche TypeScript avec TDD.
{fractal_context}
TÂCHE: {task_id}
DESCRIPTION: {description}
FICHIER: {file_path}

CONVENTIONS:
- Types: {conventions.get('types', 'Strict TypeScript, no any') if isinstance(conventions, dict) else 'Strict TypeScript, no any'}
- Testing: {conventions.get('testing', 'Vitest avec describe/it/expect') if isinstance(conventions, dict) else 'Vitest'}

CONTENU:
```typescript
{file_content[:4000] if file_content else "Utilise Read"}
```

ÉTAPES TDD:
1. Lis le fichier
2. Crée un fichier .test.ts avec des tests
3. Corrige le code
4. Lance: npx vitest run {Path(file_path).stem}.test.ts
5. Si tests passent, dis "TDD SUCCESS"
"""

    else:
        return f"""{adversarial_rules}
{retry_context}
Tu es un agent Wiggum. Corrige cette tâche:
{fractal_context}
TÂCHE: {task_id}
DESCRIPTION: {description}
FICHIER: {file_path}
DOMAINE: {domain}

Lis le fichier, corrige le problème, écris le fix.
Dis "TDD SUCCESS" quand terminé.
"""


async def run_agent(task: dict, worker_id: int) -> TDDResult:
    """
    Run an opencode agent for a single task.
    Supports fractal decomposition if task is too complex.
    """
    task_id = task.get("id", "unknown")
    result = TDDResult(task_id=task_id)

    log(f"Starting agent: {task_id}", "INFO", worker_id)

    # Step 1: Fractal analysis
    analysis = analyze_for_fractal(task)
    if analysis.should_decompose:
        log(f"Task too complex ({analysis.reason}), decomposing...", "FRACTAL", worker_id)

        if analysis.suggested_splits:
            add_subtasks(task_id, analysis.suggested_splits)
            result.decomposed = True
            result.subtask_ids = [st["id"] for st in analysis.suggested_splits]
            result.success = True  # Decomposition is a success
            log(f"Created {len(analysis.suggested_splits)} subtasks", "FRACTAL", worker_id)
            return result

    try:
        # Handle retry: increment retry_count if this is a retry
        is_retry = task.get("_is_retry", False)
        if is_retry:
            retry_count = task.get("retry_count", 0) + 1
            mark_task_status(task_id, "in_progress", retry_count=retry_count)
            log(f"🔄 Retry #{retry_count} for task {task_id}", "INFO", worker_id)
        else:
            mark_task_status(task_id, "in_progress")

        # Build the prompt
        prompt = build_agent_prompt(task)

        # Create temp file for prompt
        prompt_file = LOG_DIR / f"prompt_{worker_id}_{task_id[:20]}.txt"
        prompt_file.write_text(prompt)

        # Log file for agent output
        log_file = LOG_DIR / f"agent_{worker_id}_{task_id[:20]}.log"

        # ═══════════════════════════════════════════════════════════════════
        # IMPORTANT: Utiliser opencode + MiniMax (PAS Claude CLI - trop coûteux)
        #
        # Prérequis:
        #   1. opencode installé: npm install -g opencode
        #   2. opencode configuré avec clé MiniMax dans ~/.config/opencode/opencode.json
        #   3. Clé MiniMax coding (payante mais pas cher): https://platform.minimax.io
        #
        # PAS de fallback Claude CLI (coûteux en tokens)
        # PAS de ollama (trop lent)
        # ═══════════════════════════════════════════════════════════════════
        if not shutil.which("opencode"):
            log(f"ERREUR: opencode non trouvé. Installer: npm install -g opencode", "ERROR", worker_id)
            result.error = "opencode not installed"
            return result

        cmd = [
            "opencode", "run",
            "-m", "minimax/MiniMax-M2.1",  # Modèle MiniMax pour coding
            prompt
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(POPINZ_ROOT),
            env={
                **os.environ,
                "FORCE_COLOR": "0",
                "NO_COLOR": "1",
            }
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=AGENT_TIMEOUT
            )
            output = stdout.decode() + stderr.decode()
            result.agent_output = output[-5000:]  # Last 5000 chars

            # Write log
            log_file.write_text(output)

            # Check for fractal request from agent
            if "FRACTAL:" in output:
                log(f"Agent requested decomposition", "FRACTAL", worker_id)
                # Parse suggested subtasks from output
                # For now, use our analysis
                if analysis.suggested_splits:
                    add_subtasks(task_id, analysis.suggested_splits)
                    result.decomposed = True
                    result.subtask_ids = [st["id"] for st in analysis.suggested_splits]
                    result.success = True
                    return result

            # Check if TDD succeeded
            if "TDD SUCCESS" in output:
                result.success = True
                log(f"✅ TDD SUCCESS: {task_id}", "INFO", worker_id)
            else:
                result.error = "TDD did not complete successfully"
                log(f"❌ TDD incomplete: {task_id}", "WARN", worker_id)

        except asyncio.TimeoutError:
            proc.kill()
            result.error = f"Agent timeout ({AGENT_TIMEOUT}s)"
            log(f"⏱️ Timeout: {task_id}", "ERROR", worker_id)

        # Update task status with adversarial gate
        if result.success and not result.decomposed:
            # TDD passed → run adversarial gate
            mark_task_status(task_id, "ready_for_adversarial")
            log(f"🔍 Running adversarial gate...", "GATE", worker_id)

            approved, feedback = run_adversarial_gate(task, worker_id)

            if approved:
                mark_task_status(task_id, "completed", completed_at=datetime.now().isoformat())
                log(f"🎉 Task completed: {task_id}", "INFO", worker_id)
            else:
                mark_task_status(task_id, "adversarial_failed",
                               adversarial_feedback=feedback,
                               error="Adversarial gate rejected")
                result.success = False
                result.error = feedback
                log(f"🚫 Adversarial rejected: {task_id}", "GATE", worker_id)
        elif result.decomposed:
            # Already marked as decomposed in add_subtasks
            pass
        else:
            mark_task_status(task_id, "failed", error=result.error)

        # Cleanup prompt file
        prompt_file.unlink(missing_ok=True)

    except Exception as e:
        result.error = str(e)
        mark_task_status(task_id, "failed", error=str(e)[:500])
        log(f"❌ Exception: {task_id} - {e}", "ERROR", worker_id)

    return result


class WiggumTDD:
    """Main TDD orchestrator with fractal decomposition support"""

    def __init__(self, num_workers: int = DEFAULT_WORKERS, use_store: bool = False):
        self.num_workers = num_workers
        self.running = True
        self.use_store = use_store
        self.stats = {
            "success": 0,
            "failed": 0,
            "decomposed": 0,
            "errors": 0
        }

    async def run_once(self, task_id: str = None) -> List[TDDResult]:
        """Process one task"""
        if task_id:
            data = load_backlog()
            task = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
            if not task:
                log(f"Task {task_id} not found", "ERROR")
                return []
            tasks = [task]
        else:
            tasks = get_pending_tasks(limit=1)

        if not tasks:
            log("No pending tasks")
            return []

        result = await run_agent(tasks[0], 1)
        return [result]

    async def run_daemon(self):
        """Run continuously with dynamic worker pool and fractal support"""
        log("=" * 70)
        log(f"WIGGUM TDD - {self.num_workers} parallel agents (fractal enabled)")
        log(f"Using: opencode + MiniMax M2.1 (MINIMAX_API_KEY)")
        log("=" * 70)
        log("Tools: Read, Write, Bash, MCP")
        log("Cycle: ANALYZE → RED → GREEN → VERIFY → SUCCESS")
        log(f"Fractal thresholds: files≤{FRACTAL_THRESHOLDS['max_files']}, loc≤{FRACTAL_THRESHOLDS['max_loc']}, items≤{FRACTAL_THRESHOLDS['max_items']}")
        log("")

        # Dynamic pool: workers pick up tasks immediately when available
        semaphore = asyncio.Semaphore(self.num_workers)
        active_tasks = set()

        async def worker(task: dict, worker_id: int):
            async with semaphore:
                try:
                    result = await run_agent(task, worker_id)
                    if result.decomposed:
                        self.stats["decomposed"] += 1
                    elif result.success:
                        self.stats["success"] += 1
                    else:
                        self.stats["failed"] += 1
                except Exception as e:
                    self.stats["errors"] += 1
                    log(f"Worker exception: {e}", "ERROR", worker_id)

        worker_id = 0
        while self.running:
            # Clean up completed tasks
            done = {t for t in active_tasks if t.done()}
            active_tasks -= done

            # Get pending tasks to fill available slots
            available_slots = self.num_workers - len(active_tasks)
            if available_slots > 0:
                tasks = get_pending_tasks(limit=available_slots)

                if tasks:
                    for task in tasks:
                        worker_id = (worker_id % self.num_workers) + 1
                        t = asyncio.create_task(worker(task, worker_id))
                        active_tasks.add(t)
                elif not active_tasks:
                    # No pending tasks and no active workers
                    log(f"Stats: {self.stats['success']}✅ {self.stats['failed']}❌ {self.stats['decomposed']}🔀 {self.stats['errors']}💥")
                    log("No pending tasks, sleeping 30s...")
                    await asyncio.sleep(30)
                    continue

            # Brief pause before checking again
            await asyncio.sleep(2)

    def stop(self):
        self.running = False


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wiggum TDD - Parallel agents with fractal decomposition")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--task", type=str)
    parser.add_argument("--use-store", action="store_true", help="Use SQLite task store")
    parser.add_argument("--no-fractal", action="store_true", help="Disable fractal decomposition")
    args = parser.parse_args()

    # Disable fractal if requested
    if args.no_fractal:
        FRACTAL_THRESHOLDS["max_files"] = 9999
        FRACTAL_THRESHOLDS["max_loc"] = 999999
        FRACTAL_THRESHOLDS["max_items"] = 9999

    # ═══════════════════════════════════════════════════════════════════
    # Prérequis: opencode + MiniMax configuré
    # Config: ~/.config/opencode/opencode.json (contient la clé MiniMax)
    # PAS de Claude CLI (trop coûteux) - PAS de ollama (trop lent)
    # ═══════════════════════════════════════════════════════════════════
    if not shutil.which("opencode"):
        print("❌ ERROR: 'opencode' CLI non trouvé")
        print("   Install: npm install -g opencode")
        print("   Config: opencode (première fois = configure MiniMax)")
        sys.exit(1)

    print(f"✅ opencode trouvé (config: ~/.config/opencode/opencode.json)")
    print(f"🚀 Lancement de {args.workers} workers TDD avec MiniMax M2.1...")

    tdd = WiggumTDD(num_workers=args.workers, use_store=args.use_store)

    if args.task:
        await tdd.run_once(task_id=args.task)
    elif args.once:
        await tdd.run_once()
    else:
        await tdd.run_daemon()


if __name__ == "__main__":
    asyncio.run(main())
