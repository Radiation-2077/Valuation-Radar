from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings


def test_relative_storage_root_resolves_from_project_root() -> None:
    settings = Settings(storage_root=Path("relative-storage"))

    assert settings.storage_root == (PROJECT_ROOT / "relative-storage").resolve()
    assert settings.staging_dir.is_absolute()
