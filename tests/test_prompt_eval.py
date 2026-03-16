"""Prompt eval — pytest integration.

Runs prompt CI evals as pytest tests. Each eval+provider combo is a parametrized test case.

Usage:
    pytest tests/test_prompt_eval.py -v                    # all evals
    pytest tests/test_prompt_eval.py -v -k "tool_call"     # one suite
    pytest tests/test_prompt_eval.py -v -k "minimax"       # one provider

Requires LLM API keys in environment (skips if none available).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.prompt_eval import (
    EvalResult,
    _detect_providers,
    get_evals,
    run_single_eval,
)

# Skip entire module if no LLM keys configured
_providers = _detect_providers()
pytestmark = [
    pytest.mark.prompt_eval,
    pytest.mark.skipif(
        not any(
            os.environ.get(k)
            for k in [
                "MINIMAX_API_KEY",
                "AZURE_OPENAI_API_KEY",
                "AZURE_AI_API_KEY",
                "NVIDIA_API_KEY",
            ]
        ),
        reason="No LLM API keys configured",
    ),
]


def _make_params():
    """Generate pytest parametrize args: (eval, provider)."""
    evals = get_evals()
    providers = _detect_providers()
    params = []
    for ev in evals:
        for prov in providers:
            params.append(
                pytest.param(ev, prov, id=f"{ev.id}--{prov}")
            )
    return params


@pytest.mark.parametrize("eval_case,provider", _make_params())
async def test_prompt_eval(eval_case, provider):
    """Run a single prompt eval against a provider."""
    from platform.llm.client import get_llm_client

    llm = get_llm_client()
    result: EvalResult = await run_single_eval(llm, eval_case, provider)

    # Build detailed failure message
    if not result.passed:
        details = "\n".join(
            f"  {'✓' if ok else '✗'} {reason}"
            for ok, reason in result.assertion_results
        )
        if result.error:
            details += f"\n  Error: {result.error}"
        pytest.fail(
            f"Prompt eval '{eval_case.name}' failed on {provider} "
            f"after {result.attempts} attempts:\n{details}"
        )
