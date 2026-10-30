from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT,
    team TEXT, role TEXT, is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS handovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
    outgoing_user_id INTEGER NOT NULL, incoming_user_id INTEGER NOT NULL,
    project_name TEXT NOT NULL, transfer_date TEXT NOT NULL, transfer_scope TEXT NOT NULL DEFAULT 'General',
    description TEXT,
    notes TEXT, status TEXT NOT NULL DEFAULT 'Active',
    created_by INTEGER, accepted_by INTEGER, accepted_at TEXT,
    readiness_score REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(outgoing_user_id) REFERENCES users(id), FOREIGN KEY(incoming_user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT, handover_id INTEGER, title TEXT NOT NULL,
    file_name TEXT NOT NULL, file_type TEXT NOT NULL, storage_path TEXT,
    extracted_text TEXT NOT NULL, uploader TEXT, project_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(handover_id) REFERENCES handovers(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, handover_id INTEGER NOT NULL, title TEXT NOT NULL,
    meeting_date TEXT NOT NULL, agenda TEXT, notes TEXT, summary TEXT,
    participants TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(handover_id) REFERENCES handovers(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, handover_id INTEGER NOT NULL, meeting_id INTEGER,
    decision_text TEXT NOT NULL, rationale TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(handover_id) REFERENCES handovers(id) ON DELETE CASCADE,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, handover_id INTEGER NOT NULL, meeting_id INTEGER,
    title TEXT NOT NULL, description TEXT, owner_id INTEGER, due_date TEXT,
    priority TEXT NOT NULL DEFAULT 'Medium', status TEXT NOT NULL DEFAULT 'Open',
    outcome TEXT, completed_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(handover_id) REFERENCES handovers(id) ON DELETE CASCADE,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE SET NULL,
    FOREIGN KEY(owner_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, event_type TEXT NOT NULL,
    old_value TEXT, new_value TEXT, note TEXT, actor_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS handover_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, handover_id INTEGER NOT NULL,
    event_type TEXT NOT NULL, actor_id INTEGER, details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(handover_id) REFERENCES handovers(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, correlation_id TEXT NOT NULL, event_type TEXT NOT NULL,
    entity_type TEXT, entity_id INTEGER, metadata_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

SEED_USERS = [
    ("Aarav Mehta", "aarav@example.com", "Platform", "Senior Engineer"),
    ("Maya Shah", "maya@example.com", "Platform", "Engineer"),
    ("Rohan Kulkarni", "rohan@example.com", "Data", "Data Analyst"),
    ("Isha Patel", "isha@example.com", "Product", "Product Manager"),
]


def get_connection(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(str(path)) as connection:
        connection.executescript(SCHEMA)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(documents)")}
        for column in ("uploader", "project_name"):
            if column not in columns:
                connection.execute(f"ALTER TABLE documents ADD COLUMN {column} TEXT")
        handover_columns = {row["name"] for row in connection.execute("PRAGMA table_info(handovers)")}
        migrations = {
            "transfer_scope": "TEXT NOT NULL DEFAULT 'General'",
            "created_by": "INTEGER",
            "accepted_by": "INTEGER",
            "accepted_at": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in handover_columns:
                connection.execute(f"ALTER TABLE handovers ADD COLUMN {column} {definition}")
        history_columns = {row["name"] for row in connection.execute("PRAGMA table_info(task_history)")}
        if "actor_id" not in history_columns:
            connection.execute("ALTER TABLE task_history ADD COLUMN actor_id INTEGER")
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO users(name,email,team,role) VALUES(?,?,?,?)", SEED_USERS
            )
        if connection.execute("SELECT COUNT(*) FROM handovers").fetchone()[0] == 0:
            connection.execute(
                """INSERT INTO handovers(title,outgoing_user_id,incoming_user_id,project_name,
                   transfer_date,transfer_scope,description,notes,status,created_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                ("Payments Platform Handover", 1, 2, "Payments Platform",
                 "2026-11-15", "Service ownership and release operations",
                 "Transfer ownership of payment APIs, release procedures and incident context.",
                 "Sample transfer. Review the open release checklist and rollback process.",
                 "In Progress", 1),
            )
            handover_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                "INSERT INTO tasks(handover_id,title,description,owner_id,due_date,priority) VALUES(?,?,?,?,?,?)",
                (handover_id, "Review rollback runbook", "Validate rollback steps with the incoming owner.", 2, "2026-11-10", "High"),
            )
            task_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                "INSERT INTO task_history(task_id,event_type,new_value,note,actor_id) VALUES(?,?,?,?,?)",
                (task_id, "created", "Open", "Seeded demonstration task", 1),
            )
            connection.execute(
                "INSERT INTO handover_history(handover_id,event_type,actor_id,details) VALUES(?,?,?,?)",
                (handover_id, "created", 1, "Sample transfer created for demonstration"),
            )


@contextmanager
def transaction(database_path: str) -> Iterator[sqlite3.Connection]:
    connection = get_connection(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
