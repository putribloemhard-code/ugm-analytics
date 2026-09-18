"""Login app akreditasi: email + password, dibatasi email UGM.

Domain yang diterima (sesuai panduan DTI UGM): "ugm.ac.id" (dosen, tendik,
unit kerja) dan "mail.ugm.ac.id" (mahasiswa). Dicocokkan PERSIS terhadap
bagian setelah "@" -- bukan endswith() longgar -- supaya "x@palsu-ugm.ac.id"
atau "x@ugm.ac.id.contoh.com" tertolak.

Password di-hash bcrypt. Akun PERTAMA yang terdaftar otomatis admin.

Keamanan (Fase B):
- Rate limit: 5x gagal BERTURUT-TURUT utk 1 email dalam 15 menit -> login
  email itu ditolak sementara. Selama terkunci, password tidak dicek sama
  sekali & percobaan tidak dicatat (supaya kunci tidak terus memanjang).
  Konsekuensi yang disadari: orang lain bisa sengaja mengunci email milik
  orang lain selama <=15 menit -- harga wajar utk rate limit per-email.
- Akun diblokir: pesan KHUSUS "Akun Anda diblokir" hanya muncul kalau
  password-nya BENAR. Password salah tetap dapat pesan generik, supaya pesan
  blokir tidak bisa dipakai orang luar utk mengecek email mana yang terdaftar.
- Sesi persisten: token acak 256-bit di cookie `akreditasi_sid` (cookie
  sesi: hilang saat browser ditutup, TIDAK hilang saat halaman di-refresh),
  hash-nya di akreditasi_sessions dgn kedaluwarsa 12 jam. Cookie ditulis
  lewat JS (Streamlit tidak bisa set header Set-Cookie), jadi TIDAK HttpOnly.
  Cookie berlaku per host (port diabaikan browser) -> 1x login juga berlaku
  di app akreditasi yang berdiri sendiri (dashboard_akreditasi.py).
- Data user (termasuk is_admin & is_blocked) dibaca ulang dari DB di SETIAP
  run halaman, bukan dipercaya dari session_state -- jadi blokir, hapus akun,
  dan cabut admin langsung berlaku di sesi yang sedang terbuka.

Login Google (nanti): skema tabel sudah siap (password_hash NULLABLE, kolom
auth_provider). Akun dgn auth_provider selain 'local' ditolak di form ini.
"""

import hashlib
import json
import math
import re
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bcrypt  # noqa: E402
import streamlit as st  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

import db  # noqa: E402

DOMAIN_UGM = ("ugm.ac.id", "mail.ugm.ac.id")
PASSWORD_MIN = 8
PASSWORD_MAX_BYTES = 72  # batas bcrypt; bcrypt>=5 melempar ValueError kalau lebih
NAMA_MAX = 100
BATAS_GAGAL = 5
JENDELA_GAGAL = timedelta(minutes=15)
UMUR_SESI = timedelta(hours=12)

COOKIE_SESI = "akreditasi_sid"
_KEY_USER = "akreditasi_user"
_KEY_TOKEN = "akreditasi_token"
_LOCAL_RE = re.compile(r"^[a-z0-9._%+\-]+$")

# Hash dummy utk login dgn email yang tidak terdaftar -- tetap menjalankan
# bcrypt.checkpw supaya waktu respons tidak membocorkan email mana yang ada.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-tidak-dipakai", bcrypt.gensalt())

MSG_SALAH = "Email atau password salah."
MSG_DIBLOKIR = "Akun Anda diblokir, hubungi admin."


_DIR_LOGO = Path(__file__).resolve().parents[2] / "shared" / "assets" / "logo"


