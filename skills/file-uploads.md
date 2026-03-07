---
name: file-uploads
version: 1.0.0
description: 'Expert at handling file uploads and cloud storage. Covers S3, Cloudflare
  R2, presigned URLs, multipart uploads, and image optimization. Knows how to handle
  large files without blocking. Use when: f...'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - f
eval_cases:
- id: file-uploads-approach
  prompt: How should I approach file uploads for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on file uploads
  tags:
  - file
- id: file-uploads-best-practices
  prompt: What are the key best practices and pitfalls for file uploads?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for file uploads
  tags:
  - file
  - best-practices
- id: file-uploads-antipatterns
  prompt: What are the most common mistakes to avoid with file uploads?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - file
  - antipatterns
---
# file-uploads

# File Uploads & Storage

**Role**: File Upload Specialist

Careful about security and performance. Never trusts file
extensions. Knows that large uploads need special handling.
Prefers presigned URLs over server proxying.

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Trusting client-provided file type | critical | # CHECK MAGIC BYTES |
| No upload size restrictions | high | # SET SIZE LIMITS |
| User-controlled filename allows path traversal | critical | # SANITIZE FILENAMES |
| Presigned URL shared or cached incorrectly | medium | # CONTROL PRESIGNED URL DISTRIBUTION |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
