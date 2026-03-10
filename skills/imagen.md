---
name: imagen
version: 1.0.0
description: AI image generation skill powered by Google Gemini, enabling seamless
  visual content creation for UI placeholders, documentation, and design assets.
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/sanjay3290/ai-skills/tree/main/skills/imagen'
  triggers:
  - user requests image generation (e.g., "generate an image of...", "create a pictu
eval_cases:
- id: imagen-approach
  prompt: How should I approach imagen for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on imagen
  tags:
  - imagen
- id: imagen-best-practices
  prompt: What are the key best practices and pitfalls for imagen?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for imagen
  tags:
  - imagen
  - best-practices
- id: imagen-antipatterns
  prompt: What are the most common mistakes to avoid with imagen?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - imagen
  - antipatterns
---
# imagen

# Imagen - AI Image Generation Skill

## Overview

This skill generates images using Google Gemini's image generation model (`gemini-3-pro-image-preview`). It enables seamless image creation during any Claude Code session - whether you're building frontend UIs, creating documentation, or need visual representations of concepts.

**Cross-Platform**: Works on Windows, macOS, and Linux.

## When to Use This Skill

Automatically activate this skill when:
- User requests image generation (e.g., "generate an image of...", "create a picture...")
- Frontend development requires placeholder or actual images
- Documentation needs illustrations or diagrams
- Visualizing concepts, architectures, or ideas
- Creating icons, logos, or UI assets
- Any task where an AI-generated image would be helpful

## How It Works

1. Takes a text prompt describing the desired image
2. Calls Google Gemini API with image generation configuration
3. Saves the generated image to a specified location (defaults to current directory)
4. Returns the file path for use in your project

## Usage

### Python (Cross-Platform - Recommended)

```bash
# Basic usage
python scripts/generate_image.py "A futuristic city skyline at sunset"

# With custom output path
python scripts/generate_image.py "A minimalist app icon for a music player" "./assets/icons/music-icon.png"

# With custom size
python scripts/generate_image.py --size 2K "High resolution landscape" "./wallpaper.png"
```

## Requirements

- `GEMINI_API_KEY` environment variable must be set
- Python 3.6+ (uses standard library only, no pip install needed)

## Output

Generated images are saved as PNG files. The script returns:
- Success: Path to the generated image
- Failure: Error message with details

## Examples

### Frontend Development
```
User: "I need a hero image for my landing page - something abstract and tech-focused"
-> Generates and saves image, provides path for use in HTML/CSS
```

### Documentation
```
User: "Create a diagram showing microservices architecture"
-> Generates visual representation, ready for README or docs
```

### UI Assets
```
User: "Generate a placeholder avatar image for the user profile component"
-> Creates image in appropriate size for component use
```
