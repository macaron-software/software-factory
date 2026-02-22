"""
Skills Matcher - Semantic similarity matching between context and skills
"""
import numpy as np
import hashlib
from typing import List, Dict, Any, Tuple
from skills_storage import SkillsStorage
from skills_indexer import SkillsIndexer

class SkillsMatcher:
    def __init__(self, storage: SkillsStorage, indexer: SkillsIndexer):
        self.storage = storage
        self.indexer = indexer
        self.similarity_threshold = 0.75
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def hash_context(self, context: Dict[str, Any]) -> str:
        """Generate hash for context caching."""
        key = f"{context.get('task_type', '')}{context.get('domains', [])}{context.get('agent_role', '')}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def find_matching_skills(
        self, 
        context_query: str, 
        context: Dict[str, Any],
        top_k: int = 10,
        use_cache: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Find top-k most relevant skills for given context.
        Returns list of (skill_id, similarity_score) tuples.
        """
        context_hash = self.hash_context(context)
        
        # Check cache first
        if use_cache:
            cached = self.storage.get_cached_skills(context_hash)
            if cached:
                print(f"✅ Using cached skills for context")
                # Return cached skill IDs with placeholder scores
                return [(sid, 0.9) for sid in cached]
        
        # Generate embedding for context
        print(f"🔄 Generating context embedding...")
        context_embedding = self.indexer.generate_embedding(context_query)
        
        # Get all skills with embeddings
        print(f"🔄 Loading skills from database...")
        all_skills = self.storage.get_all_skills_with_embeddings()
        print(f"✅ Loaded {len(all_skills)} skills")
        
        # Calculate similarities
        print(f"🔄 Calculating similarities...")
        similarities = []
        for skill in all_skills:
            score = self.cosine_similarity(context_embedding, skill['embedding'])
            if score >= self.similarity_threshold:
                similarities.append((skill['id'], score))
        
        # Sort by score and take top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_skills = similarities[:top_k]
        
        print(f"✅ Found {len(top_skills)} relevant skills (threshold: {self.similarity_threshold})")
        
        # Cache results
        if use_cache and top_skills:
            skill_ids = [sid for sid, _ in top_skills]
            self.storage.cache_matched_skills(context_hash, skill_ids)
        
        return top_skills
    
    def get_skills_details(self, skill_ids: List[str]) -> List[Dict[str, Any]]:
        """Get full details for list of skill IDs."""
        details = []
        for skill_id in skill_ids:
            skill = self.storage.get_skill_by_id(skill_id)
            if skill:
                details.append(skill)
        return details
