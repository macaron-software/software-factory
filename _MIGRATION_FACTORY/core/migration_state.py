"""
Migration State Tracker

Tracks per-file migration status for incremental migrations.
Supports:
- File-level status (LEGACY/IN_PROGRESS/MIGRATED/VERIFIED)
- Phase tracking (deps/standalone/typed-forms/control-flow)
- Rollback safety checks
- Progress reporting
"""

import sqlite3
import subprocess
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class FileMigrationStatus:
    file_path: str
    phase: str
    status: str  # LEGACY|IN_PROGRESS|MIGRATED|VERIFIED
    task_id: Optional[str] = None
    migrated_at: Optional[datetime] = None
    verified_by: Optional[str] = None  # Adversarial ID
    git_commit: Optional[str] = None
    rollback_tag: Optional[str] = None
    metadata: Optional[Dict] = None


class MigrationState:
    """
    Database-backed migration state tracker

    Usage:
        state = MigrationState('sharelook')
        state.mark_migrated('src/app/auth/auth.component.ts', 'standalone', 'task-001')
        progress = state.get_migration_progress('standalone')
        # → {'total': 50, 'migrated': 32, 'percentage': 64.0}
    """

    def __init__(self, project_id: str, db_path: Optional[str] = None):
        self.project_id = project_id
        self.db_path = db_path or f"data/migration_{project_id}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Access by column name
        self._init_schema()

    def _init_schema(self):
        """Create tables if not exist"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_migration_status (
                file_path TEXT PRIMARY KEY,
                phase TEXT NOT NULL,
                status TEXT NOT NULL,
                task_id TEXT,
                migrated_at TIMESTAMP,
                verified_by TEXT,
                git_commit TEXT,
                rollback_tag TEXT,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase_status
            ON file_migration_status(phase, status)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON file_migration_status(status)
        """)

        self.conn.commit()

    def mark_legacy(self, file_path: str, phase: str):
        """Mark file as LEGACY (not yet migrated)"""
        self.conn.execute("""
            INSERT OR REPLACE INTO file_migration_status
            (file_path, phase, status, updated_at)
            VALUES (?, ?, 'LEGACY', datetime('now'))
        """, (file_path, phase))
        self.conn.commit()

    def mark_in_progress(self, file_path: str, phase: str, task_id: str):
        """Mark file as IN_PROGRESS (migration started)"""
        self.conn.execute("""
            INSERT OR REPLACE INTO file_migration_status
            (file_path, phase, status, task_id, updated_at)
            VALUES (?, ?, 'IN_PROGRESS', ?, datetime('now'))
        """, (file_path, phase, task_id))
        self.conn.commit()

    def mark_migrated(
        self,
        file_path: str,
        phase: str,
        task_id: str,
        metadata: Optional[Dict] = None
    ):
        """Mark file as MIGRATED (transform done, not yet verified)"""
        git_commit = self._get_current_commit()

        self.conn.execute("""
            INSERT OR REPLACE INTO file_migration_status
            (file_path, phase, status, task_id, migrated_at, git_commit, metadata, updated_at)
            VALUES (?, ?, 'MIGRATED', ?, datetime('now'), ?, ?, datetime('now'))
        """, (file_path, phase, task_id, git_commit, json.dumps(metadata or {})))
        self.conn.commit()

    def mark_verified(
        self,
        file_path: str,
        verified_by: str,
        rollback_tag: Optional[str] = None
    ):
        """Mark file as VERIFIED (adversarial approved)"""
        self.conn.execute("""
            UPDATE file_migration_status
            SET status = 'VERIFIED',
                verified_by = ?,
                rollback_tag = ?,
                updated_at = datetime('now')
            WHERE file_path = ?
        """, (verified_by, rollback_tag, file_path))
        self.conn.commit()

    def rollback_file(self, file_path: str) -> bool:
        """
        Rollback file to LEGACY status
        Returns: True if rollback OK, False if cannot rollback (already verified)
        """
        # Check if can rollback (not verified)
        if not self.can_rollback_file(file_path):
            return False

        self.conn.execute("""
            UPDATE file_migration_status
            SET status = 'LEGACY',
                task_id = NULL,
                migrated_at = NULL,
                verified_by = NULL,
                git_commit = NULL,
                updated_at = datetime('now')
            WHERE file_path = ?
        """, (file_path,))
        self.conn.commit()
        return True

    def can_rollback_file(self, file_path: str) -> bool:
        """
        Can rollback if:
        - File is IN_PROGRESS or MIGRATED (not yet VERIFIED)
        - OR verified_by is NULL (adversarial not yet approved)
        """
        cursor = self.conn.execute("""
            SELECT status, verified_by
            FROM file_migration_status
            WHERE file_path = ?
        """, (file_path,))

        row = cursor.fetchone()
        if not row:
            return True  # File not tracked, can "rollback" (do nothing)

        status = row['status']
        verified_by = row['verified_by']

        return status in ('IN_PROGRESS', 'MIGRATED') and verified_by is None

    def get_migration_progress(self, phase: str) -> Dict:
        """
        Get migration progress for a phase

        Returns:
            {
                'total': 50,
                'legacy': 13,
                'in_progress': 5,
                'migrated': 20,
                'verified': 12,
                'percentage_migrated': 64.0,
                'percentage_verified': 24.0
            }
        """
        cursor = self.conn.execute("""
            SELECT status, COUNT(*) as count
            FROM file_migration_status
            WHERE phase = ?
            GROUP BY status
        """, (phase,))

        stats = {row['status']: row['count'] for row in cursor.fetchall()}

        total = sum(stats.values())
        migrated = stats.get('MIGRATED', 0)
        verified = stats.get('VERIFIED', 0)
        in_progress = stats.get('IN_PROGRESS', 0)
        legacy = stats.get('LEGACY', 0)

        return {
            'total': total,
            'legacy': legacy,
            'in_progress': in_progress,
            'migrated': migrated,
            'verified': verified,
            'percentage_migrated': (migrated / total * 100) if total > 0 else 0,
            'percentage_verified': (verified / total * 100) if total > 0 else 0,
        }

    def get_file_status(self, file_path: str) -> Optional[FileMigrationStatus]:
        """Get status for specific file"""
        cursor = self.conn.execute("""
            SELECT * FROM file_migration_status
            WHERE file_path = ?
        """, (file_path,))

        row = cursor.fetchone()
        if not row:
            return None

        return FileMigrationStatus(
            file_path=row['file_path'],
            phase=row['phase'],
            status=row['status'],
            task_id=row['task_id'],
            migrated_at=datetime.fromisoformat(row['migrated_at']) if row['migrated_at'] else None,
            verified_by=row['verified_by'],
            git_commit=row['git_commit'],
            rollback_tag=row['rollback_tag'],
            metadata=json.loads(row['metadata']) if row['metadata'] else None,
        )

    def list_files_by_status(
        self,
        phase: str,
        status: str,
        limit: Optional[int] = None
    ) -> List[str]:
        """List files by status (e.g., all LEGACY files in standalone phase)"""
        query = """
            SELECT file_path
            FROM file_migration_status
            WHERE phase = ? AND status = ?
            ORDER BY file_path
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor = self.conn.execute(query, (phase, status))
        return [row['file_path'] for row in cursor.fetchall()]

    def is_rollback_safe(self, phase: Optional[str] = None) -> Dict:
        """
        Check if rollback is safe (all files verified by adversarial)

        Returns:
            {
                'safe': True/False,
                'unverified_count': 3,
                'unverified_files': ['file1.ts', 'file2.ts'],
                'message': 'SAFE' or 'UNSAFE: ...'
            }
        """
        query = """
            SELECT file_path, status
            FROM file_migration_status
            WHERE (verified_by IS NULL OR status IN ('IN_PROGRESS', 'MIGRATED'))
        """

        if phase:
            query += f" AND phase = '{phase}'"

        cursor = self.conn.execute(query)
        unverified = cursor.fetchall()

        if not unverified:
            return {
                'safe': True,
                'unverified_count': 0,
                'unverified_files': [],
                'message': '✅ SAFE: All files verified by adversarial'
            }

        unverified_files = [row['file_path'] for row in unverified]
        return {
            'safe': False,
            'unverified_count': len(unverified_files),
            'unverified_files': unverified_files,
            'message': f'❌ UNSAFE: {len(unverified_files)} files not verified yet'
        }

    def _get_current_commit(self) -> str:
        """Get current git commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return 'unknown'

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ===== CLI Helper Functions =====

