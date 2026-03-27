# SFEngine Rust Orchestration Patterns - Complete Coding Style Guide

## Overview

This document contains the **COMPLETE** coding styles used in the SFEngine orchestration layer for the simple-sf project. All orchestration patterns follow these conventions consistently.

**Reference repository path:**
```
/Users/sylvain/_MACARON-SOFTWARE/simple-sf/SFEngine/src/engine/
```

**10 total files:**
- mod.rs, types.rs, executor.rs, patterns.rs, patterns_ext.rs
- discussion.rs, mission.rs, phase.rs, workflow.rs, build.rs, resilience.rs

---

## Universal Pattern Function Signature

**Every pattern function has this exact signature:**

```rust
pub(crate) async fn run_<pattern_name>(
    agent_ids: &[&str],          // ALWAYS slice, NEVER Vec<String>
    task: &str,                  // The phase task/prompt
    phase: &str,                 // Phase name (e.g., "dev", "qa")
    workspace: &str,             // File path to project workspace
    mission_id: &str,            // UUID of current mission
    phase_id: &str,              // UUID of phase execution
    on_event: &EventCallback,    // Arc<dyn Fn(&str, AgentEvent) + Send + Sync>
) -> Result<String, String>      // Returns text output or error message
```

### Key Rules:
1. **agent_ids must be `&[&str]`** - Never use `Vec<String>` for inputs
2. **Result<String, String>** - All errors converted to String
3. **pub(crate)** - Visible within crate only
4. **async** - All pattern functions are async

---

## Complete Call Sequence for Executing Patterns

### Step 1: Retrieve Agents

```rust
let mut agents_data: Vec<Agent> = Vec::new();
for id in agent_ids {
    if let Some(a) = agents::get_agent(id) {  // Option → check for None
        agents_data.push(a);
    }
}
if agents_data.is_empty() {
    return Err("No agents found".into());  // .into() converts to String
}
```

**Key points:**
- `agents::get_agent()` returns `Option<Agent>`
- Always check with `if let Some()`
- Validate that at least one agent exists

### Step 2: Get Protocol for Agent

```rust
let protocol = protocols::protocol_for_role(&agent.role, phase);
// Returns: String containing role-specific directives
// Example: "Developer" role in "dev" phase → dev-specific instructions
```

### Step 3: Build System Prompt (3-Part Pattern)

```rust
let system = format!(
    "{}\n\n{}\n\n{}",
    agent.persona,                                      // Part 1: Agent's personality
    protocols::protocol_for_role(&agent.role, phase), // Part 2: Role-specific rules
    STYLE_RULES                                         // Part 3: Format enforcement
);
```

**STYLE_RULES constant (from types.rs):**
```rust
pub(crate) const STYLE_RULES: &str = 
"RÈGLES DE FORMAT : ZÉRO emoji, ZÉRO émoticône, ZÉRO caractère Unicode décoratif. \
Utilise uniquement du texte, des tirets (-), des pipes (|), des étoiles (*) pour la mise en forme. \
Sois structuré avec des titres en **gras** et des listes à tirets.";
```

**Important:** 
- STYLE_RULES is in FRENCH
- Enforces: No emoji, no decorative unicode, structural formatting
- Same STYLE_RULES appended to EVERY system prompt

### Step 4: Call executor::run_agent()

```rust
let result = executor::run_agent(
    &agent.id,                           // String reference
    &agent.name,                         // String reference  
    &agent.persona,                      // String reference
    &agent.role,                         // String reference
    &task,                               // The prompt/task text
    workspace,                           // File path reference
    mission_id,                          // UUID reference
    phase_id,                            // UUID reference
    Some(protocol),                      // IMPORTANT: Pass protocol
    on_event,                            // Callback reference
).await?;                                // IMPORTANT: Must .await and ?
```

**Characteristics:**
- Returns `Result<String, String>` - the agent's text output or error
- Optional protocol injects role-specific directives into system prompt
- All parameters passed as references (not owned)
- `.await?` - Propagates errors up with operator

### Step 5: Check L0 Adversarial Guard

```rust
let guard_result = guard::check_l0(&result, &agent.role, &[]);
if !guard_result.passed {
    on_event(&agent.id, AgentEvent::Response {
        content: format!("⚠️ Quality check: {} (score: {})", 
                        guard_result.issues.join(", "), 
                        guard_result.score),
    });
}
// NOTE: Execution continues even if guard fails (warnings, not blocking)
```

