"""Tests for tiered context loading (L0/L1/L2)."""
from __future__ import annotations
# Ref: feat-skills

import pytest

from platform.llm.context_tiers import (
    ContextTier,
    TierBudget,
    apply_tier_to_context,
    build_tiered_skills,
    extract_l0_summary,
    format_skill_tiered,
    select_tier,
    tier_savings_estimate,
)


# ── select_tier ─────────────────────────────────────────────────


class TestSelectTier:
    def test_routing_task_always_l0(self):
        assert select_tier(hierarchy_rank=10, task_type="route") == ContextTier.L0

    def test_tight_budget_l0(self):
        assert select_tier(token_budget=1000) == ContextTier.L0

    def test_organizer_gets_l2(self):
        assert select_tier(capability_grade="organizer") == ContextTier.L2

    def test_high_rank_gets_l2(self):
        # CEO (rank 0) should get full context
        assert select_tier(hierarchy_rank=0) == ContextTier.L2

    def test_director_gets_l2(self):
        assert select_tier(hierarchy_rank=20) == ContextTier.L2

    def test_review_task_gets_l2(self):
        assert select_tier(hierarchy_rank=50, task_type="review") == ContextTier.L2

    def test_junior_executor_gets_l1(self):
        assert select_tier(hierarchy_rank=50, task_type="execute") == ContextTier.L1

    def test_mid_executor_gets_l1(self):
        assert select_tier(hierarchy_rank=40, task_type="execute") == ContextTier.L1

    def test_default_is_l1(self):
        assert select_tier() == ContextTier.L1


# ── TierBudget ──────────────────────────────────────────────────


class TestTierBudget:
    def test_l0_budgets(self):
        b = TierBudget.for_tier(ContextTier.L0)
        assert b.skill_chars == 120
        assert b.memory_chars == 0
        assert b.skill_max == 10

    def test_l1_budgets(self):
        b = TierBudget.for_tier(ContextTier.L1)
        assert b.skill_chars == 600
        assert b.memory_chars == 800
        assert b.skill_max == 5

    def test_l2_budgets(self):
        b = TierBudget.for_tier(ContextTier.L2)
        assert b.skill_chars == 1500
        assert b.memory_chars == 4000
        assert b.skill_max == 5


# ── extract_l0_summary ─────────────────────────────────────────


class TestExtractL0Summary:
    def test_first_sentence(self):
        content = "This is a skill for testing. It has many features."
        result = extract_l0_summary(content)
        assert result == "This is a skill for testing"

    def test_strips_markdown_header(self):
        content = "# My Skill\nDoes cool things. And more."
        result = extract_l0_summary(content)
        assert result == "My Skill"

    def test_caps_at_100_chars(self):
        content = "A" * 200
        result = extract_l0_summary(content)
        assert len(result) <= 100

    def test_empty_returns_name(self):
        assert extract_l0_summary("", name="fallback") == "fallback"

    def test_empty_no_name(self):
        assert extract_l0_summary("") == "—"


# ── format_skill_tiered ────────────────────────────────────────


class TestFormatSkillTiered:
    SKILL_CONTENT = (
        "# Frontend Development\n"
        "Use semantic HTML and CSS custom properties.\n"
        "Never use !important. Always use design tokens.\n"
        "Support light and dark mode. " + "Details. " * 100
    )

    def test_l0_one_liner(self):
        result = format_skill_tiered("dev_frontend", self.SKILL_CONTENT, ContextTier.L0)
        assert result.startswith("- **dev_frontend**: ")
        assert len(result) < 150

    def test_l1_truncated(self):
        result = format_skill_tiered("dev_frontend", self.SKILL_CONTENT, ContextTier.L1)
        assert "### dev_frontend" in result
        assert len(result) <= 700  # ~600 chars budget + header

    def test_l2_full(self):
        result = format_skill_tiered("dev_frontend", self.SKILL_CONTENT, ContextTier.L2)
        assert "### dev_frontend" in result
        assert len(result) <= 1600

    def test_l0_with_relevance_ignored(self):
        result = format_skill_tiered("test", "content", ContextTier.L0, relevance=0.9)
        # L0 doesn't show relevance
        assert "relevance" not in result


# ── build_tiered_skills ────────────────────────────────────────


class TestBuildTieredSkills:
    SKILLS = [
        {"name": f"skill_{i}", "content": f"Content for skill {i}. " * 50, "similarity": 0.0}
        for i in range(8)
    ]

    def test_l0_limits_count(self):
        result = build_tiered_skills(self.SKILLS, ContextTier.L0)
        assert result.startswith("Available skills:")
        # L0 allows up to 10 skills
        assert result.count("- **skill_") == 8

    def test_l1_limits_to_5(self):
        result = build_tiered_skills(self.SKILLS, ContextTier.L1)
        assert result.count("### skill_") == 5

    def test_l2_limits_to_5(self):
        result = build_tiered_skills(self.SKILLS, ContextTier.L2)
        assert result.count("### skill_") == 5

    def test_l0_much_shorter_than_l2(self):
        l0 = build_tiered_skills(self.SKILLS, ContextTier.L0)
        l2 = build_tiered_skills(self.SKILLS, ContextTier.L2)
        # L0 should be at least 5x shorter
        assert len(l0) < len(l2) / 3

    def test_empty_skills(self):
        assert build_tiered_skills([], ContextTier.L1) == ""


# ── apply_tier_to_context ──────────────────────────────────────


class TestApplyTierToContext:
    def test_l0_strips_memory(self):
        result = apply_tier_to_context(
            ContextTier.L0,
            project_memory="Some important context about the project. " * 50,
        )
        assert result["project_memory"] == ""

    def test_l1_truncates_memory(self):
        long_mem = "x" * 5000
        result = apply_tier_to_context(ContextTier.L1, project_memory=long_mem)
        assert len(result["project_memory"]) == 800

    def test_l2_keeps_more_memory(self):
        long_mem = "x" * 5000
        result = apply_tier_to_context(ContextTier.L2, project_memory=long_mem)
        assert len(result["project_memory"]) == 4000

    def test_l0_strips_guidelines(self):
        result = apply_tier_to_context(
            ContextTier.L0, guidelines="Use PG16 with WAL. " * 100
        )
        assert result["guidelines"] == ""

    def test_l2_vision_included(self):
        result = apply_tier_to_context(
            ContextTier.L2, vision="Build a great product"
        )
        assert result["vision"] == "Build a great product"

    def test_l0_vision_excluded(self):
        result = apply_tier_to_context(
            ContextTier.L0, vision="Build a great product"
        )
        assert result["vision"] == ""


# ── tier_savings_estimate ──────────────────────────────────────


class TestTierSavingsEstimate:
    def test_l0_saves_most(self):
        result = tier_savings_estimate(5, ContextTier.L0)
        assert result["savings_pct"] > 80

    def test_l1_saves_some(self):
        result = tier_savings_estimate(5, ContextTier.L1)
        assert result["savings_pct"] > 50

    def test_l2_saves_nothing(self):
        result = tier_savings_estimate(5, ContextTier.L2)
        assert result["savings_pct"] == 0

    def test_zero_skills(self):
        result = tier_savings_estimate(0, ContextTier.L0)
        assert result["saved_tokens"] == 0
