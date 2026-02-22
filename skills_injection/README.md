# Skills Injection System

Automatic enrichment of agents with relevant GitHub skills based on mission context.

## Architecture

```
Mission Context → Context Analyzer → Skills Matcher (Embeddings) → Prompt Injector → Enhanced Agent
```

## Modules

1. **skills_indexer.py** - Generate embeddings using Azure OpenAI
2. **skills_storage.py** - SQLite storage with embeddings as BLOB
3. **skills_loader.py** - Load 1310 GitHub skills and index them
4. **context_analyzer.py** - Extract domains, keywords, task type from mission
5. **skills_matcher.py** - Semantic similarity matching (cosine)
6. **prompt_injector.py** - Inject skills into system prompts
7. **agent_enhancer.py** - Main integration point

## Usage

### 1. Initial Setup (One-time)

```bash
# Load and index all GitHub skills
python skills_loader.py
```

This will:
- Fetch 1310 skills from GitHub repos
- Generate embeddings (takes ~10 min, costs ~$0.50)
- Store in platform.db

### 2. Enhance an Agent

```python
from agent_enhancer import AgentEnhancer

enhancer = AgentEnhancer(
    db_path="/app/data/platform.db",
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    azure_api_key=os.getenv("AZURE_API_KEY")
)

result = enhancer.enhance_agent_prompt(
    base_system_prompt=agent.system_prompt,
    mission_description=mission.description,
    agent_role=agent.role,
    mission_id=mission.id
)

# Use result['enhanced_prompt'] for the agent
```

### 3. Test

```bash
python test_integration.py
```

## Performance

- Initial indexing: ~10 minutes
- Matching per mission: < 2 seconds (with cache)
- Cache hit rate: ~80% for similar missions
- Memory: ~50MB for 1310 skills in RAM

## Configuration

- `similarity_threshold`: 0.75 (adjust in skills_matcher.py)
- `max_skills`: 10 (adjust in prompt_injector.py)
- `batch_size`: 50 (adjust in skills_indexer.py)
