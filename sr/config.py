"""Runtime configuration, loaded from environment / .env with the ``SR_`` prefix."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./storage/dev.db"

    queue_backend: str = "inline"  # "inline" | "rq"
    redis_url: str = "redis://localhost:6379/0"

    storage_root: Path = REPO_ROOT / "storage"

    music_provider: str = "local_synth"
    music_http_url: str = ""
    voice_provider: str = "local_dsp"
    voice_http_url: str = ""
    stem_provider: str = "center_split"
    stem_http_url: str = ""
    analysis_provider: str = "local_mir"
    analysis_http_url: str = ""
    mastering_provider: str = "mock"
    transcription_provider: str = "mock"

    log_level: str = "INFO"
    default_seed: int = 1337
    api_cors_origins: str = "http://localhost:3000"

    # Stage 11: vocal morph / timbre blend is experimental and off by default.
    experimental_morph: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    def resolved_storage_root(self) -> Path:
        root = self.storage_root
        if not root.is_absolute():
            root = (REPO_ROOT / root).resolve()
        return root


@lru_cache
def get_settings() -> Settings:
    return Settings()