**Guard behavior:**
- Returns `GuardResult` with fields:
  - `passed: bool` - Did output pass guard?
  - `score: i32` - Quality score (0-100)
  - `issues: Vec<String>` - List of issues found
- Called AFTER executor::run_agent() returns
- Failures are warnings, not blocking errors
- Allows execution to continue (resilience principle)

### Step 6: Emit Events to Swift UI

```rust
// Status indicator
on_event(&agent.id, AgentEvent::Thinking);

// Response message
on_event(&agent.id, AgentEvent::Response {
    content: format!("⚠️ Quality: {} (score: {})", 
                    guard_result.issues.join(", "), 
                    guard_result.score),
});

// Rich JSON for discussion UI (types.rs emit_rich function)
on_event(&agent.id, AgentEvent::Response {
    content: json_string,  // Contains agent_name, role, to_agents[], round
});
```

### Step 7: Store Agent Message in Database

```rust
store_agent_msg(mission_id, phase_id, &agent.id, &agent.name, 
                "assistant", &content, None);
```

**Function signature (from types.rs):**
```rust
pub(crate) fn store_agent_msg(
    mission_id: &str,
    phase_id: &str,
    agent_id: &str,
    agent_name: &str,
    role: &str,           // "assistant" or "tool"
    content: &str,
    tool: Option<&str>    // Tool name if applicable
)
```

### Step 8: Combine and Return Outputs

```rust
Ok(outputs.join("\n\n---\n\n"))  // Separator between agent outputs
```

---

## AgentEvent Enum - Complete Reference

```rust
pub enum AgentEvent {
    Thinking,                                      // No data, just indicator
    Reasoning { active: bool },                   // Extended thinking (o1 models)
    ToolCall { tool: String, args: String },     // Tool being invoked
    ToolResult { tool: String, result: String }, // Tool result
    Response { content: String },                // Final text response (MOST USED)
    ResponseChunk { content: String },           // Streaming chunk (executor only)
    Error { message: String },                   // Error condition
}
```

### Most Common Usage:

```rust
// Just thinking indicator
on_event(&agent.id, AgentEvent::Thinking);

// Response with content (text or JSON)
on_event(&agent.id, AgentEvent::Response { 
    content: "Output text or JSON string".into() 
});

// Error
on_event(&agent.id, AgentEvent::Error { 
    message: format!("Failed to: {}", reason) 
});
```

---

## LLM Communication Patterns

### In Patterns Layer (Non-Streaming)

```rust
let result = llm::chat_completion(
    &[LLMMessage { role: "user".into(), content: prompt_text }],
    Some(&system_prompt),
    None,  // No tools in pattern layer
).await?;

let content = strip_emoji(&result.content.unwrap_or_default());
```

**Characteristics:**
- Uses non-streaming `chat_completion()`
- Single user message in array
- System prompt is `Option<&str>` (Some or None)
- Third param is `Option<Vec<Tool>>` (None in patterns)
- Returns response with `content: Option<String>`
- Must `.unwrap_or_default()` the content

### In Executor Layer (Streaming with Tools)

```rust
let resp = llm::chat_completion_streaming(
    &messages,                                    // Vec<LLMMessage>
    Some(&system),                                // System prompt
    if tool_schemas.is_empty() { 
        None 
    } else { 
        Some(&tool_schemas) 
    },
    chunk_cb,                                     // OnChunkFn callback
    Some(reasoning_cb),                           // OnReasoningFn callback
).await?;
```

**Tool-calling loop in executor.rs:**
- MAX_ROUNDS = 100 (no artificial limit, LLM decides)
- For each round:
  1. Emit `AgentEvent::Thinking`
  2. Call `llm::chat_completion_streaming()`
  3. If tool_calls returned:
     - Emit `AgentEvent::ToolCall { tool, args }`
     - Execute tool via `tools::execute_tool()`
     - Emit `AgentEvent::ToolResult { tool, result }`
     - Append tool result to message history
     - Continue to next round
  4. If text response:
     - Only emit Response if streaming didn't already deliver (check `chunked` flag)
     - Store in DB
     - Return result
  5. Sliding window: Keep messages <= 30 (keep first + recent 20)

---

## Protocol Injection Pattern

```rust
let protocol = protocols::protocol_for_role(&agent.role, phase);
// Gets: Role + phase specific instructions
```

