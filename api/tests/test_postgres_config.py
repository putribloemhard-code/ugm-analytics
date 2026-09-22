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


def test_deploy_compose_requires_every_variable():
    """compose.yml harus GAGAL kalau .env tidak lengkap, bukan diam-diam pakai string kosong."""
    import re

    compose_path = ROOT / "deploy" / "compose.yml"
    env_example_path = ROOT / "deploy" / ".env.example"
    assert compose_path.is_file(), "deploy/compose.yml must exist"
    assert env_example_path.is_file(), "deploy/.env.example must exist"

    # Komentar sering memuat contoh sintaks, jadi abaikan dulu; yang diperiksa hanya baris aktif.
    compose_text = "\n".join(
        line for line in compose_path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")
    )
    example_text = env_example_path.read_text(encoding="utf-8")

    # $$VAR (healthcheck) sengaja dilewati: itu escape Compose, bukan interpolasi host.
    raw = re.findall(r"(?<!\$)\$\{([^}]+)\}", compose_text)
    unguarded = [item for item in raw if ":?" not in item]
    assert not unguarded, (
        "Variabel berikut dipakai tanpa guard ':?' sehingga nilai kosong lolos diam-diam: "
        f"{sorted(unguarded)} — pakai ${VAR:?pesan}"
    )

    required = {item.split(":?")[0] for item in raw}
    defined = {
        line.split("=", 1)[0].strip()
        for line in example_text.splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    }
    missing = required - defined
    assert not missing, f"Variables in compose.yml missing from .env.example: {sorted(missing)}"

    # .env.example ikut ter-commit: nilai password di sana wajib masih placeholder.
    for name in ("POSTGRES_PASSWORD", "SOURCE_MYSQL_PASSWORD", "SOURCE_MYSQL_ROOT_PASSWORD"):
        line = next(line for line in example_text.splitlines() if line.startswith(name + "="))
        value = line.split("=", 1)[1].strip()
        assert value.startswith("replace"), (
            f"{name} di deploy/.env.example bukan placeholder lagi ({value!r}) — "
            "secret nyata tidak boleh masuk file yang di-commit"
        )

