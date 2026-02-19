#!/usr/bin/env python3
"""
Meta-Awareness Module - Cross-Project Error Detection
=====================================================
Detects systemic errors that affect multiple projects and escalates
them to the Factory itself for self-improvement.

Features:
1. Error pattern detection (100+ similar errors → systemic issue)
2. Cross-project learning (same error in 2+ projects → factory bug)
3. Automatic factory task creation for infrastructure fixes
"""

import hashlib
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Factory paths
FACTORY_ROOT = Path(__file__).parent.parent
DATA_DIR = FACTORY_ROOT / "data"
DB_PATH = DATA_DIR / "factory.db"


@dataclass
class SystemicError:
    """Represents a systemic error pattern"""
    pattern_hash: str
    pattern_text: str
    occurrence_count: int
    affected_projects: List[str]
    sample_errors: List[str]
    first_seen: datetime
    last_seen: datetime
    is_cross_project: bool


class MetaAwareness:
    """
    Analyzes errors across all projects to detect systemic issues
    that should be fixed in the Factory itself.
    """

    # Thresholds
    REPEAT_THRESHOLD = 50  # Same error 50+ times → systemic
    CROSS_PROJECT_THRESHOLD = 2  # Same error in 2+ projects → factory bug
    TIME_WINDOW_HOURS = 24  # Look at errors from last 24h

    # Infra patterns delegated to core.error_patterns (unified)

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self._ensure_tables()

    def _ensure_tables(self):
        """Create meta-awareness tables if not exist"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_patterns (
                id TEXT PRIMARY KEY,
                pattern_hash TEXT NOT NULL,
                pattern_text TEXT NOT NULL,
                project_id TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 1,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                escalated BOOLEAN DEFAULT FALSE,
                factory_task_id TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_patterns_hash
            ON error_patterns(pattern_hash)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_patterns_project
            ON error_patterns(project_id)
        """)
        conn.commit()
        conn.close()

    def _normalize_error(self, error: str) -> str:
        """Normalize error message for pattern matching"""
        # Remove timestamps, paths, line numbers
        normalized = error
        # Remove absolute paths
        normalized = re.sub(r'/Users/[^\s:]+', '<PATH>', normalized)
        normalized = re.sub(r'/home/[^\s:]+', '<PATH>', normalized)
        normalized = re.sub(r'/tmp/[^\s:]+', '<PATH>', normalized)
        # Remove line numbers
        normalized = re.sub(r':\d+:\d+', ':<LINE>', normalized)
        normalized = re.sub(r'line \d+', 'line <N>', normalized)
        # Remove specific IDs/hashes
        normalized = re.sub(r'[a-f0-9]{8,}', '<HASH>', normalized)
        # Remove timestamps
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TIME>', normalized)
        # Normalize whitespace
        normalized = ' '.join(normalized.split())
        return normalized[:500]  # Limit length

    def _hash_pattern(self, normalized_error: str) -> str:
        """Create a hash for the normalized error pattern"""
        return hashlib.md5(normalized_error.encode()).hexdigest()[:12]

    def _is_infra_error(self, error: str) -> bool:
        """Check if error indicates infrastructure/config issue"""
        from core.error_patterns import is_infra
        return is_infra(error, use_regex=True)

    def record_error(self, project_id: str, error: str) -> Optional[str]:
        """
        Record an error and check if it's systemic.
        Returns factory_task_id if a factory task was created.
        """
        normalized = self._normalize_error(error)
        pattern_hash = self._hash_pattern(normalized)

        conn = sqlite3.connect(self.db_path)

        # Check if this pattern exists for this project
        existing = conn.execute("""
            SELECT id, occurrence_count FROM error_patterns
            WHERE pattern_hash = ? AND project_id = ?
        """, (pattern_hash, project_id)).fetchone()

        if existing:
            # Update count
            conn.execute("""
                UPDATE error_patterns
                SET occurrence_count = occurrence_count + 1,
                    last_seen = datetime('now')
                WHERE id = ?
            """, (existing[0],))
        else:
            # Insert new
            pattern_id = f"err-{project_id}-{pattern_hash}"
            conn.execute("""
                INSERT INTO error_patterns (id, pattern_hash, pattern_text, project_id)
                VALUES (?, ?, ?, ?)
            """, (pattern_id, pattern_hash, normalized[:200], project_id))

        conn.commit()

        # Check for systemic issues
        factory_task_id = self._check_systemic(conn, pattern_hash, error)

        conn.close()
        return factory_task_id

    def _check_systemic(self, conn: sqlite3.Connection, pattern_hash: str,
                        original_error: str) -> Optional[str]:
        """Check if this pattern is systemic and create factory task if needed"""

        # Get all occurrences of this pattern
        rows = conn.execute("""
            SELECT project_id, occurrence_count, escalated, factory_task_id
            FROM error_patterns
            WHERE pattern_hash = ?
        """, (pattern_hash,)).fetchall()

        if not rows:
            return None

        # Already escalated?
        for row in rows:
            if row[2] and row[3]:  # escalated and has factory_task_id
                return row[3]

        total_count = sum(r[1] for r in rows)
        affected_projects = list(set(r[0] for r in rows))

        # Check thresholds
        is_repeat_systemic = total_count >= self.REPEAT_THRESHOLD
        is_cross_project = len(affected_projects) >= self.CROSS_PROJECT_THRESHOLD
        is_infra = self._is_infra_error(original_error)

        should_escalate = (is_repeat_systemic or is_cross_project) and is_infra

        if not should_escalate:
            return None

        # Create factory task
        factory_task_id = self._create_factory_task(
            conn, pattern_hash, original_error,
            total_count, affected_projects, is_cross_project
        )

        # Mark as escalated
        conn.execute("""
            UPDATE error_patterns
            SET escalated = TRUE, factory_task_id = ?
            WHERE pattern_hash = ?
        """, (factory_task_id, pattern_hash))
        conn.commit()

        return factory_task_id

    def _create_factory_task(self, conn: sqlite3.Connection, pattern_hash: str,
                             error: str, count: int, projects: List[str],
                             is_cross_project: bool) -> str:
        """Create a task for the factory to fix systemic issue"""

        task_id = f"meta-{pattern_hash}"

        # Determine the issue type
        if is_cross_project:
            issue_type = "CROSS-PROJECT"
            description = (
                f"[{issue_type}] Systemic error affecting {len(projects)} projects "
                f"({', '.join(projects)}): {error[:200]}"
            )
        else:
            issue_type = "SYSTEMIC"
            description = (
                f"[{issue_type}] Repeated error ({count}x): {error[:200]}"
            )

        # Check if task already exists
        existing = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

        if existing:
            return task_id

        # Create the task
        import json
        context = json.dumps({
            "type": "meta_awareness",
            "issue_type": issue_type,
            "pattern_hash": pattern_hash,
            "occurrence_count": count,
            "affected_projects": projects,
            "is_cross_project": is_cross_project,
            "original_error": error[:500],
            "suggested_files": [
                "core/project_registry.py",
                "core/cycle_worker.py",
                "core/llm_client.py",
                "mcp_lrm/server_sse.py",
            ]
        })

        conn.execute("""
            INSERT INTO tasks (
                id, project_id, type, domain, description, status,
                priority, wsjf_score, context_gz, files_json
            ) VALUES (?, 'factory', 'fix', 'python', ?, 'pending',
                      100, 10.0, ?, '[]')
        """, (task_id, description, context.encode()))

        conn.commit()

        print(f"[META-AWARENESS] Created factory task: {task_id}")
        print(f"  Issue: {issue_type}")
        print(f"  Affected: {projects}")
        print(f"  Error: {error[:100]}...")

        return task_id

    def analyze_all(self) -> List[SystemicError]:
        """
        Analyze all recent errors and return systemic issues.
        Can be called periodically or on-demand.
        """
        conn = sqlite3.connect(self.db_path)

        # Get error patterns from last 24h
        cutoff = datetime.now() - timedelta(hours=self.TIME_WINDOW_HOURS)

        rows = conn.execute("""
            SELECT pattern_hash, pattern_text, project_id, occurrence_count,
                   first_seen, last_seen
            FROM error_patterns
            WHERE last_seen > ?
            ORDER BY pattern_hash, project_id
        """, (cutoff.isoformat(),)).fetchall()

        # Group by pattern
        patterns: Dict[str, Dict] = defaultdict(lambda: {
            'text': '',
            'projects': [],
            'total_count': 0,
            'first_seen': None,
            'last_seen': None
        })

        for row in rows:
            p_hash, p_text, proj, count, first, last = row
            p = patterns[p_hash]
            p['text'] = p_text
            p['projects'].append(proj)
            p['total_count'] += count
            if not p['first_seen'] or first < p['first_seen']:
                p['first_seen'] = first
            if not p['last_seen'] or last > p['last_seen']:
                p['last_seen'] = last

        conn.close()

        # Build results
        results = []
        for p_hash, data in patterns.items():
            is_systemic = (
                data['total_count'] >= self.REPEAT_THRESHOLD or
                len(set(data['projects'])) >= self.CROSS_PROJECT_THRESHOLD
            )
            if is_systemic:
                results.append(SystemicError(
                    pattern_hash=p_hash,
                    pattern_text=data['text'],
                    occurrence_count=data['total_count'],
                    affected_projects=list(set(data['projects'])),
                    sample_errors=[data['text']],
                    first_seen=datetime.fromisoformat(data['first_seen']) if data['first_seen'] else datetime.now(),
                    last_seen=datetime.fromisoformat(data['last_seen']) if data['last_seen'] else datetime.now(),
                    is_cross_project=len(set(data['projects'])) >= self.CROSS_PROJECT_THRESHOLD
                ))

        return sorted(results, key=lambda x: -x.occurrence_count)

    def get_stats(self) -> Dict:
        """Get meta-awareness statistics"""
        conn = sqlite3.connect(self.db_path)

        stats = {
            'total_patterns': conn.execute(
                "SELECT COUNT(DISTINCT pattern_hash) FROM error_patterns"
            ).fetchone()[0],
            'total_occurrences': conn.execute(
                "SELECT SUM(occurrence_count) FROM error_patterns"
            ).fetchone()[0] or 0,
            'escalated_count': conn.execute(
                "SELECT COUNT(*) FROM error_patterns WHERE escalated = TRUE"
            ).fetchone()[0],
            'factory_tasks_created': conn.execute(
                "SELECT COUNT(DISTINCT factory_task_id) FROM error_patterns WHERE factory_task_id IS NOT NULL"
            ).fetchone()[0],
            'cross_project_patterns': 0,
        }

        # Count cross-project patterns
        cross = conn.execute("""
            SELECT pattern_hash, COUNT(DISTINCT project_id) as proj_count
            FROM error_patterns
            GROUP BY pattern_hash
            HAVING proj_count >= 2
        """).fetchall()
        stats['cross_project_patterns'] = len(cross)

        conn.close()
        return stats


# Singleton instance
_meta_awareness: Optional[MetaAwareness] = None

def get_meta_awareness() -> MetaAwareness:
    """Get or create the meta-awareness singleton"""
    global _meta_awareness
    if _meta_awareness is None:
        _meta_awareness = MetaAwareness()
    return _meta_awareness


def record_build_error(project_id: str, error: str) -> Optional[str]:
    """
    Convenience function to record a build error.
    Returns factory_task_id if escalated.
    """
    return get_meta_awareness().record_error(project_id, error)


def analyze_systemic_errors() -> List[SystemicError]:
    """Convenience function to analyze all systemic errors"""
    return get_meta_awareness().analyze_all()
