"""
question_bank.py — SQLite-backed persistent store for generated SQL questions.
"""

import sqlite3
import uuid
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

_DEFAULT_DB_PATH = "/tmp/questions.db" if os.getenv("VERCEL") else "data/questions.db"
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS questions (
    id                  TEXT PRIMARY KEY,
    difficulty          TEXT,
    topic               TEXT,
    question_text       TEXT,
    schema_sql          TEXT,
    seed_sql            TEXT,
    answer_sql          TEXT,
    expected_output     TEXT,
    status              TEXT DEFAULT 'pending_review',
    valid               INTEGER DEFAULT 0,
    clarity_score       REAL,
    generation_attempt  INTEGER DEFAULT 1,
    review_notes        TEXT,
    blueprint_json      TEXT,
    metadata_json       TEXT,
    created_at          TEXT,
    updated_at          TEXT
);
"""


class QuestionStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuestionBank:
    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        logger.info("QuestionBank ready. db=%s", db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(_DDL)
            conn.commit()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save(self, question_data: dict) -> str:
        """
        Persist a generated question. Returns the assigned UUID question_id.

        Expected keys in question_data:
            question_text, schema_sql, seed_sql, answer_sql,
            expected_output (list|str), difficulty, topic,
            valid (bool|int), clarity_score (float),
            generation_attempt (int), blueprint (dict|obj), metadata (dict)
        """
        question_id = str(uuid.uuid4())
        now = _now_iso()

        expected_output = question_data.get("expected_output", [])
        if not isinstance(expected_output, str):
            expected_output = json.dumps(expected_output, ensure_ascii=False)

        blueprint = question_data.get("blueprint")
        if blueprint is not None and not isinstance(blueprint, str):
            try:
                blueprint = json.dumps(
                    blueprint.model_dump() if hasattr(blueprint, "model_dump") else blueprint.__dict__,
                    ensure_ascii=False,
                )
            except Exception:
                blueprint = str(blueprint)

        metadata = question_data.get("metadata", {})
        if not isinstance(metadata, str):
            metadata = json.dumps(metadata, ensure_ascii=False)

        valid_flag = 1 if question_data.get("valid") else 0

        row = (
            question_id,
            question_data.get("difficulty"),
            question_data.get("topic"),
            question_data.get("question_text"),
            question_data.get("schema_sql"),
            question_data.get("seed_sql"),
            question_data.get("answer_sql"),
            expected_output,
            question_data.get("status", QuestionStatus.PENDING_REVIEW),
            valid_flag,
            question_data.get("clarity_score"),
            question_data.get("generation_attempt", 1),
            question_data.get("review_notes", ""),
            blueprint,
            metadata,
            now,
            now,
        )

        sql = """
            INSERT INTO questions (
                id, difficulty, topic, question_text, schema_sql, seed_sql,
                answer_sql, expected_output, status, valid, clarity_score,
                generation_attempt, review_notes, blueprint_json, metadata_json,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        with self._connect() as conn:
            conn.execute(sql, row)
            conn.commit()

        logger.info("Saved question. id=%s difficulty=%s topic=%s", question_id, question_data.get("difficulty"), question_data.get("topic"))
        return question_id

    def update_status(self, question_id: str, status: str, review_notes: str = "") -> bool:
        sql = """
            UPDATE questions
            SET status = ?, review_notes = ?, updated_at = ?
            WHERE id = ?
        """
        with self._connect() as conn:
            cursor = conn.execute(sql, (status, review_notes, _now_iso(), question_id))
            conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, question_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        return dict(row) if row else None

    def list_questions(
        self,
        status: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        conditions = []
        params: list = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if difficulty:
            conditions.append("difficulty = ?")
            params.append(difficulty)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM questions {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]

            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM questions GROUP BY status"
            ).fetchall()

            by_difficulty_rows = conn.execute(
                "SELECT difficulty, COUNT(*) as cnt FROM questions GROUP BY difficulty"
            ).fetchall()

            valid_count = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE valid = 1"
            ).fetchone()[0]

        by_status = {r["status"]: r["cnt"] for r in by_status_rows}
        by_difficulty = {r["difficulty"]: r["cnt"] for r in by_difficulty_rows}
        valid_rate = round(valid_count / total, 4) if total > 0 else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_difficulty": by_difficulty,
            "valid_rate": valid_rate,
        }

    def get_archived_fallback(self, difficulty: str, topic: str) -> Optional[dict]:
        """
        Returns a random approved/archived question matching difficulty + topic
        to use as fallback when generation exhausts all retries.
        """
        sql = """
            SELECT * FROM questions
            WHERE status IN ('approved', 'archived')
              AND difficulty = ?
              AND topic = ?
              AND valid = 1
            ORDER BY RANDOM()
            LIMIT 1
        """
        with self._connect() as conn:
            row = conn.execute(sql, (difficulty, topic)).fetchone()

        if row is None:
            # Relax topic constraint as secondary fallback
            sql_relaxed = """
                SELECT * FROM questions
                WHERE status IN ('approved', 'archived')
                  AND difficulty = ?
                  AND valid = 1
                ORDER BY RANDOM()
                LIMIT 1
            """
            with self._connect() as conn:
                row = conn.execute(sql_relaxed, (difficulty,)).fetchone()

        return dict(row) if row else None
