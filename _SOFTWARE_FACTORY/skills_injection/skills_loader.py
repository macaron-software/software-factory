"""
Skills Loader - Load and index GitHub skills from platform API
"""
import os
import sys
import json
import requests
from skills_indexer import SkillsIndexer
from skills_storage import SkillsStorage

class SkillsLoader:
    def __init__(self, platform_url: str, db_path: str, azure_endpoint: str, azure_api_key: str):
        self.platform_url = platform_url
        self.indexer = SkillsIndexer(azure_endpoint, azure_api_key)
        self.storage = SkillsStorage(db_path)
    
    def fetch_github_skills_from_api(self) -> list:
        """Fetch GitHub skills from platform /skills API."""
        try:
            # This would need to be adapted to actual API endpoint
            response = requests.get(f"{self.platform_url}/api/skills/export?source=github")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ API returned {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error fetching skills: {e}")
            return []
    
    def load_skills_from_python_api(self):
        """Load skills directly from Python platform module."""
        # Import platform skills module
        sys.path.insert(0, '/app/macaron_platform')
        try:
            from skills import manager as skills_manager
            return skills_manager.get_all_github_skills()
        except:
            return []
    
    def load_and_index_all(self):
        """Load all GitHub skills, generate embeddings, and store."""
        print("🔄 Fetching GitHub skills...")
        skills = self.fetch_github_skills_from_api()
        
        if not skills:
            print("⚠️  No skills fetched, trying direct Python import...")
            skills = self.load_skills_from_python_api()
        
        if not skills:
            print("❌ No skills found!")
            return 0
        
        print(f"✅ Found {len(skills)} skills")
        print(f"🔄 Generating embeddings (this may take a while)...")
        
        indexed_skills = self.indexer.index_skills_batch(skills, batch_size=50)
        
        print(f"🔄 Storing {len(indexed_skills)} skills in database...")
        self.storage.insert_skills_batch(indexed_skills)
        
        count = self.storage.get_skills_count()
        print(f"✅ Total skills in index: {count}")
        
        self.storage.close()
        return count

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/opt/macaron/.env")
    
    loader = SkillsLoader(
        platform_url="http://localhost",
        db_path="/app/data/platform.db",
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        azure_api_key=os.getenv("AZURE_API_KEY")
    )
    
    loader.load_and_index_all()
