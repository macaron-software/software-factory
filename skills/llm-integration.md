---
# SOURCE: Anthropic skills/claude-api (Apache 2.0)
# https://github.com/anthropics/skills/tree/main/skills/claude-api
#
# WHY WE PORTED THIS:
#   Our agents generate code that calls the Anthropic SDK. Without this skill,
#   agents make 5 documented anti-patterns (wrong thinking param, no streaming
#   for large outputs, prefill on Opus 4.6, deprecated output_format, raw string
#   matching tool inputs). Each one causes runtime failures that are hard to debug.
#
# WHAT WE KEPT:
#   - Common Pitfalls (Opus 4.6 behavioural changes) — highest signal section
#   - Surface selection matrix — helps agents pick the right abstraction
#   - Model catalog with exact IDs — prevents guessing/hallucinating IDs
#   - Tool use concepts — agentic loop, structured outputs, tool definitions
#
# WHAT WE DROPPED:
#   - Language detection logic (we're Python-centric)
#   - Per-language directories (python/, typescript/, etc.) — too verbose
#   - Agent SDK patterns (we have our own platform agent framework)
#   - WebFetch URLs / live-sources.md (agents should use docs directly if needed)
#
# LICENSE: Apache 2.0 — free to adapt with attribution

name: llm-integration
version: "1.1.0"
description: >
  Guidance for building code that calls the Anthropic API or SDK.
  Covers surface selection, model defaults, Opus 4.6 behavioural changes,
  tool use patterns, structured outputs, and common pitfalls.
  Activate when: writing code that imports `anthropic`, builds tool-use loops,
  handles streaming, or integrates with the Anthropic Messages API.

# EVAL CASES — philschmid.de/testing-skills format
# WHY: LLM integration skill must prevent 5 documented anti-patterns (wrong
# thinking param, no streaming for large outputs, deprecated output_format,
# raw string tool inputs, infinite loops). Each causes runtime failures.
eval_cases:
  - id: structured-output-python
    prompt: "Write Python code to call Claude with structured output (return a User with name and age fields)."
    should_trigger: true
    checks:
      - "regex:messages\\.create|client\\.messages|parse\\("
      - "regex:json_schema|schema|additionalProperties|properties"
      - "not_regex:output_format\\s*=|output_format.*:.*[\"']|\"output_format\"|'output_format'|budget_tokens\\s*=|\"budget_tokens\""
      - "regex:import anthropic|from anthropic|anthropic\\.Anthropic"
      - "length_min:80"
    expectations:
      - "uses client.messages.create() or client.messages.parse() — not raw HTTP"
      - "defines a schema with name/age fields using json_schema or Pydantic"
      - "does NOT use deprecated output_format or budget_tokens"
    tags: [structured-output, python]

  - id: agentic-tool-loop
    prompt: "Write a Python agentic loop with tool calling (one tool: get_weather(city) -> str). Stop when Claude says end_turn."
    should_trigger: true
    checks:
      - "regex:stop_reason|end_turn|tool_use"
      - "regex:tool_use|tool_result|content"
      - "regex:json\\.loads|\\[\"input\"\\]|input\\[|tool\\.input|\\.input"
      - "regex:while|loop|continue|for.*message"
      - "regex:max_iter|max_cont|max_turn|MAX_|limit|guard|break"
      - "length_min:100"
    expectations:
      - "implements loop that continues until stop_reason == 'end_turn'"
      - "appends full response.content to message history (preserves tool_use blocks)"
      - "calls json.loads() on tool inputs — not raw string matching"
      - "has a max_iterations/max_continuations guard to prevent infinite loops"
    tags: [tool-use, agentic-loop]

  - id: streaming-large-response
    prompt: "Stream a Claude response that could be up to 8000 tokens. Show correct Python code."
    should_trigger: true
    checks:
      - "regex:\\.stream|stream=True|stream\\("
      - "regex:get_final_message|finalMessage|text_stream|stream_text"
      - "not_regex:messages\\.create\\(.*max_tokens.*[89][0-9]{3}|messages\\.create\\(.*max_tokens.*[1-9][0-9]{4}"
      - "length_min:50"
    expectations:
      - "uses .stream() context manager OR streaming=True — not direct messages.create() for large outputs"
      - "collects final message with get_final_message() or equivalent"
    tags: [streaming]
---

# LLM Integration Skill

Guidance for writing code that calls the Anthropic API. Use this skill when
generating code that imports `anthropic`, `@anthropic-ai/sdk`, or integrates
with the Claude Messages API.

---

## Model Defaults

Unless requested otherwise, default to:

```python
model = "claude-opus-4-6"          # Most capable; agents + coding
thinking = {"type": "adaptive"}    # Recommended for Opus 4.6 + Sonnet 4.6
                                   # Do NOT use budget_tokens (deprecated)
stream = True                      # Required for large max_tokens; prevents timeouts
```

### Model Catalog

