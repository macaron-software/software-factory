# MongoDB DBA Skill

## Scope
MongoDB 6.x/7.x/8.x administration, sharding, replication, schema design, Atlas.

## Core Competencies

### Schema Design Patterns
- Embedding vs referencing: data access patterns drive decisions
- Polymorphic pattern: type field + union schema
- Bucket pattern: time-series grouping (IoT, logs)
- Computed pattern: pre-aggregated summaries
- Subset pattern: frequently accessed subset embedded, full data linked
- Schema versioning: schemaVersion field + migration on read/write
- Schema validation: JSON Schema in createCollection/collMod

### Sharding
- Shard key selection: cardinality, frequency, monotonicity, query isolation
- Hashed sharding: uniform distribution, no range queries on shard key
- Ranged sharding: range queries efficient, risk of hot spots
- Zone sharding: geographic data locality, tiered storage
- Chunk management: splitting, balancing, jumbo chunk remediation
- mongos: query routing, targeted vs broadcast queries

### Replica Sets
- Elections: priority, votes, election timeout, arbiters (avoid if possible)
- Read preferences: primary, primaryPreferred, secondary, nearest
- Write concerns: w:1, w:majority, w:all, j:true, wtimeout
- Oplog: sizing, oplog window monitoring, change streams
- Hidden/delayed members: reporting, backup, disaster recovery

### Aggregation Framework
- Pipeline optimization: $match early, $project to reduce documents
- Index usage: $match/$sort can use indexes, $lookup limited index use
- Memory limits: 100MB per stage, allowDiskUse for large sorts
- $merge/$out: materialized views, incremental updates
- $facet: parallel sub-pipelines, dashboard queries

### Indexes
- Types: compound, multikey, text, wildcard, partial, sparse, TTL, hashed
- Covered queries: all fields in index, no document fetch
- Index intersection: multiple single-field indexes
- ESR rule: Equality, Sort, Range ordering for compound indexes
- explain("executionStats"): totalKeysExamined, totalDocsExamined

### WiredTiger
- Cache: default 50% RAM - 1GB, eviction targets
- Compression: snappy (default), zlib (better ratio), zstd (best balance)
- Checkpoints: 60s default, journal for crash recovery between checkpoints

### Backup & Recovery
- mongodump/mongorestore: logical backup, namespace filtering
- Atlas continuous backup: point-in-time restore, snapshot scheduling
- Filesystem snapshots: consistent with journaling, fastest for large DBs
- Ops Manager: automated backups, monitoring, alerting

### Security
- Authentication: SCRAM-SHA-256, x509, LDAP, Kerberos
- Authorization: built-in roles, custom roles, db-level/collection-level
- Encryption: TLS/SSL in transit, encrypted storage engine, CSFLE, Queryable Encryption
- Audit: system event auditing, filter expressions, output formats

## Anti-Patterns
- Never use ObjectId as shard key (monotonically increasing = hot shard)
- Never embed unbounded arrays (document size limit 16MB)
- Never skip index on frequently queried fields
- Never use $where or mapReduce (use aggregation framework)
- Never ignore oplog window — if window closes, resync required

## Tools
mongosh, mongodump, mongorestore, mongos, mongostat, mongotop,
Atlas CLI, Compass, Ops Manager, mongosync, mongoimport/mongoexport
