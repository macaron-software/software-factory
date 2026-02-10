# Skill: Backward Compatibility Testing

## Purpose

Ensure new code version maintains compatibility with:
- Old API clients
- Legacy integrations
- Gradual rollout scenarios (feature flags)

## Checklist (Mandatory)

- [ ] Old API clients can still call new API (no 4xx/5xx errors)
- [ ] Feature flags work (old + new code coexist)
- [ ] Hybrid state valid (NgModules + Standalone components)
- [ ] Database migrations backward compatible (if applicable)
- [ ] External integrations unchanged
- [ ] Webhooks/callbacks still work
- [ ] Authentication/authorization unchanged

## Scenarios to Test

### 1. API Compatibility (if backend changes)

**Test:** Old client → New server

```bash
# Before migration: capture API contract
curl -s https://api/v1/users > golden_files/api_contract_before.json

# After migration: test old client
# (using old Angular app code against new backend)
curl -s https://api/v1/users > golden_files/api_contract_after.json

# Compare
diff golden_files/api_contract_{before,after}.json
# Expected: No differences (or only additions, no removals)
```

**Acceptable changes:**
- ✅ New fields added (optional)
- ✅ New endpoints added
- ❌ Fields removed
- ❌ Field types changed
- ❌ Required fields added

### 2. Feature Flag Coexistence

**Scenario:** Angular 16 and 17 code running side-by-side.

**Example (routing):**
```typescript
// Feature flag: angular17_routing
if (featureFlags.angular17_routing) {
  // Use provideRouter (Angular 17)
  bootstrapApplication(AppComponent, appConfig);
} else {
  // Use RouterModule.forRoot (Angular 16)
  platformBrowserDynamic().bootstrapModule(AppModule);
}
```

**Tests:**
- Flag ON: All routes work (provideRouter)
- Flag OFF: All routes work (RouterModule)
- Toggle flag: No crashes, graceful fallback

### 3. Hybrid Architecture (NgModules + Standalone)

**Scenario:** Some components migrated to standalone, others still in modules.

**Valid states:**
```typescript
// Module-based component (Angular 16)
@Component({selector: 'old-cmp', ...})
export class OldComponent {}

@NgModule({
  declarations: [OldComponent],
  imports: [NewStandaloneComponent], // Import standalone in module ✅
  ...
})
export class OldModule {}

// Standalone component (Angular 17)
@Component({
  selector: 'new-cmp',
  standalone: true,
  imports: [CommonModule, OldModule], // Import module in standalone ✅
  ...
})
export class NewStandaloneComponent {}
```

**Tests:**
- Old component can use new standalone component
- New standalone component can use old module
- Both render correctly

### 4. Database Migrations (if applicable)

**Backward compatible:**
```sql
-- ✅ Add new column (nullable)
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255);

-- ✅ Add new table
CREATE TABLE user_preferences (...);

-- ❌ Drop column (breaks old code)
ALTER TABLE users DROP COLUMN email;

-- ❌ Rename column (breaks old code)
ALTER TABLE users RENAME COLUMN name TO full_name;
```

**Strategy:** Add-only migrations during rollout, deprecate-then-remove later.

### 5. External Integrations

**Test:** Third-party systems still work.

```bash
# Webhook callback
curl -X POST https://external-service/webhook \
  -d '{"event": "user.created", "data": {...}}'
# Expected: 200 OK (still accepted by external service)

# OAuth flow
# Expected: Token exchange still works
```

## Gradual Rollout Strategy

### Phase 1: Canary (1% traffic)
- New code deployed to 1% of users
- Old code still serves 99%
- Monitor: error rate, latency, complaints
- **Backward compat critical** (both versions live)

### Phase 2: Ramp (10%, 50%)
- Gradually increase new code %
- Old + new coexist for days/weeks
- Feature flags allow per-user rollout

### Phase 3: Full rollout (100%)
- All users on new code
- Old code removed
- **Backward compat less critical** (single version)

## Anti-Patterns (Adversarial Rejects)

- ❌ No feature flag (big-bang deploy)
- ❌ Removing API fields during rollout
- ❌ Changing authentication mid-migration
- ❌ No hybrid state testing
- ❌ No old-client → new-server test
- ❌ Breaking database schema during rollout
- ❌ No rollback plan

## Example Test (Playwright)

```typescript
// Test: Old API contract still works after migration
test('Backward compat: API v1 users endpoint', async ({ request }) => {
  const response = await request.get('/api/v1/users');
  expect(response.status()).toBe(200);

  const users = await response.json();
  expect(users).toHaveProperty('data'); // Old format
  expect(users.data[0]).toHaveProperty('id');
  expect(users.data[0]).toHaveProperty('name');
  expect(users.data[0]).toHaveProperty('email');
  // New fields optional, not required
});

// Test: Feature flag toggle (Angular 16 ↔ 17)
test('Feature flag: angular17_routing can be toggled', async ({ page }) => {
  // Flag OFF: use old routing
  await page.goto('/?feature_angular17_routing=false');
  await expect(page).toHaveURL('/dashboard'); // Old router
  await expect(page.locator('h1')).toContainText('Dashboard');

  // Flag ON: use new routing
  await page.goto('/?feature_angular17_routing=true');
  await expect(page).toHaveURL('/dashboard'); // New router
  await expect(page.locator('h1')).toContainText('Dashboard'); // Same result
});

// Test: Hybrid (module + standalone)
test('Hybrid: Standalone component in module-based app', async ({ page }) => {
  await page.goto('/old-page'); // Module-based page
  await expect(page.locator('new-standalone-cmp')).toBeVisible(); // Standalone component works
});
```

## Rollback Criteria

If backward compatibility fails:
1. **Canary phase (1%):** Auto-rollback immediately
2. **Ramp phase (10-50%):** Manual rollback, investigate
3. **Full rollout (100%):** Emergency hotfix

**Metrics to watch:**
- Error rate (5xx, 4xx)
- API call failures
- User complaints (support tickets)
- Performance degradation

## References

- Feature Flags: https://martinfowler.com/articles/feature-toggles.html
- Canary Deployments: https://martinfowler.com/bliki/CanaryRelease.html
- Database Migrations: https://www.braintreepayments.com/blog/safe-database-migration-patterns/
