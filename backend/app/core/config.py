import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    app_name: str = "RenalSight API"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'renalsight.db').as_posix()}"
    secret_key: str = ""                      # set in .env; a random one is generated per run if empty (dev only)
    access_token_minutes: int = 60 * 12
    cors_origins: str = ("http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,"
                         "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000")
    cors_origin_regex: str = r"https://.*\.app\.github\.dev"      # GitHub Codespaces forwarded ports
    ml_dir: str = str(ROOT / "ml")

    # ---- AI Buddy providers (all optional; keys live only here, never in the front end)
    llm_chain: str = "gemini,groq,openai,xai,ollama,rules"
    llm_timeout_seconds: float = 25.0
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    xai_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    groq_model: str = "openai/gpt-oss-120b"
    openai_model: str = "gpt-4o-mini"
    xai_model: str = "grok-3-mini"
    ollama_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_enabled: bool = False        # set true once Ollama is installed and running
    buddy_messages_per_minute: int = 12

    # ---- proactive helpers
    scheduler_enabled: bool = True
    scheduler_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.secret_key:
        s.secret_key = secrets.token_urlsafe(48)
        print("[warn] SECRET_KEY not set in backend/.env: using a temporary key (tokens reset on restart).")
    return s
