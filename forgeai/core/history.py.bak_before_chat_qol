from forgeai.core.database import Database


class History:
    def __init__(self, database: Database):
        self.database = database

    def create_chat(self, title: str = "Neuer Chat") -> int:
        return self.database.execute("INSERT INTO chats(title) VALUES(?)", (title,)).lastrowid

    def list_chats(self):
        return self.database.fetchall("SELECT * FROM chats ORDER BY updated_at DESC, id DESC")

    def delete_chat(self, chat_id: int) -> None:
        self.database.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        self.database.execute("DELETE FROM chats WHERE id=?", (chat_id,))

    def add_message(self, chat_id: int, role: str, content: str) -> None:
        self.database.execute("INSERT INTO messages(chat_id, role, content) VALUES(?,?,?)", (chat_id, role, content))
        self.database.execute("UPDATE chats SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (chat_id,))

    def messages(self, chat_id: int):
        return self.database.fetchall("SELECT * FROM messages WHERE chat_id=? ORDER BY id", (chat_id,))

    def title_chat(self, chat_id: int, title: str) -> None:
        self.database.execute("UPDATE chats SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (title, chat_id))
