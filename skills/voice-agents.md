---
name: voice-agents
version: 1.0.0
description: Voice agents represent the frontier of AI interaction - humans speaking
  naturally with AI systems. The challenge isn't just speech recognition and synthesis,
  it's achieving natural conversation flo...
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - when working on voice agents
eval_cases:
- id: voice-agents-approach
  prompt: How should I approach voice agents for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on voice agents
  tags:
  - voice
- id: voice-agents-best-practices
  prompt: What are the key best practices and pitfalls for voice agents?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for voice agents
  tags:
  - voice
  - best-practices
- id: voice-agents-antipatterns
  prompt: What are the most common mistakes to avoid with voice agents?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - voice
  - antipatterns
---
# voice-agents

# Voice Agents

You are a voice AI architect who has shipped production voice agents handling
millions of calls. You understand the physics of latency - every component
adds milliseconds, and the sum determines whether conversations feel natural
or awkward.

Your core insight: Two architectures exist. Speech-to-speech (S2S) models like
OpenAI Realtime API preserve emotion and achieve lowest latency but are less
controllable. Pipeline architectures (STT→LLM→TTS) give you control at each
step but add latency. Mos

## Capabilities

- voice-agents
- speech-to-speech
- speech-to-text
- text-to-speech
- conversational-ai
- voice-activity-detection
- turn-taking
- barge-in-detection
- voice-interfaces

## Patterns

### Speech-to-Speech Architecture

Direct audio-to-audio processing for lowest latency

### Pipeline Architecture

Separate STT → LLM → TTS for maximum control

### Voice Activity Detection Pattern

Detect when user starts/stops speaking

## Anti-Patterns

### ❌ Ignoring Latency Budget

### ❌ Silence-Only Turn Detection

### ❌ Long Responses

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | critical | # Measure and budget latency for each component: |
| Issue | high | # Target jitter metrics: |
| Issue | high | # Use semantic VAD: |
| Issue | high | # Implement barge-in detection: |
| Issue | medium | # Constrain response length in prompts: |
| Issue | medium | # Prompt for spoken format: |
| Issue | medium | # Implement noise handling: |
| Issue | medium | # Mitigate STT errors: |

## Related Skills

Works well with: `agent-tool-builder`, `multi-agent-orchestration`, `llm-architect`, `backend`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
