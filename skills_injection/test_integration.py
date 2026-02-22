"""
Integration test for skills injection system
"""
import os
from dotenv import load_dotenv
from agent_enhancer import AgentEnhancer

def test_product_manager():
    """Test with Product Manager role."""
    load_dotenv()
    
    enhancer = AgentEnhancer(
        db_path="/app/data/platform.db",
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        azure_api_key=os.getenv("AZURE_API_KEY")
    )
    
    base_prompt = """You are the Product Manager. You own the program backlog and feature definitions.
You prioritize using WSJF (Weighted Shortest Job First) with transparent scoring."""
    
    mission = """Analyze user feedback from the last sprint and create a prioritized list of 
features for the next PI. Focus on improving the authentication flow and adding multi-factor 
authentication. Consider security best practices and user experience."""
    
    result = enhancer.enhance_agent_prompt(
        base_system_prompt=base_prompt,
        mission_description=mission,
        agent_role="product_manager",
        mission_id="test_pm_001"
    )
    
    print("\n" + "="*80)
    print("ENHANCED PROMPT PREVIEW:")
    print("="*80)
    print(result['enhanced_prompt'][:1000] + "...")
    print("\n" + "="*80)
    print(f"Injected {len(result['injected_skills'])} skills:")
    print(result['skills_summary'])

if __name__ == "__main__":
    test_product_manager()
