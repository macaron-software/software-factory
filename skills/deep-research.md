---
name: deep-research
version: 1.0.0
description: 'Execute autonomous multi-step research using Google Gemini Deep Research
  Agent. Use for: market analysis, competitive landscaping, literature reviews, technical
  research, due diligence. Takes 2-10 ...'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/sanjay3290/ai-skills/tree/main/skills/deep-research'
  triggers:
  - creating literature reviews
eval_cases:
- id: deep-research-approach
  prompt: How should I approach deep research for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on deep research
  tags:
  - deep
- id: deep-research-best-practices
  prompt: What are the key best practices and pitfalls for deep research?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for deep research
  tags:
  - deep
  - best-practices
- id: deep-research-antipatterns
  prompt: What are the most common mistakes to avoid with deep research?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - deep
  - antipatterns
---
# deep-research

# Gemini Deep Research Skill

Run autonomous research tasks that plan, search, read, and synthesize information into comprehensive reports.

## When to Use This Skill

Use this skill when:
- Performing market analysis
- Conducting competitive landscaping
- Creating literature reviews
- Doing technical research
- Performing due diligence
- Need detailed, cited research reports

## Requirements

- Python 3.8+
- httpx: `pip install -r requirements.txt`
- GEMINI_API_KEY environment variable

## Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/)
2. Set the environment variable:
   ```bash
   export GEMINI_API_KEY=your-api-key-here
   ```
   Or create a `.env` file in the skill directory.

## Usage

### Start a research task
```bash
python3 scripts/research.py --query "Research the history of Kubernetes"
```

### With structured output format
```bash
python3 scripts/research.py --query "Compare Python web frameworks" \
  --format "1. Executive Summary\n2. Comparison Table\n3. Recommendations"
```

### Stream progress in real-time
```bash
python3 scripts/research.py --query "Analyze EV battery market" --stream
```

### Start without waiting
```bash
python3 scripts/research.py --query "Research topic" --no-wait
```

### Check status of running research
```bash
python3 scripts/research.py --status <interaction_id>
```

### Wait for completion
```bash
python3 scripts/research.py --wait <interaction_id>
```

### Continue from previous research
```bash
python3 scripts/research.py --query "Elaborate on point 2" --continue <interaction_id>
```

### List recent research
```bash
python3 scripts/research.py --list
```

## Output Formats

- **Default**: Human-readable markdown report
- **JSON** (`--json`): Structured data for programmatic use
- **Raw** (`--raw`): Unprocessed API response

## Cost & Time

| Metric | Value |
|--------|-------|
| Time | 2-10 minutes per task |
| Cost | $2-5 per task (varies by complexity) |
| Token usage | ~250k-900k input, ~60k-80k output |

## Best Use Cases

- Market analysis and competitive landscaping
- Technical literature reviews
- Due diligence research
- Historical research and timelines
- Comparative analysis (frameworks, products, technologies)

## Workflow

1. User requests research → Run `--query "..."`
2. Inform user of estimated time (2-10 minutes)
3. Monitor with `--stream` or poll with `--status`
4. Return formatted results
5. Use `--continue` for follow-up questions

## Exit Codes

- **0**: Success
- **1**: Error (API error, config issue, timeout)
- **130**: Cancelled by user (Ctrl+C)
