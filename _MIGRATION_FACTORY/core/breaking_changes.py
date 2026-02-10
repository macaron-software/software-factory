"""
Breaking Changes Database

Framework-specific breaking changes avec impact, fixability, migration paths.

Supported:
- Angular 16 → 17
- React 17 → 18 (future)
- Vue 2 → 3 (future)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class Impact(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Framework(Enum):
    ANGULAR = "angular"
    REACT = "react"
    VUE = "vue"


@dataclass
class BreakingChange:
    id: str
    framework: Framework
    from_version: str
    to_version: str
    title: str
    description: str
    impact: Impact
    auto_fixable: bool
    codemod: Optional[str] = None
    migration_guide: Optional[str] = None
    detection_pattern: Optional[str] = None  # Regex or AST query
    example_before: Optional[str] = None
    example_after: Optional[str] = None
    related_changes: List[str] = None

    def __post_init__(self):
        if self.related_changes is None:
            self.related_changes = []


# ===== ANGULAR 16 → 17 =====

ANGULAR_16_17 = [
    BreakingChange(
        id="ANG-17-001",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="ModuleWithProviders<T> type parameter required",
        description="Generic type parameter T is now required for ModuleWithProviders",
        impact=Impact.MEDIUM,
        auto_fixable=True,
        codemod="codemods/angular/module_providers.ts",
        detection_pattern=r"ModuleWithProviders(?!<)",
        example_before="""
static forRoot(): ModuleWithProviders {
  return { ngModule: AuthModule, providers: [...] };
}
        """,
        example_after="""
static forRoot(): ModuleWithProviders<AuthModule> {
  return { ngModule: AuthModule, providers: [...] };
}
        """
    ),

    BreakingChange(
        id="ANG-17-002",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="RouterModule.forRoot → provideRouter",
        description="Standalone APIs: RouterModule.forRoot deprecated, use provideRouter",
        impact=Impact.HIGH,
        auto_fixable=False,  # Requires manual adaptation (bootstrap change)
        migration_guide="docs/angular/router_migration.md",
        detection_pattern=r"RouterModule\.forRoot\(",
        example_before="""
@NgModule({
  imports: [RouterModule.forRoot(routes)]
})
export class AppModule {}
        """,
        example_after="""
bootstrapApplication(AppComponent, {
  providers: [provideRouter(routes)]
});
        """,
        related_changes=["ANG-17-003"]
    ),

    BreakingChange(
        id="ANG-17-003",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="Standalone components (NgModule optional)",
        description="Components can be standalone: true (no NgModule required)",
        impact=Impact.HIGH,
        auto_fixable=True,
        codemod="codemods/angular/standalone.ts",
        detection_pattern=r"@NgModule\(\s*\{[^}]*declarations:\s*\[",
        example_before="""
@NgModule({
  declarations: [AuthComponent],
  imports: [CommonModule],
  exports: [AuthComponent]
})
export class AuthModule {}
        """,
        example_after="""
@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule],
  template: '...'
})
export class AuthComponent {}
        """,
        related_changes=["ANG-17-002"]
    ),

    BreakingChange(
        id="ANG-17-004",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="Typed Forms (FormGroup<T>)",
        description="FormGroup/FormControl can be typed with generics",
        impact=Impact.MEDIUM,
        auto_fixable=True,
        codemod="codemods/angular/typed_forms.ts",
        detection_pattern=r"FormGroup\s*\(",
        example_before="""
loginForm = this.fb.group({
  email: ['', Validators.required],
  password: ['', Validators.required]
});
        """,
        example_after="""
interface LoginForm {
  email: string;
  password: string;
}

