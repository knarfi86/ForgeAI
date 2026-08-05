import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(chat_id) REFERENCES chats(id)
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                last_opened TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.connection.commit()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(query, params)
        self.connection.commit()
        return cursor

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.connection.execute(query, params).fetchall()

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.connection.execute(query, params).fetchone()

    def close(self) -> None:
        self.connection.close()
