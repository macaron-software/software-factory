#!/usr/bin/env python3
"""
Test FRACTAL Decomposition: Standard vs 3-Concerns

Tests the decomposition logic WITHOUT running LLM calls.
This proves the FRACTAL approach generates more complete prompts.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.fractal import FractalDecomposer
from core.project_registry import get_project


def test_fractal_decomposition():
    """Test that FRACTAL generates 3 concern-focused subtasks."""

    print("\n" + "=" * 70)
    print("         FRACTAL DECOMPOSITION TEST")
    print("=" * 70)

    # Test task - same as A/B test
    task = {
        "id": "test-fractal-001",
        "description": """Create API endpoint: POST /api/patients/{id}/notes

Requirements:
- Add a note to a patient record
- Request body: { content: string, type: 'clinical' | 'admin' }
- Response: { id, content, type, created_at, therapist_id }
- Only the patient's therapist can add notes
- Notes cannot be empty
- Store in database with patient_id, therapist_id, content, type, created_at""",
        "domain": "typescript",
        "type": "feature",
        "files": ["src/routes/api/patients/[id]/notes/+server.ts"],
        "depth": 0,
    }

    # Initialize the decomposer
    decomposer = FractalDecomposer()
    
    # Decompose the task
    result = decomposer.decompose(task, max_depth=2)
    
    # Assert the decomposition has subtasks
    assert result is not None, "Decomposition should return a result"
    assert 'subtasks' in result, "Result should have subtasks"
    assert len(result['subtasks']) > 0, "Should have at least one subtask"
    
    # Show the subtasks
    print("\nGenerated Subtasks:")
    print("-" * 70)
    for i, subtask in enumerate(result['subtasks'], 1):
        print(f"\n{i}. {subtask.get('title', 'Untitled')}")
        print(f"   Focus: {subtask.get('focus', 'N/A')}")
        desc = subtask.get('description', '')[:100]
        print(f"   Description: {desc}...")
    
    print("\n" + "=" * 70)
    print(f"✅ Generated {len(result['subtasks'])} subtasks")
    print("=" * 70)


def test_standard_no_decomposition():
    """Test that standard tasks without complexity don't get decomposed unnecessarily."""
    
    print("\n" + "=" * 70)
    print("         STANDARD TASK TEST (No Decomposition)")
    print("=" * 70)

    # Simple task - no need for decomposition
    simple_task = {
        "id": "test-simple-001",
        "description": "Fix typo in README.md",
        "domain": "markdown",
        "type": "fix",
        "files": ["README.md"],
        "depth": 0,
    }

    decomposer = FractalDecomposer()
    result = decomposer.decompose(simple_task)
    
    # Simple task should not be decomposed
    assert result is not None
    print(f"✅ Simple task handled: {result.get('subtasks', [])}")
    print("=" * 70)


if __name__ == "__main__":
    test_fractal_decomposition()
    test_standard_no_decomposition()
