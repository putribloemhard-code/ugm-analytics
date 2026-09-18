"""Migrasi tabel MySQL untuk akun login app akreditasi. Idempoten.

Jalankan (aman diulang):
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_users.py

Tabel:
- akreditasi_users: akun login, dibatasi email UGM (lihat auth_akreditasi.py).
  `password_hash` NULLABLE & `auth_provider` disiapkan utk login Google nanti.
  `is_blocked` (Fase B) -- akun diblokir admin tidak bisa login.
- akreditasi_sessions: sesi login persisten (bertahan saat halaman di-refresh).
  Yang disimpan HASH sha256 token, bukan tokennya -- bocornya isi tabel tidak
  memberi sesi yang bisa dipakai.
- akreditasi_login_attempts: jejak percobaan login, dasar rate limit.
- akreditasi_riwayat_generate: laporan Word yang pernah di-generate per user.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = [
    f"""
    CREATE TABLE IF NOT EXISTS `{db.t('users')}` (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(254) NOT NULL,
        nama VARCHAR(100) NOT NULL,
        password_hash VARCHAR(255) NULL,
        auth_provider VARCHAR(32) NOT NULL DEFAULT 'local',
        is_admin TINYINT(1) NOT NULL DEFAULT 0,
        is_blocked TINYINT(1) NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        last_login_at DATETIME NULL,
        UNIQUE KEY uq_email (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    f"""
    CREATE TABLE IF NOT EXISTS `{db.t('sessions')}` (
        token_hash CHAR(64) PRIMARY KEY,
        user_id INT NOT NULL,
        created_at DATETIME NOT NULL,
        expires_at DATETIME NOT NULL,
        KEY idx_user (user_id),
        KEY idx_expires (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    f"""
    CREATE TABLE IF NOT EXISTS `{db.t('login_attempts')}` (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(254) NOT NULL,
        berhasil TINYINT(1) NOT NULL,
        attempted_at DATETIME NOT NULL,
        KEY idx_email_waktu (email, attempted_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    f"""
    CREATE TABLE IF NOT EXISTS `{db.t('riwayat_generate')}` (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_email VARCHAR(254) NOT NULL,
        prodi_id VARCHAR(64) NOT NULL,
        jenis_dokumen VARCHAR(8) NOT NULL,
        file_path VARCHAR(512) NOT NULL,
        generated_at DATETIME NOT NULL,
        KEY idx_user_waktu (user_email, generated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            for ddl in DDL:
                conn.exec_driver_sql(ddl)
            # Tabel users dari Fase A belum punya is_blocked -- tambahkan kalau belum ada.
            ada = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() "
                "AND table_name = %s AND column_name = 'is_blocked'", (db.t("users"),)
            ).scalar()
            if not ada:
                conn.exec_driver_sql(
                    f"ALTER TABLE `{db.t('users')}` ADD COLUMN is_blocked TINYINT(1) "
                    "NOT NULL DEFAULT 0 AFTER is_admin"
                )

    ok, _ = db.with_retry(_run, label="migrasi tabel akun akreditasi")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akun akreditasi -- cek koneksi MySQL.")
    print("OK -- tabel users (+is_blocked), sessions, login_attempts, riwayat_generate siap.")


if __name__ == "__main__":
    main()
