"""
Context Analyzer - Extract key information from mission context
"""
import re
from typing import Dict, List, Any

class ContextAnalyzer:
    def __init__(self):
        self.domain_keywords = {
            'frontend': ['react', 'vue', 'angular', 'ui', 'css', 'html', 'component', 'interface'],
            'backend': ['api', 'server', 'database', 'sql', 'rest', 'graphql', 'endpoint'],
            'devops': ['deploy', 'ci/cd', 'docker', 'kubernetes', 'pipeline', 'infrastructure'],
            'data': ['analytics', 'dataset', 'ml', 'ai', 'model', 'training', 'prediction'],
            'security': ['auth', 'permission', 'vulnerability', 'encryption', 'security'],
            'testing': ['test', 'qa', 'e2e', 'unit', 'integration', 'coverage'],
            'documentation': ['doc', 'readme', 'guide', 'tutorial', 'documentation'],
        }
    
    def analyze(self, mission_description: str, agent_role: str = "") -> Dict[str, Any]:
        """Analyze mission context and extract relevant information."""
        text = mission_description.lower()
        
        # Detect domains
        domains = []
        for domain, keywords in self.domain_keywords.items():
            if any(kw in text for kw in keywords):
                domains.append(domain)
        
        # Extract technical keywords
        tech_keywords = self._extract_technical_keywords(text)
        
        # Determine task type
        task_type = self._determine_task_type(text)
        
        # Generate context summary
        context = {
            'domains': domains,
            'tech_keywords': tech_keywords,
            'task_type': task_type,
            'agent_role': agent_role,
            'full_description': mission_description[:500]
        }
        
        return context
    
    def _extract_technical_keywords(self, text: str) -> List[str]:
        """Extract technical terms and frameworks."""
        # Simple keyword extraction - can be enhanced with NLP
        tech_patterns = [
            r'\b(react|vue|angular|django|flask|spring|express)\b',
            r'\b(python|java|javascript|typescript|go|rust)\b',
            r'\b(aws|azure|gcp|kubernetes|docker)\b',
            r'\b(api|rest|graphql|grpc)\b',
        ]
        
        keywords = []
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.extend(matches)
        
        return list(set(keywords))
    
    def _determine_task_type(self, text: str) -> str:
        """Determine the type of task."""
        if any(word in text for word in ['bug', 'fix', 'error', 'issue']):
            return 'bugfix'
        elif any(word in text for word in ['feature', 'implement', 'add', 'create']):
            return 'feature'
        elif any(word in text for word in ['refactor', 'improve', 'optimize']):
            return 'refactoring'
        elif any(word in text for word in ['test', 'qa', 'validate']):
            return 'testing'
        elif any(word in text for word in ['doc', 'readme', 'guide']):
            return 'documentation'
        else:
            return 'general'
    
    def generate_search_query(self, context: Dict[str, Any]) -> str:
        """Generate a search query for skill matching."""
        parts = []
        
        if context['task_type']:
            parts.append(context['task_type'])
        
        if context['domains']:
            parts.extend(context['domains'][:2])
        
        if context['tech_keywords']:
            parts.extend(context['tech_keywords'][:3])
        
        if context['agent_role']:
            parts.append(context['agent_role'])
        
        return " ".join(parts)