| Model | Alias | Context | Max Output | Notes |
|---|---|---|---|---|
| Claude Opus 4.6 | `claude-opus-4-6` | 200K (1M β) | 128K | Best for agents/coding; streaming required for large outputs |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 200K (1M β) | 64K | Speed+intelligence balance |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | 64K | Fastest; simple tasks |

**Never guess or construct model IDs** — use exact aliases above. Incorrect IDs cause API errors.

---

## Which Surface to Use

> Start simple. Single API calls handle most use cases. Only reach for agents when the task genuinely requires open-ended, model-driven exploration.

| Use Case | Surface |
|---|---|
| Single Q&A, classification, summarization, extraction | Direct `messages.create()` |
| Chat UI / real-time display | Streaming (`client.messages.stream()`) |
| Function calling, code execution, structured data | Tool use (Tool Runner recommended) |
| Non-latency-sensitive batch jobs (50% cost) | Batches API |
| File uploads reused across requests | Files API |
| Open-ended agentic tasks (web, files, terminal) | Agent SDK (Python/TS only) |

---

## Common Pitfalls (Opus 4.6)

These are **breaking changes** in Opus 4.6 and Sonnet 4.6. Getting them wrong causes runtime errors.

### 1. Thinking: use `adaptive`, not `budget_tokens`

```python
# ✅ CORRECT — Opus 4.6 + Sonnet 4.6
thinking = {"type": "adaptive"}

# ❌ WRONG — budget_tokens is deprecated on Opus 4.6 + Sonnet 4.6
thinking = {"type": "enabled", "budget_tokens": 10000}  # → error
```

For older models (Opus 4.5, Opus 4.1): `budget_tokens` is still required and must be < `max_tokens` (minimum 1024).

### 2. No assistant prefill on Opus 4.6

```python
# ❌ WRONG — prefilling the last assistant message returns HTTP 400 on Opus 4.6
messages = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "Here is the JSON:"},  # → 400 error
]

# ✅ CORRECT — use structured outputs or system prompt to control format
client.messages.parse(
    model="claude-opus-4-6",
    output_schema=MySchema,  # enforced by output_config.format
    ...
)
```

### 3. Streaming required for large max_tokens

```python
# ❌ WRONG — HTTP timeout if max_tokens is large
response = client.messages.create(model="claude-opus-4-6", max_tokens=8000, ...)

# ✅ CORRECT — use streaming + get_final_message()
with client.messages.stream(model="claude-opus-4-6", max_tokens=8000, ...) as stream:
    response = stream.get_final_message()  # blocks until complete
```

Opus 4.6 supports up to 128K `max_tokens`. Use streaming for anything non-trivial.

### 4. Structured outputs: use `output_config`, not `output_format`

```python
# ❌ WRONG — deprecated parameter
response = client.messages.create(output_format={"type": "json_object"}, ...)

# ✅ CORRECT — canonical API parameter (all models)
response = client.messages.create(
    output_config={"format": {"type": "json_schema", "json_schema": {...}}},
    ...
)

# ✅ BEST — use .parse() for auto-validation
response = client.messages.parse(model="claude-opus-4-6", output_schema=MySchema, ...)
```

### 5. Tool inputs: always `json.loads()`, never raw string matching

```python
# ❌ WRONG — JSON escaping changes in Opus 4.6 (Unicode, forward-slash)
if '"action": "delete"' in tool_input:  # fragile, breaks on Opus 4.6

# ✅ CORRECT
parsed = json.loads(tool_input)
if parsed.get("action") == "delete":
```

### 6. Agentic loop: ALWAYS set a max_continuations guard

```python
# ❌ WRONG — infinite loop if Claude keeps calling tools
while True:
    response = client.messages.create(...)
    if response.stop_reason == "end_turn":
        break

# ✅ CORRECT — hard limit prevents runaway loops
MAX_TURNS = 10
for _ in range(MAX_TURNS):
    response = client.messages.create(...)
    if response.stop_reason == "end_turn":
        break
# If we exit the loop without end_turn: handle gracefully (return partial result or raise)
```

---

## Tool Use

### Tool Definition (manual, non-SDK)

```python
tool = {
    "name": "get_weather",
    "description": "Get current weather. Claude uses this description to decide when to call it — be specific.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City and state, e.g. Paris, FR"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["location"],
        "additionalProperties": False,  # required for structured outputs
    },
}
```

**Best practices:**
- Use descriptive names (`get_weather` not `weather`)
- Write detailed descriptions — Claude uses them to decide when/how to call
- Use `enum` for fixed-value parameters
- Mark truly required params in `required`; make others optional with defaults
- Keep the tool set focused — too many tools confuses the model

### Tool Choice

| Value | Behavior |
|---|---|
| `{"type": "auto"}` | Claude decides (default) |
| `{"type": "any"}` | Must use at least one tool |
| `{"type": "tool", "name": "..."}` | Must use this specific tool |
| `{"type": "none"}` | Cannot use tools |

Add `"disable_parallel_tool_use": true` to force one tool per turn.

