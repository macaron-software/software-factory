# Skill: Golden Files - Snapshot Comparison

## Purpose

Capture application behavior BEFORE transformation, compare AFTER to ensure:
**Old behavior === New behavior**

Used by Comparative Adversarial to verify behavioral equivalence.

## What to Capture

### 1. API Responses (JSON)

**Before migration:**
```bash
# Capture all API endpoints
curl -s https://api/v1/users > golden_files/api/users_before.json
curl -s https://api/v1/posts > golden_files/api/posts_before.json
curl -s https://api/v1/settings > golden_files/api/settings_before.json
```

**After migration:**
```bash
curl -s https://api/v1/users > golden_files/api/users_after.json
# ... repeat for all endpoints
```

**Comparison:**
```bash
diff -u golden_files/api/users_{before,after}.json
# Expected: No differences (or explain why different)
```

### 2. Screenshots (Visual Regression)

**Before migration:**
```typescript
// Playwright
await page.goto('/dashboard');
await page.screenshot({ path: 'golden_files/screenshots/dashboard_before.png' });
```

**After migration:**
```typescript
await page.goto('/dashboard');
await page.screenshot({ path: 'golden_files/screenshots/dashboard_after.png' });
```

**Comparison (pixel diff):**
```bash
# Using pixelmatch or similar
pixelmatch \
  golden_files/screenshots/dashboard_before.png \
  golden_files/screenshots/dashboard_after.png \
  golden_files/screenshots/dashboard_diff.png \
  --threshold 0.01  # 1% pixel difference allowed
```

**Threshold:**
- 0% diff: Perfect match
- <1% diff: Acceptable (anti-aliasing, rendering differences)
- >1% diff: REJECT (visual regression)

### 3. Console Logs (Errors/Warnings)

**Before migration:**
```typescript
const consoleMessages = [];
page.on('console', msg => consoleMessages.push(msg.text()));

await page.goto('/app');
// ... interact with app

fs.writeFileSync('golden_files/console/before.json', JSON.stringify(consoleMessages));
```

**After migration:**
```typescript
// Same capture
```

**Comparison:**
```bash
diff golden_files/console/{before,after}.json
# Expected: Error count unchanged (or fewer errors)
```

**Acceptable changes:**
- ✅ Fewer errors (improvement)
- ✅ Different wording (same error, better message)
- ❌ New errors (regression)
- ❌ More errors (regression)

### 4. Network Requests

**Before migration:**
```typescript
const requests = [];
page.on('request', req => requests.push({
  url: req.url(),
  method: req.method(),
  headers: req.headers()
}));

await page.goto('/app');
fs.writeFileSync('golden_files/network/before.json', JSON.stringify(requests));
```

**After migration:**
```typescript
// Same capture
```

**Comparison:**
```bash
diff golden_files/network/{before,after}.json
# Expected: Same requests (order may differ)
```

### 5. Unit Test Outputs

**Before migration:**
```bash
npm test > golden_files/test_outputs/before.txt 2>&1
# Capture: test count, pass/fail, coverage
```

**After migration:**
```bash
npm test > golden_files/test_outputs/after.txt 2>&1
```

**Comparison:**
```bash
# Extract pass/fail counts
grep "tests" golden_files/test_outputs/before.txt
# 150 tests, 148 passed, 2 failed

grep "tests" golden_files/test_outputs/after.txt
# 150 tests, 150 passed, 0 failed  # ✅ Same or better
```

**Expected:** Same test count, same or more passing tests.

### 6. Performance Metrics

**Before migration:**
```typescript
const metrics = await page.evaluate(() => JSON.stringify(performance.timing));
fs.writeFileSync('golden_files/perf/before.json', metrics);
```

**After migration:**
```typescript
// Same capture
```

**Comparison:**
```bash
# Extract load time
jq '.loadEventEnd - .navigationStart' golden_files/perf/before.json
# 1250ms

jq '.loadEventEnd - .navigationStart' golden_files/perf/after.json
# 1180ms  # ✅ 5% faster (acceptable)
```

**Threshold:** ±15% allowed (rendering variations, network)

## Capture Strategy (Automated)

### Pre-Transform Hook