**System prompt construction with protocol:**

```rust
let system = format!(
    "{}\n\n{}\n\n{}",
    agent.persona,                                      // From agent catalog
    protocols::protocol_for_role(&agent.role, phase), // Role-specific
    STYLE_RULES                                         // Format enforcement
);
```

**Protocol purpose:**
- Inject role-specific behavior (e.g., "Developer" vs "QA")
- Phase-aware (e.g., different instructions for "dev" vs "qa" phase)
- Examples: coding standards, testing requirements, review criteria

---

## Error Handling Patterns

### Pattern 1: Option → Result with Context

```rust
let agent = agents::get_agent(agent_id)
    .ok_or(format!("Agent {} not found", agent_id))?;
```

### Pattern 2: Result Propagation with ?

```rust
let result = executor::run_agent(...).await?;
```

### Pattern 3: Match on Result

```rust
match result {
    Ok(output) => { /* handle success */ }
    Err(e) => return Err(format!("Context: {}", e)),
}
```

### Pattern 4: Convert to String with .into()

```rust
return Err("No agents found".into());  // Converts &str to String
```

### Pattern 5: Logging (Server-Side Only)

```rust
eprintln!("[db] Failed to store agent message: {}", e);
eprintln!("[engine] Phase {} failed (attempt {}): {}", phase, attempt + 1, e);
```

**Format:** `eprintln!("[MODULE] message")`
- Bracketed module prefix for context
- Only for server-side debugging
- Never reaches client/Swift

---

## Guard Check Pattern (L0 Adversarial)

```rust
let guard_result = guard::check_l0(&result, &agent.role, &[]);
if !guard_result.passed {
    on_event(&agent.id, AgentEvent::Response {
        content: format!("⚠️ Quality: {} (score: {})", 
                        guard_result.issues.join(", "), 
                        guard_result.score),
    });
}
// Execution continues regardless of guard failure
```

**GuardResult structure:**
```rust
struct GuardResult {
    passed: bool,           // Did output pass all checks?
    score: i32,             // Quality score (0-100)
    issues: Vec<String>,    // List of problems found
}
```

**Key characteristics:**
- Always called after executor::run_agent()
- Warnings only, never blocking
- Allows resilience (execution continues)
- Typically skipped/ignored in actual execution (informational)

---

## Emoji Stripping & Content Handling

### Function: strip_emoji()

```rust
pub(crate) fn strip_emoji(text: &str) -> String {
    text.chars().filter(|c| {
        let cp = *c as u32;
        cp < 0x2600 ||                    // ASCII + Latin + punctuation
        (cp >= 0x3000 && cp < 0xFE00) ||  // CJK
        (cp >= 0xFF00 && cp < 0xFFF0)     // Fullwidth forms
    }).collect::<String>()
    .lines()
    .map(|l| l.trim_end())
    .collect::<Vec<_>>()
    .join("\n")
}
```

**Usage:**
```rust
let content = strip_emoji(&result.content.unwrap_or_default());
```

**Effect:**
- Removes emoji (Unicode > 0x2600)
- Keeps ASCII, Latin extended, CJK, punctuation
- Trims trailing whitespace per line
- Enforced via STYLE_RULES in system prompt

---

## Context Truncation Pattern

```rust
pub(crate) fn truncate_ctx(s: &str, max: usize) -> String {
    if s.len() <= max { 
        s.to_string() 
    } else { 
        format!("{}…", &s[..max])  // Add ellipsis if truncated
    }
}
```

**Usage:**
```rust
let truncated = truncate_ctx(&output, 1500);  // Returns String
```

**Used to keep context windows manageable in discussions.**

---

## Database Storage Pattern

### Direct DB Access

```rust
if let Err(e) = db::with_db(|conn| {
    conn.execute(
        "INSERT INTO agent_messages (...) VALUES (?1, ?2, ?3, ...)",
        params![mission_id, phase_id, agent_id, agent_name, content],
    )
}) {
    eprintln!("[db] Failed to store agent message: {}", e);
}
```

**Pattern:**
- `db::with_db()` takes closure with database connection
- `conn.execute()` for INSERT/UPDATE
- `params![]` macro for parameterized queries
- Error logged with `eprintln!()`, not propagated

### Helper Functions

