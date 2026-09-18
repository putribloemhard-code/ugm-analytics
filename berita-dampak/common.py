"""Konstanta, styling, dan helper yang dipakai bareng oleh semua halaman
dashboard (lihat pages_app/) -- supaya tidak ada duplikasi antar halaman.
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import html

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, utk shared/

from shared.style import apply_custom_css  # noqa: E402
from scripts.keywords import KEYWORDS  # noqa: E402
from scripts.kepmen_sdg import (  # noqa: E402
    SDG_NAMA,
    TOPIK_KEPMEN,
    TOPIK_KEPMEN_ALL,
    TEMA_KEPMEN_LENGKAP,
    WARNA_PILAR,
    sdg_label,
)
from scripts.kepmen_sdg import LABEL_TOPIC_ALL as LABEL_TOPIC  # noqa: E402
from scripts.unit_kerja import UNIT_KERJA  # noqa: E402

# 44 fakultas/sekolah/unit kerja, diurutkan Fakultas -> Sekolah -> Unit Kerja
# (lalu alfabetis per kategori) supaya gampang di-scan/cari di multiselect.
_URUTAN_KATEGORI = {"Fakultas": 0, "Sekolah": 1, "Unit Kerja": 2}
UNIT_KERJA_OPSI = sorted(
    UNIT_KERJA.keys(),
    key=lambda k: (_URUTAN_KATEGORI[UNIT_KERJA[k]["kategori"]], UNIT_KERJA[k]["nama"]),
)
WARNA_KATEGORI = {"Fakultas": "#3949ab", "Sekolah": "#00897b", "Unit Kerja": "#8e24aa"}

# Semua keyword (14 tema resmi Kepmen) untuk breakdown.
KEYWORDS_ALL = dict(KEYWORDS)
KEYWORDS_ALL.update({k: v["keywords"] for k, v in TEMA_KEPMEN_LENGKAP.items()})

# 14 tema dikelompokkan per pilar (urutan sesuai LABEL_TOPIC) -- dipakai untuk
# pecah dropdown tema jadi 1 per pilar, bukan 1 dropdown raksasa isi 14 tema.
TOPIK_PER_PILAR = {
    p: [k for k in LABEL_TOPIC if TOPIK_KEPMEN_ALL[k]["dampak"] == p]
    for p in ["Lingkungan", "Ekonomi", "Sosial"]
}
PILAR_ICON_SIDEBAR = {"Lingkungan": "🌳", "Ekonomi": "💼", "Sosial": "🤝"}
PILAR_ICON = PILAR_ICON_SIDEBAR

STOPWORDS = set(
    """dan di ke dari yang untuk dengan pada dalam sebagai oleh ini itu atau
    serta akan telah dapat tidak juga para bagi agar karena antara melalui
    terhadap tentang hingga sampai setelah sebelum ketika saat secara merupakan
    menjadi adalah yaitu yakni tahun baru kembali lebih paling sangat ada bisa
    harus sudah sedang masih semua setiap berbagai sebuah suatu satu dua tiga
    indonesia universitas ugm gadjah mada the and for with from that this are
    was were has have had will its their into about through during after
    before more most also can could should would may of to in is it on at by
    an be as or you your we our they them his her not but what when where how
    why do does did done up out off over under antara""".split()
)


def token_freq(df: pd.DataFrame) -> Counter:
    """Frekuensi kata pada judul + deskripsi (stopword dibuang)."""
    c: Counter = Counter()
    teks = df["judul"].fillna("") + " " + df["deskripsi"].fillna("")
    for t in teks:
        for kata in re.findall(r"[a-z]{3,}", t.lower()):
            if kata not in STOPWORDS:
                c[kata] += 1
    return c


def hover_keterangan(fig, keterangan: str):
    """Tambahkan baris penjelasan ke tooltip hover semua trace.

    Disisipkan sebelum kotak nama trace (<extra>) sehingga angka default
    (x/y/z + hover_data) tetap tampil, ditambah penjelasan cara hitung.
    """
    sisip = f"<br><span style='font-size:11px'>{keterangan}</span>"
    for tr in fig.data:
        ht = getattr(tr, "hovertemplate", None) or ""
        if "<extra>" in ht:
            tr.hovertemplate = ht.replace("<extra>", sisip + "<extra>", 1)
        elif ht:
            tr.hovertemplate = ht + sisip
        else:
            nama = getattr(tr, "name", "") or ""
            header = f"{nama}<br>" if nama else ""
            tr.hovertemplate = header + "%{x} — %{y}" + sisip + "<extra></extra>"
    return fig


def penjelasan(teks: str):
    """Caption penjelasan di bawah chart: tujuan & cara hitung angka."""
    st.caption(f"💡 {teks}")


def insight_top2(df: pd.DataFrame, label_col: str, value_col: str, satuan: str = "berita") -> str:
    """Kalimat insight top-1 vs top-2 dari dataframe chart peringkat/distribusi --
    dihitung langsung dari data ter-filter saat itu (non-AI), jadi otomatis akurat
    untuk kombinasi filter/pilar apa pun. df tidak harus urut, fungsi ini yang
    mengurutkan turun berdasarkan `value_col`."""
    d = df.sort_values(value_col, ascending=False).reset_index(drop=True)
    top = d.iloc[0]
    n1 = int(top[value_col])
    if len(d) > 1:
        second = d.iloc[1]
        n2 = int(second[value_col])
        beda_text = f"{(n1 - n2) / n2 * 100:.0f}% lebih tinggi" if n2 else "jauh lebih tinggi"
        return (
            f"**{top[label_col]}** paling dominan dengan {n1:,} {satuan}, "
            f"{beda_text} dari {second[label_col]} ({n2:,} {satuan})."
        )
    return f"**{top[label_col]}** dengan {n1:,} {satuan}."


def insight_heatmap(matrix: pd.DataFrame, satuan: str = "berita") -> str:
    """Kalimat insight sel tertinggi dari matrix heatmap (index=baris, columns=kolom)
    -- dihitung langsung dari data ter-filter saat itu (non-AI)."""
    stacked = matrix.stack()
    if not len(stacked):
        return "Belum ada data untuk kombinasi ini."
    (row, col), val = stacked.idxmax(), stacked.max()
    return f"Kombinasi tertinggi: **{row} × {col}** dengan {int(val):,} {satuan}."


# Konfigurasi toolbar kamera Plotly -- WAJIB dipakai di semua st.plotly_chart
# supaya tombol unduh gambar (kamera, pojok kanan atas chart) selalu terlihat.
PLOTLY_CONFIG = {"displaylogo": False}


CSS = """
<style>
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1200px; }