def logo_data_uri(file: str) -> str:
    """Logo di shared/assets/logo/ sbg data URI; "" kalau filenya belum ada
    (logo yang belum disiapkan tidak boleh menjatuhkan halaman login)."""
    import base64

    path = _DIR_LOGO / file
    if not path.is_file():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def md_aman(teks: str) -> str:
    """Escape karakter markdown -- nama user tampil di st.caption/markdown."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~])", r"\\\1", str(teks))


# ---------------------------------------------------------------- validasi
def normalisasi_email(email: str) -> str:
    return (email or "").strip().lower()


def validasi_email(email: str) -> str | None:
    """Return pesan error, atau None kalau valid."""
    if email.count("@") != 1:
        return "Format email tidak valid."
    lokal, domain = email.split("@")
    if not lokal or not _LOCAL_RE.match(lokal) or len(email) > 254:
        return "Format email tidak valid."
    if domain not in DOMAIN_UGM:
        return "Hanya email UGM (@ugm.ac.id atau @mail.ugm.ac.id) yang boleh mendaftar."
    return None


def validasi_password(password: str, konfirmasi: str) -> str | None:
    if len(password) < PASSWORD_MIN:
        return f"Password minimal {PASSWORD_MIN} karakter."
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return f"Password maksimal {PASSWORD_MAX_BYTES} byte."
    if password != konfirmasi:
        return "Konfirmasi password tidak sama."
    return None


# ---------------------------------------------------------------- registrasi
def registrasi(email: str, nama: str, password: str, konfirmasi: str) -> tuple[bool, str]:
    email = normalisasi_email(email)
    nama = (nama or "").strip()
    err = validasi_email(email)
    if err:
        return False, err
    if not nama:
        return False, "Nama wajib diisi."
    if len(nama) > NAMA_MAX:
        return False, f"Nama maksimal {NAMA_MAX} karakter."
    err = validasi_password(password, konfirmasi)
    if err:
        return False, err

    tabel = db.t("users")
    hash_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    try:
        with db.get_engine().begin() as conn:
            new_id = conn.execute(
                text(f"INSERT INTO `{tabel}` (email, nama, password_hash, auth_provider, "
                     "is_admin, is_blocked, created_at) "
                     "VALUES (:email, :nama, :ph, 'local', 0, 0, :now)"),
                {"email": email, "nama": nama, "ph": hash_pw, "now": datetime.now()},
            ).lastrowid
            # Admin = baris dgn id TERKECIL. Dicek sesudah insert (bukan "hitung
            # dulu, baru insert") supaya 2 pendaftaran bersamaan tidak sama-sama
            # jadi admin.
            if conn.execute(text(f"SELECT MIN(id) FROM `{tabel}`")).scalar() == new_id:
                conn.execute(text(f"UPDATE `{tabel}` SET is_admin = 1 WHERE id = :id"),
                             {"id": new_id})
    except IntegrityError:
        return False, "Email sudah terdaftar -- silakan login."
    return True, "Registrasi berhasil -- silakan login."


# ---------------------------------------------------------------- rate limit
def _sisa_kunci_detik(conn, email: str) -> int | None:
    """Detik tersisa sampai email ini boleh mencoba lagi, atau None kalau tidak
    terkunci. Terkunci = 5 percobaan TERAKHIR dalam 15 menit semuanya gagal
    (satu yang berhasil memutus rentetan)."""
    now = datetime.now()
    rows = conn.execute(
        text(f"SELECT berhasil, attempted_at FROM `{db.t('login_attempts')}` "
             "WHERE email = :email AND attempted_at >= :batas "
             "ORDER BY attempted_at DESC, id DESC LIMIT :n"),
        {"email": email, "batas": now - JENDELA_GAGAL, "n": BATAS_GAGAL},
    ).all()
    if len(rows) < BATAS_GAGAL or any(r.berhasil for r in rows):
        return None
    sisa = (rows[-1].attempted_at + JENDELA_GAGAL - now).total_seconds()
    return math.ceil(sisa) if sisa > 0 else None


def _catat_percobaan(conn, email: str, berhasil: bool) -> None:
    now = datetime.now()
    conn.execute(
        text(f"INSERT INTO `{db.t('login_attempts')}` (email, berhasil, attempted_at) "
             "VALUES (:email, :b, :now)"),
        {"email": email[:254], "b": int(berhasil), "now": now},
    )
    # Buang jejak lama -- rate limit cuma butuh 15 menit terakhir.
    conn.execute(text(f"DELETE FROM `{db.t('login_attempts')}` WHERE attempted_at < :batas"),
                 {"batas": now - timedelta(days=1)})


# ---------------------------------------------------------------- login & sesi
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _baris_ke_user(row) -> dict:
    return {"id": row["id"], "email": row["email"], "nama": row["nama"],
            "is_admin": bool(row["is_admin"]), "created_at": row["created_at"],
            "last_login_at": row["last_login_at"]}


def ambil_user_aktif(user_id: int) -> dict | None:
    """Data user TERKINI dari DB; None kalau akun sudah dihapus atau diblokir."""
    with db.get_engine().connect() as conn:
        row = conn.execute(
            text(f"SELECT id, email, nama, is_admin, is_blocked, created_at, last_login_at "
                 f"FROM `{db.t('users')}` WHERE id = :id"),
            {"id": user_id},
        ).mappings().first()
    if row is None or row["is_blocked"]:
        return None
    return _baris_ke_user(row)


def login(email: str, password: str) -> tuple[dict | None, str, str | None]:
    """Return (user, pesan_error, token_sesi). user None = gagal."""
    email = normalisasi_email(email)
    engine = db.get_engine()
    tabel = db.t("users")

    with engine.begin() as conn:
        sisa = _sisa_kunci_detik(conn, email)
    if sisa:
        return None, (f"Terlalu banyak percobaan login gagal untuk email ini. "
                      f"Coba lagi dalam {math.ceil(sisa / 60)} menit."), None

    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT id, email, nama, password_hash, auth_provider, is_admin, "
                 f"is_blocked, created_at, last_login_at FROM `{tabel}` WHERE email = :email"),
            {"email": email},
        ).mappings().first()

    pw = password.encode("utf-8")
    bisa_dicek = (row is not None and row["auth_provider"] == "local"
                  and row["password_hash"] and len(pw) <= PASSWORD_MAX_BYTES)
    if bisa_dicek:
        cocok = bcrypt.checkpw(pw, row["password_hash"].encode("ascii"))
    else:
        bcrypt.checkpw(pw[:PASSWORD_MAX_BYTES], _DUMMY_HASH)
        cocok = False

    if not cocok:
        with engine.begin() as conn:
            _catat_percobaan(conn, email, False)
        return None, MSG_SALAH, None
    if row["is_blocked"]:
        return None, MSG_DIBLOKIR, None

    now = datetime.now()
    token = secrets.token_urlsafe(32)
    with engine.begin() as conn:
        _catat_percobaan(conn, email, True)
        conn.execute(text(f"UPDATE `{tabel}` SET last_login_at = :now WHERE id = :id"),
                     {"now": now, "id": row["id"]})
        conn.execute(text(f"DELETE FROM `{db.t('sessions')}` WHERE expires_at < :now"),
                     {"now": now})
        conn.execute(
            text(f"INSERT INTO `{db.t('sessions')}` (token_hash, user_id, created_at, expires_at) "
                 "VALUES (:h, :uid, :now, :exp)"),
            {"h": _hash_token(token), "uid": row["id"], "now": now, "exp": now + UMUR_SESI},
        )
    user = _baris_ke_user(row)
    user["last_login_at"] = now
    return user, "", token


def _user_id_dari_token(token: str) -> int | None:
    with db.get_engine().connect() as conn:
        return conn.execute(
            text(f"SELECT user_id FROM `{db.t('sessions')}` "
                 "WHERE token_hash = :h AND expires_at > :now"),
            {"h": _hash_token(token), "now": datetime.now()},
        ).scalar()


def hapus_sesi_user(conn, user_id: int) -> None:
    """Putus semua sesi login milik user (dipakai saat blokir/hapus akun)."""
    conn.execute(text(f"DELETE FROM `{db.t('sessions')}` WHERE user_id = :id"), {"id": user_id})


def _set_cookie_js(token: str | None) -> None:
    """Tulis (token) / hapus (None) cookie sesi lewat skrip di halaman. Pakai
    st.html (langsung di halaman) -- BUKAN components.html, yang iframe-nya
    tetap memakan ruang ~150px di bawah judul walau height=0."""
    if token:
        isi = f"{COOKIE_SESI}={token}; path=/; SameSite=Strict"
    else:
        isi = f"{COOKIE_SESI}=; path=/; SameSite=Strict; Max-Age=0"
    st.html(
        "<script>"
        f"var c = {json.dumps(isi)};"
        "if (window.location.protocol === 'https:') c += '; Secure';"
        "document.cookie = c;"
        "</script>",
        unsafe_allow_javascript=True,
    )


def pulihkan_user() -> dict | None:
    """User yang sedang login (data TERKINI dari DB) atau None. Tidak
    menggambar apa pun -- aman dipanggil dari mana saja (mis. utk menentukan
    menu navigasi). Urutan: sesi Streamlit yang sedang berjalan -> cookie sesi
    (kasus halaman baru di-refresh)."""
    ss = st.session_state
    user = ss.get(_KEY_USER)
    if user:
        segar = ambil_user_aktif(user["id"])
        token = ss.get(_KEY_TOKEN)
        if segar is None or (token and _user_id_dari_token(token) != segar["id"]):
            ss.pop(_KEY_USER, None)
            ss.pop(_KEY_TOKEN, None)
            return None
        ss[_KEY_USER] = segar
        return segar

    token = st.context.cookies.get(COOKIE_SESI)
    if token:
        uid = _user_id_dari_token(token)
        segar = ambil_user_aktif(uid) if uid else None
        if segar:
            ss[_KEY_USER] = segar
            ss[_KEY_TOKEN] = token
            return segar
    return None


def user_aktif() -> dict | None:
    """User di sesi berjalan (setelah wajib_login/pulihkan_user dipanggil di
    run yang sama)."""
    return st.session_state.get(_KEY_USER)


def keluar() -> None:
    token = st.session_state.pop(_KEY_TOKEN, None)
    st.session_state.pop(_KEY_USER, None)
    if token:
        with db.get_engine().begin() as conn:
            conn.execute(text(f"DELETE FROM `{db.t('sessions')}` WHERE token_hash = :h"),
                         {"h": _hash_token(token)})


# ---------------------------------------------------------------- UI
# Gaya gerbang login -- disuntikkan HANYA saat form login tampil (run itu
# berakhir dgn st.stop()), jadi tidak bocor ke halaman lain. Warna kartu pakai
# abu semi-transparan supaya serasi di tema terang maupun gelap. Gambar panel
# = hero Beranda (app/static/, disajikan dashboard utama); di app berdiri
# sendiri static serving tidak aktif, jadi panel jatuh ke gradien biru.
_CSS_GERBANG = """
<style>
/* Latar halaman gerbang login SENGAJA dibiarkan apa adanya (ikut tema
   Streamlit) -- versi krem/"nude" pernah dicoba lalu dibatalkan. */
