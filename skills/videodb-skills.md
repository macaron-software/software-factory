---
name: videodb-skills
version: 1.0.0
description: Upload, stream, search, edit, transcribe, and generate AI video and audio
  using the VideoDB SDK.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on videodb skills
eval_cases:
- id: videodb-skills-approach
  prompt: How should I approach videodb skills for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on videodb skills
  tags:
  - videodb
- id: videodb-skills-best-practices
  prompt: What are the key best practices and pitfalls for videodb skills?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for videodb skills
  tags:
  - videodb
  - best-practices
- id: videodb-skills-antipatterns
  prompt: What are the most common mistakes to avoid with videodb skills?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - videodb
  - antipatterns
---
# videodb-skills

# VideoDB Skills

## Purpose

The only video skill your agent needs. Upload any video, connect real-time streams, search inside by what was said or shown, build complex editing workflows with overlays, generate AI media, add subtitles, and get instant streaming links — all via the VideoDB Python SDK.

## When to Use This Skill

- User wants to upload and process videos from YouTube, URLs, or local files
- User needs to search for moments by speech or visual scenes
- User asks for transcription, subtitles, or subtitle styling
- User wants to edit clips — trim, combine, add text/image/audio overlays
- User needs AI-generated media (images, video, music, sound effects, voiceovers)
- User wants to transcode, change resolution, or reframe for social platforms
- User needs real-time screen or audio capture with AI transcription
- User asks for playable streaming links for any video output

## Setup

### Step 1: Install the skill

```bash
npx skills add video-db/skills
```

### Step 2: Run setup

```
/videodb setup
```

The agent guides API key setup ($20 free credits, no credit card), installs the SDK, and verifies the connection.

Alternatively, set the API key manually:

```bash
export VIDEO_DB_API_KEY=sk-xxx
```

### Step 3: Install the SDK

```bash
pip install "videodb[capture]" python-dotenv
```

## Capabilities

| Capability  | Description                                                               |
| ----------- | ------------------------------------------------------------------------- |
| Upload      | Ingest videos from YouTube, URLs, or local files                          |
| Search      | Find moments by speech (semantic/keyword) or visual scenes                |
| Transcripts | Generate timestamped transcripts from any video                           |
| Edit        | Combine clips, trim, add text/image/audio overlays                        |
| Subtitles   | Auto-generate and style subtitles                                         |
| AI Generate | Create images, video, music, sound effects, and voiceovers from text      |
| Capture     | Real-time screen and audio capture with AI transcription                  |
| Transcode   | Change resolution, quality, aspect ratio, or reframe for social platforms |
| Stream      | Get playable HLS links for anything you build                             |

## Examples

**Upload and transcribe:**

```
"Upload https://www.youtube.com/watch?v=FgrO9ADPZSA and give me a transcript"
```

**Search across videos:**

```
"Search for 'product demo' in my latest video"
```

**Add subtitles:**

```
"Add subtitles with white text on black background"
```

**Multi-clip editing:**

```
"Take clips from 10s-30s and 45s-60s, add a title card, and combine them"
```

**AI media generation:**

```
"Generate background music and overlay it on my video"
```

**Real-time capture:**

```
"Capture my screen and transcribe it in real-time"
```

**Reframe for social:**

```
"Convert this to vertical for Instagram Reels"
```

## Repository

https://github.com/video-db/skills

**Version:** 1.1.0
**Maintained By:** [VideoDB](https://github.com/video-db)
