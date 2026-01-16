#!/usr/bin/env python3
"""
fractal.py - Fractal Task Decomposition pour Wiggum TDD

Implémente la logique de décomposition fractale:
- Détecte quand une task est trop large
- Découpe en sous-tasks atomiques
- Crée les fichiers de sous-tasks avec contrats et DoD

Seuils de décomposition:
- MAX_FILES: 5 fichiers touchés
- MAX_LOC: 400 lignes de code
- MAX_ITEMS: 10 éléments (routes, endpoints, etc.)

Usage:
    from fractal import FractalDecomposer
    decomposer = FractalDecomposer(tasks_dir)
    if decomposer.should_decompose(task_analysis):
        sub_tasks = decomposer.decompose(task_id, task_analysis)
"""

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# ============================================================================
# SEUILS DE DÉCOMPOSITION
# ============================================================================
MAX_FILES = 5          # Max fichiers à toucher
MAX_LOC = 400          # Max lignes de code à écrire
MAX_ITEMS = 10         # Max éléments (routes, endpoints, etc.)
MAX_DOMAINS = 2        # Max domaines différents (DB, API, UI)

# Domains connus
DOMAIN_PATTERNS = {
    "db": [r'migration', r'schema', r'\.sql$', r'entity\.rs', r'repository'],
    "api": [r'grpc', r'handler', r'service\.rs', r'route', r'controller'],
    "ui": [r'\.svelte$', r'\+page', r'component', r'\.tsx?$'],
    "test": [r'\.spec\.', r'test_', r'_test\.'],
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================
@dataclass
class TaskAnalysis:
    """Analyse d'une task pour décider de la décomposition."""
    task_id: str
    title: str
    description: str
    files_estimated: List[str] = field(default_factory=list)
    loc_estimated: int = 0
    items: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    priority: str = "P1"
    wsjf: float = 7.0

    def exceeds_thresholds(self) -> Tuple[bool, List[str]]:
        """Check if task exceeds decomposition thresholds."""
        reasons = []

        if len(self.files_estimated) > MAX_FILES:
            reasons.append(f"files={len(self.files_estimated)} > {MAX_FILES}")

        if self.loc_estimated > MAX_LOC:
            reasons.append(f"LOC={self.loc_estimated} > {MAX_LOC}")

        if len(self.items) > MAX_ITEMS:
            reasons.append(f"items={len(self.items)} > {MAX_ITEMS}")

        if len(self.domains) > MAX_DOMAINS:
            reasons.append(f"domains={len(self.domains)} > {MAX_DOMAINS}")

        return len(reasons) > 0, reasons


@dataclass
class SubTask:
    """Sous-task générée par décomposition fractale."""
    id: str
    parent_id: str
    title: str
    description: str
    contract: str  # Interface/signature attendue
    dod: List[str]  # Definition of Done
    files: List[str]
    items: List[str]
    domain: str
    priority: str
    wsjf: float


# ============================================================================
# TASK ANALYZER
# ============================================================================
class TaskAnalyzer:
    """Analyse une task pour estimer sa complexité."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def _detect_domains(self, task_content: str, files: List[str]) -> List[str]:
        """Détecte les domaines impactés."""
        domains = set()

        content_lower = task_content.lower()
        all_files = " ".join(files).lower()

        for domain, patterns in DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content_lower) or re.search(pattern, all_files):
                    domains.add(domain)
                    break

        return list(domains)

    def _estimate_files(self, task_content: str) -> List[str]:
        """Estime les fichiers à modifier."""
        files = []

        # Cherche des patterns de fichiers
        file_patterns = re.findall(r'[\w/]+\.(rs|ts|svelte|sql|proto)', task_content)
        files.extend(file_patterns)

        # Cherche des chemins explicites
        path_patterns = re.findall(r'(?:src|routes|tests)/[\w/]+\.[\w]+', task_content)
        files.extend(path_patterns)

        return list(set(files))

    def _extract_items(self, task_content: str) -> List[str]:
        """Extrait les éléments à implémenter (routes, endpoints, etc.)."""
        items = []

        # Routes/endpoints mentionnés
        routes = re.findall(r'/[\w/\-:]+', task_content)
        items.extend([r for r in routes if len(r) > 2])

        # RPCs/méthodes mentionnées
        rpcs = re.findall(r'(?:Create|Update|Delete|Get|List|Find)\w+', task_content)
        items.extend(rpcs)

        # Components/pages
        components = re.findall(r'(?:Page|Component|Widget|Modal)\w*', task_content)
        items.extend(components)

        return list(set(items))

    def _estimate_loc(self, files: List[str], items: List[str]) -> int:
        """Estime les lignes de code à écrire."""
        # Heuristique: ~30 LOC par fichier, ~20 LOC par item
        return len(files) * 30 + len(items) * 20

    def analyze(self, task_file: Path) -> TaskAnalysis:
        """Analyse une task file et retourne une TaskAnalysis."""
        content = task_file.read_text()

        # Extract metadata
        title_match = re.search(r'^# Task \w+: (.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Unknown"

        priority_match = re.search(r'\*\*Priority\*\*:\s*(\w+)', content)
        priority = priority_match.group(1) if priority_match else "P1"

        wsjf_match = re.search(r'\*\*WSJF.*?\*\*:\s*([\d.]+)', content)
        wsjf = float(wsjf_match.group(1)) if wsjf_match else 7.0

        # Extract description
        desc_match = re.search(r'## Description\n(.+?)(?=\n##|\n---|\Z)', content, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""

        # Analyze content
        files = self._estimate_files(content)
        items = self._extract_items(content)
        domains = self._detect_domains(content, files)
        loc = self._estimate_loc(files, items)

        task_id = task_file.stem

        return TaskAnalysis(
            task_id=task_id,
            title=title,
            description=description,
            files_estimated=files,
            loc_estimated=loc,
            items=items,
            domains=domains,
            priority=priority,
            wsjf=wsjf
        )


# ============================================================================
# FRACTAL DECOMPOSER
# ============================================================================
class FractalDecomposer:
    """
    Décompose une task trop large en sous-tasks atomiques.

    Stratégies de décomposition:
    1. Par domaine (DB, API, UI séparés)
    2. Par chunks d'items (groupes de 5-8 items)
    3. Par vertical slice (1 feature end-to-end)
    """

    def __init__(self, tasks_dir: Path, project_root: Optional[Path] = None):
        self.tasks_dir = tasks_dir
        self.project_root = project_root or tasks_dir.parent.parent
        self.status_dir = tasks_dir.parent / "status"
        self._next_id_counter = None  # Track IDs being generated in this session

    def should_decompose(self, analysis: TaskAnalysis) -> Tuple[bool, List[str]]:
        """Décide si la task doit être décomposée."""
        return analysis.exceeds_thresholds()

    def _get_next_task_id(self, prefix: str = "T") -> str:
        """Trouve le prochain ID de task disponible."""
        # Initialize counter on first call
        if self._next_id_counter is None:
            existing = list(self.tasks_dir.glob(f"{prefix}*.md"))
            max_num = 0
            for f in existing:
                try:
                    num = int(f.stem[len(prefix):])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
            self._next_id_counter = max_num + 1

        # Return current and increment for next call
        task_id = f"{prefix}{self._next_id_counter:03d}"
        self._next_id_counter += 1
        return task_id

    def _decompose_by_domain(self, analysis: TaskAnalysis) -> List[SubTask]:
        """Décompose par domaine (DB, API, UI)."""
        sub_tasks = []

        for domain in analysis.domains:
            # Filter items for this domain
            domain_items = []
            domain_files = []

            for item in analysis.items:
                item_lower = item.lower()
                for pattern in DOMAIN_PATTERNS.get(domain, []):
                    if re.search(pattern, item_lower):
                        domain_items.append(item)
                        break

            for f in analysis.files_estimated:
                f_lower = f.lower()
                for pattern in DOMAIN_PATTERNS.get(domain, []):
                    if re.search(pattern, f_lower):
                        domain_files.append(f)
                        break

            if domain_items or domain_files:
                sub_id = self._get_next_task_id()
                sub_tasks.append(SubTask(
                    id=sub_id,
                    parent_id=analysis.task_id,
                    title=f"{analysis.title} - {domain.upper()} layer",
                    description=f"Implement {domain} layer for: {analysis.description[:100]}...",
                    contract=f"Domain: {domain}",
                    dod=[
                        f"All {domain} code implemented",
                        "Tests pass",
                        "No stubs or TODOs"
                    ],
                    files=domain_files,
                    items=domain_items,
                    domain=domain,
                    priority=analysis.priority,
                    wsjf=analysis.wsjf
                ))

        return sub_tasks

    def _decompose_by_chunks(self, analysis: TaskAnalysis, chunk_size: int = 5) -> List[SubTask]:
        """Décompose par chunks d'items."""
        sub_tasks = []

        items = analysis.items
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            chunk_num = i // chunk_size + 1

            sub_id = self._get_next_task_id()
            sub_tasks.append(SubTask(
                id=sub_id,
                parent_id=analysis.task_id,
                title=f"{analysis.title} - Batch {chunk_num}",
                description=f"Implement batch {chunk_num}: {', '.join(chunk[:3])}...",
                contract=f"Items: {chunk}",
                dod=[
                    f"All {len(chunk)} items implemented",
                    "Tests pass for all items",
                    "Integration verified"
                ],
                files=[],  # Will be determined during execution
                items=chunk,
                domain=analysis.domains[0] if analysis.domains else "mixed",
                priority=analysis.priority,
                wsjf=analysis.wsjf
            ))

        return sub_tasks

    def decompose(self, analysis: TaskAnalysis, strategy: str = "auto") -> List[SubTask]:
        """
        Décompose une task en sous-tasks.

        Strategies:
        - "domain": Sépare par domaine (DB, API, UI)
        - "chunks": Découpe les items en groupes
        - "auto": Choisit la meilleure stratégie
        """
        exceeds, reasons = analysis.exceeds_thresholds()

        if not exceeds:
            return []  # No decomposition needed

        # Auto-select strategy
        if strategy == "auto":
            if len(analysis.domains) > MAX_DOMAINS:
                strategy = "domain"
            else:
                strategy = "chunks"

        if strategy == "domain":
            return self._decompose_by_domain(analysis)
        else:
            return self._decompose_by_chunks(analysis)

    def create_sub_task_files(self, sub_tasks: List[SubTask]) -> List[Path]:
        """Crée les fichiers de sous-tasks."""
        created_files = []

        for sub in sub_tasks:
            task_file = self.tasks_dir / f"{sub.id}.md"
            status_file = self.status_dir / f"{sub.id}.status"

            content = f"""# Task {sub.id}: {sub.title}

**Priority**: {sub.priority}
**WSJF Score**: {sub.wsjf}
**Queue**: TDD
**Parent**: {sub.parent_id}
**Domain**: {sub.domain}
**Generated by**: Fractal Decomposer

## Description
{sub.description}

## Contract
{sub.contract}

## Items to Implement
{chr(10).join(f'- [ ] {item}' for item in sub.items)}

## Files to Modify
{chr(10).join(f'- {f}' for f in sub.files) if sub.files else '- (To be determined)'}

## Definition of Done (DoD)
{chr(10).join(f'- [ ] {d}' for d in sub.dod)}

## Success Criteria
- [ ] All items implemented
- [ ] Tests pass
- [ ] No stubs, TODOs, or NotImplemented
- [ ] Code reviewed by adversarial gate

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
MODEL_TIER: TIER2
WSJF: {sub.wsjf}
PARENT_TASK: {sub.parent_id}
---END_RALPH_STATUS---
"""

            task_file.write_text(content)
            status_file.write_text("PENDING\n")
            created_files.append(task_file)

        return created_files

    def mark_parent_as_decomposed(self, parent_id: str, sub_task_ids: List[str]):
        """Marque la task parente comme décomposée."""
        parent_file = self.tasks_dir / f"{parent_id}.md"
        parent_status = self.status_dir / f"{parent_id}.status"

        if parent_file.exists():
            content = parent_file.read_text()

            # Add decomposition note
            decompose_note = f"""

## Fractal Decomposition
**Status**: DECOMPOSED
**Sub-tasks**: {', '.join(sub_task_ids)}
**Timestamp**: {datetime.now().isoformat()}

This task was too large and has been decomposed into smaller sub-tasks.
"""
            content = content.replace("---RALPH_STATUS---", decompose_note + "\n---RALPH_STATUS---")
            content = re.sub(r'STATUS: PENDING', 'STATUS: DECOMPOSED', content)

            parent_file.write_text(content)

        if parent_status.exists():
            parent_status.write_text("DECOMPOSED\n")


# ============================================================================
# INTEGRATION WITH WIGGUM
# ============================================================================
def check_and_decompose(task_file: Path, tasks_dir: Path, project_root: Path) -> Tuple[bool, List[str]]:
    """
    Vérifie si une task doit être décomposée et la décompose si nécessaire.

    Returns:
        (was_decomposed, sub_task_ids)
    """
    analyzer = TaskAnalyzer(project_root)
    decomposer = FractalDecomposer(tasks_dir, project_root)

    analysis = analyzer.analyze(task_file)
    should, reasons = decomposer.should_decompose(analysis)

    if not should:
        return False, []

    print(f"[FRACTAL] Task {analysis.task_id} needs decomposition: {', '.join(reasons)}")

    sub_tasks = decomposer.decompose(analysis)
    created = decomposer.create_sub_task_files(sub_tasks)

    sub_ids = [s.id for s in sub_tasks]
    decomposer.mark_parent_as_decomposed(analysis.task_id, sub_ids)

    print(f"[FRACTAL] Created {len(sub_ids)} sub-tasks: {', '.join(sub_ids)}")

    return True, sub_ids


# ============================================================================
# CLI
# ============================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fractal task decomposition")
    parser.add_argument("task_file", help="Task file to analyze/decompose")
    parser.add_argument("--analyze-only", "-a", action="store_true", help="Only analyze, don't decompose")
    parser.add_argument("--force", "-f", action="store_true", help="Force decomposition even if below thresholds")

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    tasks_dir = script_dir / "tasks"
    project_root = script_dir.parent.parent

    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = tasks_dir / args.task_file

    if not task_file.exists():
        print(f"Task file not found: {task_file}")
        return 1

    analyzer = TaskAnalyzer(project_root)
    analysis = analyzer.analyze(task_file)

    print(f"=== Task Analysis: {analysis.task_id} ===")
    print(f"Title: {analysis.title}")
    print(f"Files: {len(analysis.files_estimated)} estimated")
    print(f"LOC: ~{analysis.loc_estimated}")
    print(f"Items: {len(analysis.items)}")
    print(f"Domains: {', '.join(analysis.domains)}")

    exceeds, reasons = analysis.exceeds_thresholds()
    if exceeds:
        print(f"\n⚠️ EXCEEDS THRESHOLDS: {', '.join(reasons)}")

        if not args.analyze_only:
            decomposed, sub_ids = check_and_decompose(task_file, tasks_dir, project_root)
            if decomposed:
                print(f"\n✓ Decomposed into {len(sub_ids)} sub-tasks")
    else:
        print("\n✓ Within thresholds - no decomposition needed")

    return 0


if __name__ == "__main__":
    exit(main())
