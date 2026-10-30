from pathlib import Path
import sqlite3
from typing import Any

from database.connection import get_connection


def query(database_path: str, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with get_connection(database_path) as connection:
        return connection.execute(sql, params).fetchall()


def execute(database_path: str, sql: str, params: tuple[Any, ...] = ()) -> int:
    with get_connection(database_path) as connection:
        cursor = connection.execute(sql, params)
        connection.commit()
        return int(cursor.lastrowid)


def ensure_directories(upload_dir: str) -> None:
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
