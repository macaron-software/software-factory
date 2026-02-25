"""Tests for LLM response cache."""
import os
import tempfile

import pytest

from platform.llm.cache import LLMCache, _cache_key


@pytest.fixture
def cache(tmp_path):
    db_path = tmp_path / "test_cache.db"
    return LLMCache(db_path=db_path)


MSGS = [{"role": "user", "content": "Hello"}]


class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("gpt-5", MSGS, 0.7)
        k2 = _cache_key("gpt-5", MSGS, 0.7)
        assert k1 == k2

    def test_different_model(self):
        k1 = _cache_key("gpt-5", MSGS, 0.7)
        k2 = _cache_key("gpt-4", MSGS, 0.7)
        assert k1 != k2

    def test_different_temperature(self):
        k1 = _cache_key("gpt-5", MSGS, 0.7)
        k2 = _cache_key("gpt-5", MSGS, 0.3)
        assert k1 != k2

    def test_different_messages(self):
        k1 = _cache_key("gpt-5", MSGS, 0.7)
        k2 = _cache_key("gpt-5", [{"role": "user", "content": "Bye"}], 0.7)
        assert k1 != k2

    def test_with_tools(self):
        k1 = _cache_key("gpt-5", MSGS, 0.7, tools=None)
        k2 = _cache_key("gpt-5", MSGS, 0.7, tools=[{"name": "search"}])
        assert k1 != k2


class TestCachePutGet:
    def test_miss_returns_none(self, cache):
        assert cache.get("gpt-5", MSGS, 0.7) is None

    def test_put_then_get(self, cache):
        cache.put("gpt-5", MSGS, 0.7, "Hello back!", tokens_in=10, tokens_out=5)
        hit = cache.get("gpt-5", MSGS, 0.7)
        assert hit is not None
        assert hit["content"] == "Hello back!"
        assert hit["tokens_in"] == 10
        assert hit["tokens_out"] == 5
        assert hit["cached"] is True

    def test_different_model_no_cross(self, cache):
        cache.put("gpt-5", MSGS, 0.7, "response-5")
        assert cache.get("gpt-4", MSGS, 0.7) is None

    def test_hit_increments_count(self, cache):
        cache.put("gpt-5", MSGS, 0.7, "resp")
        cache.get("gpt-5", MSGS, 0.7)
        cache.get("gpt-5", MSGS, 0.7)
        stats = cache.stats()
        assert stats["hits"] == 2

    def test_replace_on_same_key(self, cache):
        cache.put("gpt-5", MSGS, 0.7, "old")
        cache.put("gpt-5", MSGS, 0.7, "new")
        hit = cache.get("gpt-5", MSGS, 0.7)
        assert hit["content"] == "new"


class TestCacheInvalidate:
    def test_invalidate_all(self, cache):
        cache.put("gpt-5", MSGS, 0.7, "a")
        cache.put("gpt-4", MSGS, 0.7, "b")
        removed = cache.invalidate()
        assert removed == 2
        assert cache.get("gpt-5", MSGS, 0.7) is None

    def test_invalidate_by_model(self, cache):
        cache.put("gpt-5", MSGS, 0.7, "a")
        cache.put("gpt-4", MSGS, 0.7, "b")
        removed = cache.invalidate(model="gpt-5")
        assert removed == 1
        assert cache.get("gpt-4", MSGS, 0.7) is not None


class TestCacheStats:
    def test_stats_empty(self, cache):
        s = cache.stats()
        assert s["entries"] == 0
        assert s["hits"] == 0
        assert s["misses"] == 0
        assert s["enabled"] is True

    def test_stats_after_operations(self, cache):
        cache.put("m", MSGS, 0.7, "r", tokens_in=100, tokens_out=50)
        cache.get("m", MSGS, 0.7)  # hit
        cache.get("m", [{"role": "user", "content": "x"}], 0.7)  # miss
        s = cache.stats()
        assert s["entries"] == 1
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["tokens_saved"] == 150


class TestCacheEviction:
    def test_evicts_oldest_at_capacity(self, cache):
        # Override max size for test
        import platform.llm.cache as cache_mod
        old_max = cache_mod._MAX_SIZE
        cache_mod._MAX_SIZE = 5
        try:
            for i in range(6):
                msgs = [{"role": "user", "content": f"msg-{i}"}]
                cache.put("m", msgs, 0.7, f"resp-{i}")
            s = cache.stats()
            assert s["entries"] <= 5
            assert s["evictions"] >= 1
        finally:
            cache_mod._MAX_SIZE = old_max
