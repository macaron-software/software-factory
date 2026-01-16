#!/usr/bin/env python3
"""
LRM Brain v4 - E2E Journey Focused Analysis

Analyzes:
1. FAILED tasks from previous runs
2. E2E journey coverage gaps
3. Missing selectors (data-testid)
4. AO compliance test gaps
5. User journey completeness

Creates actionable micro-tasks with:
- Real file paths
- Real selectors
- Real test data
- AO references
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from datetime import datetime

# ============================================================================
# CONFIG
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TASKS_DIR = SCRIPT_DIR / "tasks"
STATUS_DIR = SCRIPT_DIR / "status"

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[1;35m"
CYAN = "\033[0;36m"
NC = "\033[0m"

def log(msg: str, color: str = NC):
    print(f"{color}[BRAIN-v4] {msg}{NC}", file=sys.stderr)

def bash(cmd: str, cwd: str = None, timeout: int = 60) -> Tuple[int, str]:
    """Execute real bash command."""
    try:
        result = subprocess.run(
            cmd, shell=True,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True, text=True,
            timeout=timeout
        )
        return result.returncode, (result.stdout + result.stderr)[:30000]
    except Exception as e:
        return 1, str(e)

# ============================================================================
# AO REFERENCE MAPPING
# ============================================================================
AO_REFS = {
    "franceconnect": "AO-IDFM-AUTH-3.1.3",
    "sso": "AO-IDFM-AUTH-3.1",
    "mfa": "AO-IDFM-AUTH-3.1.4",
    "booking": "AO-IDFM-BOOKING-3.2",
    "subscription": "AO-IDFM-SUB-3.3",
    "payment": "AO-IDFM-PAY-3.4",
    "station": "AO-IDFM-STATION-3.5",
    "bike": "AO-IDFM-BIKE-3.6",
    "tcl": "AO-LYON-TCL-4.1",
    "box": "AO-NANTES-BOX-5.1",
    "incident": "AO-COMMON-INC-6.1",
    "rgpd": "AO-COMMON-RGPD-7.1",
    "admin": "AO-COMMON-ADMIN-8.1",
}

def get_ao_ref(context: str) -> str:
    """Get AO reference from context."""
    context_lower = context.lower()
    for key, ref in AO_REFS.items():
        if key in context_lower:
            return ref
    return ""

# ============================================================================
# ANALYZERS
# ============================================================================

def analyze_failed_tasks() -> List[Dict]:
    """Find and analyze FAILED tasks for retry."""
    log("Analyzing FAILED tasks...", CYAN)
    findings = []

    for status_file in STATUS_DIR.glob("*.status"):
        status = status_file.read_text().strip()
        if status == "FAILED":
            task_id = status_file.stem
            task_file = TASKS_DIR / f"{task_id}.md"
            if task_file.exists():
                content = task_file.read_text()

                # Extract description
                desc_match = re.search(r'^# Task [^:]+:\s*(.+)$', content, re.MULTILINE)
                description = desc_match.group(1) if desc_match else "Unknown"

                # Extract file
                file_match = re.search(r'^## File\n([^\n]+)', content, re.MULTILINE)
                target_file = file_match.group(1).split(':')[0] if file_match else ""

                findings.append({
                    "type": "retry_failed",
                    "task_id": task_id,
                    "severity": "P0",
                    "message": f"Retry failed task: {description}",
                    "file": target_file,
                    "ao_ref": get_ao_ref(content)
                })

    log(f"  Found {len(findings)} failed tasks to retry", BLUE)
    return findings

def analyze_e2e_journeys() -> List[Dict]:
    """Analyze E2E journey test coverage."""
    log("Analyzing E2E journey coverage...", CYAN)
    findings = []

    # Define expected journeys per tenant
    expected_journeys = {
        "idfm": [
            ("subscriber-onboarding", "New user registers, selects plan, pays, gets bike"),
            ("booking-flow", "User searches station, books bike, rides, returns"),
            ("franceconnect-login", "User logs in via FranceConnect SSO"),
            ("subscription-upgrade", "User upgrades subscription plan"),
            ("incident-report", "User reports bike incident"),
        ],
        "nantes": [
            ("box-securise-booking", "User books secure box for bike"),
            ("subscriber-onboarding", "New Naolib user registration"),
            ("booking-flow", "Book bike in Nantes network"),
        ],
        "lyon": [
            ("tcl-multimodal", "Combined TCL + bike journey"),
            ("subscriber-onboarding", "New TCL user registration"),
            ("booking-flow", "Book bike in Lyon network"),
        ],
        "common": [
            ("admin-user-management", "Admin manages users"),
            ("admin-reporting", "Admin generates reports"),
            ("profile-management", "User updates profile"),
            ("payment-flow", "User adds payment method"),
        ]
    }

    # Check which journeys exist
    _, existing = bash("find tests/e2e/journeys -name '*.spec.ts' 2>/dev/null")
    existing_files = set(existing.strip().split('\n'))

    for tenant, journeys in expected_journeys.items():
        for journey_name, description in journeys:
            # Check if journey exists
            pattern = f"*{journey_name}*"
            found = any(journey_name in f for f in existing_files)

            if not found:
                ao_ref = get_ao_ref(journey_name)
                if not ao_ref:
                    ao_ref = f"AO-{tenant.upper()}-JOURNEY"

                findings.append({
                    "type": "missing_journey",
                    "severity": "P1",
                    "message": f"Missing E2E journey: {journey_name} - {description}",
                    "file": f"tests/e2e/journeys/{tenant}-{journey_name}.spec.ts",
                    "tenant": tenant,
                    "journey_name": journey_name,
                    "description": description,
                    "ao_ref": ao_ref
                })

    log(f"  Found {len(findings)} missing journeys", BLUE)
    return findings

def analyze_selectors() -> List[Dict]:
    """Analyze missing data-testid selectors in components."""
    log("Analyzing IHM selectors...", CYAN)
    findings = []

    # Key components that MUST have testids
    critical_selectors = {
        "LoginWidget": ["login-form", "login-email", "login-password", "login-submit", "franceconnect-login", "sso-google"],
        "BookingForm": ["booking-form", "station-select", "bike-select", "date-picker", "booking-submit"],
        "StationMap": ["station-map", "station-marker", "station-popup", "search-input"],
        "SubscriptionCard": ["plan-card", "plan-price", "plan-select", "plan-features"],
        "PaymentForm": ["payment-form", "card-number", "card-expiry", "card-cvc", "payment-submit"],
        "ProfileForm": ["profile-form", "profile-name", "profile-email", "profile-save"],
        "IncidentForm": ["incident-form", "incident-type", "incident-description", "incident-submit"],
        "AdminDashboard": ["admin-stats", "admin-users-table", "admin-actions"],
    }

    # Find Svelte components
    _, svelte_files = bash("find veligo-platform/frontend/src -name '*.svelte' -type f 2>/dev/null")

    for component, expected_ids in critical_selectors.items():
        # Find component file
        component_file = None
        for f in svelte_files.strip().split('\n'):
            if component in f:
                component_file = f
                break

        if component_file:
            _, content = bash(f"cat '{component_file}' 2>/dev/null")

            for testid in expected_ids:
                if f'data-testid="{testid}"' not in content and f"data-testid='{testid}'" not in content:
                    findings.append({
                        "type": "missing_selector",
                        "severity": "P1",
                        "message": f"Missing data-testid='{testid}' in {component}",
                        "file": component_file,
                        "selector": testid,
                        "component": component,
                        "ao_ref": get_ao_ref(component)
                    })

    log(f"  Found {len(findings)} missing selectors", BLUE)
    return findings

def analyze_test_data() -> List[Dict]:
    """Analyze test fixtures and data completeness."""
    log("Analyzing test data/fixtures...", CYAN)
    findings = []

    # Check fixtures exist
    required_fixtures = [
        ("tests/e2e/fixtures/users.json", ["idfm_user", "nantes_user", "lyon_user", "admin_user"]),
        ("tests/e2e/fixtures/stations.json", ["idfm_stations", "nantes_stations", "lyon_stations"]),
        ("tests/e2e/fixtures/bikes.json", ["electric", "cargo", "classic"]),
        ("tests/e2e/fixtures/plans.json", ["basic", "standard", "premium"]),
    ]

    for fixture_path, required_keys in required_fixtures:
        full_path = PROJECT_ROOT / fixture_path
        if not full_path.exists():
            findings.append({
                "type": "missing_fixture",
                "severity": "P1",
                "message": f"Missing test fixture: {fixture_path}",
                "file": fixture_path,
                "required_keys": required_keys,
                "ao_ref": "AO-COMMON-TEST"
            })
        else:
            # Check fixture content
            try:
                content = json.loads(full_path.read_text())
                for key in required_keys:
                    if key not in str(content).lower():
                        findings.append({
                            "type": "incomplete_fixture",
                            "severity": "P2",
                            "message": f"Fixture {fixture_path} missing key: {key}",
                            "file": fixture_path,
                            "missing_key": key,
                            "ao_ref": "AO-COMMON-TEST"
                        })
            except:
                pass

    log(f"  Found {len(findings)} fixture issues", BLUE)
    return findings

def analyze_ao_compliance() -> List[Dict]:
    """Analyze AO compliance test coverage."""
    log("Analyzing AO compliance...", CYAN)
    findings = []

    # Required AO tests
    ao_requirements = {
        "AO-IDFM-AUTH-3.1.3": {
            "name": "FranceConnect SSO",
            "test_pattern": "franceconnect",
            "required_tests": ["login", "callback", "logout", "session-sync"]
        },
        "AO-IDFM-BOOKING-3.2": {
            "name": "Bike Booking",
            "test_pattern": "booking",
            "required_tests": ["search", "reserve", "start-ride", "end-ride", "cancel"]
        },
        "AO-NANTES-BOX-5.1": {
            "name": "Secure Box",
            "test_pattern": "box",
            "required_tests": ["availability", "reserve", "unlock", "lock", "timeout"]
        },
        "AO-LYON-TCL-4.1": {
            "name": "TCL Multimodal",
            "test_pattern": "tcl",
            "required_tests": ["journey-plan", "ticket-integration", "realtime"]
        },
    }

    # Find existing AO tests
    _, ao_tests = bash("find tests/e2e/ao-compliance -name '*.spec.ts' 2>/dev/null")
    ao_test_content = ""
    for f in ao_tests.strip().split('\n'):
        if f:
            _, content = bash(f"cat '{f}' 2>/dev/null")
            ao_test_content += content

    for ao_ref, spec in ao_requirements.items():
        for required_test in spec["required_tests"]:
            test_name = f"{spec['test_pattern']}-{required_test}"
            if test_name not in ao_test_content.lower() and required_test not in ao_test_content.lower():
                findings.append({
                    "type": "missing_ao_test",
                    "severity": "P0",
                    "message": f"Missing AO compliance test: {spec['name']} - {required_test}",
                    "file": f"tests/e2e/ao-compliance/{spec['test_pattern']}/{required_test}.spec.ts",
                    "ao_ref": ao_ref,
                    "test_name": required_test
                })

    log(f"  Found {len(findings)} AO compliance gaps", BLUE)
    return findings

# ============================================================================
# TASK GENERATION - More detailed for E2E
# ============================================================================

def create_journey_task(task_id: str, finding: Dict) -> None:
    """Create detailed E2E journey task."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    tenant = finding.get('tenant', 'common')
    journey_name = finding.get('journey_name', 'unknown')
    description = finding.get('description', '')

    # Generate test template
    test_template = f'''import {{ test, expect }} from '@playwright/test';
import {{ users }} from '../fixtures/users.json';
import {{ stations }} from '../fixtures/stations.json';

const BASE_URL = process.env.{tenant.upper()}_URL || 'https://{tenant}.veligo.app';

test.describe('[{finding.get("ao_ref", "AO-REF")}] {journey_name}', () => {{

  test('Complete {journey_name} journey', async ({{ page }}) => {{
    // Step 1: Navigate to starting point
    await page.goto(`${{BASE_URL}}/`);

    // Step 2: User actions
    // TODO: Implement {description}

    // Step 3: Verify success
    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
  }});

}});
'''

    content = f"""# Task {task_id}: Create E2E Journey - {journey_name}

**Priority**: {finding['severity']}
**Queue**: TDD
**AO_REF**: {finding.get('ao_ref', '')}
**Tenant**: {tenant}

## Description
{finding['message']}

Journey: {description}

## File to Create
{finding['file']}

## Test Template
```typescript
{test_template}
```

## Required Selectors
- Navigation: `[data-testid="nav-*"]`
- Forms: `[data-testid="form-*"]`
- Buttons: `[data-testid="btn-*"]`
- Status: `[data-testid="status-*"]`

## Success Criteria
- [ ] Test file created with proper structure
- [ ] All user steps implemented
- [ ] Selectors use data-testid
- [ ] Test runs without skip
- [ ] AO compliance verified

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
WSJF: {10 if finding['severity'] == 'P0' else 8}
---END_RALPH_STATUS---
"""

    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(content)
    (STATUS_DIR / f"{task_id}.status").write_text("PENDING")
    log(f"Created {task_id}: E2E Journey - {journey_name}", GREEN)

