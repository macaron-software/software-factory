# SQLite DBA Skill

## Scope
SQLite 3.35+ administration, WAL optimization, FTS5, embedded database patterns.

## Core Competencies

### WAL Mode
- journal_mode=WAL: concurrent reads during writes, no reader blocking
- wal_autocheckpoint: default 1000 pages, tune for write-heavy workloads
- wal_checkpoint(TRUNCATE): reclaim WAL file space, run during low traffic
- WAL file growth: checkpoint regularly, monitor -wal file size
- mmap_size: memory-mapped I/O for reads, faster than traditional I/O

### PRAGMA Tuning
- cache_size: default -2000 (2MB), increase for large datasets (-64000 = 64MB)
- page_size: 4096 default, 8192 for BLOB-heavy, must set before first write
- synchronous: NORMAL for WAL mode (safe + fast), FULL for rollback journal
- temp_store: MEMORY for faster temp tables, FILE for large temp results
- journal_size_limit: cap rollback journal size
- foreign_keys: ON (off by default — always enable explicitly)
- optimize: run after bulk writes to update query planner statistics

### Index Strategies
- Covering indexes: include all SELECT columns, avoid table lookup
- Partial indexes: WHERE clause on index, smaller + faster
- Expression indexes: computed column indexing
- WITHOUT ROWID: key-value tables, clustered by PRIMARY KEY
- EXPLAIN QUERY PLAN: SCAN vs SEARCH, index usage, temp B-trees

### FTS5 (Full-Text Search)
- Tokenizers: unicode61 (default), porter (stemming), trigram (substring)
- Content tables: external content (content=, content_rowid=)
- Rank functions: bm25(), rank column, custom ranking
- Prefix queries: prefix="2 3" for autocomplete
- Triggers: keep FTS5 in sync with source table (INSERT/UPDATE/DELETE)

### Schema Migration
- user_version PRAGMA: integer version tracking, no external tools needed
- ALTER TABLE limitations: ADD COLUMN (all versions), RENAME (3.25+), DROP (3.35+)
- 12-step migration: create new → copy data → drop old → rename new
- Idempotent DDL: CREATE TABLE IF NOT EXISTS, no DROP IF EXISTS before 3.35
- Backup before migration: .backup or VACUUM INTO

### Concurrency
- Single writer: only one write transaction at a time
- Multiple readers: unlimited concurrent readers in WAL mode
- busy_timeout: milliseconds to wait before SQLITE_BUSY, default 0
- BEGIN IMMEDIATE: acquire write lock immediately, avoid SQLITE_BUSY mid-transaction
- Connection pooling: application-level, one connection per thread typical

### Backup
- .backup command: online backup to file, consistent snapshot
- VACUUM INTO: hot backup to new file, compacted
- File copy: safe only after WAL checkpoint (no -wal/-shm files pending)
- sqlite3_backup_* API: C API for programmatic backup, page-level copy

### Performance Limits
- Max DB size: 281 TB (theoretical), practical limit depends on filesystem
- Max row size: 1 billion bytes (default 1GB)
- Max columns: 2000 (default), 32767 (compile-time)
- Max attached: 125 databases (compile-time)
- Max page count: 4,294,967,294 pages
- Single file: no partitioning, no sharding — plan around this

## Anti-Patterns
- Never use SQLite for high-concurrency write workloads (use PG/MySQL)
- Never skip PRAGMA journal_mode=WAL (default rollback is slow)
- Never forget PRAGMA foreign_keys=ON (off by default)
- Never use VACUUM on large DBs during peak traffic (locks entire DB)
- Never rely on implicit rowid ordering (use ORDER BY explicitly)
- Never open same DB from multiple processes without WAL mode
- Never store large BLOBs inline (use external files + path reference)

## Tools
sqlite3 CLI, .schema, .dump, .import, EXPLAIN QUERY PLAN, PRAGMA integrity_check,
.dbinfo, sqlite3_analyzer, sqldiff, litestream (streaming replication)
