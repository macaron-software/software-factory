# Elasticsearch / OpenSearch DBA Skill

## Scope
Elasticsearch 8.x / OpenSearch 2.x cluster administration, index design, search tuning, ILM.

## Core Competencies

### Index Design
- Mappings: keyword vs text, multi-fields, dynamic mapping control
- Nested vs object: nested for independent query, object for simple structure
- Flattened type: unknown/variable key structures without mapping explosion
- Index templates: component templates + index templates, priority ordering
- Data streams: append-only time-series, backing indices, rollover

### Shard Management
- Sizing: 20-50GB per shard target, max 200M documents per shard
- Primary + replicas: availability vs write throughput trade-off
- Allocation awareness: rack/zone-based, forced awareness
- Shrink/split: reduce shard count on old indices, increase on hot indices
- Oversharding: too many shards = cluster state overhead, slow queries

### Index Lifecycle Management (ILM)
- Hot phase: rollover on size/age/doc_count, force merge
- Warm phase: read-only, shrink, segment merge, downsample
- Cold phase: searchable snapshots (full/partial), reduced replicas
- Frozen phase: searchable snapshots (shared cache), minimal resources
- Delete phase: TTL-based cleanup, snapshot before delete

### Search Optimization
- Query DSL: bool/function_score/dis_max, filter vs query context
- Profiling: _profile API, shard-level timing, collector breakdown
- Slow log: search/index slow log, threshold configuration
- Runtime fields: on-the-fly computed fields, no re-index needed
- Caching: request cache, query cache, fielddata cache, node query cache

### Aggregations
- Terms: precision (shard_size), doc_count_error_upper_bound
- Date histogram: calendar vs fixed intervals, time zone handling
- Composite: pagination for large aggregations, after_key
- Pipeline: bucket_script, derivative, moving_avg, cumulative_sum
- Transform jobs: continuous, pivot, latest, destination index

### Cluster Operations
- Node roles: master-eligible, data (hot/warm/cold/frozen), ingest, coordinating, ML
- Rolling restart: shard allocation disable, synced flush, restart, re-enable
- Upgrade: rolling upgrade (minor), full cluster restart (major)
- Circuit breakers: parent, fielddata, request, in-flight, accounting
- Thread pools: search, write, analyze — rejection monitoring

### Monitoring
- _cat APIs: health, indices, shards, nodes, allocation, thread_pool
- _cluster/health: status (green/yellow/red), unassigned shards
- _nodes/stats: JVM heap, GC, thread pool, circuit breakers, transport
- Index stats: search rate, indexing rate, merge stats, refresh stats

### Security
- Native realm: users, roles, role mappings
- LDAP/SAML/OIDC: external identity providers
- Field-level security: restrict fields per role
- Document-level security: query-based access control
- Audit logging: access, authentication, index events

## Anti-Patterns
- Never use default 5 primary shards for all indices (right-size per index)
- Never skip ILM for time-series data (storage costs explode)
- Never use text field for exact matching (use keyword)
- Never ignore JVM heap > 75% (GC pressure, circuit breaker trips)
- Never disable replicas on production indices (data loss on node failure)
- Never use wildcard queries on text fields (slow, no caching)

## Tools
curl/_cat API, Kibana/OpenSearch Dashboards, elasticsearch-head, Cerebro,
Elasticdump, Reindex API, Snapshot/Restore, esrally (benchmarking)
