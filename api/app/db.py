from __future__ import annotations

from functools import lru_cache

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine

from app.config import load_settings


def build_database_url() -> URL:
    # Dibaca saat dipanggil (bukan saat impor) supaya perubahan env setelah impor ikut terbaca.
    settings = load_settings()
    settings.require_postgres()
    return URL.create(
        "postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_database,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(build_database_url(), pool_pre_ping=True, pool_recycle=3600)
