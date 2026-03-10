"""Structured output validation for agent phases."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def validate_output(output: str, schema: dict) -> tuple[bool, list[str]]:
    """
    Validate agent output against a simple schema.
    Returns (is_valid, list_of_errors).
    Schema format: {"required": ["field1"], "type": "object", "properties": {...}}
    """
    if not schema or not output:
        return True, []
    try:
        data = json.loads(output.strip())
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    errors = []
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    props = schema.get("properties", {})
    _type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for field, spec in props.items():
        if field in data:
            expected_type = spec.get("type")
            value = data[field]
            if expected_type and expected_type in _type_map:
                if not isinstance(value, _type_map[expected_type]):
                    errors.append(
                        f"Field '{field}': expected {expected_type}, got {type(value).__name__}"
                    )

    return len(errors) == 0, errors


def build_correction_prompt(output: str, schema: dict, errors: list[str]) -> str:
    """Build a correction prompt for invalid structured output."""
    return (
        f"\n\nYour previous response was invalid. Errors: {'; '.join(errors)}. "
        f"Please respond with ONLY valid JSON matching this schema: {json.dumps(schema, indent=2)}. "
        "No explanation, no markdown code blocks, just the JSON object."
    )
