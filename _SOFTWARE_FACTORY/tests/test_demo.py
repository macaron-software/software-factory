"""Tests for demo mode — mock LLM responses and data seeding."""
import os
import pytest
from unittest.mock import patch


def test_demo_response_bug():
    """Demo provider returns bug-related response for bug keywords."""
    from platform.llm.client import LLMClient, LLMMessage
    client = LLMClient()
    resp = client._demo_response([LLMMessage(role="user", content="Fix this critical bug in production")])
    assert "fix" in resp.content.lower() or "issue" in resp.content.lower()
    assert resp.provider == "demo"
    assert resp.model == "demo"


def test_demo_response_deploy():
    """Demo provider returns deployment-related response."""
    from platform.llm.client import LLMClient, LLMMessage
    client = LLMClient()
    resp = client._demo_response([LLMMessage(role="user", content="Deploy the application to staging")])
    assert "deploy" in resp.content.lower()


def test_demo_response_generic():
    """Demo provider returns generic response for unknown topics."""
    from platform.llm.client import LLMClient, LLMMessage
    client = LLMClient()
    resp = client._demo_response([LLMMessage(role="user", content="Hello world")])
    assert resp.content
    assert resp.tokens_out > 0


def test_demo_is_demo_mode():
    """is_demo_mode returns True when PLATFORM_LLM_PROVIDER=demo."""
    from platform.demo import is_demo_mode
    with patch.dict(os.environ, {"PLATFORM_LLM_PROVIDER": "demo"}):
        assert is_demo_mode() is True
    with patch.dict(os.environ, {"PLATFORM_LLM_PROVIDER": "openai"}):
        assert is_demo_mode() is False
