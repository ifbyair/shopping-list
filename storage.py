"""
storage.py — handles all persistence for the shopping agent.

Two responsibilities:
  1. Shopping list → JSON file (unchanged)
  2. Conversation history → SQLite database (new)

SQLite is built into Python, needs no server, and survives process restarts.
On Railway, we'll mount a volume so it also survives deploys.
"""

import json
import os
import sqlite3

DATA_FILE = "shopping_list.json"
DB_FILE   = "/app/data/conversations.db"

DEFAULT_DATA = {
    "items": [
        {"name": "toilet paper", "status": "inactive", "staple": True},
        {"name": "dish soap",    "status": "inactive", "staple": True},
        {"name": "olive oil",    "status": "inactive", "staple": True},
        {"name": "coffee",       "status": "inactive", "staple": True},
    ]
}


# ── Shopping list (unchanged) ─────────────────────────────────────────────────

def load() -> dict:
    if not os.path.exists(DATA_FILE):
        save(DEFAULT_DATA)
        return DEFAULT_DATA
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Conversation history ──────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure the table exists."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            sender  TEXT PRIMARY KEY,
            history TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def load_history(sender: str) -> list:
    """Load conversation history for a sender. Returns empty list if none."""
    conn = _get_db()
    row = conn.execute(
        "SELECT history FROM conversations WHERE sender = ?", (sender,)
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else []


def save_history(sender: str, history: list) -> None:
    """Save (upsert) conversation history for a sender."""
    conn = _get_db()
    conn.execute("""
        INSERT INTO conversations (sender, history)
        VALUES (?, ?)
        ON CONFLICT(sender) DO UPDATE SET history = excluded.history
    """, (sender, json.dumps(history)))
    conn.commit()
    conn.close()


def clear_history(sender: str) -> None:
    """Clear conversation history for a sender (e.g. on user request)."""
    conn = _get_db()
    conn.execute("DELETE FROM conversations WHERE sender = ?", (sender,))
    conn.commit()
    conn.close()
