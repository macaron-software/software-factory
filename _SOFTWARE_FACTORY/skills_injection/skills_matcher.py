"""
Skills Matcher - Semantic similarity matching between context and skills
"""

import hashlib
from typing import Any

import numpy as np

from .keyword_matcher import KeywordSkillsMatcher
from .skills_indexer import SkillsIndexer
from .skills_storage import SkillsStorage


class SkillsMatcher:
    def __init__(self, storage: SkillsStorage, indexer: SkillsIndexer):
        self.storage = storage
        self.indexer = indexer
        self.similarity_threshold = 0.75
        self.keyword_matcher = KeywordSkillsMatcher(storage)  # Fallback matcher

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def hash_context(self, context: dict[str, Any]) -> str:
        """Generate hash for context caching."""
        key = f"{context.get('task_type', '')}{context.get('domains', [])}{context.get('agent_role', '')}"
        return hashlib.md5(key.encode()).hexdigest()  # noqa: S324

    def find_matching_skills(
        self, context_query: str, context: dict[str, Any], top_k: int = 10, use_cache: bool = True
    ) -> list[tuple[str, float]]:
        """
        Find top-k most relevant skills for given context.
        Returns list of (skill_id, similarity_score) tuples.
        """
        context_hash = self.hash_context(context)

        # Check cache first
        if use_cache:
            cached = self.storage.get_cached_skills(context_hash)
            if cached:
                print("✅ Using cached skills for context")
                # Return cached skill IDs with placeholder scores
                return [(sid, 0.9) for sid in cached]

        # Generate embedding for context
        print("🔄 Generating context embedding...")
        try:
            context_embedding = self.indexer.generate_embedding(context_query)

            # Check if embedding is valid (not all zeros)
            if not context_embedding or all(v == 0.0 for v in context_embedding):
                raise ValueError("Empty or zero embedding returned")

        except Exception as e:
            print(f"⚠️  Embedding generation failed: {e}")
            print("🔄 Falling back to keyword-based matching...")
            return self.keyword_matcher.find_matching_skills(context_query, context, top_k)

        # Get all skills with embeddings
        print("🔄 Loading skills from database...")
        all_skills = self.storage.get_all_skills_with_embeddings()
        print(f"✅ Loaded {len(all_skills)} skills")

        # If no skills have embeddings, fall back to keyword matching
        if not all_skills or all(all(v == 0.0 for v in s.get("embedding", [])) for s in all_skills):
            print("⚠️  No valid embeddings found in database")
            print("🔄 Falling back to keyword-based matching...")
            return self.keyword_matcher.find_matching_skills(context_query, context, top_k)

        # Calculate similarities
        print("🔄 Calculating similarities...")
        similarities = []
        for skill in all_skills:
            score = self.cosine_similarity(context_embedding, skill["embedding"])
            if score >= self.similarity_threshold:
                similarities.append((skill["id"], score))

        # Sort by score and take top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_skills = similarities[:top_k]

        print(
            f"✅ Found {len(top_skills)} relevant skills (threshold: {self.similarity_threshold})"
        )

        # Cache results
        if use_cache and top_skills:
            skill_ids = [sid for sid, _ in top_skills]
            self.storage.cache_matched_skills(context_hash, skill_ids)

        return top_skills

    def get_skills_details(self, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Get full details for list of skill IDs."""
        details = []
        for skill_id in skill_ids:
            skill = self.storage.get_skill_by_id(skill_id)
            if skill:
                details.append(skill)
        return details
