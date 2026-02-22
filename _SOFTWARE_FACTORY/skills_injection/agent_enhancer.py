"""
Agent Enhancer - Main integration point for skills injection
"""
import os
from typing import Dict, Any
from skills_storage import SkillsStorage
from skills_indexer import SkillsIndexer
from context_analyzer import ContextAnalyzer
from skills_matcher import SkillsMatcher
from prompt_injector import PromptInjector

class AgentEnhancer:
    """
    Main class to enhance agents with automatic skills injection.
    """
    def __init__(self, db_path: str, azure_endpoint: str, azure_api_key: str):
        self.storage = SkillsStorage(db_path)
        self.indexer = SkillsIndexer(azure_endpoint, azure_api_key)
        self.analyzer = ContextAnalyzer()
        self.matcher = SkillsMatcher(self.storage, self.indexer)
        self.injector = PromptInjector()
    
    def enhance_agent_prompt(
        self,
        base_system_prompt: str,
        mission_description: str,
        agent_role: str,
        mission_id: str = "",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Enhance an agent's system prompt with relevant skills.
        
        Args:
            base_system_prompt: Original agent system prompt
            mission_description: Description of the mission/task
            agent_role: Role of the agent (e.g., 'product_manager')
            mission_id: Optional mission ID for tracking
            use_cache: Whether to use cached skill matches
        
        Returns:
            Dictionary with enhanced_prompt, injected_skills, and metadata
        """
        print(f"\n🚀 Enhancing agent: {agent_role}")
        print(f"📋 Mission: {mission_description[:100]}...")
        
        # Step 1: Analyze context
        print(f"🔍 Analyzing context...")
        context = self.analyzer.analyze(mission_description, agent_role)
        print(f"   Domains: {context['domains']}")
        print(f"   Task type: {context['task_type']}")
        print(f"   Keywords: {context['tech_keywords'][:5]}")
        
        # Step 2: Generate search query
        search_query = self.analyzer.generate_search_query(context)
        print(f"🔎 Search query: {search_query}")
        
        # Step 3: Find matching skills
        matched_skill_ids = self.matcher.find_matching_skills(
            search_query, 
            context,
            top_k=10,
            use_cache=use_cache
        )
        
        if not matched_skill_ids:
            print(f"⚠️  No relevant skills found (threshold: {self.matcher.similarity_threshold})")
            return {
                'enhanced_prompt': base_system_prompt,
                'injected_skills': [],
                'metadata': context
            }
        
        # Step 4: Get skill details
        skill_ids = [sid for sid, score in matched_skill_ids]
        skills_details = self.matcher.get_skills_details(skill_ids)
        
        print(f"✅ Matched {len(skills_details)} skills:")
        for i, (skill_id, score) in enumerate(matched_skill_ids[:5]):
            skill = next((s for s in skills_details if s['id'] == skill_id), None)
            if skill:
                print(f"   {i+1}. {skill['title']} (score: {score:.3f})")
        
        # Step 5: Inject skills into prompt
        enhanced_prompt = self.injector.inject_skills(base_system_prompt, skills_details)
        
        # Step 6: Track usage
        if mission_id:
            for skill_id, _ in matched_skill_ids:
                self.storage.track_skill_usage(mission_id, agent_role, skill_id, injected=True)
        
        print(f"✅ Enhanced prompt size: {len(enhanced_prompt)} chars (original: {len(base_system_prompt)})")
        
        return {
            'enhanced_prompt': enhanced_prompt,
            'injected_skills': [{'id': sid, 'score': score} for sid, score in matched_skill_ids],
            'skills_summary': self.injector.create_skills_summary(skills_details),
            'metadata': context
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the skills index."""
        total_skills = self.storage.get_skills_count()
        return {
            'total_indexed_skills': total_skills,
            'similarity_threshold': self.matcher.similarity_threshold,
        }

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test enhancement
    enhancer = AgentEnhancer(
        db_path="/app/data/platform.db",
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        azure_api_key=os.getenv("AZURE_API_KEY")
    )
    
    print(enhancer.get_stats())
