"""Uji profil akun & aksi admin akreditasi (services/accreditation_account.py).

Semua uji memakai SQLite sementara di memori dengan skema yang sama seperti MySQL produksi
(tabel akreditasi_*), jadi tidak menyentuh database asli sama sekali. Tabel sengaja dibuat
tanpa dialek MySQL supaya uji ini juga jalan di PostgreSQL.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.services.accreditation_account import AccreditationAccountService, AksiDitolak

DDL = [
    """
    CREATE TABLE akreditasi_users (
        id INTEGER PRIMARY KEY,
        email VARCHAR(254) NOT NULL UNIQUE,
        nama VARCHAR(100) NOT NULL,
        password_hash VARCHAR(255),
        auth_provider VARCHAR(32) NOT NULL DEFAULT 'local',
        is_admin BOOLEAN NOT NULL DEFAULT 0,
        is_blocked BOOLEAN NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL,
        last_login_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE akreditasi_sessions (
        token_hash VARCHAR(64) PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE akreditasi_riwayat_generate (
        id INTEGER PRIMARY KEY,
        user_email VARCHAR(254) NOT NULL,
        prodi_id VARCHAR(64) NOT NULL,
        jenis_dokumen VARCHAR(8) NOT NULL,
        file_path VARCHAR(512) NOT NULL,
        generated_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE akreditasi_login_attempts (
        id INTEGER PRIMARY KEY,
        email VARCHAR(254) NOT NULL,
        berhasil BOOLEAN NOT NULL,
        attempted_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE akreditasi_prodi (
        id INTEGER PRIMARY KEY,
        fakultas_id INTEGER,
        nama VARCHAR(150) NOT NULL,
        jenjang VARCHAR(20),
        slug VARCHAR(64) NOT NULL,
        url VARCHAR(500)
    )
    """,
    "CREATE TABLE akreditasi_fakultas (id INTEGER PRIMARY KEY, nama VARCHAR(150) NOT NULL, slug VARCHAR(64), url VARCHAR(500))",
    """
    CREATE TABLE akreditasi_data_manual (
        id INTEGER PRIMARY KEY,
        prodi_id VARCHAR(64) NOT NULL DEFAULT 'mei',
        item_id VARCHAR(64) NOT NULL,
        baris_ke INTEGER NOT NULL DEFAULT 1,
        kolom VARCHAR(255) NOT NULL,
        tahun VARCHAR(16),
        nilai TEXT,
        link_bukti VARCHAR(1000),
        diisi_oleh VARCHAR(255),
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE akreditasi_upload_file (
        id INTEGER PRIMARY KEY,
        prodi_id VARCHAR(64) NOT NULL,
        nama_file VARCHAR(500) NOT NULL,
        path_lokal VARCHAR(1000) NOT NULL,
        tipe_file VARCHAR(10),
        ukuran_bytes INTEGER,
        status VARCHAR(32),
        diupload_oleh VARCHAR(255),
        uploaded_at TIMESTAMP,
        diekstrak_at TIMESTAMP
    )
    """,
]

ADMIN = {"id": 1, "email": "admin@ugm.ac.id", "nama": "Admin Uji", "is_admin": True}
MHS = {"id": 2, "email": "mhs@mail.ugm.ac.id", "nama": "Mahasiswa Uji", "is_admin": False}


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    with eng.begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))
        conn.execute(text(
            "INSERT INTO akreditasi_users (id, email, nama, auth_provider, is_admin, is_blocked, created_at, last_login_at) "
            "VALUES (1, :a, 'Admin Uji', 'local', 1, 0, '2026-09-17 19:37:22', '2026-09-21 13:46:43')"
        ), {"a": ADMIN["email"]})
        conn.execute(text(
            "INSERT INTO akreditasi_users (id, email, nama, auth_provider, is_admin, is_blocked, created_at, last_login_at) "
            "VALUES (2, :m, 'Mahasiswa Uji', 'local', 0, 0, '2026-09-18 08:00:00', NULL)"
        ), {"m": MHS["email"]})
        conn.execute(text("INSERT INTO akreditasi_fakultas (id, nama, slug) VALUES (1, 'Fakultas MIPA', 'fmipa')"))
        conn.execute(text(
            "INSERT INTO akreditasi_prodi (id, fakultas_id, nama, jenjang, slug) "
            "VALUES (1, 1, 'Magister Elektronika dan Instrumentasi', 'S2', 'mei')"
        ))
        # Satu item LED + satu item LKPS yang dikonfirmasi mahasiswa -> muncul di "sedang dikerjakan".
        conn.execute(text(
            "INSERT INTO akreditasi_data_manual (id, prodi_id, item_id, baris_ke, kolom, nilai, diisi_oleh, updated_at) "
            "VALUES (1, 'mei', 'led_b1_sejarah', 1, 'Narasi', 'isi', :m, '2026-09-19 10:00:00')"
        ), {"m": MHS["email"]})
        conn.execute(text(
            "INSERT INTO akreditasi_riwayat_generate (id, user_email, prodi_id, jenis_dokumen, file_path, generated_at) "
            "VALUES (1, :m, 'mei', 'LED', 'D:/x/mei/a.docx', '2026-09-18 09:17:47')"
        ), {"m": MHS["email"]})
        conn.execute(text(
            "INSERT INTO akreditasi_upload_file (id, prodi_id, nama_file, path_lokal, status, diupload_oleh, uploaded_at) "
            "VALUES (1, 'mei', 'a.pdf', 'D:/x/mei/a.pdf', 'belum_diekstrak', :m, '2026-09-16 11:51:49')"
        ), {"m": MHS["email"]})
    return eng


def test_profile_memuat_identitas_dan_statistik(engine):
    profil = AccreditationAccountService(engine).profile(MHS)
    assert profil["user"]["nama"] == "Mahasiswa Uji"
    assert profil["user"]["is_admin"] is False
    # Format tampilan mengikuti dashboard lama (page_profil.py): "18 Sep 2026, 09:17"
    assert profil["user"]["terdaftar"] == "18 Sep 2026, 08:00"
    assert profil["user"]["login_terakhir"] is None
    assert profil["stats"] == {"dokumen_digenerate": 1, "dokumen_diupload": 1}


def test_profile_menampilkan_pekerjaan_berjalan_dan_riwayat(engine):
    profil = AccreditationAccountService(engine).profile(MHS)
    assert len(profil["ongoing"]) == 1
    kerja = profil["ongoing"][0]
    assert kerja["prodi_id"] == "mei"
    assert kerja["dokumen"] == "LED"          # item led_b1_sejarah tergolong dokumen LED
    assert kerja["nama_fakultas"] == "Fakultas MIPA"
    assert kerja["item_milik_user"] == 1
    assert kerja["total"] > 0 and 0 <= kerja["persen"] <= 100
    assert profil["riwayat"]["total"] == 1
    assert profil["riwayat"]["rows"][0]["nama_prodi"] == "Magister Elektronika dan Instrumentasi"
    assert profil["riwayat"]["rows"][0]["digenerate"] == "18 Sep 2026, 09:17"


def test_profile_user_tanpa_data_tidak_error(engine):
    kosong = {"id": 99, "email": "baru@ugm.ac.id", "nama": "Baru", "is_admin": False}
    profil = AccreditationAccountService(engine).profile(kosong)
    assert profil["ongoing"] == []
    assert profil["riwayat"] == {"total": 0, "batas": 50, "rows": []}
    assert profil["stats"] == {"dokumen_digenerate": 0, "dokumen_diupload": 0}


def test_admin_overview_hanya_untuk_admin(engine):
    service = AccreditationAccountService(engine)
    with pytest.raises(AksiDitolak):
        service.admin_overview(MHS)
    data = service.admin_overview(ADMIN)
    assert data["summary"] == {"total_akun": 2, "admin": 1, "diblokir": 0}
    admin = next(u for u in data["users"] if u["id"] == 1)
    assert admin["diri_sendiri"] is True and admin["n_generate"] == 0
    mhs = next(u for u in data["users"] if u["id"] == 2)
    assert mhs["diri_sendiri"] is False and mhs["n_generate"] == 1


def test_admin_tidak_bisa_menyentuh_akun_sendiri(engine):
    service = AccreditationAccountService(engine)
    for aksi, nilai in (("blokir", True), ("admin", False), ("hapus", None)):
        with pytest.raises(AksiDitolak):
            service.admin_action(ADMIN, aksi, ADMIN["id"], nilai)


def test_blokir_mencabut_sesi_dan_bisa_dibuka(engine):
    service = AccreditationAccountService(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO akreditasi_sessions (token_hash, user_id, created_at, expires_at) "
            "VALUES ('h', 2, '2026-09-21 10:00:00', '2026-09-22 10:00:00')"
        ))
    hasil = service.admin_action(ADMIN, "blokir", 2, True)
    assert "dipasang" in hasil["message"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_blocked FROM akreditasi_users WHERE id = 2")).scalar() == 1
        # Sesi user yang diblokir harus ikut dihapus supaya tidak tetap login.
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_sessions WHERE user_id = 2")).scalar() == 0
    service.admin_action(ADMIN, "blokir", 2, False)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_blocked FROM akreditasi_users WHERE id = 2")).scalar() == 0


def test_status_admin_diberikan_dan_dicabut(engine):
    service = AccreditationAccountService(engine)
    service.admin_action(ADMIN, "admin", 2, True)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_admin FROM akreditasi_users WHERE id = 2")).scalar() == 1
    service.admin_action(ADMIN, "admin", 2, False)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_admin FROM akreditasi_users WHERE id = 2")).scalar() == 0


def test_hapus_akun_membersihkan_sesi_riwayat_dan_percobaan_login(engine):
    service = AccreditationAccountService(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO akreditasi_login_attempts (id, email, berhasil, attempted_at) "
            "VALUES (1, :m, 0, '2026-09-20 07:00:00')"
        ), {"m": MHS["email"]})
    hasil = service.admin_action(ADMIN, "hapus", 2)
    assert "dihapus" in hasil["message"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_users")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_riwayat_generate")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_login_attempts")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_sessions")).scalar() == 0
        # Data yang pernah dikonfirmasi user SENGAJA tetap ada (data resmi prodi).
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_data_manual")).scalar() == 1


def test_target_tidak_ada_ditolak(engine):
    with pytest.raises(AksiDitolak):
        AccreditationAccountService(engine).admin_action(ADMIN, "blokir", 999, True)


def test_admin_yang_diblokir_tidak_bisa_beraksi(engine):
    service = AccreditationAccountService(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE akreditasi_users SET is_blocked = 1 WHERE id = 1"))
    with pytest.raises(AksiDitolak):
        service.admin_action(ADMIN, "admin", 2, True)


def test_aksi_tidak_dikenal_ditolak(engine):
    with pytest.raises(AksiDitolak):
        AccreditationAccountService(engine).admin_action(ADMIN, "terbang", 2)


def test_login_dikunci_setelah_lima_kali_gagal(engine):
    """Padanan rate limit auth_akreditasi.py lama: 5 gagal beruntun -> terkunci, password benar pun ditolak."""
    from app.services.accreditation_auth import login, register

    ok, _ = register(engine, "baru@ugm.ac.id", "Baru", "rahasia-123")
    assert ok
    for _ in range(5):
        user, pesan, _ = login(engine, "baru@ugm.ac.id", "salah-salah")
        assert user is None and pesan == "Email atau password salah."
    user, pesan, token = login(engine, "baru@ugm.ac.id", "rahasia-123")
    assert user is None and token is None and "Terlalu banyak percobaan" in pesan


def test_login_berhasil_memutus_rentetan_gagal(engine):
    from app.services.accreditation_auth import login, register

    register(engine, "baru@ugm.ac.id", "Baru", "rahasia-123")
    for _ in range(4):
        login(engine, "baru@ugm.ac.id", "salah-salah")
    user, _, token = login(engine, "baru@ugm.ac.id", "rahasia-123")
    assert user and token
    for _ in range(4):
        login(engine, "baru@ugm.ac.id", "salah-salah")
    user, _, _ = login(engine, "baru@ugm.ac.id", "rahasia-123")
    assert user is not None
