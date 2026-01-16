#!/usr/bin/env python3
"""
backlog_to_tasks.py - Convertit le backlog markdown en fichiers T*.md atomiques

Parse VELIGO_TDD_BACKLOG_COMPLET.md et génère des fichiers de tâches individuels
pour le Wiggum daemon.

Usage:
    python3 backlog_to_tasks.py
"""
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TASKS_DIR = SCRIPT_DIR / "tasks"
STATUS_DIR = SCRIPT_DIR / "status"
BACKLOG_FILE = TASKS_DIR / "VELIGO_TDD_BACKLOG_COMPLET.md"

def get_next_task_id() -> int:
    """Trouve le prochain ID de tâche disponible."""
    existing_ids = []
    for f in TASKS_DIR.glob("T*.md"):
        try:
            # Extract number from T### format
            num = int(re.search(r'T(\d+)', f.stem).group(1))
            existing_ids.append(num)
        except (AttributeError, ValueError):
            pass
    return max(existing_ids) + 1 if existing_ids else 400

def parse_backlog(content: str) -> list:
    """Parse le backlog markdown et extrait les tâches."""
    tasks = []

    # Pattern pour les lignes de tableau: | ID | Task | WSJF | Files | Test File |
    table_pattern = r'\|\s*([A-Z0-9\-]+)\s*\|\s*(.+?)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*`(.+?)`\s*\|'

    current_phase = ""
    current_section = ""

    lines = content.split('\n')
    for i, line in enumerate(lines):
        # Detect phase
        if line.startswith('## '):
            current_phase = line.strip('# ').strip()
        elif line.startswith('### '):
            current_section = line.strip('# ').strip()

        # Parse table rows
        match = re.match(table_pattern, line)
        if match:
            task_id = match.group(1)
            description = match.group(2).strip()
            wsjf = float(match.group(3))
            files_count = int(match.group(4))
            test_file = match.group(5)

            # Determine priority from WSJF
            if wsjf >= 9.0:
                priority = "P0"
            elif wsjf >= 7.5:
                priority = "P1"
            elif wsjf >= 6.0:
                priority = "P2"
            else:
                priority = "P3"

            # Determine domain/category from ID prefix
            if task_id.startswith("J-E2E"):
                category = "JOURNEY"
                queue = "TDD"
            elif task_id.startswith("AO-"):
                category = "AO_COMPLIANCE"
                queue = "TDD"
            elif task_id.startswith("WL-"):
                category = "WHITE_LABEL"
                queue = "TDD"
            elif task_id.startswith("MOD-"):
                category = "MODULE"
                queue = "TDD"
            elif task_id.startswith("TPL-"):
                category = "TEMPLATE"
                queue = "TDD"
            else:
                category = "GENERAL"
                queue = "TDD"

            tasks.append({
                "original_id": task_id,
                "description": description,
                "wsjf": wsjf,
                "files_count": files_count,
                "test_file": test_file,
                "priority": priority,
                "category": category,
                "queue": queue,
                "phase": current_phase,
                "section": current_section,
            })

    return tasks

def create_task_file(task_num: int, task: dict) -> Path:
    """Crée un fichier de tâche individuel."""
    task_id = f"T{task_num:03d}"

    content = f"""# Task {task_id}: {task['description']}

**Priority**: {task['priority']}
**WSJF Score**: {task['wsjf']}
**Queue**: {task['queue']}
**Category**: {task['category']}
**Original ID**: {task['original_id']}
**Phase**: {task['phase']}
**Section**: {task['section']}

## Description
{task['description']}

## Test File
`{task['test_file']}`

## Estimated Files
{task['files_count']} fichier(s) à modifier

## Success Criteria
- [ ] Test E2E créé/modifié: `{task['test_file']}`
- [ ] Test passe en local
- [ ] Pas de test.skip() sans condition
- [ ] Code review adversarial passé
- [ ] Pas de stubs ou TODOs

## Definition of Done (DoD)
- [ ] Feature complètement implémentée
- [ ] Tests E2E verts
- [ ] Conformité AO vérifiée (si applicable)
- [ ] Documentation mise à jour

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: {'high' if task['files_count'] > 4 else 'medium' if task['files_count'] > 2 else 'low'}
WSJF: {task['wsjf']}
CATEGORY: {task['category']}
ORIGINAL_ID: {task['original_id']}
---END_RALPH_STATUS---
"""

    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(content)

    # Create status file
    status_file = STATUS_DIR / f"{task_id}.status"
    status_file.write_text("PENDING\n")

    return task_file

def main():
    """Parse le backlog et génère les fichiers de tâches."""
    print("=" * 60)
    print("BACKLOG TO TASKS CONVERTER")
    print("=" * 60)

    if not BACKLOG_FILE.exists():
        print(f"ERROR: Backlog file not found: {BACKLOG_FILE}")
        return 1

    content = BACKLOG_FILE.read_text()
    tasks = parse_backlog(content)

    if not tasks:
        print("ERROR: No tasks found in backlog")
        return 1

    print(f"Found {len(tasks)} tasks in backlog")

    # Sort by WSJF (highest first)
    tasks.sort(key=lambda t: t['wsjf'], reverse=True)

    next_id = get_next_task_id()
    print(f"Starting task IDs at T{next_id:03d}")

    created = []
    for i, task in enumerate(tasks):
        task_file = create_task_file(next_id + i, task)
        created.append(task_file.name)
        print(f"  Created {task_file.name}: {task['description'][:50]}... (WSJF={task['wsjf']})")

    print(f"\n{'=' * 60}")
    print(f"DONE: Created {len(created)} task files")
    print(f"Range: T{next_id:03d} - T{next_id + len(created) - 1:03d}")
    print(f"{'=' * 60}")

    # Summary by category
    categories = {}
    for task in tasks:
        cat = task['category']
        categories[cat] = categories.get(cat, 0) + 1

    print("\nTasks by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    return 0

if __name__ == "__main__":
    exit(main())