### Agentic Loop (manual)

```python
messages = [{"role": "user", "content": user_query}]
max_continuations = 5

for _ in range(max_continuations):
    response = client.messages.create(model="claude-opus-4-6", tools=tools, messages=messages)

    # Always append full response.content to preserve tool_use blocks
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "end_turn":
        break

    # Handle server-side tool pause (web search, code execution hit loop limit)
    if response.stop_reason == "pause_turn":
        # Re-send as-is — API resumes automatically from tool_use block
        continue

    # Execute all tool calls, collect results
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = execute_tool(block.name, json.loads(block.input))
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

    messages.append({"role": "user", "content": tool_results})
```

**Use Tool Runner instead when you don't need fine-grained control** — it handles this loop automatically.

---

## Structured Outputs

```python
from pydantic import BaseModel
import anthropic

class Analysis(BaseModel):
    summary: str
    sentiment: str
    score: float

client = anthropic.Anthropic()
response = client.messages.parse(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Analyse this review: ..."}],
    output_schema=Analysis,
)
result: Analysis = response.parsed
```

**Supported models:** Opus 4.6, Sonnet 4.6, Haiku 4.5, Opus 4.5, Opus 4.1.

**JSON Schema constraints:**
- ✅ Supported: `object`, `array`, `string`, `integer`, `number`, `boolean`, `null`, `enum`, `const`, `anyOf`, `allOf`, `$ref`
- ❌ Not supported: recursive schemas, `minimum`/`maximum`, `minLength`/`maxLength`
- ⚠️ Always set `additionalProperties: false` on objects

**Notes:**
- First request with a new schema has one-time compilation cost (24h cache after)
- Incompatible with: Citations API, message prefilling
- If `stop_reason == "refusal"`: safety refusal, output may not match schema
- If `stop_reason == "max_tokens"`: output incomplete — increase `max_tokens`

---

## Don't Reimplement SDK Features

```python
# ❌ WRONG — reimplementing what the SDK already does
class ChatMessage:
    role: str
    content: str  # duplicates Anthropic.MessageParam

result = new Promise((resolve) => {  # reimplementing finalMessage()
    stream.on("message", resolve)
})

# ✅ CORRECT — use SDK types and helpers
from anthropic import Anthropic
from anthropic.types import MessageParam, Tool, ToolUseBlock

stream.get_final_message()          # Python
await stream.finalMessage()         # TypeScript
```

Use typed exception classes, not string matching:
```python
# ❌ if "rate limit" in str(e):
# ✅
except anthropic.RateLimitError:
    ...
except anthropic.APIStatusError as e:
    print(e.status_code, e.message)
```

---

## Output / Reports

For tasks producing documents, reports, or visualizations:
- Code execution sandbox has `python-docx`, `python-pptx`, `matplotlib`, `pillow`, `pypdf` pre-installed
- Claude can generate formatted files (DOCX, PDF, charts) via the Files API
- Prefer structured file output over plain stdout for "report"-type requests
- Never truncate inputs silently — if content exceeds context, notify the user and discuss options (chunking, summarization)

---

## MiniMax-M2.7 — Tool Calling (SF Platform specific)

**⚠️ BUG RÉSOLU (2026-03-07) — Historique pour ne pas régresser**

### Problème
MiniMax-M2.7 supporte nativement le format OpenAI tool_calls/tool (voir https://platform.minimax.io/docs/guides/text-m2-function-call).
Le code SF convertissait à tort les messages d'historique en texte plat :
```
# ❌ CE QUE LE CODE FAISAIT (mauvais — cause hallucinations)
assistant: "[Appel outils: code_write]"        # sans les arguments !
user:      "[Résultat de code_write]:\n{output}"

# ✅ CE QUE M2.7 ATTEND (format natif)
assistant: {tool_calls: [{name: code_write, arguments: {path, content}}]}
tool:      {tool_call_id: "...", content: output}
```

Sans les arguments dans l'historique, l'agent ne sait plus ce qu'il a écrit → il hallucine
"j'ai écrit INCEPTION.md" sans pouvoir vérifier → HALLUCINATION/ECHO/XXX escalations.

### Fix (platform/llm/client.py)
- Mangling text désactivé pour M2.7 (actif uniquement pour `model == "MiniMax-M2.7"`)
- `tool_choice = "required"` au lieu de `"auto"` (M2.7 supporte required)
- `parallel_tool_calls = False` (appels séquentiels plus fiables)

### Paramètres M2.7 recommandés
```python
body["tool_choice"] = "required"          # force l'appel d'outil
body["parallel_tool_calls"] = False       # séquentiel
body["max_tokens"] = max(max_tokens, 16000)  # pour les <think> blocks
# temperature: 0.1-0.3 pour agents code (déjà correct dans agent store)
```

### M2.1 legacy (garder mangling)
MiniMax-M2.7 rejette `role: "tool"` → convertir en `role: "user"`.
Vérifier `model == "MiniMax-M2.7"` avant d'activer le workaround.