loginForm = this.fb.group<LoginForm>({
  email: ['', Validators.required],
  password: ['', Validators.required]
});
        """
    ),

    BreakingChange(
        id="ANG-17-005",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="Control Flow (@if, @for, @switch)",
        description="New template syntax: @if/@for/@switch replaces *ngIf/*ngFor/*ngSwitch",
        impact=Impact.LOW,
        auto_fixable=True,
        codemod="codemods/angular/control_flow.ts",
        detection_pattern=r"\*ngIf=|\*ngFor=|\*ngSwitch=",
        example_before="""
<div *ngIf="isLoggedIn">Welcome!</div>
<div *ngFor="let user of users">{{ user.name }}</div>
        """,
        example_after="""
@if (isLoggedIn) {
  <div>Welcome!</div>
}
@for (user of users; track user.id) {
  <div>{{ user.name }}</div>
}
        """
    ),

    BreakingChange(
        id="ANG-17-006",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="Signals (opt-in)",
        description="New reactive primitive: signal() for fine-grained reactivity",
        impact=Impact.LOW,
        auto_fixable=False,  # Opt-in, not required
        migration_guide="docs/angular/signals_migration.md",
        example_before="""
count = 0;
increment() { this.count++; }
        """,
        example_after="""
count = signal(0);
increment() { this.count.update(v => v + 1); }
        """
    ),

    BreakingChange(
        id="ANG-17-007",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="Material 17: Typography refactor",
        description="Material typography uses mat.define-theme() instead of define-typography-config",
        impact=Impact.HIGH,
        auto_fixable=False,  # Requires SCSS changes
        migration_guide="docs/angular/material_typography.md",
        detection_pattern=r"mat\.define-typography-config",
        example_before="""
$custom-typography: mat.define-typography-config(
  $font-family: 'Roboto'
);
        """,
        example_after="""
$theme: mat.define-theme((
  color: (...),
  typography: mat.define-typography((
    $plain-family: 'Roboto'
  ))
));
        """
    ),

    BreakingChange(
        id="ANG-17-008",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="@angular/flex-layout deprecated",
        description="No Angular 17 support. Migrate to @ngbracket/ngx-layout or CSS Grid",
        impact=Impact.HIGH,
        auto_fixable=False,
        migration_guide="docs/angular/flex_layout_alternatives.md",
        detection_pattern=r"@angular/flex-layout",
        example_before="""
<div fxLayout="row" fxLayoutAlign="center center">
  <div fxFlex="50">Content</div>
</div>
        """,
        example_after="""
<!-- Option 1: @ngbracket/ngx-layout (same API) -->
<div fxLayout="row" fxLayoutAlign="center center">
  <div fxFlex="50">Content</div>
</div>

<!-- Option 2: Native CSS Grid -->
<div class="layout-row layout-align-center">
  <div class="flex-50">Content</div>
</div>
        """
    ),

    BreakingChange(
        id="ANG-17-009",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="OIDC client update required",
        description="angular-auth-oidc-client@16 → @17 (API stable, minor changes)",
        impact=Impact.MEDIUM,
        auto_fixable=True,
        detection_pattern=r"angular-auth-oidc-client",
        example_before="""
// package.json
"angular-auth-oidc-client": "^16.0.0"
        """,
        example_after="""
