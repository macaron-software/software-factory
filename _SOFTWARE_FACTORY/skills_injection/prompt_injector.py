"""
Prompt Injector - Inject matched skills into agent system prompts
"""
from typing import List, Dict, Any

class PromptInjector:
    def __init__(self):
        self.max_skills = 10
        self.injection_template = """

## 🎯 Available Expert Skills

You have access to these curated expert skills. Use them when they match the task context:

{skills_section}

**Usage**: Apply these patterns and approaches when they're relevant to your current task. Don't force them if they don't fit naturally.
"""
    
    def format_skill(self, skill: Dict[str, Any], rank: int) -> str:
        """Format a single skill for injection."""
        title = skill.get('title', 'Untitled')
        content = skill.get('content', 'No content available')[:300]  # Limit to 300 chars
        source = skill.get('source', 'unknown')
        repo = skill.get('metadata', {}).get('repo', '')
        
        return f"""{rank}. **{title}**
   Source: {repo if repo else source}
   {content}...
"""
    
    def inject_skills(self, base_prompt: str, matched_skills: List[Dict[str, Any]]) -> str:
        """Inject matched skills into the base system prompt."""
        if not matched_skills:
            return base_prompt
        
        # Limit to max_skills
        skills_to_inject = matched_skills[:self.max_skills]
        
        # Format each skill
        skills_section = "\n".join([
            self.format_skill(skill, i+1) 
            for i, skill in enumerate(skills_to_inject)
        ])
        
        # Create injection block
        injection = self.injection_template.format(skills_section=skills_section)
        
        # Inject at the end of the system prompt
        enhanced_prompt = base_prompt + injection
        
        return enhanced_prompt
    
    def create_skills_summary(self, matched_skills: List[Dict[str, Any]]) -> str:
        """Create a compact summary of injected skills for logging."""
        return ", ".join([s.get('title', 'Unknown') for s in matched_skills[:5]])
