from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    postgres_host: str | None
    postgres_port: int
    postgres_user: str | None
    postgres_password: str | None
    postgres_database: str | None
    api_cors_origins: tuple[str, ...]
    api_prefix: str = "/api/v1"
    accreditation_upload_dir: str = "/app/data/accreditation/uploads"
    accreditation_generated_dir: str = "/app/data/accreditation/generated"
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


def load_settings() -> Settings:
    """Baca ulang dari environment setiap kali dipanggil.

    Sebelumnya `settings = Settings()` dibuat saat impor, sehingga nilai env yang diubah setelah
    impor (monkeypatch di test, atau skrip pratinjau seperti web/dev_api_mysql.py) tidak terbaca.
    """
    return Settings(
        postgres_host=os.getenv("POSTGRES_HOST"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_user=os.getenv("POSTGRES_USER"),
        postgres_password=os.getenv("POSTGRES_PASSWORD"),
        postgres_database=os.getenv("POSTGRES_DB"),
        api_cors_origins=tuple(
            origin.strip()
            for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        ),
        accreditation_upload_dir=os.getenv("ACCREDITATION_UPLOAD_DIR", "/app/data/accreditation/uploads"),
        accreditation_generated_dir=os.getenv("ACCREDITATION_GENERATED_DIR", "/app/data/accreditation/generated"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings untuk pemakaian runtime (di-cache supaya tidak parse env tiap request)."""
    return load_settings()


class _SettingsProxy:
    """`settings.<nama>` tetap jalan seperti objek biasa, tapi selalu membaca env terbaru.

    Kompatibilitas: kode lama (dan test) memakai `from app.config import settings`.
    """

    def __getattr__(self, name: str):
        return getattr(load_settings(), name)


settings = _SettingsProxy()
