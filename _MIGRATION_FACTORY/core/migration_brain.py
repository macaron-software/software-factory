"""
Migration Brain - Orchestrator for code migrations

Différence vs SF Brain:
- SF Brain: Analyse code pour trouver bugs/features à développer
- Migration Brain: Analyse DELTA (before→after, breaking changes, risk)

Workflow:
1. Load MIGRATION_PLAN.md (before/after state)
2. Load breaking changes (framework CHANGELOG)
3. Scan codebase usage patterns (CoVe)
4. Calculate risk scores (HIGH/MEDIUM/LOW)
5. Generate tasks ordered by dependency + risk
6. Output: backlog_tasks.json
"""

import os
import json
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

from core.breaking_changes import BreakingChangesDB, BreakingChange, Impact
from core.analyzers.angular_analyzer import AngularAnalyzer, AnalysisResult


@dataclass
class MigrationTask:
    """
    Migration task (different from SF Task)

    SF Task: pending → tdd → code_written → build → deploy
    Migration Task: pending → pre_validate → transform → post_validate → compare → verified
    """
    id: str
    project_id: str
    phase: str  # deps|standalone|typed-forms|control-flow|signals|material
    framework: str  # angular|react|vue
    from_version: str
    to_version: str

    # Migration-specific
    breaking_changes: List[str]  # IDs like ["ANG-17-001", "ANG-17-002"]
    codemod_available: bool
    risk_score: int  # 1-10
    wsjf_score: float  # Priority (business value / cost)
    rollback_strategy: str  # git_tag|feature_flag|canary

    # Files to transform
    files: List[str]
    file_count: int

    # État migration
    status: str  # pending|pre_validating|transforming|comparing|verified|rollback|failed

    # Metadata
    description: str
    metadata: Optional[Dict] = None
    created_at: Optional[str] = None


@dataclass
class MigrationPlan:
    """
    Parsed from MIGRATION_PLAN.md

    Contains:
    - Before state (Angular 16)
    - After state (Angular 17)
    - Breaking changes list
    - Phases (deps, standalone, typed-forms, etc.)
    - Success criteria
    """
    project_id: str
    framework: str
    from_version: str
    to_version: str
    root_path: str

    phases: List[Dict]  # [{name: 'deps', auto: true, risk: 'LOW'}]
    breaking_changes: List[str]  # IDs
    success_criteria: Dict


