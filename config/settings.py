from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_path: str
    upload_dir: str
    log_path: str
    chroma_dir: str
    gemini_api_key: str
    gemini_model: str


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(
        database_path=os.getenv("DATABASE_PATH", str(root / "data" / "knowledgebridge.db")),
        upload_dir=os.getenv("UPLOAD_DIR", str(root / "data" / "uploads")),
        log_path=os.getenv("LOG_PATH", str(root / "logs" / "knowledgebridge.log")),
        chroma_dir=os.getenv("CHROMA_DIR", str(root / "data" / "chroma")),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    )
