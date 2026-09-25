"""Uji ruang kerja akreditasi (services/accreditation_workspace.py): isi item per laporan, ekstraksi, Word.

SQLite sementara dengan skema tabel akreditasi_* yang sama seperti MySQL/PostgreSQL (termasuk kolom
laporan_id dari accreditation_laporan.ensure_schema); ekstraksi AI memakai extractor palsu.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services import accreditation_workspace as ws
from app.services.accreditation_laporan import ensure_schema as ensure_laporan
from app.services.accreditation_workspace import AccreditationWorkspaceService, NotFound, WorkspaceError

DDL = [
    "CREATE TABLE akreditasi_fakultas (id INTEGER PRIMARY KEY, nama VARCHAR(150) NOT NULL, slug VARCHAR(64), url VARCHAR(500))",
    """CREATE TABLE akreditasi_prodi (id INTEGER PRIMARY KEY, fakultas_id INTEGER, nama VARCHAR(150) NOT NULL,
       jenjang VARCHAR(20), slug VARCHAR(64) NOT NULL, url VARCHAR(500))""",
    """CREATE TABLE akreditasi_data_manual (id INTEGER PRIMARY KEY, prodi_id VARCHAR(64) NOT NULL, item_id VARCHAR(64) NOT NULL,
       baris_ke INTEGER NOT NULL DEFAULT 1, kolom VARCHAR(255) NOT NULL, tahun VARCHAR(16), nilai TEXT,
       link_bukti VARCHAR(1000), diisi_oleh VARCHAR(255), updated_at TIMESTAMP)""",
    """CREATE TABLE akreditasi_upload_file (id INTEGER PRIMARY KEY, prodi_id VARCHAR(64) NOT NULL, nama_file VARCHAR(500) NOT NULL,
       path_lokal VARCHAR(1000) NOT NULL, tipe_file VARCHAR(16), ukuran_bytes INTEGER, status VARCHAR(32),
       diupload_oleh VARCHAR(255), uploaded_at TIMESTAMP, diekstrak_at TIMESTAMP)""",
    """CREATE TABLE akreditasi_upload_ekstraksi (id INTEGER PRIMARY KEY, upload_file_id INTEGER NOT NULL, prodi_id VARCHAR(64) NOT NULL,
       item_id VARCHAR(64) NOT NULL, baris_ke INTEGER NOT NULL DEFAULT 1, nama_kolom VARCHAR(255) NOT NULL, nilai TEXT,
       kutipan TEXT, created_at TIMESTAMP NOT NULL, dikonfirmasi_at TIMESTAMP)""",
    """CREATE TABLE akreditasi_riwayat_generate (id INTEGER PRIMARY KEY, user_email VARCHAR(254) NOT NULL, prodi_id VARCHAR(64) NOT NULL,
       jenis_dokumen VARCHAR(8) NOT NULL, file_path VARCHAR(512) NOT NULL, generated_at TIMESTAMP NOT NULL)""",
    """CREATE TABLE akreditasi_sessions (token_hash CHAR(64) PRIMARY KEY, user_id INTEGER NOT NULL,
       created_at TIMESTAMP NOT NULL, expires_at TIMESTAMP NOT NULL)""",
]
EMAIL = "penyusun@ugm.ac.id"
# Item tabel LKPS multi-baris dan item narasi LED dari registry asli.
TABEL = "lkps_3_c_1"
NARASI = "led_b1_sejarah"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                        connect_args={"check_same_thread": False})
    with eng.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        conn.execute(text("INSERT INTO akreditasi_fakultas (id, nama, slug) VALUES (1, 'Fakultas MIPA', 'fmipa')"))
        conn.execute(text("INSERT INTO akreditasi_prodi (id, fakultas_id, nama, jenjang, slug) "
                          "VALUES (1, 1, 'Magister Elektronika dan Instrumentasi', 'Magister', 'mei')"))
    ensure_laporan(eng)
    return eng


def buat_laporan(engine, dokumen: str, tahun: int = 2026, prodi: str = "mei") -> dict:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_laporan (prodi_id, dokumen, tahun, created_at) VALUES (:p, :d, :t, :c)"),
                     {"p": prodi, "d": dokumen, "t": tahun, "c": datetime(2026, 9, 1)})
        lap_id = conn.execute(text("SELECT id FROM akreditasi_laporan WHERE prodi_id = :p AND dokumen = :d AND tahun = :t"),
                              {"p": prodi, "d": dokumen, "t": tahun}).scalar_one()
    return {"id": lap_id, "prodi_id": prodi, "dokumen": dokumen, "tahun": tahun, "nama": None}


@pytest.fixture()
def svc(engine, tmp_path):
    return AccreditationWorkspaceService(engine, upload_root=tmp_path / "up", generated_root=tmp_path / "gen")


@pytest.fixture()
def led(engine):
    return buat_laporan(engine, "LED")


@pytest.fixture()
def lkps(engine):
    return buat_laporan(engine, "LKPS")


def _item(workspace, item_id):
    return next(i for g in workspace["groups"] for i in g["items"] if i["id"] == item_id)


def test_workspace_led_dan_lkps_terpisah(svc, led, lkps):
    a, b = svc.workspace(led), svc.workspace(lkps)
    assert a["prodi"]["nama"] == "Magister Elektronika dan Instrumentasi"
    assert a["laporan"] == {"id": led["id"], "tahun": 2026, "nama": "LED 2026"}
    assert a["ringkasan"]["lengkap"] == 0 and a["ringkasan"]["persen"] == 0
    ids_led = {i["id"] for g in a["groups"] for i in g["items"]}
    ids_lkps = {i["id"] for g in b["groups"] for i in g["items"]}
    assert NARASI in ids_led and TABEL in ids_lkps and not ids_led & ids_lkps
    # Tab LED Kriteria A/B/C memuat cuplikan tabel LKPS terkait; LKPS tidak.
    assert any(g["cuplikan"] for g in a["groups"]) and not any(g["cuplikan"] for g in b["groups"])
    kosong = _item(b, TABEL)
    assert kosong["state"] == "kosong" and kosong["rows"] == [{k: "" for k in kosong["kolom"]}]


def test_simpan_item_tabel_menulis_ulang_dan_membuang_baris_kosong(svc, engine, lkps):
    k = _item(svc.workspace(lkps), TABEL)["kolom"]
    rows = [{k[0]: "Kerja sama A", k[1]: "PT X"}, {k[0]: "", k[1]: "  "}, {k[0]: "Kerja sama B"}]
    hasil = svc.save_item(lkps, TABEL, rows, EMAIL)
    assert hasil["baris"] == 2 and hasil["sel"] == 3
    item = _item(svc.workspace(lkps), TABEL)
    assert item["state"] == "terisi" and item["diisi_oleh"] == EMAIL
    assert [r[k[0]] for r in item["rows"]] == ["Kerja sama A", "Kerja sama B"]

    svc.save_item(lkps, TABEL, [{k[0]: "Pengganti"}], EMAIL)  # simpan ulang = ganti seluruh isi
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_data_manual")).scalar() == 1
        assert conn.execute(text("SELECT laporan_id FROM akreditasi_data_manual")).scalar() == lkps["id"]
    ringkasan = svc.workspace(lkps)["ringkasan"]
    # lkps_3_c_1 berstatus "tidak_tersedia / akses_data" di data_source_map.json.
    assert ringkasan["terisi_manual"] == 1 and ringkasan["akses_data"]["lengkap"] == 1


def test_laporan_tahun_berbeda_tidak_saling_menimpa(svc, engine, lkps):
    lama = buat_laporan(engine, "LKPS", 2025)
    k = _item(svc.workspace(lkps), TABEL)["kolom"]
    svc.save_item(lama, TABEL, [{k[0]: "Tahun lalu"}], EMAIL)
    svc.save_item(lkps, TABEL, [{k[0]: "Tahun ini"}], EMAIL)
    assert _item(svc.workspace(lama), TABEL)["rows"][0][k[0]] == "Tahun lalu"
    assert _item(svc.workspace(lkps), TABEL)["rows"][0][k[0]] == "Tahun ini"


def test_simpan_narasi_hanya_satu_baris_dan_kolom_asing_diabaikan(svc, engine, led):
    k = _item(svc.workspace(led), NARASI)["kolom"]
    svc.save_item(led, NARASI, [{k[0]: "SK 1990", "kolom_liar": "x"}, {k[0]: "diabaikan"}], EMAIL)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT kolom, nilai, baris_ke FROM akreditasi_data_manual")).all()
    assert [tuple(r) for r in rows] == [(k[0], "SK 1990", 1)]


def test_simpan_menolak_input_tidak_valid(svc, monkeypatch, led, lkps):
    with pytest.raises(NotFound):
        svc.save_item(lkps, "item_tidak_ada", [], EMAIL)
    with pytest.raises(WorkspaceError):  # item LKPS tidak boleh disimpan ke laporan LED
        svc.save_item(led, TABEL, [], EMAIL)
    with pytest.raises(WorkspaceError):
        svc.save_item(lkps, TABEL, "bukan list", EMAIL)
    with pytest.raises(WorkspaceError):
        svc.save_item(lkps, TABEL, [{}] * (ws.MAX_ROWS_PER_ITEM + 1), EMAIL)
    registry = ws._registry()
    monkeypatch.setitem(registry.KEBUTUHAN_DATA[TABEL], "status_ketersediaan", "belum_tersedia")
    with pytest.raises(WorkspaceError):
        svc.save_item(lkps, TABEL, [], EMAIL)


def test_tambah_prodi_slug_unik(svc):
    a = svc.add_program(1, "Magister Kecerdasan Artifisial", "Magister")
    assert a["slug"] == "magister-kecerdasan-artifisial"
    with pytest.raises(WorkspaceError):  # nama sama di fakultas sama
        svc.add_program(1, "magister kecerdasan artifisial", "Magister")
    with pytest.raises(WorkspaceError):
        svc.add_program(1, "Prodi X", "S9")
    with pytest.raises(NotFound):
        svc.add_program(99, "Prodi X", "Sarjana")


def test_generate_word_dicatat_di_riwayat_laporan(svc, engine, lkps):
    k = _item(svc.workspace(lkps), TABEL)["kolom"]
    svc.save_item(lkps, TABEL, [{k[0]: "Kerja sama unik 123"}], EMAIL)
    content, filename = svc.generate(lkps, EMAIL)
    assert filename.startswith("Laporan_Akreditasi_LKPS_2026_mei_")
    teks = "\n".join(c.text for t in Document(BytesIO(content)).tables for r in t.rows for c in r.cells)
    assert "Kerja sama unik 123" in teks
    riwayat = svc.workspace(lkps)["riwayat_word"]
    assert len(riwayat) == 1 and riwayat[0]["oleh"] == EMAIL
    # Staf lain yang membuka laporan yang sama bisa mengunduh; akun lain tidak lewat Profil.
    assert svc.laporan_file(lkps, riwayat[0]["id"])[0] == content
    assert svc.history_file(riwayat[0]["id"], EMAIL)[0] == content
    with pytest.raises(NotFound):
        svc.history_file(riwayat[0]["id"], "lain@ugm.ac.id")
    with pytest.raises(NotFound):  # riwayat laporan lain
        svc.laporan_file(buat_laporan(engine, "LKPS", 2025), riwayat[0]["id"])


def test_riwayat_di_luar_folder_generate_ditolak(svc, engine, tmp_path):
    luar = tmp_path / "rahasia.docx"
    luar.write_bytes(b"x")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_riwayat_generate (id, user_email, prodi_id, jenis_dokumen, file_path, generated_at) "
                          "VALUES (9, :e, 'mei', 'LED', :f, '2026-09-21')"), {"e": EMAIL, "f": str(luar)})
    with pytest.raises(NotFound):
        svc.history_file(9, EMAIL)


def _upload(engine, lap, rows):
    with engine.begin() as conn:
        for upload_id, nama, status in rows:
            conn.execute(text("INSERT INTO akreditasi_upload_file (id, prodi_id, laporan_id, nama_file, path_lokal, tipe_file, status, uploaded_at) "
                              "VALUES (:id, 'mei', :l, :n, :p, 'pdf', :s, :t)"),
                         {"id": upload_id, "l": lap["id"], "n": nama, "p": f"/x/{nama}", "s": status,
                          "t": datetime(2026, 9, 20, 0, upload_id)})


def test_ekstraksi_langsung_masuk_tabel_tanpa_menimpa(engine, tmp_path, monkeypatch, lkps):
    monkeypatch.setenv("OPENAI_API_KEY", "uji")
    svc0 = AccreditationWorkspaceService(engine, generated_root=tmp_path)
    k = _item(svc0.workspace(lkps), TABEL)["kolom"]
    hasil_file = {
        "/x/a.pdf": [{"item_id": TABEL, "baris_ke": 1, "nama_kolom": k[0], "nilai": "Kerja sama A", "kutipan": "q"},
                     {"item_id": TABEL, "baris_ke": 1, "nama_kolom": k[1], "nilai": "PT A", "kutipan": "q"}],
        # File kedua: satu baris sama dengan yang sudah ada (dilewati), satu baris baru (ditambahkan).
        "/x/b.pdf": [{"item_id": TABEL, "baris_ke": 1, "nama_kolom": k[0], "nilai": "kerja  sama a", "kutipan": "q"},
                     {"item_id": TABEL, "baris_ke": 1, "nama_kolom": k[1], "nilai": "PT A", "kutipan": "q"},
                     {"item_id": TABEL, "baris_ke": 2, "nama_kolom": k[0], "nilai": "Kerja sama B", "kutipan": "q"},
                     {"item_id": TABEL, "baris_ke": 2, "nama_kolom": "Kolom Asing", "nilai": "?", "kutipan": "q"}],
    }
    calls = []

    def fake(path, tipe, dokumen, progress):
        calls.append(path)
        progress(1, 1)
        if path.endswith("rusak.pdf"):
            return [], {"n_batch": 0, "n_batch_gagal": 0, "error": "Gagal ekstrak teks file: rusak"}
        return hasil_file[path], {"n_batch": 1, "n_batch_gagal": 0}

    svc = AccreditationWorkspaceService(engine, generated_root=tmp_path, extractor=fake)
    svc.save_item(lkps, TABEL, [{k[0]: "Isian tim"}], EMAIL)          # isian tim tetap ada
    _upload(engine, lkps, [(1, "a.pdf", "belum_diekstrak"), (2, "rusak.pdf", "belum_diekstrak")])
    assert svc.start_extraction(lkps, background=False) == {"dimulai": 2}
    _upload(engine, lkps, [(3, "b.pdf", "belum_diekstrak")])
    assert svc.start_extraction(lkps, background=False) == {"dimulai": 2}  # b.pdf + rusak.pdf dicoba ulang
    ws_ = svc.workspace(lkps)
    baris = [r[k[0]] for r in _item(ws_, TABEL)["rows"]]
    assert baris == ["Isian tim", "Kerja sama A", "Kerja sama B"]
    status = {(r["nama_file"], r["kolom"], r["nilai"]): r["status"] for r in ws_["ekstraksi"]["riwayat"]}
    assert status[("a.pdf", k[0], "Kerja sama A")] == "ditambahkan"
    assert status[("b.pdf", k[0], "kerja  sama a")] == "sudah_ada"
    assert status[("b.pdf", k[0], "Kerja sama B")] == "ditambahkan"
    assert status[("b.pdf", "Kolom Asing", "?")] == "kolom_lain"
    uploads = {u["nama_file"]: u for u in ws_["uploads"]}
    assert uploads["a.pdf"]["status"] == "diekstrak"
    assert uploads["rusak.pdf"]["status"] == "gagal_ekstrak" and "rusak" in uploads["rusak.pdf"]["ringkasan"]["error"]
    with engine.connect() as conn:
        oleh = {r[0] for r in conn.execute(text("SELECT DISTINCT diisi_oleh FROM akreditasi_data_manual"))}
    assert oleh == {EMAIL, "AI: a.pdf", "AI: b.pdf"}


def test_ekstraksi_narasi_mengisi_kolom_kosong_saja(engine, tmp_path, monkeypatch, led):
    monkeypatch.setenv("OPENAI_API_KEY", "uji")
    k = _item(AccreditationWorkspaceService(engine).workspace(led), NARASI)["kolom"]

    def fake(path, tipe, dokumen, progress):
        return [{"item_id": NARASI, "baris_ke": 1, "nama_kolom": k[0], "nilai": "Versi AI", "kutipan": ""},
                {"item_id": NARASI, "baris_ke": 1, "nama_kolom": k[1], "nilai": "Kolom kosong diisi", "kutipan": ""}], {"n_batch": 1}

    svc = AccreditationWorkspaceService(engine, generated_root=tmp_path, extractor=fake)
    svc.save_item(led, NARASI, [{k[0]: "Versi tim"}], EMAIL)
    _upload(engine, led, [(1, "a.pdf", "belum_diekstrak")])
    svc.start_extraction(led, background=False)
    ws_ = svc.workspace(led)
    assert _item(ws_, NARASI)["rows"][0][k[0]] == "Versi tim"
    assert _item(ws_, NARASI)["rows"][0][k[1]] == "Kolom kosong diisi"
    assert {r["nilai"]: r["status"] for r in ws_["ekstraksi"]["riwayat"]} == {
        "Versi AI": "tidak_menimpa", "Kolom kosong diisi": "ditambahkan"}


def test_ekstraksi_butuh_api_key(svc, monkeypatch, led):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(WorkspaceError):
        svc.start_extraction(led, background=False)
    assert svc.workspace(led)["ekstraksi"]["tersedia"] is False


def test_endpoint_wajib_login():
    from app.main import app
    from app.api.v1.analytics import service

    class Fake:
        engine = create_engine("sqlite+pysqlite:///:memory:")

    sebelumnya = dict(app.dependency_overrides)
    app.dependency_overrides[service] = lambda: Fake()
    try:
        client = TestClient(app)
        with Fake.engine.begin() as conn:
            conn.execute(text("CREATE TABLE akreditasi_users (id INTEGER, email TEXT, nama TEXT, is_admin INTEGER, is_blocked INTEGER)"))
            conn.execute(text("CREATE TABLE akreditasi_sessions (token_hash TEXT, user_id INTEGER, expires_at TIMESTAMP)"))
        for method, path in [("get", "/api/v1/analytics/accreditation/workspace?laporan_id=1"),
                             ("get", "/api/v1/analytics/accreditation/laporan?prodi_id=mei"),
                             ("post", "/api/v1/analytics/accreditation/laporan"),
                             ("post", "/api/v1/analytics/accreditation/prodi/mei/buka"),
                             ("post", "/api/v1/analytics/accreditation/prodi/mei/kunci"),
                             ("post", "/api/v1/analytics/accreditation/prodi/mei/reset"),
                             ("get", "/api/v1/analytics/accreditation/admin/reset"),
                             ("post", "/api/v1/analytics/accreditation/workspace/items/x"),
                             ("post", "/api/v1/analytics/accreditation/programs"),
                             ("post", "/api/v1/analytics/accreditation/extractions"),
                             ("post", "/api/v1/analytics/accreditation/generate"),
                             ("get", "/api/v1/analytics/accreditation/history/1/file"),
                             ("get", "/api/v1/analytics/accreditation/laporan/1/riwayat/1/file")]:
            kwargs = {"json": {}} if method == "post" else {}
            assert getattr(client, method)(path, **kwargs).status_code == 401, path
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)


def test_hapus_laporan_membersihkan_data_dan_berkas(svc, engine, tmp_path, lkps):
    k = _item(svc.workspace(lkps), TABEL)["kolom"]
    lain = buat_laporan(engine, "LKPS", 2025)
    svc.save_item(lkps, TABEL, [{k[0]: "Dihapus"}], EMAIL)
    svc.save_item(lain, TABEL, [{k[0]: "Tetap"}], EMAIL)
    unggah = tmp_path / "up" / "mei" / "a.pdf"
    unggah.parent.mkdir(parents=True)
    unggah.write_bytes(b"x")
    luar = tmp_path / "luar.pdf"
    luar.write_bytes(b"x")
    with engine.begin() as conn:
        for i, path in ((1, unggah), (2, luar)):
            conn.execute(text("INSERT INTO akreditasi_upload_file (id, prodi_id, laporan_id, nama_file, path_lokal, tipe_file, status, uploaded_at) "
                              "VALUES (:i, 'mei', :l, 'a.pdf', :p, 'pdf', 'diekstrak', '2026-09-20')"), {"i": i, "l": lkps["id"], "p": str(path)})
    content, _ = svc.generate(lkps, EMAIL)
    word = next((tmp_path / "gen").rglob("*.docx"))
    hasil = svc.hapus_laporan(lkps)
    assert "LKPS 2026 dihapus" in hasil["message"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_laporan WHERE id = :l"), {"l": lkps["id"]}).scalar() == 0
        for tabel in ("akreditasi_data_manual", "akreditasi_upload_file", "akreditasi_riwayat_generate"):
            assert conn.execute(text(f"SELECT COUNT(*) FROM {tabel} WHERE laporan_id = :l"), {"l": lkps["id"]}).scalar() == 0
    assert not unggah.exists() and not word.exists()
    assert luar.exists()  # berkas di luar folder upload/generate tidak disentuh
    assert _item(svc.workspace(lain), TABEL)["rows"][0][k[0]] == "Tetap"  # laporan lain utuh
