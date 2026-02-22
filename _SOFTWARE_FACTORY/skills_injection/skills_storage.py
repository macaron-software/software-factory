"""
Skills Storage - Database schema and operations for skills_index
"""

import json
import pickle
import sqlite3
from typing import Any


class SkillsStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize database connection and create tables."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Create skills_index table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS skills_index (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                embedding BLOB NOT NULL,
                metadata TEXT,
                source TEXT,
                repo TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_skills_source ON skills_index(source, repo)
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS skills_cache (
                context_hash TEXT PRIMARY KEY,
                skill_ids TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hits INTEGER DEFAULT 0
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS skills_usage (
                mission_id TEXT,
                agent_role TEXT,
                skill_id TEXT,
                injected BOOLEAN DEFAULT 1,
                used BOOLEAN DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def insert_skills_batch(self, skills: list[dict[str, Any]]):
        """Insert multiple skills in a transaction."""
        cursor = self.conn.cursor()

        for skill in skills:
            embedding_blob = pickle.dumps(skill["embedding"])
            metadata_json = json.dumps(skill.get("metadata", {}))

            cursor.execute(
                """
                INSERT OR REPLACE INTO skills_index 
                (id, title, content, embedding, metadata, source, repo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    skill["id"],
                    skill["title"],
                    skill.get("content", ""),
                    embedding_blob,
                    metadata_json,
                    skill["metadata"].get("source", "unknown"),
                    skill["metadata"].get("repo", ""),
                ),
            )

        self.conn.commit()
        print(f"✅ Inserted {len(skills)} skills into database")

    def get_all_skills_with_embeddings(self) -> list[dict[str, Any]]:
        """Retrieve all skills with their embeddings."""
        cursor = self.conn.execute("""
            SELECT id, title, content, embedding, metadata, source, repo
            FROM skills_index
        """)

        skills = []
        for row in cursor.fetchall():
            skills.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "embedding": pickle.loads(row["embedding"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "source": row["source"],
                    "repo": row["repo"],
                }
            )

        return skills

    def get_skill_by_id(self, skill_id: str) -> dict[str, Any] | None:
        """Get a specific skill by ID."""
        cursor = self.conn.execute(
            """
            SELECT id, title, content, metadata, source, repo
            FROM skills_index
            WHERE id = ?
        """,
            (skill_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "source": row["source"],
            "repo": row["repo"],
        }

    def get_all_skills(self) -> list[dict[str, Any]]:
        """Get all skills without embeddings (for keyword matching)."""
        cursor = self.conn.execute("""
            SELECT id, title, content, metadata, source, repo
            FROM skills_index
        """)

        skills = []
        for row in cursor.fetchall():
            skills.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "source": row["source"],
                    "repo": row["repo"],
                }
            )

        return skills

    def get_skills_count(self) -> int:
        """Get total number of indexed skills."""
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM skills_index")
        return cursor.fetchone()["count"]

    def cache_matched_skills(self, context_hash: str, skill_ids: list[str]):
        """Cache matched skills for a context."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO skills_cache (context_hash, skill_ids, hits)
            VALUES (?, ?, COALESCE((SELECT hits FROM skills_cache WHERE context_hash = ?), 0) + 1)
        """,
            (context_hash, json.dumps(skill_ids), context_hash),
        )
        self.conn.commit()

    def get_cached_skills(self, context_hash: str) -> list[str] | None:
        """Get cached skill IDs for a context."""
        cursor = self.conn.execute(
            """
            SELECT skill_ids FROM skills_cache WHERE context_hash = ?
        """,
            (context_hash,),
        )

        row = cursor.fetchone()
        if row:
            return json.loads(row["skill_ids"])
        return None

    def track_skill_usage(
        self,
        mission_id: str,
        agent_role: str,
        skill_id: str,
        injected: bool = True,
        used: bool = False,
    ):
        """Track skill injection and usage."""
        self.conn.execute(
            """
            INSERT INTO skills_usage (mission_id, agent_role, skill_id, injected, used)
            VALUES (?, ?, ?, ?, ?)
        """,
            (mission_id, agent_role, skill_id, injected, used),
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
