"""SQLite persistence: connection handling, schema, and demo seed data."""
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',   -- sanitized HTML
    version    INTEGER NOT NULL DEFAULT 1, -- optimistic-concurrency counter
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS document_shares (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('viewer', 'editor')),
    created_at  TEXT NOT NULL,
    PRIMARY KEY (document_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_shares_user ON document_shares(user_id);
"""

DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("alice@ajaia.test", "Alice Owner"),
    ("bob@ajaia.test", "Bob Editor"),
    ("carol@ajaia.test", "Carol Viewer"),
]

WELCOME_HTML = (
    "<h1>Welcome to Ajaia Docs</h1>"
    "<p>This is a <strong>seeded</strong> document owned by Alice. It is shared with "
    "<em>Bob</em> as an <u>editor</u> and with Carol as a viewer.</p>"
    "<h2>Try this</h2>"
    "<ul><li>Format text with the toolbar or Ctrl/Cmd+B, I, U</li>"
    "<li>Open the Share dialog to grant access</li>"
    "<li>Import a .txt, .md or .docx file</li></ul>"
    "<ol><li>Edits autosave</li><li>Refresh the page: everything is still here</li></ol>"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(app) -> None:
    """Create tables and seed demo users + one shared document (idempotent)."""
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        if not app.config.get("SEED_DEMO_DATA", True):
            conn.commit()
            return
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            pw = generate_password_hash(DEMO_PASSWORD)
            conn.executemany(
                "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                [(email, name, pw) for email, name in DEMO_USERS],
            )
            ids = {r[0]: r[1] for r in conn.execute("SELECT email, id FROM users")}
            ts = now_iso()
            cur = conn.execute(
                "INSERT INTO documents (owner_id, title, content, created_at, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (ids["alice@ajaia.test"], "Welcome to Ajaia Docs", WELCOME_HTML, ts, ts,
                 ids["alice@ajaia.test"]),
            )
            doc_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO document_shares (document_id, user_id, role, created_at) VALUES (?, ?, ?, ?)",
                [(doc_id, ids["bob@ajaia.test"], "editor", ts),
                 (doc_id, ids["carol@ajaia.test"], "viewer", ts)],
            )
        conn.commit()
    finally:
        conn.close()