```rust
// Store agent message
store_agent_msg(mission_id, phase_id, &agent.id, &agent.name, 
                "assistant", &content, None);

// Store discussion message
store_discussion_msg(&session_id, &agent.id, &agent.name, 
                    &agent.role, round, &content);
```

---

## Event Emission for Rich UI (Discussion Flows)

### emit_rich() Function (types.rs, lines 79-90)

```rust
pub(crate) fn emit_rich(on_event: &EventCallback, agent: &Agent, 
                        content: &str, to_agents: &[&str], round: usize) {
    let to_json: Vec<String> = to_agents.iter()
        .map(|s| format!("\"{}\"", s))
        .collect();
    let json = format!(
        r#"{{"content":{},"agent_name":"{}","role":"{}",
            "message_type":"response","to_agents":[{}],"round":{}}}"#,
        serde_json::to_string(content).unwrap_or_else(...),
        agent.name.replace('"', "\\\""),
        agent.role.replace('"', "\\\""),
        to_json.join(","),
        round,
    );
    on_event(&agent.id, AgentEvent::Response { content: json });
}
```

**Usage (in discussion.rs):**
```rust
emit_discuss(agent, &content, "response", &other_ids, round);
```

**JSON structure:**
```json
{
  "content": "agent's message text",
  "agent_name": "Alice",
  "role": "Developer",
  "message_type": "response",
  "to_agents": ["bob-id", "charlie-id"],
  "round": 1
}
```

---

## Key Constants

```rust
// From types.rs
pub(crate) const PHASE_TIMEOUT_SECS: u64 = 900;      // 15 minutes
pub(crate) const MAX_NETWORK_ROUNDS: usize = 3;      // Discussion rounds
pub(crate) const CONTEXT_BUDGET: usize = 12000;      // Token budget
pub(crate) const MAX_PHASE_RETRIES: usize = 3;       // Retry attempts

// From executor.rs  
const MAX_ROUNDS: usize = 100;                       // Tool-call rounds

// Pattern-specific
const MAX_LOOP_ITERATIONS: usize = 5;                // Writer-reviewer loop
const MAX_GATE_LOOPBACKS: usize = 3;                 // Gate retry attempts
```

---

## Pattern Implementation Summary

### Basic Patterns (patterns.rs)

| Pattern | Purpose | Loop Type |
|---------|---------|-----------|
| **network** | Discussion rounds (leader + debaters) | Fixed rounds |
| **sequential** | Agents execute in sequence | For loop over agents |
| **parallel** | All agents on same task independently | For loop (conceptually parallel) |
| **solo** | Single agent executes | No loop |
| **loop** | Writer ↔ Reviewer with iterations | While with MAX_LOOP_ITERATIONS |

### Advanced Patterns (patterns_ext.rs)

| Pattern | Purpose |
|---------|---------|
| **hierarchical** | Manager decomposes → workers execute → manager re-integrates |
| **aggregator** | All work independently → aggregator consolidates |
| **router** | First agent routes to best specialist |
| **wave** | Agents in dependency waves (~3 per wave), parallel within waves |

### Dispatcher (patterns.rs)

```rust
pub(crate) async fn run_pattern(
    agent_ids: &[&str],
    task: &str,
    phase: &str,
    pattern: &str,
    workspace: &str,
    mission_id: &str,
    phase_id: &str,
    on_event: &EventCallback,
) -> Result<String, String> {
    match pattern {
        "network" | "debate" => run_network(...).await,
        "parallel" => run_parallel(...).await,
        "solo" => run_solo(...).await,
        "loop" | "adversarial-pair" => run_loop(...).await,
        "hierarchical" => run_hierarchical(...).await,
        "aggregator" => run_aggregator(...).await,
        "router" => run_router(...).await,
        "wave" => run_wave(...).await,
        _ => run_sequential(...).await,  // DEFAULT
    }
}
```

---

## Retry Strategy (resilience.rs)