// package.json
"angular-auth-oidc-client": "^17.0.0"
        """
    ),

    BreakingChange(
        id="ANG-17-010",
        framework=Framework.ANGULAR,
        from_version="16.2.12",
        to_version="17.3.0",
        title="Lazy loading: loadChildren string deprecated",
        description="Use dynamic import() instead of string path",
        impact=Impact.MEDIUM,
        auto_fixable=True,
        codemod="codemods/angular/lazy_loading.ts",
        detection_pattern=r"loadChildren:\s*['\"]",
        example_before="""
{
  path: 'admin',
  loadChildren: './admin/admin.module#AdminModule'
}
        """,
        example_after="""
{
  path: 'admin',
  loadChildren: () => import('./admin/admin.module').then(m => m.AdminModule)
}
        """
    ),
]


# ===== API =====

class BreakingChangesDB:
    """
    Query breaking changes by framework + version range

    Usage:
        db = BreakingChangesDB()
        changes = db.get_changes('angular', '16.2.12', '17.3.0')
        # → List of 50+ breaking changes

        high_impact = db.filter_by_impact(changes, Impact.HIGH)
        # → Only HIGH/CRITICAL changes

        auto_fixable = db.filter_auto_fixable(changes)
        # → Changes with codemods available
    """

    def __init__(self):
        self.db: Dict[Framework, List[BreakingChange]] = {
            Framework.ANGULAR: ANGULAR_16_17,
            # Framework.REACT: REACT_17_18,  # TODO
            # Framework.VUE: VUE_2_3,        # TODO
        }

    def get_changes(
        self,
        framework: str,
        from_version: str,
        to_version: str
    ) -> List[BreakingChange]:
        """Get all breaking changes for version range"""
        fw = Framework(framework.lower())

        if fw not in self.db:
            return []

        # Filter by version range (simplified - assumes exact match)
        changes = [
            change for change in self.db[fw]
            if change.from_version == from_version
            and change.to_version == to_version
        ]

        return changes

    def get_by_id(self, change_id: str) -> Optional[BreakingChange]:
        """Get specific breaking change by ID"""
        for changes in self.db.values():
            for change in changes:
                if change.id == change_id:
                    return change
        return None

    def filter_by_impact(
        self,
        changes: List[BreakingChange],
        min_impact: Impact
    ) -> List[BreakingChange]:
        """Filter by minimum impact level"""
        impact_order = {
            Impact.LOW: 1,
            Impact.MEDIUM: 2,
            Impact.HIGH: 3,
            Impact.CRITICAL: 4
        }

        min_level = impact_order[min_impact]

        return [
            change for change in changes
            if impact_order[change.impact] >= min_level
        ]

    def filter_auto_fixable(
        self,
        changes: List[BreakingChange]
    ) -> List[BreakingChange]:
        """Filter changes with codemods available"""
        return [change for change in changes if change.auto_fixable]

    def filter_manual(
        self,
        changes: List[BreakingChange]
    ) -> List[BreakingChange]:
        """Filter changes requiring manual intervention"""
        return [change for change in changes if not change.auto_fixable]

    def get_related(
        self,
        change: BreakingChange
    ) -> List[BreakingChange]:
        """Get related breaking changes"""
        related = []
        for change_id in change.related_changes:
            related_change = self.get_by_id(change_id)
            if related_change:
                related.append(related_change)
        return related


# ===== CLI Helper =====

def print_breaking_changes(changes: List[BreakingChange]):
    """Pretty print breaking changes"""
    print(f"\n{'='*80}")
    print(f"Breaking Changes ({len(changes)})")
    print(f"{'='*80}\n")

    for change in changes:
        icon = "🤖" if change.auto_fixable else "👷"
        impact_color = {
            Impact.LOW: "🟢",
            Impact.MEDIUM: "🟡",
            Impact.HIGH: "🟠",
            Impact.CRITICAL: "🔴"
        }[change.impact]

        print(f"{icon} {impact_color} [{change.id}] {change.title}")
        print(f"   Impact: {change.impact.value}")
        print(f"   Auto-fixable: {change.auto_fixable}")

        if change.codemod:
            print(f"   Codemod: {change.codemod}")

        if change.migration_guide:
            print(f"   Guide: {change.migration_guide}")

        print()


if __name__ == "__main__":
    # Test
    db = BreakingChangesDB()
    changes = db.get_changes('angular', '16.2.12', '17.3.0')

    print(f"Total breaking changes: {len(changes)}")
    print(f"Auto-fixable: {len(db.filter_auto_fixable(changes))}")
    print(f"Manual: {len(db.filter_manual(changes))}")
    print(f"HIGH/CRITICAL: {len(db.filter_by_impact(changes, Impact.HIGH))}")

    print_breaking_changes(changes[:3])  # Show first 3