class MigrationBrain:
    """
    Analyze migration delta and generate tasks

    Usage:
        brain = MigrationBrain('sharelook')
        tasks = await brain.analyze()
        # → 127 tasks (50 standalone, 45 typed-forms, etc.)

        brain.save_backlog(tasks)
        # → data/migration_backlog.json
    """

    def __init__(self, project_id: str, config_path: Optional[str] = None):
        self.project_id = project_id
        self.config_path = config_path or f"projects/{project_id}.yaml"
        self.config = self._load_config()

        self.db = BreakingChangesDB()

    def _load_config(self) -> Dict:
        """Load project config from YAML"""
        import yaml

        config_file = Path(__file__).parent.parent / self.config_path

        if not config_file.exists():
            raise FileNotFoundError(f"Config not found: {config_file}")

        with open(config_file) as f:
            return yaml.safe_load(f)

    async def analyze(self) -> List[MigrationTask]:
        """
        Full migration analysis

        Steps:
        1. Load breaking changes (framework CHANGELOG)
        2. Scan codebase (usage patterns via analyzer)
        3. Calculate risk scores
        4. Generate tasks per phase
        5. Order by dependency + WSJF

        Returns: Ordered list of migration tasks
        """
        print(f"[Migration Brain] Analyzing {self.project_id}...")

        migration_config = self.config['migration']
        framework = migration_config['framework']
        from_version = migration_config['from_version']
        to_version = migration_config['to_version']
        root_path = migration_config['root_path']

        # 1. Load breaking changes
        breaking_changes = self.db.get_changes(framework, from_version, to_version)
        print(f"[Migration Brain] Found {len(breaking_changes)} breaking changes")

        # 2. Scan codebase
        analyzer = AngularAnalyzer(root_path)
        analysis = analyzer.analyze()
        print(f"[Migration Brain] Scanned: {analysis.stats}")

        # 3. Generate tasks per phase
        all_tasks = []

        for phase_config in self.config.get('phases', []):
            phase_name = phase_config['name']
            print(f"[Migration Brain] Generating tasks for phase: {phase_name}")

            tasks = self._generate_phase_tasks(
                phase_config,
                analysis,
                breaking_changes,
                framework,
                from_version,
                to_version
            )

            all_tasks.extend(tasks)

        # 4. Calculate WSJF and order
        for task in all_tasks:
            task.wsjf_score = self._calculate_wsjf(task, analysis)

        # Sort by WSJF (higher = more important)
        all_tasks.sort(key=lambda t: t.wsjf_score, reverse=True)

        print(f"[Migration Brain] Generated {len(all_tasks)} tasks")

        return all_tasks

    def _generate_phase_tasks(
        self,
        phase_config: Dict,
        analysis: AnalysisResult,
        breaking_changes: List[BreakingChange],
        framework: str,
        from_version: str,
        to_version: str
    ) -> List[MigrationTask]:
        """Generate tasks for specific phase"""
        phase_name = phase_config['name']
        tasks = []

        if phase_name == 'deps':
            # Single task: update dependencies
            tasks.append(MigrationTask(
                id=f"{self.project_id}-deps-001",
                project_id=self.project_id,
                phase='deps',
                framework=framework,
                from_version=from_version,
                to_version=to_version,
                breaking_changes=['ANG-17-009'],  # OIDC update
                codemod_available=False,
                risk_score=2,  # LOW risk
                wsjf_score=0.0,  # Will be calculated
                rollback_strategy='git_tag',
                files=['package.json'],
                file_count=1,
                status='pending',
                description=f"Update Angular {from_version} → {to_version} dependencies",
                created_at=datetime.now().isoformat()
            ))

        elif phase_name == 'standalone':
            # One task per NgModule
            for i, module in enumerate(analysis.modules, 1):
                tasks.append(MigrationTask(
                    id=f"{self.project_id}-standalone-{i:03d}",
                    project_id=self.project_id,
                    phase='standalone',
                    framework=framework,
                    from_version=from_version,
                    to_version=to_version,
                    breaking_changes=['ANG-17-002', 'ANG-17-003'],
                    codemod_available=True,
                    risk_score=7,  # HIGH risk (architectural)
                    wsjf_score=0.0,
                    rollback_strategy='git_tag',
                    files=[module.file_path] + [
                        # Include component files from declarations
                        # (simplified - would need file resolution)
                    ],
                    file_count=len(module.declarations) + 1,
                    status='pending',
                    description=f"Migrate {module.name} to standalone",
                    metadata={'module_name': module.name},
                    created_at=datetime.now().isoformat()
                ))

        elif phase_name == 'typed-forms':
            # One task per untyped form
            untyped_forms = [f for f in analysis.forms if not f.typed]

            for i, form in enumerate(untyped_forms, 1):
                tasks.append(MigrationTask(
                    id=f"{self.project_id}-typed-forms-{i:03d}",
                    project_id=self.project_id,
                    phase='typed-forms',
                    framework=framework,
                    from_version=from_version,
                    to_version=to_version,
                    breaking_changes=['ANG-17-004'],
                    codemod_available=True,
                    risk_score=5,  # MEDIUM risk
                    wsjf_score=0.0,
                    rollback_strategy='git_tag',
                    files=[form.file_path],
                    file_count=1,
                    status='pending',
                    description=f"Add types to {form.variable_name} form",
                    metadata={'form_name': form.variable_name},
                    created_at=datetime.now().isoformat()
                ))

        elif phase_name == 'control-flow':
            # One task per component with *ngIf/*ngFor
            components_with_old_syntax = [
                c for c in analysis.components
                if 'ANG-17-005' in analysis.breaking_changes_detected
                and c.file_path in analysis.breaking_changes_detected.get('ANG-17-005', [])
            ]

            for i, component in enumerate(components_with_old_syntax, 1):
                tasks.append(MigrationTask(
                    id=f"{self.project_id}-control-flow-{i:03d}",
                    project_id=self.project_id,
                    phase='control-flow',
                    framework=framework,
                    from_version=from_version,
                    to_version=to_version,
                    breaking_changes=['ANG-17-005'],
                    codemod_available=True,
                    risk_score=3,  # LOW risk (opt-in)
                    wsjf_score=0.0,
                    rollback_strategy='git_tag',
                    files=[component.file_path],
                    file_count=1,
                    status='pending',
                    description=f"Migrate {component.name} to @if/@for syntax",
                    metadata={'component_name': component.name},
                    created_at=datetime.now().isoformat()
                ))

        return tasks

    def _calculate_wsjf(self, task: MigrationTask, analysis: AnalysisResult) -> float:
        """
        Calculate WSJF (Weighted Shortest Job First)

        WSJF = (Business Value + Time Criticality + Risk Reduction) / Job Size

        Business Value: How important is this change?
        Time Criticality: Must be done now?
        Risk Reduction: Does it unblock other work?
        Job Size: Effort (file count, complexity)
        """

        # Business Value (1-10)
        # deps = HIGH (blocks everything), standalone = MEDIUM, control-flow = LOW
        business_value = {
            'deps': 10,
            'standalone': 7,
            'typed-forms': 6,
            'control-flow': 3,
            'signals': 2,
            'material': 5
        }.get(task.phase, 5)

        # Time Criticality (1-10)
        # deps = CRITICAL (must be first), others = LOW
        time_criticality = 10 if task.phase == 'deps' else 3

        # Risk Reduction (1-10)
        # Inverse of risk_score (high risk = high value to reduce it)
        risk_reduction = 11 - task.risk_score

        # Job Size (effort)
        # More files = more effort = lower priority
        job_size = task.file_count

        wsjf = (business_value + time_criticality + risk_reduction) / max(job_size, 1)

        return round(wsjf, 2)

    def save_backlog(self, tasks: List[MigrationTask], output_path: Optional[str] = None):
        """
        Save tasks to backlog JSON

        Format: {tasks: [...]}
        """
        output_path = output_path or f"data/migration_backlog_{self.project_id}.json"

        output_file = Path(__file__).parent.parent / output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)

        backlog = {
            'project_id': self.project_id,
            'generated_at': datetime.now().isoformat(),
            'total_tasks': len(tasks),
            'tasks': [asdict(task) for task in tasks]
        }

        with open(output_file, 'w') as f:
            json.dump(backlog, f, indent=2)

        print(f"[Migration Brain] Saved {len(tasks)} tasks to {output_file}")

    def load_backlog(self, input_path: Optional[str] = None) -> List[MigrationTask]:
        """Load tasks from backlog JSON"""
        input_path = input_path or f"data/migration_backlog_{self.project_id}.json"

        input_file = Path(__file__).parent.parent / input_path

        if not input_file.exists():
            return []

        with open(input_file) as f:
            backlog = json.load(f)

        tasks = [
            MigrationTask(**task_data)
            for task_data in backlog['tasks']
        ]

        return tasks


# ===== CLI Helper =====

async def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migration_brain.py <project_id>")
        print("Example: python migration_brain.py sharelook")
        sys.exit(1)

    project_id = sys.argv[1]

    brain = MigrationBrain(project_id)
    tasks = await brain.analyze()

    # Print summary
    print(f"\n{'='*80}")
    print(f"Migration Tasks Generated: {len(tasks)}")
    print(f"{'='*80}\n")

    # Group by phase
    by_phase = {}
    for task in tasks:
        by_phase.setdefault(task.phase, []).append(task)

    for phase, phase_tasks in by_phase.items():
        print(f"{phase}: {len(phase_tasks)} tasks")

    # Save backlog
    brain.save_backlog(tasks)

    print(f"\n✅ Backlog saved to data/migration_backlog_{project_id}.json")


if __name__ == "__main__":
    asyncio.run(main())
