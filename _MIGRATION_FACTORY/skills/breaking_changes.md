# Skill: Breaking Changes Detection & Documentation

## Purpose

Systematically detect, document, and migrate breaking changes when upgrading frameworks.

## Checklist (Mandatory)

- [ ] All breaking changes listed in MIGRATION_PLAN.md
- [ ] Each breaking change has REF to framework changelog
- [ ] Impact analysis per breaking change (files affected, risk score)
- [ ] Migration path documented (before → after code examples)
- [ ] Rollback strategy per breaking change
- [ ] Codemod available OR manual steps documented
- [ ] Test coverage for breaking change (golden files)

## Common Angular Breaking Changes (16→17)

### 1. ModuleWithProviders<T> Type Parameter

**Before (Angular 16):**
```typescript
@NgModule({...})
export class FeatureModule {
  static forRoot(): ModuleWithProviders {
    return {ngModule: FeatureModule, providers: [...]};
  }
}
```

**After (Angular 17):**
```typescript
@NgModule({...})
export class FeatureModule {
  static forRoot(): ModuleWithProviders<FeatureModule> {
    return {ngModule: FeatureModule, providers: [...]};
  }
}
```

**Impact:** Medium (30% of modules use this pattern)
**Migration:** Codemod available (`codemods/angular/module_providers.ts`)
**Rollback:** Git revert

### 2. RouterModule.forRoot → provideRouter

**Before (Angular 16):**
```typescript
@NgModule({
  imports: [RouterModule.forRoot(routes)],
  ...
})
export class AppModule {}
```

**After (Angular 17):**
```typescript
// app.config.ts
export const appConfig: ApplicationConfig = {
  providers: [provideRouter(routes)]
};

// main.ts
bootstrapApplication(AppComponent, appConfig);
```

**Impact:** HIGH (architectural change, affects bootstrap)
**Migration:** Manual (no codemod, requires refactoring)
**Rollback:** Feature flag (`angular17_routing`)

### 3. Typed FormGroups

**Before (Angular 16):**
```typescript
this.form = this.fb.group({
  name: [''],
  email: ['']
});
// Type: FormGroup (any)
```

**After (Angular 17):**
```typescript
interface UserForm {
  name: FormControl<string>;
  email: FormControl<string>;
}

this.form = this.fb.group<UserForm>({
  name: [''],
  email: ['']
});
// Type: FormGroup<UserForm>
```

**Impact:** Medium (pervasive, affects all forms)
**Migration:** Semi-auto (codemod can detect, needs manual types)
**Rollback:** Git revert (no runtime change)

### 4. Control Flow Syntax

**Before (Angular 16):**
```html
<div *ngIf="user">{{ user.name }}</div>
<div *ngFor="let item of items">{{ item }}</div>
```

**After (Angular 17):**
```html
@if (user) {
  <div>{{ user.name }}</div>
}
@for (item of items; track item.id) {
  <div>{{ item }}</div>
}
```

**Impact:** Low (opt-in, no breaking change)
**Migration:** Auto (codemod available)
**Rollback:** Not needed (old syntax still works)

## Detection Workflow

1. **Load Framework Changelog**
   - Parse official CHANGELOG.md (GitHub)
   - Extract breaking changes section
   - Categorize by impact (low/medium/high)

2. **Scan Codebase**
   - Use AST parser (TypeScript Compiler API, jscodeshift)
   - Find usage patterns for each breaking change
   - Count occurrences per file

3. **Impact Analysis**
   - Risk score = impact × occurrences × complexity
   - Complexity: low (codemod) < medium (semi-auto) < high (manual)

4. **Document**
   - Generate MIGRATION_PLAN.md section
   - Include code examples (before/after)
   - List all affected files

5. **Prioritize**
   - Sort by risk score (high first)
   - Group by phase (deps → standalone → forms → ...)

## Anti-Patterns (Adversarial Rejects)

- ❌ Skipping breaking change (silent ignore)
- ❌ Documenting breaking change AFTER deploy
- ❌ No rollback strategy
- ❌ No backward compatibility testing
- ❌ No REF to official changelog (hallucination)
- ❌ Missing impact analysis (files affected)
- ❌ No code examples (before/after)
- ❌ No test coverage for breaking change

## Example Output (Migration Task)

```json
{
  "type": "migration",
  "domain": "angular",
  "description": "[ANG-17-002] Migrate RouterModule.forRoot to provideRouter in app.module.ts",
  "files": ["ai08-admin-ihm/src/app/app.module.ts"],
  "wsjf_score": 9,
  "context": {
    "breaking_change_ref": "ANG-17-002",
    "impact": "high",
    "codemod": null,
    "manual_steps": [
      "1. Create app.config.ts with provideRouter",
      "2. Update main.ts to use bootstrapApplication",
      "3. Remove AppModule",
      "4. Test routing still works"
    ],
    "rollback_strategy": "feature_flag: angular17_routing",
    "test_coverage": "E2E: test all routes, verify navigation"
  }
}
```

## Golden Files (Behavior Preservation)

For each breaking change, capture BEFORE/AFTER snapshots:

1. **API Responses** (if breaking change affects backend calls)
   ```bash
   curl -s https://api/endpoint > golden_files/api_responses/endpoint_before.json
   ```

2. **Screenshots** (if breaking change affects UI)
   ```bash
   playwright screenshot golden_files/screenshots/page_before.png
   ```

3. **Unit Test Outputs**
   ```bash
   npm test > golden_files/test_outputs/before.txt
   ```

4. **Comparison** (after transformation)
   ```bash
   diff golden_files/api_responses/endpoint_{before,after}.json
   # Must be identical (or explain differences)
   ```

## References

- Angular CHANGELOG: https://github.com/angular/angular/blob/main/CHANGELOG.md
- Migration Guide: https://angular.io/guide/update
- Breaking Changes Policy: https://angular.io/guide/releases#breaking-changes
