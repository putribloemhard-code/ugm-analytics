from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_postgres_engine_url_uses_environment(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "ugm_app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "not-a-real-secret")
    monkeypatch.setenv("POSTGRES_DB", "ugm_analytics")

    from app.db import build_database_url

    url = build_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "postgres"
    assert url.port == 5432
    assert url.database == "ugm_analytics"
    assert url.username == "ugm_app"