def create_selector_task(task_id: str, finding: Dict) -> None:
    """Create task for adding missing selector."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    content = f"""# Task {task_id}: Add selector {finding['selector']}

**Priority**: {finding['severity']}
**Queue**: TDD
**AO_REF**: {finding.get('ao_ref', '')}

## Description
Add missing data-testid="{finding['selector']}" to {finding['component']}

## File to Modify
{finding['file']}

## Change Required
Find the appropriate element and add:
```svelte
data-testid="{finding['selector']}"
```

## Example
```svelte
<button
  type="submit"
  class="btn-primary"
  data-testid="{finding['selector']}"
>
  Submit
</button>
```

## Success Criteria
- [ ] Selector added to correct element
- [ ] Component still renders correctly
- [ ] E2E tests can find the selector

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: simple
WSJF: 7
---END_RALPH_STATUS---
"""

    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(content)
    (STATUS_DIR / f"{task_id}.status").write_text("PENDING")
    log(f"Created {task_id}: Add selector {finding['selector']}", GREEN)

def create_generic_task(task_id: str, finding: Dict) -> None:
    """Create generic task."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    content = f"""# Task {task_id}: {finding['message'][:60]}

**Priority**: {finding['severity']}
**Queue**: TDD
**AO_REF**: {finding.get('ao_ref', '')}

