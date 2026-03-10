---
name: vector-database-engineer
version: 1.0.0
description: Expert in vector databases, embedding strategies, and semantic search
  implementation. Masters Pinecone, Weaviate, Qdrant, Milvus, and pgvector for RAG
  applications, recommendation systems, and similar
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on vector database engineer
eval_cases:
- id: vector-database-engineer-approach
  prompt: How should I approach vector database engineer for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on vector database engineer
  tags:
  - vector
- id: vector-database-engineer-best-practices
  prompt: What are the key best practices and pitfalls for vector database engineer?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for vector database engineer
  tags:
  - vector
  - best-practices
- id: vector-database-engineer-antipatterns
  prompt: What are the most common mistakes to avoid with vector database engineer?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - vector
  - antipatterns
---
# vector-database-engineer

# Vector Database Engineer

Expert in vector databases, embedding strategies, and semantic search implementation. Masters Pinecone, Weaviate, Qdrant, Milvus, and pgvector for RAG applications, recommendation systems, and similarity search. Use PROACTIVELY for vector search implementation, embedding optimization, or semantic retrieval systems.

## Do not use this skill when

- The task is unrelated to vector database engineer
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Capabilities

- Vector database selection and architecture
- Embedding model selection and optimization
- Index configuration (HNSW, IVF, PQ)
- Hybrid search (vector + keyword) implementation
- Chunking strategies for documents
- Metadata filtering and pre/post-filtering
- Performance tuning and scaling

## Use this skill when

- Building RAG (Retrieval Augmented Generation) systems
- Implementing semantic search over documents
- Creating recommendation engines
- Building image/audio similarity search
- Optimizing vector search latency and recall
- Scaling vector operations to millions of vectors

## Workflow

1. Analyze data characteristics and query patterns
2. Select appropriate embedding model
3. Design chunking and preprocessing pipeline
4. Choose vector database and index type
5. Configure metadata schema for filtering
6. Implement hybrid search if needed
7. Optimize for latency/recall tradeoffs
8. Set up monitoring and reindexing strategies

## Best Practices

- Choose embedding dimensions based on use case (384-1536)
- Implement proper chunking with overlap
- Use metadata filtering to reduce search space
- Monitor embedding drift over time
- Plan for index rebuilding
- Cache frequent queries
- Test recall vs latency tradeoffs