/* Panel brand: gambar hero asli (navy), teks putih. */
.gerbang-panel {
    position: relative; overflow: hidden; border-radius: 22px;
    min-height: 420px; padding: 44px 40px; box-sizing: border-box;
    display: flex; flex-direction: column; justify-content: center;
    color: #fff;
    background-color: #00214a;
    background-image:
        linear-gradient(100deg, rgba(2,12,40,0.88) 0%, rgba(2,12,40,0.68) 58%, rgba(2,12,40,0.3) 100%),
        url("app/static/hero_bg.jpg"),
        linear-gradient(135deg, #00214a 0%, #052c5b 55%, #0a3364 100%);
    background-size: cover; background-position: 70% center; background-repeat: no-repeat;
    box-shadow: 0 20px 44px rgba(12,30,70,0.28);
}
.gerbang-panel, .gerbang-panel * { color: #fff !important; }
.gerbang-badge {
    align-self: flex-start; display: inline-flex; align-items: center; gap: 7px;
    font-size: 0.75rem; font-weight: 600; letter-spacing: 0.04em;
    background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.3);
    border-radius: 999px; padding: 5px 14px 5px 8px; margin-bottom: 18px;
}
.gerbang-badge img { height: 1.3rem; width: auto; }
.gerbang-judul {
    font-size: 2.1rem; font-weight: 800; line-height: 1.15; margin: 0 0 10px;
    text-shadow: 0 2px 14px rgba(0,8,30,0.45);
}
.gerbang-panel .gerbang-judul span { color: #ffc72c !important; }
.gerbang-sub {
    font-size: 0.95rem; line-height: 1.6; margin: 0;
    text-shadow: 0 1px 8px rgba(0,8,30,0.5);
}
.gerbang-sapa { font-size: 1.45rem; font-weight: 800; margin: 6px 0 2px; }
.gerbang-sapa-sub { font-size: 0.9rem; opacity: 0.7; margin: 0 0 12px; }
[data-testid="stForm"] {
    border: 1px solid rgba(127,127,127,0.22); border-radius: 18px;
    padding: 22px 22px 18px; background: rgba(127,127,127,0.05);
    box-shadow: 0 10px 28px rgba(0,12,45,0.08);
}
[data-testid="stForm"] input { border-radius: 10px; }
/* Tab aktif (Streamlit 1.61 = react-aria): teks tetap warna teks tema (tidak ada
   satu warna biru yang kontrasnya >=4.5:1 di tema terang DAN gelap sekaligus),
   ditebalkan; garis penandanya biru #2563eb (>=3:1 di kedua tema). */
[data-testid="stTab"][aria-selected="true"],
[data-testid="stTab"][aria-selected="true"] p { color: inherit !important; font-weight: 700; }
[data-testid="stTabs"] .react-aria-SelectionIndicator { background-color: #2563eb !important; }
[data-testid="stFormSubmitButton"] button {
    width: 100%; border: none; border-radius: 12px; padding: 0.65rem 1rem;
    font-weight: 700; letter-spacing: 0.02em; color: #fff;
    background: linear-gradient(90deg, #00214a 0%, #0a3364 100%);
    box-shadow: 0 8px 20px rgba(31,95,191,0.35);
    transition: transform .12s ease, box-shadow .12s ease;
}
[data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button * { color: #fff !important; }
[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-1px); box-shadow: 0 12px 26px rgba(31,95,191,0.45);
}
[data-testid="stFormSubmitButton"] button:focus-visible {
    outline: 3px solid #ffc72c; outline-offset: 2px;
}
</style>
"""

_PANEL_GERBANG = f"""
<div class="gerbang-panel">
  <div class="gerbang-badge"><img src="{logo_data_uri('LogoUGM.png')}" alt="">
    Universitas Gadjah Mada</div>
  <div class="gerbang-judul">Portal <span>Akreditasi</span></div>
  <p class="gerbang-sub">Kelola kelengkapan data LED &amp; LKPS, ekstrak dokumen pendukung,
     dan susun laporan akreditasi program studi dalam satu tempat.</p>
</div>
"""


def _render_form_login() -> None:
    with st.form("form_login_akreditasi"):
        email = st.text_input("Email UGM", placeholder="nama@ugm.ac.id")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk", type="primary", width="stretch"):
            user, pesan, token = login(email, password)
            if user:
                st.session_state[_KEY_USER] = user
                st.session_state[_KEY_TOKEN] = token
                st.rerun()
            st.error(pesan)


def _render_form_registrasi() -> None:
    with st.form("form_registrasi_akreditasi"):
        email = st.text_input("Email UGM", placeholder="nama@ugm.ac.id atau nama@mail.ugm.ac.id")
        nama = st.text_input("Nama lengkap")
        password = st.text_input("Password", type="password",
                                 help=f"Minimal {PASSWORD_MIN} karakter.")
        konfirmasi = st.text_input("Konfirmasi password", type="password")
        if st.form_submit_button("Buat akun", type="primary", width="stretch"):
            ok, pesan = registrasi(email, nama, password, konfirmasi)
            (st.success if ok else st.error)(pesan)


def wajib_login() -> dict:
    """Pasang di awal halaman: kalau belum login, tampilkan form login/daftar
    lalu st.stop() -- tidak ada konten halaman lain yang ikut dirender. Kalau
    sudah login, tampilkan info akun + tombol keluar, return data user."""
    user = pulihkan_user()
    cookie = st.context.cookies.get(COOKIE_SESI)
    if user:
        token = st.session_state.get(_KEY_TOKEN)
        if token and cookie != token:
            _set_cookie_js(token)
        col1, col2 = st.columns([5, 1])
        col1.caption(f"Masuk sebagai **{md_aman(user['nama'])}** ({md_aman(user['email'])})"
                     + (" · admin" if user["is_admin"] else ""))
        if col2.button("Keluar", key="akreditasi_logout"):
            keluar()
            st.rerun()
        return user

    if cookie:
        _set_cookie_js(None)  # cookie basi (sudah keluar / kedaluwarsa / diblokir)

    if not db.table_exists(db.get_engine(), db.t("users")):
        st.error("Tabel akun belum ada. Jalankan sekali dari folder akreditasi:\n\n"
                 "```\n..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_users.py\n```")
        st.stop()

    st.html(_CSS_GERBANG)
    kiri, kanan = st.columns([1.05, 1], gap="large", vertical_alignment="center")
    kiri.markdown(_PANEL_GERBANG, unsafe_allow_html=True)
    with kanan:
        st.markdown(
            '<div class="gerbang-sapa">Selamat datang 👋</div>'
            '<div class="gerbang-sapa-sub">Masuk untuk melanjutkan, atau buat akun baru '
            'dengan email UGM Anda.</div>',
            unsafe_allow_html=True,
        )
        tab_login, tab_daftar = st.tabs(["Masuk", "Daftar akun baru"])
        with tab_login:
            _render_form_login()
        with tab_daftar:
            _render_form_registrasi()
    st.stop()
