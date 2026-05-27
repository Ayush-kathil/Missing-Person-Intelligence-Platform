import sqlite3
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path
from logger_config import logger

DB_PATH = Path(os.getenv("DB_PATH", "sessions.db"))


def init_db():
    """Initializes the SQLite database and creates the sessions table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)
            conn.commit()
    except Exception as e:
        logger.bind(event="db_init_error", error=str(e)).error(
            "Failed to initialize database"
        )


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves session metadata from SQLite."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data FROM sessions WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    except Exception as e:
        logger.bind(event="db_get_error", error=str(e)).error(
            f"Failed to get session {session_id}"
        )
        return None


def set_session(session_id: str, data: Dict[str, Any]) -> None:
    """Stores session metadata in SQLite."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_id, data) 
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET data=excluded.data
            """,
                (session_id, json.dumps(data)),
            )
            conn.commit()
    except Exception as e:
        logger.bind(event="db_set_error", error=str(e)).error(
            f"Failed to set session {session_id}"
        )


def delete_session(session_id: str) -> None:
    """Deletes a session from SQLite."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
    except Exception as e:
        logger.bind(event="db_delete_error", error=str(e)).error(
            f"Failed to delete session {session_id}"
        )


def flush_all_sessions() -> None:
    """Flushes all session data from SQLite."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions")
            conn.commit()
    except Exception as e:
        logger.bind(event="db_flush_error", error=str(e)).error(
            "Failed to flush all sessions"
        )


# Initialize DB on module load
init_db()