## Description
{finding['message']}

## File
{finding.get('file', 'TBD')}

## Success Criteria
- [ ] Issue resolved
- [ ] Tests pass
- [ ] No regressions

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
WSJF: {10 if finding['severity'] == 'P0' else 8 if finding['severity'] == 'P1' else 5}
---END_RALPH_STATUS---
"""

    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(content)
    (STATUS_DIR / f"{task_id}.status").write_text("PENDING")
    log(f"Created {task_id}: {finding['message'][:40]}...", GREEN)

def get_next_task_id() -> int:
    """Get next available task ID."""
    existing = list(TASKS_DIR.glob("T*.md"))
    if not existing:
        return 200  # Start from T200 for v4 tasks

    max_id = 0
    for f in existing:
        try:
            num = int(f.stem[1:])
            max_id = max(max_id, num)
        except:
            pass
    return max_id + 1

# ============================================================================
# MAIN
# ============================================================================

def run_analysis():
    """Run comprehensive E2E focused analysis."""
    log("=" * 70, MAGENTA)
    log("LRM BRAIN v4 - E2E JOURNEY FOCUSED ANALYSIS", MAGENTA)
    log("=" * 70, MAGENTA)

    all_findings = []

    # 1. Retry failed tasks first
    all_findings.extend(analyze_failed_tasks())

    # 2. E2E Journey coverage
    all_findings.extend(analyze_e2e_journeys())

    # 3. IHM Selectors
    all_findings.extend(analyze_selectors())

    # 4. Test data/fixtures
    all_findings.extend(analyze_test_data())

    # 5. AO Compliance
    all_findings.extend(analyze_ao_compliance())

    log(f"\n{'='*70}", MAGENTA)
    log(f"Total findings: {len(all_findings)}", BLUE)

    # Create tasks
    task_id = get_next_task_id()
    tasks_created = []

    # Sort by severity
    sorted_findings = sorted(all_findings, key=lambda x: x['severity'])

    for finding in sorted_findings[:30]:  # Max 30 tasks
        tid = f"T{task_id:03d}"

        if finding['type'] == 'missing_journey':
            create_journey_task(tid, finding)
        elif finding['type'] == 'missing_selector':
            create_selector_task(tid, finding)
        else:
            create_generic_task(tid, finding)

        tasks_created.append(tid)
        task_id += 1

    log("=" * 70, MAGENTA)
    log("ANALYSIS COMPLETE", MAGENTA)
    log(f"Tasks created: {len(tasks_created)}", GREEN)

    # Summary by type
    by_type = {}
    for f in all_findings:
        t = f['type']
        by_type[t] = by_type.get(t, 0) + 1

    log("\nFindings by type:", CYAN)
    for t, count in sorted(by_type.items()):
        log(f"  {t}: {count}", BLUE)

    log("=" * 70, MAGENTA)

    return tasks_created

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LRM Brain v4 - E2E Journey Analyzer")
    parser.add_argument("--analyze", action="store_true", help="Run analysis")
    parser.add_argument("--list", action="store_true", help="List tasks")

    args = parser.parse_args()

    if args.analyze:
        run_analysis()
    elif args.list:
        for f in sorted(TASKS_DIR.glob("T*.md")):
            status_file = STATUS_DIR / f"{f.stem}.status"
            status = status_file.read_text().strip() if status_file.exists() else "UNKNOWN"
            print(f"{f.stem}: {status}")
    else:
        parser.print_help()
