"""Uji pemicu update data berita (services/refresh.py) dengan skrip pipeline palsu di folder sementara."""
from __future__ import annotations

import os
import sys
import time

import pytest

from app.services import refresh

FAKE_PIPELINE = """
import os, sys, time
from pathlib import Path
lock = Path(sys.argv[0]).resolve().parent / "lock"
lock.write_text(str(os.getpid()))
print("=== UPDATE BERITA-DAMPAK mulai ===", flush=True)
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
print("=== SELESAI. Total waktu 1 dtk (exit 0) ===", flush=True)
lock.unlink()
"""


@pytest.fixture()
def fake(tmp_path, monkeypatch):
    script = tmp_path / "update_mingguan.py"
    script.write_text(FAKE_PIPELINE, encoding="utf-8")
    monkeypatch.setattr(refresh, "SCRIPT", script)
    monkeypatch.setattr(refresh, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(refresh, "LOG", tmp_path / "log.txt")
    monkeypatch.setattr(refresh, "BERITA_DIR", tmp_path)
    monkeypatch.setenv("UGM_ANALYTICS_PYTHON", sys.executable)
    return tmp_path


def _tunggu(kondisi, batas=20.0):
    akhir = time.time() + batas
    while time.time() < akhir:
        if kondisi():
            return True
        time.sleep(0.1)
    return False


def test_status_awal_idle_dan_bisa_dipicu(fake):
    st = refresh.status("2026-09-15")
    assert st["status"] == "idle" and st["trigger_available"] is True and st["updated_at"] == "2026-09-15"


def test_update_berjalan_lalu_selesai_dengan_log(fake, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "1.5")
    hasil = refresh.start()
    assert hasil["pid"] > 0
    assert _tunggu(lambda: refresh.status()["status"] == "running")
    with pytest.raises(refresh.RefreshError):  # tidak boleh dobel
        refresh.start()
    assert _tunggu(lambda: refresh.status()["status"] == "finished")
    st = refresh.status()
    assert st["last_exit"] == 0 and any("SELESAI" in line for line in st["log_tail"])


def test_lock_yatim_dibersihkan(fake):
    # PID yang hampir pasti tidak hidup -> lock basi, status terhenti, dan start() boleh jalan.
    (fake / "lock").write_text("999999")
    assert refresh.status()["status"] == "stale_lock"
    refresh.start()
    assert _tunggu(lambda: refresh.status()["status"] == "finished")


def test_tanpa_venv_pipeline_tidak_tersedia(fake, monkeypatch):
    monkeypatch.setenv("UGM_ANALYTICS_PYTHON", str(fake / "tidak-ada" / "python.exe"))
    assert refresh.status()["trigger_available"] is False
    with pytest.raises(refresh.RefreshError):
        refresh.start()


def test_pid_proses_ini_hidup_dan_pid_nol_tidak():
    assert refresh._pid_alive(os.getpid()) is True
    assert refresh._pid_alive(0) is False


def test_endpoint_refresh_khusus_admin(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.v1 import analytics
    from app.main import app

    class Fake:
        engine = object()

        def _last_update(self):
            return None

    sebelumnya = dict(app.dependency_overrides)
    app.dependency_overrides[analytics.service] = lambda: Fake()
    try:
        client = TestClient(app)
        monkeypatch.setattr(analytics, "_auth_user", lambda request, api: {"id": 2, "email": "x@ugm.ac.id", "is_admin": False})
        assert client.post("/api/v1/analytics/refresh").status_code == 403
        monkeypatch.setattr(analytics, "_auth_user", lambda request, api: {"id": 1, "email": "a@ugm.ac.id", "is_admin": True})
        monkeypatch.setattr(refresh, "start", lambda: (_ for _ in ()).throw(refresh.RefreshError("sedang jalan")))
        assert client.post("/api/v1/analytics/refresh").status_code == 409
        assert "trigger_available" in client.get("/api/v1/analytics/refresh-status").json()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