/* Kotak metrik & kartu: nuansa navy background.png (hero Beranda). Kode
   warnanya DIAMBIL LANGSUNG dari gambarnya (#00214a sisi kiri yang gelap ->
   #0a3364 sisi kanan) supaya benar-benar sewarna dengan hero, bukan kira-kira.
   Warna TETAP (tidak ikut tema terang/gelap) supaya teks putih di dalamnya
   selalu kontras -- sama seperti hero & panel login. */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #00214a 0%, #052c5b 55%, #0a3364 100%);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 12px;
    padding: 14px 16px 10px;
    box-shadow: 0 6px 18px rgba(8,25,65,0.18);
}
div[data-testid="stMetric"] * { color: #fff !important; }
div[data-testid="stMetric"] div[data-testid="stMetricLabel"] * { color: rgba(255,255,255,0.82) !important; }
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {
    font-size: 1.25rem !important; font-weight: 700; line-height: 1.3 !important;
    white-space: normal !important; overflow: visible !important;
    text-overflow: unset !important; overflow-wrap: break-word !important;
}
div[data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.75; }

/* Narasi/insight box */
div[data-testid="stAlertContentInfo"] { font-size: 0.97rem; line-height: 1.6; }
div[data-testid="stNotification"] { border-radius: 12px; }

/* Kartu pilar dampak */
.pilar-card {
    border-radius: 14px;
    padding: 18px 12px 14px;
    text-align: center;
    transition: box-shadow 0.15s ease;
    height: 100%;
    box-sizing: border-box;
}
.pilar-card-icon { font-size: 2.1rem; line-height: 1; margin-bottom: 2px; }
.pilar-card-name {
    font-size: 0.95rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px;
}
.pilar-card-count { font-size: 2.4rem; font-weight: 800; line-height: 1.15; margin-top: 6px; }
.pilar-card-unit { font-size: 0.78rem; opacity: 0.65; margin-bottom: 10px; }
.pilar-card-theme {
    font-size: 0.83rem; opacity: 0.85;
    border-top: 1px solid rgba(128,128,128,0.22);
    padding-top: 8px; margin-top: 2px; min-height: 3.4em;
}

/* Kartu shortcut Beranda -- SATU elemen <a> (kartu + tombol "Buka ->" jadi
   satu blok HTML, lihat pages_app/beranda.py) supaya ukurannya menyesuaikan
   diri sendiri, bukan digabung dari dua elemen Streamlit terpisah (custom
   div + st.button). display:flex + footer margin-top:auto membuat
   "Buka ->" selalu menempel di bawah kartu apa pun panjang teks
   deskripsinya, dan kartu tetap rata tinggi lewat height:100% (kolomnya
   sendiri sudah stretch align, lihat shared/style.py). */
.home-card {
    display: flex;
    flex-direction: column;
    border-radius: 16px;
    padding: 24px 18px;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.14);
    background: linear-gradient(135deg, #00214a 0%, #052c5b 55%, #0a3364 100%);
    box-shadow: 0 8px 22px rgba(8,25,65,0.2);
    height: 100%;
    box-sizing: border-box;
    text-decoration: none;
    transition: box-shadow 0.15s ease, border-color 0.15s ease;
}
/* `<a>` punya warna+underline default browser/tema Streamlit dgn spesifisitas
   lebih tinggi dari `color:inherit` biasa -- paksa pakai warna teks tema
   (var Streamlit) supaya kartu ini terlihat SAMA seperti versi <div> lama,
   bukan seperti link biru pada umumnya. */
.home-card,
.home-card * {
    text-decoration: none !important;
    color: #fff !important;
}
.home-card:hover {
    border-color: rgba(255,199,44,0.55);
    box-shadow: 0 12px 28px rgba(8,25,65,0.3);
}
.home-card-icon { font-size: 2.4rem; line-height: 1; margin-bottom: 8px; }
/* Logo gambar pengganti emoji (aset sama dgn menu sidebar): chip putih setinggi
   emoji (2.4rem), logo hitam di dalamnya -- tetap terlihat di tema gelap. */
.home-card-logo {
    display: inline-flex; align-items: center; justify-content: center;
    width: 2.4rem; height: 2.4rem; border-radius: 10px;
    background: #fff !important; box-shadow: 0 0 0 1px rgba(0,0,0,0.08);
    vertical-align: top;
}
.home-card-logo img { width: 82%; height: 82%; object-fit: contain; }
/* Judul halaman dgn logo gambar (pengganti emoji di st.title). Jarak
   logo-teks pakai margin-right di .logo, BUKAN gap: Streamlit membungkus isi
   <h1> dalam satu <span>, jadi logo & teks bukan dua flex item -- gap tidak
   pernah kelihatan (logo terlihat mepet ke huruf pertama). */
/* Pakai h1.judul-halaman + !important: aturan h1 bawaan Streamlit (44px)
   spesifisitasnya lebih tinggi dari .judul-halaman biasa, jadi font-size di
   sini tidak akan berlaku kalau ditulis dgn selektor kelas saja. */
h1.judul-halaman {
    display: flex; align-items: center;
    font-size: 2.1rem !important; font-weight: 700;
    line-height: 1.25 !important; margin: 0 0 0.8rem !important;
    padding: 0 !important;
}
.judul-halaman .logo {
    display: inline-flex; align-items: center; justify-content: center;
    width: 0.92em; height: 0.92em; border-radius: 12px; flex: 0 0 auto;
    margin-right: 0.8rem;
    background: #fff; box-shadow: 0 0 0 1px rgba(0,0,0,0.08);
}
.judul-halaman .logo img { width: 78%; height: 78%; object-fit: contain; }
/* Ikon "link" bawaan Streamlit di sebelah heading -- tidak relevan di sini. */
.judul-halaman [data-testid="stHeaderActionElements"] { display: none; }
.home-card-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 6px; }
.home-card-desc { font-size: 0.85rem; color: rgba(255,255,255,0.85) !important; }
.home-card-footer {
    margin-top: auto;
    padding-top: 16px;
    font-size: 0.85rem;
    font-weight: 600;
    border-top: 1px solid rgba(128,128,128,0.2);
}
</style>
"""


def inject_css():
    apply_custom_css()
    st.markdown(CSS, unsafe_allow_html=True)


# Logo custom menu sidebar: url_path halaman -> file di assets/nav_icons/.
# st.Page(icon=...) HANYA menerima emoji tunggal atau ":material/...:" (lihat
# docstring st.Page), tidak menerima file gambar. Jadi ketiga halaman ini
# didaftarkan TANPA icon, lalu logonya dipasang lewat CSS ::before pada link
# menu yang href-nya berakhiran "/<url_path>". Selector "$=" aman: "/sdgs"
# tidak ikut cocok dengan "/dampak-sdgs".
# Key = url_path halaman ("" = Beranda, href-nya persis "/").
IKON_MENU_SIDEBAR = {
    "": "home.png",
    "sdgs": "sdgs.png",
    "dampak-sdgs": "dampakXsdgs.png",
    "akreditasi": "certificate.png",
    "dampak": "dampak.png",  # halaman dampak_saja.py -- FILE BELUM ADA, dilewati
}
# Aset dipakai bareng dashboard & modul login akreditasi -> ditaruh di shared/.
_DIR_IKON = Path(__file__).resolve().parents[1] / "shared" / "assets" / "logo"


@st.cache_resource
def data_uri_ikon(file: str) -> str:
    """Logo di shared/assets/logo/ sbg data URI (dipakai sidebar, kartu Beranda,
    judul halaman). None kalau filenya belum ada -- logo yang belum disiapkan
    TIDAK boleh menjatuhkan seluruh dashboard."""
    import base64

    path = _DIR_IKON / file
    if not path.is_file():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def judul_halaman(teks: str, file_logo: str) -> None:
    """Judul halaman (pengganti st.title) dgn logo gambar, bukan emoji -- logo
    yang SAMA dengan menu sidebar (lihat IKON_MENU_SIDEBAR) supaya judul dan
    menu tidak memakai ikon berbeda. Kalau file logonya belum ada, judul tetap
    tampil tanpa logo (data_uri_ikon mengembalikan "")."""
    uri = data_uri_ikon(file_logo)
    logo = f'<span class="logo"><img src="{uri}" alt=""></span>' if uri else ""
    st.markdown(
        f'<h1 class="judul-halaman">{logo}{html.escape(teks)}</h1>',
        unsafe_allow_html=True,
    )


@st.cache_resource
def css_ikon_sidebar() -> str:
    """<style> logo menu sidebar (base64, total <25 KB, di-cache per proses).
    Logo hitam dipasang di "chip" putih supaya tetap terlihat di tema gelap."""
    selector, aturan = [], []
    for url_path, file in IKON_MENU_SIDEBAR.items():
        uri = data_uri_ikon(file)
        if not uri:  # logo belum disiapkan -> menu itu tetap pakai ikon bawaan
            continue
        s = f'[data-testid="stSidebarNav"] a[href$="/{url_path}"]::before'
        selector.append(s)
        aturan.append(f'{s} {{ background-image: url("{uri}"); }}')
    if not aturan:
        return ""
    return (
        "<style>"
        + ",".join(selector) + " {"
        # Chip 22px tapi margin -3px kiri-kanan -> lebar tata letak 16px, SAMA
        # dgn kotak ikon emoji menu lain, jadi teks menu tetap sejajar.
        ' content: ""; flex: 0 0 auto; width: 22px; height: 22px;'
        ' margin: 0 -3px; border-radius: 6px;'
        ' background-color: #fff; background-repeat: no-repeat;'
        ' background-position: center; background-size: 82%;'
        ' box-shadow: 0 0 0 1px rgba(0,0,0,0.08); }'
        + "".join(aturan)
        + "</style>"
    )


def load_data_or_stop():
    """Load data + narasi cache dari MySQL; tampilkan pesan error & st.stop()
    kalau gagal (dipanggil di awal tiap halaman yang butuh data)."""
    from data_loader import load, load_narasi_cache

    try:
        data = load()
        narasi_cache = load_narasi_cache()
        return data, narasi_cache
    except KeyError as e:
        st.error(f"Variabel environment {e} belum diset. Isi file .env di root project "
                 "(MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB).")
        st.stop()
    except Exception as e:
        st.error(f"Gagal terhubung/membaca data dari MySQL: {e}")
        st.info(
            "Cek: (1) service MySQL sudah berjalan di host/port yang dikonfigurasi, "
            "(2) kredensial di .env (MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/"
            "MYSQL_DB) sudah benar, (3) user MySQL sudah punya akses ke database "
            "tsb, (4) tabel berprefix 'berita_' sudah ada (lihat migrasi_ke_mysql.py)."
        )
        st.stop()
