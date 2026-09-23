"""Uji ruang kerja akreditasi (services/accreditation_workspace.py): isi item, draft AI, prodi, Word.

SQLite sementara dengan skema tabel akreditasi_* yang sama seperti MySQL/PostgreSQL; ekstraksi
AI memakai extractor palsu, jadi tidak ada panggilan jaringan.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services import accreditation_workspace as ws
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
    return eng


@pytest.fixture()
def svc(engine, tmp_path):
    return AccreditationWorkspaceService(engine, upload_root=tmp_path / "up", generated_root=tmp_path / "gen")


def _item(workspace, item_id):
    return next(i for g in workspace["groups"] for i in g["items"] if i["id"] == item_id)


def _kolom(svc, dokumen, item_id):
    return _item(svc.workspace("mei", dokumen), item_id)["kolom"]


def test_workspace_led_dan_lkps_terpisah(svc):
    led, lkps = svc.workspace("mei", "LED"), svc.workspace("mei", "LKPS")
    assert led["prodi"]["nama"] == "Magister Elektronika dan Instrumentasi"
    assert led["ringkasan"]["lengkap"] == 0 and led["ringkasan"]["persen"] == 0
    ids_led = {i["id"] for g in led["groups"] for i in g["items"]}
    ids_lkps = {i["id"] for g in lkps["groups"] for i in g["items"]}
    assert NARASI in ids_led and TABEL in ids_lkps and not ids_led & ids_lkps
    # Tab LED Kriteria A/B/C memuat cuplikan tabel LKPS terkait; LKPS tidak.
    assert any(g["cuplikan"] for g in led["groups"]) and not any(g["cuplikan"] for g in lkps["groups"])
    kosong = _item(lkps, TABEL)
    assert kosong["state"] == "kosong" and kosong["rows"] == [{k: "" for k in kosong["kolom"]}]


def test_workspace_prodi_tidak_dikenal(svc):
    with pytest.raises(NotFound):
        svc.workspace("tidak-ada", "LED")
    with pytest.raises(WorkspaceError):
        svc.workspace("mei", "APT")


def test_simpan_item_tabel_menulis_ulang_dan_membuang_baris_kosong(svc, engine):
    k = _kolom(svc, "LKPS", TABEL)
    rows = [{k[0]: "Kerja sama A", k[1]: "PT X"}, {k[0]: "", k[1]: "  "}, {k[0]: "Kerja sama B"}]
    hasil = svc.save_item("mei", TABEL, rows, [], EMAIL)
    assert hasil["baris"] == 2 and hasil["sel"] == 3
    item = _item(svc.workspace("mei", "LKPS"), TABEL)
    assert item["state"] == "terisi" and item["diisi_oleh"] == EMAIL
    assert [r[k[0]] for r in item["rows"]] == ["Kerja sama A", "Kerja sama B"]

    svc.save_item("mei", TABEL, [{k[0]: "Pengganti"}], [], EMAIL)  # simpan ulang = ganti seluruh isi
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_data_manual")).scalar() == 1
    ringkasan = svc.workspace("mei", "LKPS")["ringkasan"]
    assert ringkasan["perlu_manual_terisi"] == 1


def test_simpan_narasi_hanya_satu_baris_dan_kolom_asing_diabaikan(svc, engine):
    k = _kolom(svc, "LED", NARASI)
    svc.save_item("mei", NARASI, [{k[0]: "SK 1990", "kolom_liar": "x"}, {k[0]: "diabaikan"}], [], EMAIL)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT kolom, nilai, baris_ke FROM akreditasi_data_manual")).all()
    assert [tuple(r) for r in rows] == [(k[0], "SK 1990", 1)]


def test_simpan_menolak_input_tidak_valid(svc, monkeypatch):
    with pytest.raises(NotFound):
        svc.save_item("mei", "item_tidak_ada", [], [], EMAIL)
    with pytest.raises(NotFound):
        svc.save_item("prodi-lain", TABEL, [], [], EMAIL)
    with pytest.raises(WorkspaceError):
        svc.save_item("mei", TABEL, "bukan list", [], EMAIL)
    with pytest.raises(WorkspaceError):
        svc.save_item("mei", TABEL, [{}] * (ws.MAX_ROWS_PER_ITEM + 1), [], EMAIL)
    registry = ws._registry()
    monkeypatch.setitem(registry.KEBUTUHAN_DATA[TABEL], "status_ketersediaan", "belum_tersedia")
    with pytest.raises(WorkspaceError):
        svc.save_item("mei", TABEL, [], [], EMAIL)


def _tambah_ekstraksi(engine, rows):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_upload_file (id, prodi_id, nama_file, path_lokal, tipe_file, status, uploaded_at) "
                          "VALUES (1, 'mei', 'a.pdf', '/x/a.pdf', 'pdf', 'diekstrak', '2026-09-20'), "
                          "(2, 'mei', 'b.pdf', '/x/b.pdf', 'pdf', 'diekstrak', '2026-09-21')"))
        for i, (file_id, baris, kolom, nilai) in enumerate(rows, start=1):
            conn.execute(text("INSERT INTO akreditasi_upload_ekstraksi (id, upload_file_id, prodi_id, item_id, baris_ke, "
                              "nama_kolom, nilai, kutipan, created_at) VALUES (:id, :f, 'mei', :item, :b, :k, :n, 'kutipan', '2026-09-21')"),
                         {"id": i, "f": file_id, "item": TABEL, "b": baris, "k": kolom, "n": nilai})


def test_draft_ai_tidak_menimpa_manual_dan_konflik_dibiarkan_kosong(svc, engine):
    k = _kolom(svc, "LKPS", TABEL)
    svc.save_item("mei", TABEL, [{k[0]: "Manual"}], [], EMAIL)
    _tambah_ekstraksi(engine, [
        (1, 1, k[0], "AI menimpa?"),   # sel sudah diisi manual -> skipped
        (1, 1, k[1], "PT AI"),         # sel kosong -> diisi draft
        (1, 2, k[0], "Versi A"),       # dua file beda nilai -> konflik
        (2, 2, k[0], "Versi B"),
    ])
    ws_ = svc.workspace("mei", "LKPS")
    assert ws_["ekstraksi"]["item_menunggu_review"] == 1
    draft = _item(ws_, TABEL)["draft"]
    assert draft["rows"][0] == {**{c: "" for c in k}, k[0]: "Manual", k[1]: "PT AI"}
    assert draft["rows"][1][k[0]] == ""
    assert [c["kolom"] for c in draft["ai_cells"]] == [k[1]]
    assert [c["nilai"] for c in draft["skipped"]] == ["AI menimpa?"]
    assert {o["nilai"] for o in draft["conflicts"][0]["opsi"]} == {"Versi A", "Versi B"}
    assert sorted(draft["ekstraksi_ids"]) == [1, 2, 3, 4]

    # Simpan dengan ekstraksi_ids -> preview ditandai selesai direview, tidak muncul lagi.
    svc.save_item("mei", TABEL, draft["rows"], draft["ekstraksi_ids"], EMAIL)
    ws_ = svc.workspace("mei", "LKPS")
    assert _item(ws_, TABEL)["draft"] is None and ws_["ekstraksi"]["item_menunggu_review"] == 0


def test_konfirmasi_ekstraksi_tidak_bisa_lintas_item(svc, engine):
    k = _kolom(svc, "LKPS", TABEL)
    _tambah_ekstraksi(engine, [(1, 1, k[0], "x")])
    svc.save_item("mei", "lkps_3_c_2", [], [1], EMAIL)  # id milik item lain -> diabaikan
    assert _item(svc.workspace("mei", "LKPS"), TABEL)["draft"] is not None


def test_tambah_prodi_slug_unik(svc):
    a = svc.add_program(1, "Magister Kecerdasan Artifisial", "Magister")
    assert a["slug"] == "magister-kecerdasan-artifisial"
    with pytest.raises(WorkspaceError):  # nama sama di fakultas sama
        svc.add_program(1, "magister kecerdasan artifisial", "Magister")
    with pytest.raises(WorkspaceError):
        svc.add_program(1, "Prodi X", "S9")
    with pytest.raises(NotFound):
        svc.add_program(99, "Prodi X", "Sarjana")
    assert svc.workspace(a["slug"], "LED")["prodi"]["nama"] == "Magister Kecerdasan Artifisial"


def test_generate_word_dicatat_di_riwayat_dan_bisa_diunduh_ulang(svc, engine, tmp_path):
    k = _kolom(svc, "LKPS", TABEL)
    svc.save_item("mei", TABEL, [{k[0]: "Kerja sama unik 123"}], [], EMAIL)
    content, filename = svc.generate("mei", "LKPS", EMAIL)
    assert filename.startswith("Laporan_Akreditasi_LKPS_mei_")
    teks = "\n".join(c.text for t in Document(BytesIO(content)).tables for r in t.rows for c in r.cells)
    assert "Kerja sama unik 123" in teks
    with engine.connect() as conn:
        riwayat_id = conn.execute(text("SELECT id FROM akreditasi_riwayat_generate")).scalar_one()
    ulang, _ = svc.history_file(riwayat_id, EMAIL)
    assert ulang == content
    with pytest.raises(NotFound):  # riwayat milik orang lain
        svc.history_file(riwayat_id, "lain@ugm.ac.id")


def test_riwayat_di_luar_folder_generate_ditolak(svc, engine, tmp_path):
    luar = tmp_path / "rahasia.docx"
    luar.write_bytes(b"x")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_riwayat_generate (id, user_email, prodi_id, jenis_dokumen, file_path, generated_at) "
                          "VALUES (9, :e, 'mei', 'LED', :f, '2026-09-21')"), {"e": EMAIL, "f": str(luar)})
    with pytest.raises(NotFound):
        svc.history_file(9, EMAIL)


def test_ekstraksi_menyimpan_preview_dan_status(engine, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "uji")
    k = None
    calls = []

    def fake(path, tipe, dokumen, progress):
        calls.append((path, tipe, dokumen))
        progress(1, 1)
        if path.endswith("rusak.pdf"):
            return [], {"n_batch": 0, "n_batch_gagal": 0, "error": "Gagal ekstrak teks file: rusak"}
        return [{"item_id": TABEL, "baris_ke": 1, "nama_kolom": k, "nilai": "Dari AI", "kutipan": "..."}], {"n_batch": 1, "n_batch_gagal": 0}

    svc = AccreditationWorkspaceService(engine, generated_root=tmp_path, extractor=fake)
    k = _kolom(svc, "LKPS", TABEL)[0]
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_upload_file (id, prodi_id, nama_file, path_lokal, tipe_file, status, uploaded_at) "
                          "VALUES (1, 'mei', 'a.pdf', '/x/a.pdf', 'pdf', 'belum_diekstrak', '2026-09-20'), "
                          "(2, 'mei', 'rusak.pdf', '/x/rusak.pdf', 'pdf', 'belum_diekstrak', '2026-09-21'), "
                          "(3, 'mei', 'c.pdf', '/x/c.pdf', 'pdf', 'diekstrak', '2026-09-21')"))
    assert svc.start_extraction("mei", "LKPS", background=False) == {"dimulai": 2}
    assert [c[0] for c in calls] == ["/x/a.pdf", "/x/rusak.pdf"]
    uploads = {u["nama_file"]: u for u in svc.workspace("mei", "LKPS")["uploads"]}
    assert uploads["a.pdf"]["status"] == "diekstrak"
    assert uploads["rusak.pdf"]["status"] == "gagal_ekstrak" and "rusak" in uploads["rusak.pdf"]["ringkasan"]["error"]
    assert _item(svc.workspace("mei", "LKPS"), TABEL)["draft"]["rows"][0][k] == "Dari AI"
    # Tidak ada file baru -> hanya file gagal yang dicoba ulang.
    calls.clear()
    assert svc.start_extraction("mei", "LKPS", background=False) == {"dimulai": 1}
    assert [c[0] for c in calls] == ["/x/rusak.pdf"]


def test_ekstraksi_butuh_api_key(svc, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(WorkspaceError):
        svc.start_extraction("mei", "LED", background=False)
    assert svc.workspace("mei", "LED")["ekstraksi"]["tersedia"] is False


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
        for method, path in [("get", "/api/v1/analytics/accreditation/workspace?prodi_id=mei"),
                             ("post", "/api/v1/analytics/accreditation/workspace/items/x"),
                             ("post", "/api/v1/analytics/accreditation/programs"),
                             ("post", "/api/v1/analytics/accreditation/extractions"),
                             ("post", "/api/v1/analytics/accreditation/generate"),
                             ("get", "/api/v1/analytics/accreditation/history/1/file")]:
            kwargs = {"json": {}} if method == "post" else {}
            assert getattr(client, method)(path, **kwargs).status_code == 401, path
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
