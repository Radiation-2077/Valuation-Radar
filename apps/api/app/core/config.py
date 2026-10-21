from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "估值雷达 API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'storage' / 'app.db'}"
    legacy_data_dir: Path = PROJECT_ROOT.parent / "data"
    legacy_reports_dir: Path = PROJECT_ROOT.parent
    legacy_common_dir: Path = PROJECT_ROOT.parent / "common"
    timezone: str = "Asia/Shanghai"
    codex_binary: str = "codex"
    codex_timeout_seconds: int = 1_200
    codex_model: str | None = None
    frontend_dist: Path = PROJECT_ROOT / "apps" / "web" / "dist"
    storage_root: Path = PROJECT_ROOT / "storage"

    @property
    def staging_dir(self) -> Path:
        return self.storage_root / "staging"

    def ensure_storage(self) -> None:
        for path in (
            self.storage_root,
            self.staging_dir,
            self.storage_root / "backups",
            self.storage_root / "logs",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