def print_progress(project_id: str, phase: str):
    """CLI: Print migration progress"""
    with MigrationState(project_id) as state:
        progress = state.get_migration_progress(phase)

        print(f"\n{'='*60}")
        print(f"Migration Progress: {project_id} / {phase}")
        print(f"{'='*60}")
        print(f"Total files:       {progress['total']}")
        print(f"Legacy remaining:  {progress['legacy']}")
        print(f"In progress:       {progress['in_progress']}")
        print(f"Migrated:          {progress['migrated']} ({progress['percentage_migrated']:.1f}%)")
        print(f"Verified:          {progress['verified']} ({progress['percentage_verified']:.1f}%)")
        print(f"{'='*60}\n")


def print_file_status(project_id: str, file_path: str):
    """CLI: Print status for specific file"""
    with MigrationState(project_id) as state:
        status = state.get_file_status(file_path)

        if not status:
            print(f"❌ File not tracked: {file_path}")
            return

        print(f"\n{'='*60}")
        print(f"File: {status.file_path}")
        print(f"{'='*60}")
        print(f"Status:       {status.status} {'✅' if status.status == 'VERIFIED' else ''}")
        print(f"Phase:        {status.phase}")
        print(f"Task:         {status.task_id or 'N/A'}")
        print(f"Migrated at:  {status.migrated_at or 'N/A'}")
        print(f"Verified by:  {status.verified_by or 'Not yet verified'}")
        print(f"Git commit:   {status.git_commit or 'N/A'}")
        print(f"Rollback tag: {status.rollback_tag or 'N/A'}")
        print(f"{'='*60}\n")


def print_rollback_safety(project_id: str, phase: Optional[str] = None):
    """CLI: Check if rollback is safe"""
    with MigrationState(project_id) as state:
        safety = state.is_rollback_safe(phase)

        print(f"\n{'='*60}")
        print(f"Rollback Safety Check: {project_id}")
        if phase:
            print(f"Phase: {phase}")
        print(f"{'='*60}")
        print(safety['message'])

        if not safety['safe']:
            print(f"\nUnverified files ({safety['unverified_count']}):")
            for file_path in safety['unverified_files'][:10]:  # Show first 10
                print(f"  - {file_path}")

            if safety['unverified_count'] > 10:
                print(f"  ... and {safety['unverified_count'] - 10} more")

        print(f"{'='*60}\n")
