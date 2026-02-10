"""
Angular Codebase Analyzer

Scans Angular codebase to detect:
- NgModules (for standalone migration)
- Components/Directives/Pipes
- FormGroups (for typed forms)
- Template syntax (*ngIf, *ngFor for control flow)
- RouterModule usage
- Material components
- Breaking changes usage patterns

Uses:
- Grep for fast pattern matching
- AST parsing for accurate detection (optional)
"""

import os
import re
import subprocess
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NgModule:
    file_path: str
    name: str
    declarations: List[str]
    imports: List[str]
    exports: List[str]
    providers: List[str]


@dataclass
class Component:
    file_path: str
    name: str
    selector: str
    standalone: bool
    inputs: List[str]
    outputs: List[str]


@dataclass
class FormGroup:
    file_path: str
    variable_name: str
    typed: bool  # Has generic <T>
    fields: List[str]


@dataclass
class AnalysisResult:
    """Complete codebase analysis result"""
    modules: List[NgModule]
    components: List[Component]
    forms: List[FormGroup]
    routes_count: int
    breaking_changes_detected: Dict[str, List[str]]  # change_id → files
    stats: Dict[str, int]


class AngularAnalyzer:
    """
    Analyze Angular codebase for migration planning

    Usage:
        analyzer = AngularAnalyzer('/path/to/angular/project')
        result = analyzer.analyze()

        print(f"Modules: {len(result.modules)}")
        print(f"Components: {len(result.components)}")
        print(f"Forms: {len(result.forms)}")
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.src_path = self.project_root / "src"

    def analyze(self) -> AnalysisResult:
        """
        Full codebase analysis

        Scans:
        1. NgModules (declarations, imports, exports)
        2. Components (standalone?, @Input, @Output)
        3. FormGroups (typed?)
        4. Routes (count)
        5. Breaking changes patterns
        """
        print(f"[Analyzer] Scanning {self.project_root}...")

        modules = self._scan_modules()
        components = self._scan_components()
        forms = self._scan_forms()
        routes_count = self._count_routes()
        breaking_changes = self._detect_breaking_changes()

        stats = {
            'modules': len(modules),
            'components': len(components),
            'standalone_components': len([c for c in components if c.standalone]),
            'forms': len(forms),
            'typed_forms': len([f for f in forms if f.typed]),
            'routes': routes_count,
        }

        print(f"[Analyzer] Found: {stats}")

        return AnalysisResult(
            modules=modules,
            components=components,
            forms=forms,
            routes_count=routes_count,
            breaking_changes_detected=breaking_changes,
            stats=stats
        )

    def _scan_modules(self) -> List[NgModule]:
        """Find all @NgModule declarations"""
        modules = []

        # Find files with @NgModule
        files = self._grep_files(r"@NgModule\s*\(", "*.ts")

        for file_path in files:
            try:
                content = Path(file_path).read_text()

                # Extract module name (export class XxxModule)
                name_match = re.search(r"export\s+class\s+(\w+Module)", content)
                if not name_match:
                    continue

                name = name_match.group(1)

                # Extract @NgModule metadata
                module_match = re.search(
                    r"@NgModule\s*\(\s*\{([^}]+)\}\s*\)",
                    content,
                    re.DOTALL
                )

                if not module_match:
                    continue

                metadata = module_match.group(1)

                # Parse declarations, imports, exports, providers
                declarations = self._extract_array(metadata, 'declarations')
                imports = self._extract_array(metadata, 'imports')
                exports = self._extract_array(metadata, 'exports')
                providers = self._extract_array(metadata, 'providers')

                modules.append(NgModule(
                    file_path=file_path,
                    name=name,
                    declarations=declarations,
                    imports=imports,
                    exports=exports,
                    providers=providers
                ))

            except Exception as e:
                print(f"[Analyzer] Error parsing {file_path}: {e}")

        return modules

    def _scan_components(self) -> List[Component]:
        """Find all @Component declarations"""
        components = []

        # Find files with @Component
        files = self._grep_files(r"@Component\s*\(", "*.ts")

        for file_path in files:
            try:
                content = Path(file_path).read_text()

                # Extract component name
                name_match = re.search(r"export\s+class\s+(\w+Component)", content)
                if not name_match:
                    continue

                name = name_match.group(1)

                # Extract @Component metadata
                component_match = re.search(
                    r"@Component\s*\(\s*\{([^}]+)\}\s*\)",
                    content,
                    re.DOTALL
                )

                if not component_match:
                    continue

                metadata = component_match.group(1)

                # Parse selector
                selector_match = re.search(r"selector:\s*['\"]([^'\"]+)['\"]", metadata)
                selector = selector_match.group(1) if selector_match else ""

                # Check if standalone
                standalone = "standalone: true" in metadata or "standalone:true" in metadata

                # Extract @Input/@Output
                inputs = re.findall(r"@Input\(\)\s+(\w+)", content)
                outputs = re.findall(r"@Output\(\)\s+(\w+)", content)

                components.append(Component(
                    file_path=file_path,
                    name=name,
                    selector=selector,
                    standalone=standalone,
                    inputs=inputs,
                    outputs=outputs
                ))

            except Exception as e:
                print(f"[Analyzer] Error parsing {file_path}: {e}")

        return components

    def _scan_forms(self) -> List[FormGroup]:
        """Find all FormGroup declarations"""
        forms = []

        # Find files with FormGroup or FormBuilder
        files = self._grep_files(r"FormGroup|FormBuilder", "*.ts")

        for file_path in files:
            try:
                content = Path(file_path).read_text()

                # Find FormBuilder.group(...) or new FormGroup(...)
                # Pattern 1: fb.group<T>({ ... })
                typed_forms = re.findall(
                    r"(\w+)\s*=\s*this\.fb\.group<(\w+)>\s*\(",
                    content
                )

                for var_name, type_name in typed_forms:
                    forms.append(FormGroup(
                        file_path=file_path,
                        variable_name=var_name,
                        typed=True,
                        fields=[]  # TODO: Extract fields
                    ))

                # Pattern 2: fb.group({ ... }) (untyped)
                untyped_forms = re.findall(
                    r"(\w+)\s*=\s*this\.fb\.group\s*\(",
                    content
                )

                # Filter out already found typed forms
                typed_vars = {var for var, _ in typed_forms}

                for var_name in untyped_forms:
                    if var_name not in typed_vars:
                        forms.append(FormGroup(
                            file_path=file_path,
                            variable_name=var_name,
                            typed=False,
                            fields=[]
                        ))

            except Exception as e:
                print(f"[Analyzer] Error parsing {file_path}: {e}")

        return forms

    def _count_routes(self) -> int:
        """Count total routes in routing modules"""
        # Find routing files
        files = self._grep_files(r"Routes|RouterModule", "*.ts")

        total_routes = 0

        for file_path in files:
            try:
                content = Path(file_path).read_text()

                # Count { path: '...' } occurrences
                routes = len(re.findall(r"{\s*path:\s*['\"]", content))
                total_routes += routes

            except Exception as e:
                print(f"[Analyzer] Error counting routes in {file_path}: {e}")

        return total_routes

    def _detect_breaking_changes(self) -> Dict[str, List[str]]:
        """
        Detect usage of breaking changes patterns

        Returns: {change_id: [file_paths]}
        """
        from core.breaking_changes import BreakingChangesDB

        db = BreakingChangesDB()
        changes = db.get_changes('angular', '16.2.12', '17.3.0')

        detections = {}

        for change in changes:
            if not change.detection_pattern:
                continue

            # Grep for pattern
            files = self._grep_files(change.detection_pattern, "*.ts")

            if files:
                detections[change.id] = files

        return detections

    def _grep_files(self, pattern: str, file_pattern: str = "*") -> List[str]:
        """
        Grep for pattern in project files

        Returns: List of absolute file paths
        """
        try:
            # Use ripgrep if available (faster), fallback to grep
            cmd = [
                'rg',
                '--files-with-matches',
                '--type', 'typescript',
                '--glob', file_pattern,
                pattern,
                str(self.src_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # Don't raise on non-zero (no matches)
            )

            if result.returncode == 0:
                files = result.stdout.strip().split('\n')
                return [f for f in files if f]

            return []

        except FileNotFoundError:
            # Fallback to grep if rg not available
            try:
                cmd = [
                    'grep',
                    '-rl',
                    '--include', file_pattern,
                    pattern,
                    str(self.src_path)
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode == 0:
                    files = result.stdout.strip().split('\n')
                    return [f for f in files if f]

                return []

            except Exception as e:
                print(f"[Analyzer] Grep failed: {e}")
                return []

    def _extract_array(self, metadata: str, key: str) -> List[str]:
        """
        Extract array values from NgModule metadata

        Example:
            declarations: [ComponentA, ComponentB]
            → ['ComponentA', 'ComponentB']
        """
        pattern = rf"{key}:\s*\[(.*?)\]"
        match = re.search(pattern, metadata, re.DOTALL)

        if not match:
            return []

        array_content = match.group(1)

        # Split by comma, clean whitespace/newlines
        items = [
            item.strip()
            for item in array_content.split(',')
            if item.strip()
        ]

        return items


# ===== CLI Helper =====

def print_analysis_report(result: AnalysisResult):
    """Pretty print analysis report"""
    print(f"\n{'='*80}")
    print("Angular Codebase Analysis Report")
    print(f"{'='*80}\n")

    print(f"📦 Modules: {result.stats['modules']}")
    print(f"🧩 Components: {result.stats['components']}")
    print(f"   - Standalone: {result.stats['standalone_components']}")
    print(f"   - NgModule-based: {result.stats['components'] - result.stats['standalone_components']}")

    print(f"\n📝 Forms: {result.stats['forms']}")
    print(f"   - Typed: {result.stats['typed_forms']}")
    print(f"   - Untyped: {result.stats['forms'] - result.stats['typed_forms']}")

    print(f"\n🚦 Routes: {result.stats['routes']}")

    print(f"\n⚠️  Breaking Changes Detected:")
    if result.breaking_changes_detected:
        for change_id, files in result.breaking_changes_detected.items():
            print(f"   [{change_id}] {len(files)} files affected")
    else:
        print("   None detected")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python angular_analyzer.py <project_root>")
        sys.exit(1)

    project_root = sys.argv[1]
    analyzer = AngularAnalyzer(project_root)
    result = analyzer.analyze()

    print_analysis_report(result)
