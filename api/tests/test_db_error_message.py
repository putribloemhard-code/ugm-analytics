"""Uji pesan error saat basis data tidak bisa dihubungi.

Penyebab paling sering di laptop: servis MySQL belum menyala, sehingga koneksi ditolak.
Tanpa penanganan ini klien melihat 500 dan mengira kodenya rusak.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_operational_error_jadi_503_dengan_pesan_jelas():
    @app.get("/_uji/db-mati")
    def db_mati():  # pragma: no cover - hanya dipanggil lewat uji
        raise OperationalError("SELECT 1", {}, Exception("Can't connect to MySQL server on 'localhost'"))

    response = client.get("/_uji/db-mati")
    assert response.status_code == 503
    body = response.json()
    assert "tidak dapat dihubungi" in body["detail"]
    assert "MySQL" in body["penyebab"] or "connect" in body["penyebab"].lower()
