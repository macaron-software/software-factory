"""
Keyword-based Skills Matcher - Fallback when embeddings unavailable
"""

import re
from typing import Any


class KeywordSkillsMatcher:
    """
    Simple keyword-based matching as fallback when Azure embeddings unavailable.
    Uses TF-IDF-like scoring based on keyword frequency and relevance.
    """

    def __init__(self, storage):
        self.storage = storage
        self.similarity_threshold = 0.3  # Lower threshold for keyword matching

        # Domain-specific keyword weights
        self.domain_weights = {
            "frontend": [
                "react",
                "vue",
                "angular",
                "css",
                "html",
                "ui",
                "ux",
                "component",
                "responsive",
            ],
            "backend": [
                "api",
                "database",
                "sql",
                "server",
                "endpoint",
                "rest",
                "graphql",
                "microservice",
            ],
            "devops": [
                "docker",
                "kubernetes",
                "k8s",
                "ci/cd",
                "deploy",
                "cloud",
                "aws",
                "azure",
                "terraform",
            ],
            "data": [
                "etl",
                "pipeline",
                "analytics",
                "bigquery",
                "airflow",
                "spark",
                "warehouse",
                "dbt",
            ],
            "security": [
                "auth",
                "oauth",
                "jwt",
                "encryption",
                "ssl",
                "mfa",
                "2fa",
                "vulnerability",
                "audit",
            ],
            "testing": [
                "test",
                "jest",
                "pytest",
                "e2e",
                "unit",
                "integration",
                "qa",
                "playwright",
                "cypress",
            ],
            "mobile": ["ios", "android", "react-native", "flutter", "swift", "kotlin", "mobile"],
            "documentation": [
                "docs",
                "readme",
                "guide",
                "tutorial",
                "api-docs",
                "swagger",
                "openapi",
            ],
        }

        # Task type keywords
        self.task_keywords = {
            "feature": ["implement", "build", "create", "add", "develop"],
            "bug": ["fix", "debug", "resolve", "issue", "error", "problem"],
            "refactor": ["refactor", "improve", "optimize", "clean", "restructure"],
            "documentation": ["document", "write", "explain", "describe", "guide"],
            "security": ["secure", "protect", "vulnerability", "audit", "compliance"],
            "performance": ["optimize", "performance", "speed", "cache", "scale"],
        }

    def extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        # Convert to lowercase
        text = text.lower()

        # Remove special chars but keep hyphens and underscores
        text = re.sub(r"[^\w\s\-_]", " ", text)

        # Split into words
        words = text.split()

        # Filter out common stop words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
        }

        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        return keywords

    def calculate_keyword_score(
        self, skill: dict[str, Any], context_keywords: list[str], domains: list[str], task_type: str
    ) -> float:
        """Calculate relevance score based on keyword matching."""
        score = 0.0

        # Extract skill text
        skill_text = f"{skill.get('title', '')} {skill.get('content', '')}".lower()
        skill_keywords = self.extract_keywords(skill_text)

        # 1. Direct keyword matches (40% weight)
        keyword_matches = set(context_keywords) & set(skill_keywords)
        if skill_keywords:
            keyword_score = len(keyword_matches) / len(set(context_keywords + skill_keywords))
            score += keyword_score * 0.4

        # 2. Domain matching (30% weight)
        domain_score = 0.0
        for domain in domains:
            domain_kw = self.domain_weights.get(domain, [])
            domain_matches = sum(1 for kw in domain_kw if kw in skill_text)
            if domain_kw:
                domain_score += domain_matches / len(domain_kw)
        if domains:
            domain_score /= len(domains)
        score += domain_score * 0.3

        # 3. Task type matching (20% weight)
        task_kw = self.task_keywords.get(task_type, [])
        task_matches = sum(1 for kw in task_kw if kw in skill_text)
        if task_kw:
            task_score = task_matches / len(task_kw)
            score += task_score * 0.2

        # 4. Boost for exact phrase matches (10% weight)
        for keyword in context_keywords:
            if len(keyword) > 4 and keyword in skill_text:
                score += 0.1

        return min(score, 1.0)  # Cap at 1.0

    def find_matching_skills(
        self, context_query: str, context: dict[str, Any], top_k: int = 10
    ) -> list[tuple[str, float]]:
        """
        Find top-k most relevant skills using keyword matching.
        Returns list of (skill_id, score) tuples.
        """
        print("🔍 Keyword-based matching (fallback mode)...")

        # Extract context information
        domains = context.get("domains", [])
        task_type = context.get("task_type", "general")
        context_keywords = self.extract_keywords(context_query)

        print(f"   Keywords: {', '.join(context_keywords[:10])}...")
        print(f"   Domains: {', '.join(domains)}")
        print(f"   Task type: {task_type}")

        # Get all skills from database
        all_skills = self.storage.get_all_skills()
        print(f"   Loaded {len(all_skills)} skills from database")

        # Calculate scores for each skill
        scored_skills = []
        for skill in all_skills:
            score = self.calculate_keyword_score(skill, context_keywords, domains, task_type)
            if score >= self.similarity_threshold:
                scored_skills.append((skill["id"], score))

        # Sort by score and take top-k
        scored_skills.sort(key=lambda x: x[1], reverse=True)
        top_skills = scored_skills[:top_k]

        print(
            f"✅ Found {len(top_skills)} relevant skills (threshold: {self.similarity_threshold})"
        )

        return top_skills

    def get_skills_details(self, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Get full details for list of skill IDs."""
        details = []
        for skill_id in skill_ids:
            skill = self.storage.get_skill_by_id(skill_id)
            if skill:
                details.append(skill)
        return details