```python
async def pre_transform_capture(project: Project, app: str):
    """Capture golden files before transformation."""

    # 1. Start app
    await subprocess_run(f"cd {app} && npm start", background=True)
    await asyncio.sleep(10)  # Wait for app ready

    # 2. Playwright: capture screenshots + network + console
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Track console
        console_messages = []
        page.on('console', lambda msg: console_messages.append(msg.text()))

        # Track network
        requests = []
        page.on('request', lambda req: requests.append({
            'url': req.url(),
            'method': req.method()
        }))

        # Visit pages
        for url in PAGES_TO_TEST:
            await page.goto(url)
            await page.screenshot({
                'path': f'golden_files/screenshots/{url.replace("/", "_")}_before.png'
            })

        # Save console + network
        with open('golden_files/console/before.json', 'w') as f:
            json.dump(console_messages, f)
        with open('golden_files/network/before.json', 'w') as f:
            json.dump(requests, f)

        await browser.close()

    # 3. API: capture endpoints
    for endpoint in API_ENDPOINTS:
        response = requests.get(endpoint)
        with open(f'golden_files/api/{endpoint.replace("/", "_")}_before.json', 'w') as f:
            json.dump(response.json(), f)

    # 4. Tests: run and capture output
    await subprocess_run(f"cd {app} && npm test > ../golden_files/test_outputs/before.txt 2>&1")
```

### Post-Transform Hook

```python
async def post_transform_capture(project: Project, app: str):
    """Capture golden files after transformation, compare."""

    # Same capture as pre-transform, but save to *_after.json files
    # ...

    # Compare
    diffs = []

    # API diffs
    for file in glob('golden_files/api/*_before.json'):
        after_file = file.replace('_before', '_after')
        if not files_equal(file, after_file):
            diffs.append(f"API diff: {file}")

    # Screenshot diffs (pixel comparison)
    for file in glob('golden_files/screenshots/*_before.png'):
        after_file = file.replace('_before', '_after')
        pixel_diff = compare_images(file, after_file)
        if pixel_diff > 0.01:  # >1% diff
            diffs.append(f"Visual regression: {file} ({pixel_diff*100:.1f}% diff)")

    # Console diffs
    before_errors = count_errors('golden_files/console/before.json')
    after_errors = count_errors('golden_files/console/after.json')
    if after_errors > before_errors:
        diffs.append(f"Console errors increased: {before_errors} → {after_errors}")

    return diffs  # Return to Comparative Adversarial
```

## Comparative Adversarial Integration

```python
class ComparativeAdversarial:
    async def validate_transform(self, old_state, new_state, task):
        # L0: Golden file diff (deterministic)
        diffs = compare_golden_files(old_state, new_state)

        if diffs:
            return ValidationResult.REJECT(
                reason="Behavioral regression detected",
                diffs=diffs
            )

        # ... L1, L2 (LLM checks)

        return ValidationResult.APPROVE
```

## Anti-Patterns (Adversarial Rejects)

- ❌ No golden files captured (can't compare)
- ❌ Golden files captured AFTER transformation (too late)
- ❌ Comparing only 1 page (insufficient coverage)
- ❌ Ignoring visual regressions (>1% pixel diff)
- ❌ Not testing all API endpoints
- ❌ Not capturing console errors
- ❌ No performance baseline

## Example: Angular 16→17 Golden Files

```
golden_files/
├── api/
│   ├── users_before.json
│   ├── users_after.json
│   ├── posts_before.json
│   └── posts_after.json
├── screenshots/
│   ├── dashboard_before.png
│   ├── dashboard_after.png
│   ├── settings_before.png
│   ├── settings_after.png
│   └── diff/
│       ├── dashboard_diff.png (if >1% diff)
│       └── dashboard_diff.txt (pixel diff %)
├── console/
│   ├── before.json
│   └── after.json
├── network/
│   ├── before.json
│   └── after.json
├── test_outputs/
│   ├── before.txt
│   └── after.txt
└── perf/
    ├── before.json
    └── after.json
```

## Rollback Decision Tree

```
Golden files diff detected?
├─ YES: API responses changed?
│   ├─ YES: REJECT + ROLLBACK (breaking change)
│   └─ NO: Visual regression?
│       ├─ YES (>1%): REJECT + ROLLBACK
│       └─ NO: Console errors increased?
│           ├─ YES: REJECT + ROLLBACK
│           └─ NO: Performance degraded?
│               ├─ YES (>15%): WARN (create perf task)
│               └─ NO: APPROVE
└─ NO: APPROVE (behavior preserved)
```

## References

- Visual Regression Testing: https://www.browserstack.com/guide/visual-regression-testing
- Snapshot Testing: https://jestjs.io/docs/snapshot-testing
- Golden Files Pattern: https://ro-che.info/articles/2017-12-04-golden-tests
