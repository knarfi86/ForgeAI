from pathlib import Path


class Config:
    APP_NAME = "ForgeAI"
    LOCAL_OLLAMA_URL = "http://localhost:11434"
    DEFAULT_OLLAMA_URL = LOCAL_OLLAMA_URL
    DEFAULT_MODEL = "qwen2.5-coder:latest"
    BASE_DIR = Path.home() / ".forgeai"
    DATABASE_PATH = BASE_DIR / "forgeai.db"
    CHAT_EXPORT_DIR = BASE_DIR / "chats"
    PROJECTS_DIR = BASE_DIR / "projects"
    LOG_DIR = BASE_DIR / "logs"
    LOG_PATH = LOG_DIR / "ForgeAI.log"

    @classmethod
    def ensure_directories(cls) -> None:
        for directory in (cls.BASE_DIR, cls.CHAT_EXPORT_DIR, cls.PROJECTS_DIR, cls.LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)
