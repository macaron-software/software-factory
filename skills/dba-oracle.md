# Oracle DBA Skill

## Scope
Oracle Database 19c/21c/23ai administration, performance, HA, backup/recovery.

## Core Competencies

### Architecture
- SGA: shared pool, buffer cache, redo log buffer, large pool, Java pool, streams pool
- PGA: sort area, hash area, session memory
- Background: DBWR, LGWR, CKPT, SMON, PMON, ARCn, MMON, MMNL
- Multitenant: CDB/PDB architecture, resource manager, common/local users

### High Availability
- RAC: cache fusion, GCS/GES, interconnect tuning, TAF/FCF, services
- Data Guard: physical/logical standby, Active Data Guard, Far Sync
- GoldenGate: real-time replication, conflict resolution, bidirectional

### Performance
- AWR: automatic snapshots, report generation, baseline comparison
- ASH: active session sampling, top SQL, wait event analysis
- ADDM: automatic diagnostic recommendations
- SQL Tuning: SQL profiles, plan baselines, optimizer hints, adaptive plans
- Wait events: db file sequential/scattered read, log file sync, enqueue, latch free

### Backup & Recovery
- RMAN: full/incremental/cumulative, block change tracking, catalog
- PITR: point-in-time recovery, tablespace PITR, flashback database/table
- Data Pump: expdp/impdp, parallel, transportable tablespaces

### Storage
- ASM: disk groups, rebalancing, mirroring, ACFS
- Tablespace: locally managed, ASSM, bigfile, compressed
- Partitioning: range/list/hash/composite/interval/reference

### Security
- TDE: tablespace/column encryption, wallet/keystore management
- VPD: virtual private database, fine-grained access control
- Database Vault: realm protection, command rules
- Unified Auditing: policies, audit trail management
- Privilege Analysis: used/unused privilege tracking

## Anti-Patterns
- Never use RULE-based optimizer (deprecated since 10g)
- Never skip AWR snapshot before/after changes
- Never bypass RMAN for production backups
- Never use NOLOGGING without understanding recovery implications
- Never run Data Guard failover without testing switchover first

## Tools
sqlplus, RMAN, expdp/impdp, adrci, DBCA, DGMGRL, srvctl, crsctl, asmcmd, OEM
