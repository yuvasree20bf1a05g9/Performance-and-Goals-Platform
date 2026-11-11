"""Runtime settings (12-factor: everything overridable through environment variables)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_profile: str
    frontend_dist: Path
    cors_origins: list[str]

    @property
    def data_dir(self) -> Path:
        return ROOT / "data" / self.data_profile


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'backend' / 'performance.db').as_posix()}"),
        data_profile=os.getenv("DATA_PROFILE", "full"),
        frontend_dist=Path(os.getenv("FRONTEND_DIST", ROOT / "frontend" / "dist")),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    )