```rust
pub(crate) async fn run_phase_with_retry(
    agent_ids: &[&str],
    task: &str,
    phase: &str,
    pattern: &str,
    workspace: &str,
    mission_id: &str,
    phase_id: &str,
    on_event: &EventCallback,
) -> Result<String, String> {
    for attempt in 0..=MAX_PHASE_RETRIES {
        if attempt > 0 {
            let backoff_secs = 2u64.pow(attempt as u32);  // 2s, 4s, 8s
            eprintln!("[engine] Phase {} attempt {} — backoff {}s", 
                      phase, attempt + 1, backoff_secs);
            tokio::time::sleep(Duration::from_secs(backoff_secs)).await;
            
            // LLM health probe
            if let Err(_) = llm_health_probe().await {
                // Attempt auto-restart
                let _ = restart_llm_server().await;
            }
            
            // Inject previous error feedback
            current_task = format!(
                "{}\n\n## PREVIOUS ATTEMPT {} FAILED:\n{}\n\nFix and retry.",
                task, attempt, last_error
            );
        }
        
        match run_pattern(agent_ids, &current_task, phase, pattern, 
                         workspace, mission_id, phase_id, on_event).await {
            Ok(output) => return Ok(output),
            Err(e) => last_error = e,
        }
    }
    
    Err(format!("Phase {} failed after {} retries", phase, MAX_PHASE_RETRIES))
}
```

**Strategy:**
- Exponential backoff: 2^attempt seconds
- LLM health probe before each retry
- Auto-restart LLM server on probe failure
- Inject previous error feedback into task
- Max retries: 3

---

## Best Practices for New Patterns

### DO's ✓

- Use `&[&str]` for agent_ids (always slice)
- Use `Result<String, String>` for errors
- Call `agents::get_agent()` for each agent
- Get protocol via `protocols::protocol_for_role()`
- Call `executor::run_agent()` with protocol
- Call `guard::check_l0()` after execution
- Emit `AgentEvent::Thinking` before work
- Emit `AgentEvent::Response` for all results
- Strip emoji via `strip_emoji()`
- Store messages via `store_agent_msg()`
- Join outputs with `"\n\n---\n\n"`
- Handle empty agent_ids with error
- Use `.into()` to convert to String
- Use `.await?` for async calls
- Use `format!()` for string building

### DON'Ts ✗

- Don't use `Vec<String>` for inputs (use `&[&str]`)
- Don't create custom error types (use String)
- Don't call `agents::get_agent()` without checking Some()
- Don't skip `guard::check_l0()`
- Don't emit Response without context
- Don't ignore emoji in LLM output
- Don't skip database storage
- Don't use blocking calls
- Don't `panic!()` (return Err)
- Don't modify input parameters
- Don't ignore tool results
- Don't use English in system prompts (use French)

---

## Summary Table

| Aspect | Pattern |
|--------|---------|
| **Function Signature** | `async fn run_<name>(&[&str], &str, &str, &str, &str, &str, &EventCallback) -> Result<String, String>` |
| **Error Handling** | Result<String, String> with .into() and .await? |
| **Ownership** | Slices for inputs, Arc for callbacks |
| **Logging** | eprintln!("[MODULE] msg") for server only |
| **Events** | AgentEvent::Response { content } for all updates |
| **Protocol** | protocols::protocol_for_role(&role, phase) |
| **Guards** | guard::check_l0() after execution (warnings) |
| **Retry** | Exponential backoff, max 3, with health probe |
| **Timeouts** | 15 min per phase, tokio::time::timeout |
| **Emoji** | strip_emoji() on all LLM output |
| **Language** | French prompts + STYLE_RULES enforcement |
| **Database** | rusqlite with params![] macro |
| **Memory** | Project-scoped memory store for agent cross-talk |

---

## Complete Files Reference

All complete file contents are available in:
- `/Users/sylvain/_MACARON-SOFTWARE/simple-sf/SFEngine/src/engine/`

Files:
1. **mod.rs** - Module declarations + re-exports (35 lines)
2. **types.rs** - Constants, enums, utilities (103 lines)
3. **executor.rs** - Agent execution engine (185 lines)
4. **patterns.rs** - Basic patterns dispatcher + 5 patterns (376 lines)
5. **patterns_ext.rs** - Advanced patterns + test wrappers (400 lines)
6. **discussion.rs** - SAFe intake discussion (268 lines)
7. **mission.rs** - Mission orchestration (380 lines)
8. **phase.rs** - Phase execution wrapper (~100 lines+)
9. **workflow.rs** - Plan parsing + PM planning (~100 lines+)
10. **build.rs** - Auto-build checks (~80 lines+)
11. **resilience.rs** - Retry + health probe (~100 lines+)

---

## Document Information

**Created:** 2024
**Scope:** SFEngine Rust orchestration patterns
**Coverage:** All 11 engine module files
**Total content:** Complete file contents + complete coding style guide
**Version:** Complete reference including executor.rs AgentEvent details

