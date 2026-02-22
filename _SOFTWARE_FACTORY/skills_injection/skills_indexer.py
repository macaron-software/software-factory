"""
Skills Indexer - Generate semantic embeddings for GitHub skills
Uses Azure OpenAI text-embedding-ada-002
"""
import os
import json
import hashlib
from typing import List, Dict, Any
from openai import AzureOpenAI

class SkillsIndexer:
    def __init__(self, azure_endpoint: str, azure_api_key: str):
        self.client = AzureOpenAI(
            api_version="2024-08-01-preview",
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key
        )
        self.embedding_model = "text-embedding-ada-002"
        self.dimension = 1536
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * self.dimension
    
    def prepare_skill_text(self, skill: Dict[str, Any]) -> str:
        """Prepare skill content for embedding - combine title, description, tags."""
        parts = []
        if skill.get('title'):
            parts.append(f"Title: {skill['title']}")
        if skill.get('description'):
            parts.append(f"Description: {skill['description']}")
        if skill.get('content'):
            # Truncate content to 2000 chars to avoid token limits
            content = skill['content'][:2000]
            parts.append(f"Content: {content}")
        if skill.get('tags'):
            parts.append(f"Tags: {', '.join(skill['tags'])}")
        if skill.get('domain'):
            parts.append(f"Domain: {skill['domain']}")
        
        return "\n".join(parts)
    
    def generate_skill_id(self, skill: Dict[str, Any]) -> str:
        """Generate unique ID for skill based on content hash."""
        content = f"{skill.get('title', '')}{skill.get('repo', '')}{skill.get('path', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def index_skills_batch(self, skills: List[Dict[str, Any]], batch_size: int = 50) -> List[Dict[str, Any]]:
        """Index multiple skills in batches."""
        indexed = []
        
        for i in range(0, len(skills), batch_size):
            batch = skills[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(skills)-1)//batch_size + 1}...")
            
            for skill in batch:
                text = self.prepare_skill_text(skill)
                embedding = self.generate_embedding(text)
                
                indexed_skill = {
                    'id': self.generate_skill_id(skill),
                    'title': skill.get('title', 'Untitled'),
                    'content': skill.get('content', ''),
                    'embedding': embedding,
                    'metadata': {
                        'source': skill.get('source', 'github'),
                        'repo': skill.get('repo', ''),
                        'path': skill.get('path', ''),
                        'tags': skill.get('tags', []),
                        'domain': skill.get('domain', ''),
                    }
                }
                indexed.append(indexed_skill)
        
        return indexed
