import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS clones (
    slug              TEXT PRIMARY KEY,
    edit_secret       TEXT NOT NULL,
    name              TEXT NOT NULL,
    provider          TEXT NOT NULL DEFAULT 'gemini',
    api_key_encrypted BLOB NOT NULL,
    system_prompt     TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def insert_clone(
    slug: str,
    edit_secret: str,
    name: str,
    provider: str,
    api_key_encrypted: bytes,
    system_prompt: str,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO clones (slug, edit_secret, name, provider, api_key_encrypted, system_prompt) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (slug, edit_secret, name, provider, api_key_encrypted, system_prompt),
        )


def get_clone(slug: str) -> sqlite3.Row | None:
    with connect() as conn:
        cur = conn.execute("SELECT * FROM clones WHERE slug = ?", (slug,))
        return cur.fetchone()


def update_clone(
    slug: str,
    name: str,
    system_prompt: str,
    api_key_encrypted: bytes | None = None,
) -> None:
    with connect() as conn:
        if api_key_encrypted is not None:
            conn.execute(
                "UPDATE clones SET name=?, system_prompt=?, api_key_encrypted=? WHERE slug=?",
                (name, system_prompt, api_key_encrypted, slug),
            )
        else:
            conn.execute(
                "UPDATE clones SET name=?, system_prompt=? WHERE slug=?",
                (name, system_prompt, slug),
            )
