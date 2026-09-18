from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_host: str | None = os.getenv("POSTGRES_HOST")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str | None = os.getenv("POSTGRES_USER")
    postgres_password: str | None = os.getenv("POSTGRES_PASSWORD")
    postgres_database: str | None = os.getenv("POSTGRES_DB")
    api_cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    )
    api_prefix: str = "/api/v1"
    accreditation_upload_dir: str = os.getenv("ACCREDITATION_UPLOAD_DIR", "/app/data/accreditation/uploads")
    accreditation_max_upload_bytes: int = 25 * 1024 * 1024

    def require_postgres(self) -> None:
        missing = [
            name
            for name, value in {
                "POSTGRES_HOST": self.postgres_host,
                "POSTGRES_USER": self.postgres_user,
                "POSTGRES_PASSWORD": self.postgres_password,
                "POSTGRES_DB": self.postgres_database,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing PostgreSQL settings: {', '.join(missing)}")


settings = Settings()
