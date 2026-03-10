#!/usr/bin/env python3
"""
A/B Test: Standard vs Fractal Implementation

Compare:
- A: Wiggum Standard (no decomposition)
- B: Wiggum Fractal (3 concerns: feature/guards/failures)

Metrics:
- Largeur: aspects covered
- Profondeur: detail level
- Gaps: missing RBAC, validation, errors, edge cases
- KISS: code simplicity
- Patterns: good practices
- Anti-patterns: code smells
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project
from core.task_store import TaskStore, Task
from core.adversarial import AdversarialGate, ARCH_COMPLETENESS_CHECKS


# Test task definition
TEST_TASK = {
    "id": "ab-test-patient-notes",
    "description": """Create API endpoint: POST /api/patients/{id}/notes

Requirements:
- Add a note to a patient record
- Request body: { content: string, type: 'clinical' | 'admin' }
- Response: { id, content, type, created_at, therapist_id }
- Only the patient's therapist can add notes
- Notes cannot be empty
- Store in database with patient_id, therapist_id, content, type, created_at
""",
    "domain": "typescript",
    "type": "feature",
    "files": ["ms-dashboard/src/routes/api/patients/[id]/notes/+server.ts"],
}


def analyze_code(code: str, filename: str) -> dict:
    """Analyze generated code for completeness."""

    gate = AdversarialGate()

    # Architecture checks
    arch_issues = gate.check_architecture_completeness(code, filename)

    # Pattern checks
    result = gate.check_code(code, "typescript", filename)

    # Manual checks for specific patterns
    checks = {
        "has_auth_check": any([
            "getSession" in code,
            "validateSession" in code,
            "locals.user" in code,
            "401" in code,
        ]),
        "has_permission_check": any([
            "403" in code,
            "Forbidden" in code,
            "checkPermission" in code,
            "therapist" in code.lower() and ("id" in code.lower() or "check" in code.lower()),
        ]),
        "has_input_validation": any([
            "validate" in code.lower(),
            "zod" in code.lower(),
            "typeof" in code,
            "!content" in code or "content.trim()" in code,
        ]),
        "has_type_check": any([
            "'clinical'" in code and "'admin'" in code,
            "type ===" in code,
            "includes(" in code,
        ]),
        "has_404_handling": "404" in code,
        "has_400_handling": "400" in code,
        "has_specific_errors": any([
            "400" in code,
            "404" in code,
            "409" in code,
            "422" in code,
        ]) and "500" not in code[-200:],  # Not ending with generic 500
        "has_logging": any([
            "console.error" in code,
            "logger" in code.lower(),
            "log(" in code,
        ]),
        "has_db_insert": any([
            "INSERT" in code.upper(),
            ".create(" in code,
            ".insert(" in code,
        ]),
        "has_response_format": any([
            "id," in code and "content" in code and "created_at" in code,
            "json({" in code,
        ]),
        "lines_of_code": len(code.split("\n")),
        "complexity": code.count("if ") + code.count("try ") + code.count("catch "),
    }

    # Calculate scores
    guards_score = sum([
        checks["has_auth_check"] * 2,
        checks["has_permission_check"] * 2,
        checks["has_input_validation"] * 1,
        checks["has_type_check"] * 1,
    ])

    failures_score = sum([
        checks["has_404_handling"] * 1,
        checks["has_400_handling"] * 1,
        checks["has_specific_errors"] * 2,
        checks["has_logging"] * 1,
    ])

    feature_score = sum([
        checks["has_db_insert"] * 2,
        checks["has_response_format"] * 1,
    ])

    return {
        "checks": checks,
        "arch_issues": [i.to_dict() for i in arch_issues],
        "pattern_issues": [i.to_dict() for i in result.issues],
        "scores": {
            "feature": feature_score,
            "guards": guards_score,
            "failures": failures_score,
            "total": feature_score + guards_score + failures_score,
            "max_possible": 14,
        },
        "gaps": {
            "missing_auth": not checks["has_auth_check"],
            "missing_permission": not checks["has_permission_check"],
            "missing_validation": not checks["has_input_validation"],
            "missing_type_check": not checks["has_type_check"],
            "missing_404": not checks["has_404_handling"],
            "missing_400": not checks["has_400_handling"],
            "missing_specific_errors": not checks["has_specific_errors"],
            "missing_logging": not checks["has_logging"],
        },
        "kiss": {
            "lines": checks["lines_of_code"],
            "complexity": checks["complexity"],
            "is_simple": checks["lines_of_code"] < 100 and checks["complexity"] < 15,
        },
    }


def print_comparison(result_a: dict, result_b: dict):
    """Print side-by-side comparison."""

    print("\n" + "=" * 80)
    print("                    A/B TEST RESULTS: STANDARD vs FRACTAL")
    print("=" * 80)

    print("\n### SCORES (higher = better)")
    print(f"{'Metric':<20} {'Standard':>15} {'Fractal':>15} {'Winner':>10}")
    print("-" * 60)

    for key in ["feature", "guards", "failures", "total"]:
        a_val = result_a["scores"][key]
        b_val = result_b["scores"][key]
        winner = "FRACTAL" if b_val > a_val else "STANDARD" if a_val > b_val else "TIE"
        print(f"{key:<20} {a_val:>15} {b_val:>15} {winner:>10}")

    print(f"\n{'Max possible':<20} {result_a['scores']['max_possible']:>15}")

    print("\n### GAPS (missing = bad)")
    print(f"{'Gap':<30} {'Standard':>12} {'Fractal':>12}")
    print("-" * 54)

    for key, a_val in result_a["gaps"].items():
        b_val = result_b["gaps"][key]
        a_str = "❌ MISSING" if a_val else "✅"
        b_str = "❌ MISSING" if b_val else "✅"
        print(f"{key:<30} {a_str:>12} {b_str:>12}")

    print("\n### KISS (simplicity)")
    print(f"{'Metric':<20} {'Standard':>15} {'Fractal':>15}")
    print("-" * 50)
    print(f"{'Lines of code':<20} {result_a['kiss']['lines']:>15} {result_b['kiss']['lines']:>15}")
    print(f"{'Complexity':<20} {result_a['kiss']['complexity']:>15} {result_b['kiss']['complexity']:>15}")
    print(f"{'Is simple?':<20} {'Yes' if result_a['kiss']['is_simple'] else 'No':>15} {'Yes' if result_b['kiss']['is_simple'] else 'No':>15}")

    print("\n### ARCHITECTURE ISSUES")
    print(f"Standard: {len(result_a['arch_issues'])} issues")
    for issue in result_a['arch_issues']:
        print(f"  - {issue['rule']}: {issue['message']}")
    print(f"\nFractal: {len(result_b['arch_issues'])} issues")
    for issue in result_b['arch_issues']:
        print(f"  - {issue['rule']}: {issue['message']}")

    # Overall winner
    a_total = result_a["scores"]["total"]
    b_total = result_b["scores"]["total"]
    a_gaps = sum(result_a["gaps"].values())
    b_gaps = sum(result_b["gaps"].values())

    print("\n" + "=" * 80)
    print("                           VERDICT")
    print("=" * 80)
    print(f"Standard: Score {a_total}/14, Gaps {a_gaps}")
    print(f"Fractal:  Score {b_total}/14, Gaps {b_gaps}")

    if b_total > a_total and b_gaps < a_gaps:
        print("\n🏆 FRACTAL WINS: Higher score AND fewer gaps")
    elif b_total > a_total:
        print("\n🏆 FRACTAL WINS: Higher score")
    elif a_total > b_total:
        print("\n🏆 STANDARD WINS: Higher score")
    elif b_gaps < a_gaps:
        print("\n🏆 FRACTAL WINS: Fewer gaps")
    else:
        print("\n🤝 TIE")


# Mock generated code for testing the analyzer
MOCK_STANDARD_CODE = '''
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { db } from '$lib/db';

export const POST: RequestHandler = async ({ params, request }) => {
    try {
        const { content, type } = await request.json();
        const patientId = params.id;

        // Insert note
        const result = await db.query(
            'INSERT INTO notes (patient_id, content, type, created_at) VALUES ($1, $2, $3, NOW()) RETURNING *',
            [patientId, content, type]
        );

        return json(result.rows[0]);
    } catch (error) {
        console.error('Error:', error);
        return json({ error: 'Failed to create note' }, { status: 500 });
    }
};
'''

MOCK_FRACTAL_CODE = '''
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { db } from '$lib/db';
import { getSession } from '$lib/auth';

export const POST: RequestHandler = async ({ params, request, locals }) => {
    // GUARDS: Authentication
    const session = await getSession(locals);
    if (!session?.user) {
        return json({ error: 'Unauthorized' }, { status: 401 });
    }

    const therapistId = session.user.id;
    const patientId = params.id;

    // GUARDS: Authorization - check therapist owns this patient
    const patientCheck = await db.query(
        'SELECT therapist_id FROM patients WHERE id = $1 LIMIT 1',
        [patientId]
    );

    if (patientCheck.rows.length === 0) {
        return json({ error: 'Patient not found' }, { status: 404 });
    }

    if (patientCheck.rows[0].therapist_id !== therapistId) {
        return json({ error: 'Forbidden: Not your patient' }, { status: 403 });
    }

    // GUARDS: Input validation
    const body = await request.json();
    const { content, type } = body;

    if (!content || typeof content !== 'string' || content.trim().length === 0) {
        return json({ error: 'Content is required and must be non-empty' }, { status: 400 });
    }

    if (!type || !['clinical', 'admin'].includes(type)) {
        return json({ error: 'Type must be clinical or admin' }, { status: 400 });
    }

    // FEATURE: Insert note
    try {
        const result = await db.query(
            'INSERT INTO notes (patient_id, therapist_id, content, type, created_at) VALUES ($1, $2, $3, $4, NOW()) RETURNING id, content, type, created_at, therapist_id',
            [patientId, therapistId, content.trim(), type]
        );

        return json(result.rows[0], { status: 201 });
    } catch (error) {
        console.error('Failed to create note:', error);
        return json({ error: 'Failed to create note' }, { status: 500 });
    }
};
'''


if __name__ == "__main__":
    print("Analyzing mock code samples...")
    print("\nNote: In real test, this would run Wiggum Standard and Fractal")
    print("For now, using mock generated code to demonstrate analysis.\n")

    result_a = analyze_code(MOCK_STANDARD_CODE, "+server.ts")
    result_b = analyze_code(MOCK_FRACTAL_CODE, "+server.ts")

    print_comparison(result_a, result_b)
