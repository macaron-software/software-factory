# MySQL / MariaDB DBA Skill

## Scope
MySQL 8.x / MariaDB 10.x/11.x administration, replication, optimization, backup.

## Core Competencies

### InnoDB Engine
- Buffer pool: sizing (70-80% RAM), multiple instances, warmup, monitoring
- Redo log: innodb_log_file_size, group commit, log buffer
- Undo: tablespace management, purge tuning, long transaction detection
- Change buffer: merge operations, monitoring secondary index updates
- Doublewrite: data integrity, performance trade-offs
- Page compression: punch hole, transparent compression

### Replication
- Async: binlog position, auto-failover, multi-source
- Semi-sync: rpl_semi_sync_master_wait_point (AFTER_SYNC)
- Group Replication: single-primary, multi-primary, conflict detection
- GTID: global transaction identifiers, failover simplification
- Binlog formats: ROW (recommended), STATEMENT, MIXED
- ProxySQL: query routing, read/write split, connection pooling

### Query Optimization
- EXPLAIN FORMAT=JSON/TREE: access type, key usage, filtered rows
- Optimizer hints: INDEX, NO_INDEX, JOIN_ORDER, MERGE/NO_MERGE
- Index strategies: covering, prefix, invisible, descending, functional
- Query rewrite: plugin-based, optimizer_switch settings

### Schema Changes (Zero-Downtime)
- pt-online-schema-change: trigger-based, chunk size, throttling
- gh-ost: triggerless, binary log based, cut-over
- Instant DDL: ADD COLUMN (last), DROP COLUMN (8.0.29+)
- ALTER TABLE online: ALGORITHM=INPLACE/INSTANT/COPY

### Monitoring
- performance_schema: events_statements_summary, file_summary, memory_summary
- sys schema: innodb_lock_waits, schema_redundant_indexes, statements_with_*
- Slow query log: long_query_time, log_queries_not_using_indexes
- SHOW ENGINE INNODB STATUS: transactions, deadlocks, buffer pool stats

### Backup
- mysqldump: single-transaction, routines, events, triggers
- mysqlpump: parallel dump, compression, filtering
- Percona XtraBackup: hot backup, incremental, compressed, encrypted
- MySQL Shell dump/load: parallel, chunked, progress tracking

### Security
- Authentication: caching_sha2_password, LDAP, PAM, Kerberos
- Roles: CREATE ROLE, GRANT role, SET DEFAULT ROLE
- SSL/TLS: required connections, certificate management
- Audit: Enterprise Audit, MariaDB Audit Plugin
- Data masking: Enterprise Masking, gen_rnd_*, mask_inner/outer

## Anti-Patterns
- Never ALTER large tables without pt-osc or gh-ost
- Never use MyISAM for transactional tables
- Never set innodb_flush_log_at_trx_commit=0 in production
- Never use FLOAT/DOUBLE for financial data (use DECIMAL)
- Never skip binary log validation after failover

## Tools
mysql, mysqldump, mysqlpump, pt-query-digest, pt-online-schema-change, gh-ost,
xtrabackup, mysqlsh, ProxySQL, MySQL Router, Orchestrator, PMM
