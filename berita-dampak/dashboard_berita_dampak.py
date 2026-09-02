"""Dashboard Streamlit analisis dampak berita UGM.

Sumber: MySQL ugm_analytics (tabel berita_berita, berita_berita_topik,
berita_ringkasan_topik_tahun, berita_sitemap, dst. — prefix "berita_", nama
tabel diwarisi dari migrasi awal DuckDB->MySQL; sejak 2026-08-29 seluruh
pipeline (scripts/update_mingguan.py) baca/tulis MySQL langsung, tidak ada
lagi DuckDB perantara -- lihat scripts/db.py dan PIPELINE.md).
Jalankan: streamlit run dashboard_berita_dampak.py
"""

import os
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.keywords import KEYWORDS  # noqa: E402
from scripts.sdg_keywords import SDG_KEYWORDS  # noqa: E402
from scripts.kepmen_sdg import (  # noqa: E402
    SDG_NAMA,
    TOPIK_KEPMEN,
    TOPIK_KEPMEN_ALL,
    TEMA_KEPMEN_LENGKAP,
    WARNA_PILAR,
    sdg_label,
)
from scripts.kepmen_sdg import LABEL_TOPIC_ALL as LABEL_TOPIC  # noqa: E402
from scripts.narasi_logic import (  # noqa: E402
    generate_executive_summary,
    generate_impact_insight,
    generate_sdg_saja_summary,
)
from scripts.unit_kerja import UNIT_KERJA  # noqa: E402

# 44 fakultas/sekolah/unit kerja, diurutkan Fakultas -> Sekolah -> Unit Kerja
# (lalu alfabetis per kategori) supaya gampang di-scan/cari di multiselect.
_URUTAN_KATEGORI = {"Fakultas": 0, "Sekolah": 1, "Unit Kerja": 2}
UNIT_KERJA_OPSI = sorted(
    UNIT_KERJA.keys(),
    key=lambda k: (_URUTAN_KATEGORI[UNIT_KERJA[k]["kategori"]], UNIT_KERJA[k]["nama"]),
)
WARNA_KATEGORI = {"Fakultas": "#3949ab", "Sekolah": "#00897b", "Unit Kerja": "#8e24aa"}

# Kredensial MySQL dibaca dari .env di root project (JANGAN di-commit; lihat .gitignore).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Semua keyword (14 tema resmi Kepmen) untuk breakdown.
KEYWORDS_ALL = dict(KEYWORDS)
KEYWORDS_ALL.update({k: v["keywords"] for k, v in TEMA_KEPMEN_LENGKAP.items()})

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


st.set_page_config(page_title="Analisis Dampak UGM", layout="wide", page_icon="🎓")
st.markdown(
    """
    <style>
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1200px; }

    /* Metric cards -- netral biar aman di light & dark theme */
    div[data-testid="stMetric"] {
        background: rgba(128,128,128,0.07);
        border: 1px solid rgba(128,128,128,0.16);
        border-radius: 12px;
        padding: 14px 16px 10px;
    }
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
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Analisis Dampak UGM")
st.caption("Sumber: berita ugm.ac.id")


@st.cache_resource
def _get_engine():
    """Engine SQLAlchemy ke MySQL, di-cache lintas rerun (cache_resource: koneksi
    tidak bisa/perlu di-pickle seperti DataFrame biasa di cache_data)."""
    host = os.environ["MYSQL_HOST"]
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ["MYSQL_USER"]
    password = os.environ["MYSQL_PASSWORD"]
    db = os.environ["MYSQL_DB"]
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    # pool_recycle: buang koneksi setelah 1 jam idle (server Streamlit long-lived
    # bisa idle lama antar rerun -- hindari "MySQL server has gone away").
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


@st.cache_data(ttl=300)
def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame]:
    engine = _get_engine()
    berita = pd.read_sql("SELECT * FROM berita_berita", engine)
    topik = pd.read_sql("SELECT * FROM berita_berita_topik", engine)
    ringkas = pd.read_sql("SELECT * FROM berita_ringkasan_topik_tahun", engine)
    sitemap = pd.read_sql("SELECT url, lastmod FROM berita_sitemap", engine)
    bk = pd.read_sql("SELECT * FROM berita_berita_kepmen_all", engine)
    bs = pd.read_sql("SELECT * FROM berita_berita_sdg_all", engine)
    rp = pd.read_sql("SELECT * FROM berita_ringkasan_pilar", engine)
    rpt = pd.read_sql("SELECT * FROM berita_ringkasan_pilar_tahun", engine)
    rsa = pd.read_sql("SELECT * FROM berita_ringkasan_sdg_all", engine)
    ss = pd.read_sql("SELECT * FROM berita_sitemap_sdg", engine)
    rsg = pd.read_sql("SELECT * FROM berita_ringkasan_sdg_sitemap", engine)
    rsgt = pd.read_sql("SELECT * FROM berita_ringkasan_sdg_sitemap_tahun", engine)
    uk = pd.read_sql("SELECT * FROM berita_unit_kerja", engine)
    return berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt, uk


@st.cache_data(ttl=300)
def load_narasi_cache() -> dict:
    """Narasi hasil rangkaian LLM (Gemini), digenerate mingguan lewat
    scripts/generate_narasi_llm.py -> tabel berita_narasi_cache. Dipakai HANYA
    saat filter sidebar masih posisi default (semua tahun/tema/sumber/pilar/
    SDG) -- kalau tabel belum ada / kosong / gagal baca, fallback otomatis ke
    narasi template (generate_executive_summary / generate_impact_insight),
    dashboard tetap jalan normal tanpa LLM.
    """
    try:
        engine = _get_engine()
        df = pd.read_sql("SELECT cache_key, narasi FROM berita_narasi_cache", engine)
        return dict(zip(df["cache_key"], df["narasi"]))
    except Exception:  # noqa: BLE001
        return {}


try:
    berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt, uk = load()
    NARASI_CACHE = load_narasi_cache()
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

# ---------- Sidebar filter global ----------
st.sidebar.header("Filter")
mode = st.sidebar.radio(
    "Mode analisis",
    ["Berdampak", "Berdampak × SDGs", "SDGs"],
    index=1,
    help="Berdampak: 3 dampak & 14 tema Kepmen (tanpa bagian SDG). "
         "Berdampak × SDGs: tampilan sekarang (tema + SDG dari berita bertema). "
         "SDGs: mapping langsung seluruh 32.130 URL berita ke SDG "
         "(tanpa tema dampak) — jangkauan lebih luas.",
)
tahun_opsi = sorted(
    berita["tanggal"].dropna().str[:4].unique()
) if len(berita) else ["2005", "2026"]
tahun_awal, tahun_akhir = st.sidebar.select_slider(
    "Rentang tahun",
    options=tahun_opsi,
    value=(tahun_opsi[0], tahun_opsi[-1]),
)
# Semua berita (RSS + sitemap) selalu ikut dihitung -- bukan pilihan yang
# perlu diputuskan user, cuma dua cara pengambilan data yang saling melengkapi
# (RSS = berita terbaru, sitemap = arsip). Tidak ada lagi filter "Sumber" di UI.
sumber_pilih = ["sitemap", "rss"]

# 14 tema dikelompokkan per pilar (urutan sesuai LABEL_TOPIC) -- dipakai untuk
# pecah dropdown tema jadi 1 per pilar, bukan 1 dropdown raksasa isi 14 tema.
TOPIK_PER_PILAR = {
    p: [k for k in LABEL_TOPIC if TOPIK_KEPMEN_ALL[k]["dampak"] == p]
    for p in ["Lingkungan", "Ekonomi", "Sosial"]
}
PILAR_ICON_SIDEBAR = {"Lingkungan": "🌳", "Ekonomi": "💼", "Sosial": "🤝"}

topik_pilih: list = []
pilar_pilih: list = []
unit_pilih: list = []
if mode == "SDGs":
    # Mode SDG: filter berdasarkan SDG, bukan tema dampak.
    sdg_pilih = st.sidebar.multiselect(
        "SDG (17)",
        options=list(range(1, 18)),
        default=list(range(1, 18)),
        format_func=lambda s: f"SDG {s} — {SDG_NAMA.get(s, s)}",
    )
else:
    sdg_pilih = list(range(1, 18))
    # 1) Pilih dampak (pilar) dulu ...
    pilar_pilih = st.sidebar.multiselect(
        "Dampak",
        options=["Lingkungan", "Ekonomi", "Sosial"],
        default=["Lingkungan", "Ekonomi", "Sosial"],
        format_func=lambda p: f"{PILAR_ICON_SIDEBAR[p]} {p}",
    )
    # 2) ... baru tema Kepmen-nya, satu dropdown TERPISAH per dampak terpilih
    #    (bukan 1 dropdown gabungan isi 14 tema sekaligus).
    if pilar_pilih:
        st.sidebar.caption("Tema resmi Kepmen per dampak:")
        for p in ["Lingkungan", "Ekonomi", "Sosial"]:
            if p not in pilar_pilih:
                continue
            opsi_tema_p = TOPIK_PER_PILAR[p]
            pilih_p = st.sidebar.multiselect(
                f"{PILAR_ICON_SIDEBAR[p]} {p}",
                options=opsi_tema_p,
                default=opsi_tema_p,
                format_func=lambda k: LABEL_TOPIC[k],
                key=f"tema_pilar_{p}",
            )
            topik_pilih.extend(pilih_p)
    else:
        st.sidebar.caption("⚠️ Pilih minimal satu dampak untuk melihat tema.")

# Filter fakultas/unit kerja (independen dari tema/pilar Kepmen DAN dari mode
# SDGs/Berdampak -- SENGAJA di luar if/else mode di atas supaya tetap muncul
# & berlaku di ketiga mode, termasuk mode "SDGs" yang punya jalur data sendiri
# (lihat penerapannya di situ, beda dari filter unit di jalur Berdampak).
# Default kosong = tidak memfilter apa pun sampai user pilih (lihat
# berita_unit_kerja, tabel dari scripts/tag_unit_kerja.py).
unit_pilih = st.sidebar.multiselect(
    "Fakultas / Unit Kerja",
    options=UNIT_KERJA_OPSI,
    default=[],
    format_func=lambda k: UNIT_KERJA[k]["nama"],
    help="Filter berita yang menyebut fakultas/sekolah/unit kerja ini "
         "(nama resmi, hasil keyword matching). Kosong = tidak memfilter.",
)

# Narasi LLM ter-cache (lihat load_narasi_cache di atas) cuma valid utk posisi
# filter DEFAULT -- begitu user ganti tahun/tema/pilar/SDG, angka2 dalam
# narasi cache jadi gak sesuai lagi, jadi WAJIB balik ke template pandas
# yang dihitung ulang dari data ter-filter (generate_executive_summary /
# generate_impact_insight / narasi mode SDGs saja).
FILTER_ADALAH_DEFAULT = (
    tahun_awal == tahun_opsi[0]
    and tahun_akhir == tahun_opsi[-1]
    and set(topik_pilih) == set(LABEL_TOPIC.keys())
    and set(pilar_pilih) == {"Lingkungan", "Ekonomi", "Sosial"}
    and set(sdg_pilih) == set(range(1, 18))
    and not unit_pilih
)


def narasi_llm_atau_fallback(cache_key: str, fallback: str) -> str:
    """Pakai narasi hasil LLM (cache mingguan) kalau ada & filter default;
    kalau tidak, pakai narasi template (fallback) yang selalu akurat untuk
    filter apa pun."""
    if FILTER_ADALAH_DEFAULT and cache_key in NARASI_CACHE:
        return NARASI_CACHE[cache_key]
    return fallback


# ---------- Tombol update berita terbaru ----------
# Pipeline (scripts/update_mingguan.py) menulis langsung ke MySQL di setiap
# step (prefix "berita_", lihat scripts/db.py) -- dashboard ini baca dari
# MySQL yang sama, jadi data baru muncul begitu pipeline selesai.
st.sidebar.divider()
update_log = Path(__file__).resolve().parent / "logs_update_dashboard.txt"
if update_log.exists():
    mtime = update_log.stat().st_mtime
    import time as _time

    st.sidebar.caption(f"Update terakhir: {_time.strftime('%Y-%m-%d %H:%M', _time.localtime(mtime))}")
else:
    st.sidebar.caption("Data terakhir diambil dari ugm.ac.id.")

if st.sidebar.button("🔄 Update Berita Terbaru", use_container_width=True):
    import subprocess

    script = Path(__file__).resolve().parent / "scripts" / "update_mingguan.py"
    py = os.environ.get("UGM_ANALYTICS_PYTHON", sys.executable)
    lock = Path(__file__).resolve().parent / "data" / ".update_lock"
    if lock.exists():
        st.warning(
            "Update lain sedang berjalan di background (dari tombol ini atau "
            "cron mingguan). Tunggu sampai selesai (±10 menit), lalu muat "
            "ulang halaman ini."
        )
        st.stop()
    # Jalankan update sebagai proses terpisah; dashboard TIDAK diblokir.
    log_f = open(update_log, "w", encoding="utf-8")
    p = subprocess.Popen(
        [str(py), str(script)],
        cwd=str(Path(__file__).resolve().parent),
        stdout=log_f, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    st.success(
        f"Update dimulai di background (PID {p.pid}). "
        "Proses memakan waktu ±10 menit (fetch berita baru dari ugm.ac.id, "
        "langsung ditulis ke MySQL). Setelah selesai, muat ulang halaman — "
        "data baru otomatis tampil. Log: logs_update_dashboard.txt"
    )
    st.stop()

# ---------- Mode "SDGs": mapping langsung seluruh 32.130 URL ke SDG ----------
if mode == "SDGs":
    st.subheader("Analisis SDGs — Seluruh Berita UGM (32.130 URL)")
    st.caption(
        "Mapping langsung url berita sitemap ke 17 SDG (tanpa tema dampak Kepmen): "
        "kata-kata slug URL untuk yang belum di-fetch + judul & deskripsi untuk "
        "4.787 yang sudah. Satu berita bisa masuk beberapa SDG. Filter SDG & "
        "Fakultas/Unit Kerja di sidebar berlaku di sini."
    )
    sitemap["tahun"] = sitemap["lastmod"].str[:4]
    sm = sitemap[sitemap["tahun"].between(tahun_awal, tahun_akhir)].copy()
    if unit_pilih:
        # sitemap simpan url MENTAH (bisa ada trailing slash/query string),
        # sedangkan berita_unit_kerja simpan url BERSIH (konvensi
        # normalisasi.py) -- samakan bentuknya dulu sebelum dicocokkan,
        # jangan langsung .isin() dua bentuk url yang berbeda.
        unit_urls_bersih = set(uk.loc[uk["unit_kerja"].isin(unit_pilih), "url"])
        sm_url_bersih = sm["url"].str.split("?").str[0].str.rstrip("/")
        sm = sm[sm_url_bersih.isin(unit_urls_bersih)]
    ss_f = ss[ss["sdg"].isin(sdg_pilih) & ss["url"].isin(set(sm["url"]))]
    n_url = len(sm)
    n_tag = ss_f["url"].nunique()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total berita (sitemap)", f"{n_url:,}")
    c2.metric("Berita bertanda SDG", f"{n_tag:,}")
    c3.metric("Cakupan", f"{100 * n_tag / n_url:.1f}%" if n_url else "—")
    if not len(ss_f):
        st.warning("Tidak ada data SDG untuk rentang tahun ini.")
        st.stop()

    # ---------- Ringkasan Eksekutif (mode SDGs saja) ----------
    st.subheader("Ringkasan Eksekutif")
    narasi_sdg_saja_fallback = generate_sdg_saja_summary(sm, ss_f, tahun_awal, tahun_akhir)
    st.info(narasi_llm_atau_fallback("sdg_saja", narasi_sdg_saja_fallback))
    penjelasan(
        "Ringkasan ini dihitung ulang tiap dashboard dimuat dari data ter-filter saat itu — "
        "sama seperti Ringkasan Eksekutif di mode Berdampak."
    )

    # Distribusi per SDG
    st.subheader("Distribusi Berita per SDG")
    dist = ss_f.groupby("sdg")["url"].nunique().reset_index(name="jumlah")
    # Label sumbu pendek 'SDG n'; nama lengkap di kolom 'nama' (tabel & hover).
    dist["label"] = dist["sdg"].map(lambda s: f"SDG {s}")
    dist["nama"] = dist["sdg"].map(SDG_NAMA.get)
    fig_d = px.bar(
        dist.sort_values("jumlah"), x="label", y="jumlah", color="sdg",
        title="Jumlah berita per SDG (seluruh URL sitemap)",
        labels={"label": "SDG", "jumlah": "Jumlah berita"},
        hover_data={"nama": True, "sdg": False, "label": False},
    )
    fig_d.update_layout(height=460, showlegend=False,
                        xaxis=dict(tickangle=-45, tickfont=dict(size=10),
                                   automargin=True))
    hover_keterangan(
        fig_d,
        "URL unik yang match keyword SDG ini; satu URL bisa masuk beberapa SDG.",
    )
    st.plotly_chart(fig_d, width="stretch")
    penjelasan(
        "Jangkauan tiap SDG: jumlah URL unik sitemap yang teksnya (slug "
        "URL / judul / deskripsi) mengandung keyword SDG tsb. Satu URL "
        "bisa dihitung di beberapa SDG."
    )

    # Tren per tahun + heatmap SDG x tahun
    st.subheader("Tren SDG per Tahun")
    sdg_tahun = (
        ss_f.merge(sm[["url", "tahun"]], on="url", how="left")
        .drop_duplicates(subset=["url", "sdg", "tahun"])
        .groupby(["tahun", "sdg"])
        .size()
        .reset_index(name="jumlah")
    )
    if len(sdg_tahun):
        sdg_tahun["label"] = sdg_tahun["sdg"].map(lambda s: f"SDG {s}")
        fig_t = px.line(
            sdg_tahun, x="tahun", y="jumlah", color="label", markers=True,
            title="Jumlah berita bertanda SDG per tahun",
            labels={"tahun": "Tahun", "jumlah": "Jumlah berita", "label": "SDG"},
        )
        fig_t.update_layout(height=420)
        hover_keterangan(fig_t, "URL unik bertanda SDG ini pada tahun tsb.")
        st.plotly_chart(fig_t, width="stretch")
        penjelasan(
            "Perkembangan tiap SDG antar tahun (berdasar lastmod sitemap). "
            "Angka = URL unik yang match keyword SDG pada tahun itu."
        )

        st.markdown("**Heatmap SDG × Tahun**")
        piv = (
            sdg_tahun.pivot_table(index="sdg", columns="tahun", values="jumlah",
                                  aggfunc="sum", fill_value=0)
        )
        piv_h = piv.copy()
        # index jadi string 'SDG n' -> sumbu kategori menampilkan SEMUA label
        # otomatis di posisi benar (override tickvals 0..n di axis kategori
        # bikin label menipis/misplace — terlihat '5 10 15' bertabrakan).
        piv_h.index = [f"SDG {c}" for c in piv.index]
        fig_h = px.imshow(
            piv_h, text_auto=True, aspect="auto",
            title="Jumlah berita per kombinasi SDG × tahun",
            labels={"x": "Tahun", "y": "SDG", "color": "Berita"},
            color_continuous_scale="blues",
        )
        fig_h.update_xaxes(tickangle=-45, tickfont=dict(size=10),
                           automargin=True)
        fig_h.update_yaxes(tickfont=dict(size=11), automargin=True)
        fig_h.update_traces(textfont=dict(size=8))
        fig_h.update_layout(height=480)
        hover_keterangan(fig_h, "URL unik yang masuk SDG baris pada tahun kolom.")
        st.plotly_chart(fig_h, width="stretch")
        penjelasan(
            "Kombinasi SDG × tahun: sel = jumlah URL unik berita yang match "
            "keyword SDG pada tahun tsb; sel kosong (0) = tidak ada berita."
        )

    # Tabel ringkasan
    st.subheader("Ringkasan per SDG")
    ring = dist.copy()
    ring["sdg_label"] = ring["sdg"].map(lambda s: f"SDG {s}")
    ring = ring[["sdg_label", "nama", "jumlah"]].sort_values("jumlah", ascending=False)
    ring.columns = ["SDG", "Nama", "Jumlah berita"]
    st.dataframe(ring, width="stretch", hide_index=True)

    # Keyword per SDG
    with st.expander("Lihat keyword per SDG (dasar mapping)"):
        kw_rows = []
        for sdg, kws in SDG_KEYWORDS.items():
            kw_rows.append({
                "SDG": f"SDG {sdg}",
                "Nama": SDG_NAMA.get(sdg, sdg),
                "Keyword": ", ".join(kws),
            })
        # Lebar kolom Keyword dipaksa lebar (640px) supaya tabel overflow dan
        # scroll HORIZONTAL muncul — default auto-fit memotong teks tanpa scroll.
        st.dataframe(
            pd.DataFrame(kw_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "SDG": st.column_config.TextColumn(width="small"),
                "Nama": st.column_config.TextColumn(width="medium"),
                "Keyword": st.column_config.TextColumn(width=640),
            },
        )

    # Cek manual
    with st.expander("Berita tanpa tanda SDG (cek manual)"):
        tagged = set(ss_f["url"])
        belum = sm[~sm["url"].isin(tagged)]
        st.write(f"{len(belum)} berita (dalam rentang tahun) tidak masuk SDG mana pun.")
        if len(belum):
            st.dataframe(
                belum[["url", "lastmod"]].sort_values("lastmod", ascending=False).head(200),
                width="stretch", hide_index=True,
            )
    st.stop()

# Terapkan filter
b = berita.copy()
b["tahun"] = b["tanggal"].str[:4]
b = b[b["tahun"].between(tahun_awal, tahun_akhir) & b["sumber"].isin(sumber_pilih)]
# b_tanpa_filter_unit = tahun+sumber saja, TANPA filter "Fakultas / Unit Kerja"
# -- dipakai KHUSUS tab "Fakultas/Unit Kerja" (lihat bawah) supaya chart
# ranking unit tetap independen & adil dibandingkan, tidak bias ke unit yang
# sedang dipilih di sidebar (co-occurrence di dalam subset yang sudah
# dipersempit filter unit itu sendiri akan selalu membuat unit itu jadi
# bar terpanjang -- bukan bug data, tapi menyesatkan secara UX).
b_tanpa_filter_unit = b.copy()
if unit_pilih:
    # Filter fakultas/unit kerja berlaku AND dengan filter lain -- persempit
    # ke berita yang menyebut salah satu unit terpilih (berita_unit_kerja).
    b = b[b["url"].isin(set(uk.loc[uk["unit_kerja"].isin(unit_pilih), "url"]))]
# t = semua tema Kepmen (14 tema resmi) dari tabel gabungan.
# Kalau filter tema/pilar kosong, fallback ke 4 tema inti (tema berita).
def _build_t(b_df: pd.DataFrame) -> pd.DataFrame:
    t_ = bk[bk["topik"].isin(topik_pilih)] if topik_pilih else bk
    if pilar_pilih:
        t_ = t_[t_["dampak"].isin(pilar_pilih)]
    if len(b_df) and len(t_):
        t_ = t_[t_["url"].isin(set(b_df["url"]))]
    return t_


t = _build_t(b)
# t_tanpa_filter_unit = versi t yang diturunkan dari b_tanpa_filter_unit (BUKAN
# b) -- WAJIB, karena t sendiri di-intersect ke url yang ada di b (baris di
# atas), jadi kalau langsung dipakai buat selected_t di tab "Fakultas/Unit
# Kerja", ikut "tercemar" filter unit walau sudah ganti dasar berita-nya ke
# b_tanpa_filter_unit -- ini akar bug nyata: sebelumnya cuma benerin di titik
# pemakaian (selected_news_tanpa_filter_unit), tapi selected_t yang jadi
# rujukan filter url-nya sendiri sudah kepersempit dari sini.
t_tanpa_filter_unit = _build_t(b_tanpa_filter_unit)

# Tema yang harus tampil penuh di chart (sinkron 14 tema): semua tema yang
# dipilih di sidebar DAN masuk pilar terpilih — tema tanpa match (mis.
# Pengajaran & Pembelajaran, 0 berita) tetap tampil dengan angka 0.
_pilar_set = set(pilar_pilih) if pilar_pilih else {"Lingkungan", "Ekonomi", "Sosial"}
TOPIK_TAMPIL = [
    k for k in LABEL_TOPIC
    if k in set(topik_pilih) and TOPIK_KEPMEN_ALL[k]["dampak"] in _pilar_set
]

# ---------- Ringkasan ----------
if len(b) == 0 or len(t) == 0:
    st.warning("Tidak ada data untuk filter ini. Ubah filter di sidebar.")
    st.stop()

b_t = b.merge(t, on="url", how="inner")

# Tabel Kepmen/SDG ke berita yang lolos filter (dipakai ringkasan
# eksekutif, tab per pilar, dan Analisis Lintas-Pilar di bawah).
urls_t = set(b_t["url"])
bk_f = t[t["url"].isin(urls_t)].copy()
bs_f = bs[bs["url"].isin(urls_t)].copy()

# ---------- Ringkasan Eksekutif Dinamis ----------
if mode != "SDGs":
    st.subheader("Ringkasan Eksekutif")
    ringkasan = generate_executive_summary(b, t, bs_f, mode, tahun_awal, tahun_akhir)
    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Total berita dampak", f"{ringkasan['total_berita']:,}")
    _pilar_delta_label = (
        f"{ringkasan['pilar_top_pct']:+.1f}%" if ringkasan["pilar_top_pct"] is not None
        else (f"+{ringkasan['pilar_top_naik']} berita" if ringkasan["pilar_top_naik"] else None)
    )
    rc2.metric("Dampak pertumbuhan tertinggi", ringkasan["pilar_top"], _pilar_delta_label)
    rc3.metric(f"Sorotan {tahun_akhir}", f"{ringkasan['berita_tahun_ini']:,} berita")
    rc4.metric(ringkasan["topik_top_kind_label"], ringkasan["topik_top_short"])
    _exec_cache_key = "exec_berdampak_sdgs" if mode == "Berdampak × SDGs" else "exec_berdampak"
    st.info(narasi_llm_atau_fallback(_exec_cache_key, ringkasan["narasi"]))
    penjelasan(
        "Ringkasan ini dihitung ulang tiap dashboard dimuat dari data ter-filter saat itu \u2014 "
        "otomatis ikut berubah begitu ada berita baru masuk lewat update mingguan, bukan teks statis."
    )

    # ---------- Overview: 3 pilar dampak, klik satu untuk drill-down ----------
    st.subheader("Overview Dampak UGM")
    st.caption("Klik salah satu dampak di bawah untuk melihat detail tema, tren, dan insight otomatis.")
    st.session_state.setdefault("selected_pilar", None)

    PILAR_ICON = {"Lingkungan": "🌳", "Ekonomi": "💼", "Sosial": "🤝"}
    pilar_order = ["Lingkungan", "Ekonomi", "Sosial"]
    pilar_cards = st.columns(3, gap="medium")
    for idx, pilar in enumerate(pilar_order):
        pilar_topik = t[t["dampak"] == pilar].copy()
        pilar_urls = set(pilar_topik["url"])
        pilar_news = b[b["url"].isin(pilar_urls)]
        pilar_total = int(pilar_news["url"].nunique())
        tema_terbanyak = (
            pilar_topik.groupby("topik")["url"].nunique().sort_values(ascending=False).head(1)
        )
        if not tema_terbanyak.empty:
            top_theme_name = LABEL_TOPIC.get(tema_terbanyak.index[0], tema_terbanyak.index[0])
            top_theme_n = int(tema_terbanyak.iloc[0])
        else:
            top_theme_name, top_theme_n = "-", 0
        with pilar_cards[idx]:
            is_active = st.session_state["selected_pilar"] == pilar
            warna = WARNA_PILAR[pilar]
            border_w = "3px" if is_active else "1px"
            shadow = f"0 6px 16px {warna}40" if is_active else "0 1px 3px rgba(0,0,0,0.08)"
            st.markdown(
                f"""
                <div class="pilar-card" style="border:{border_w} solid {warna};
                     background:{warna}14; box-shadow:{shadow};">
                    <div class="pilar-card-icon">{PILAR_ICON[pilar]}</div>
                    <div class="pilar-card-name" style="color:{warna};">{pilar}</div>
                    <div class="pilar-card-count">{pilar_total:,}</div>
                    <div class="pilar-card-unit">berita</div>
                    <div class="pilar-card-theme">Tema terbanyak (subset dari total)<br>
                        <b>{top_theme_name}</b> — {top_theme_n:,} berita</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "✓ Sedang dilihat" if is_active else "Lihat detail →",
                key=f"pilar_{pilar}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["selected_pilar"] = pilar

    if st.session_state["selected_pilar"] is None:
        st.info("👆 Klik salah satu dampak di atas untuk melihat detail tema, tren, dan insight.")
        st.stop()

    selected_pilar = st.session_state["selected_pilar"]
    selected_t = t[t["dampak"] == selected_pilar].copy()
    selected_news = b[b["url"].isin(set(selected_t["url"]))].copy()
    selected_news["tahun"] = selected_news["tanggal"].str[:4]
    # Versi TANPA filter "Fakultas / Unit Kerja" (tahun/sumber/tema/pilar
    # tetap berlaku) -- khusus untuk tab "Fakultas/Unit Kerja" di bawah. WAJIB
    # pakai selected_t_tanpa_filter_unit (dari t_tanpa_filter_unit), BUKAN
    # selected_t biasa -- selected_t sendiri sudah ke-intersect ke url di b
    # (yang sudah unit-filtered), jadi kalau dipakai di sini filter unit tetap
    # bocor lewat daftar url tema-nya walau basis beritanya sudah diganti.
    selected_t_tanpa_filter_unit = t_tanpa_filter_unit[t_tanpa_filter_unit["dampak"] == selected_pilar]
    selected_news_tanpa_filter_unit = b_tanpa_filter_unit[
        b_tanpa_filter_unit["url"].isin(set(selected_t_tanpa_filter_unit["url"]))
    ].copy()
    bk_f_pilar = bk_f[bk_f["dampak"] == selected_pilar].copy()
    bs_f_pilar = bs_f[bs_f["url"].isin(set(bk_f_pilar["url"]))].copy()
    b_t_pilar = b_t[b_t["url"].isin(set(bk_f_pilar["url"]))].copy()
    TOPIK_TAMPIL_PILAR = [k for k in TOPIK_TAMPIL if TOPIK_KEPMEN_ALL[k]["dampak"] == selected_pilar]

    st.markdown("---")
    st.subheader(f"Detail Dampak: {selected_pilar}")

    tab_labels = ["Ringkasan & Insight", "Tema Resmi Kepmen"]
    if mode != "Berdampak":
        tab_labels.append("SDGs Terkait")
    tab_labels += ["Tren & Musiman", "Kata Kunci & Berita", "Fakultas/Unit Kerja"]
    tabs = st.tabs(tab_labels)
    tab_iter = iter(tabs)

    # --- Tab: Ringkasan & Insight ---
    with next(tab_iter):
        _insight_fallback = generate_impact_insight(
            selected_news, selected_pilar, tahun_awal, tahun_akhir, selected_t, mode, bs_f_pilar,
        )
        # Cache LLM cuma digenerate utk mode "Berdampak x SDGs" (paling
        # lengkap) -- mode lain otomatis fallback ke template (key gak match).
        _pilar_key = (
            f"pilar_{selected_pilar.lower()}" if mode == "Berdampak × SDGs"
            else f"pilar_{selected_pilar.lower()}_{mode}"
        )
        st.info(narasi_llm_atau_fallback(_pilar_key, _insight_fallback))

        c1, c2, c3 = st.columns(3)
        c1.metric("Berita unik", f"{selected_news['url'].nunique():,}")
        c2.metric("Tema aktif", f"{selected_t['topik'].nunique()}")
        c3.metric("Tahun jangkauan", f"{selected_news['tahun'].min()}\u2013{selected_news['tahun'].max()}")

        topik_counts = (
            selected_t.groupby("topik")["url"].nunique().reset_index(name="jumlah")
            .sort_values("jumlah", ascending=False)
        )
        topik_counts["label"] = topik_counts["topik"].map(LABEL_TOPIC)
        fig_detail = px.bar(
            topik_counts, x="jumlah", y="label", orientation="h",
            title=f"Distribusi tema dalam dampak {selected_pilar}",
            labels={"label": "Tema", "jumlah": "Jumlah berita"},
            color="label", color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_detail.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig_detail, width="stretch")

        trend_detail = selected_news.groupby("tahun")["url"].nunique().reset_index(name="jumlah")
        fig_trend = px.line(
            trend_detail, x="tahun", y="jumlah", markers=True,
            title=f"Tren berita per tahun untuk dampak {selected_pilar}",
            labels={"tahun": "Tahun", "jumlah": "Jumlah berita"},
        )
        fig_trend.update_layout(height=360)
        st.plotly_chart(fig_trend, width="stretch")

        st.markdown("**Daftar tema dalam dampak ini**")
        st.dataframe(
            topik_counts[["label", "jumlah"]].rename(columns={"label": "Tema", "jumlah": "Jumlah berita"}),
            width="stretch", hide_index=True,
        )

    # --- Tab: Tema Resmi Kepmen ---
    with next(tab_iter):
        if len(bk_f_pilar):
            dist_k_t_p = (
                bk_f_pilar.groupby("topik")["url"].nunique().reset_index(name="jumlah")
                .set_index("topik").reindex(TOPIK_TAMPIL_PILAR, fill_value=0).reset_index()
            )
            dist_k_t_p["topik_kepmen"] = dist_k_t_p["topik"].map(
                lambda k: TOPIK_KEPMEN_ALL[k]["topik_kepmen"]
            )
            dist_k_p = (
                dist_k_t_p.groupby("topik_kepmen")["jumlah"].sum().reset_index().sort_values("jumlah")
            )
            fig_k_p = px.bar(
                dist_k_p, x="jumlah", y="topik_kepmen", orientation="h",
                title=f"Berita per Tema Resmi Kepmen \u2014 dampak {selected_pilar}",
                labels={"topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita"},
                color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
            )
            fig_k_p.update_layout(height=340, showlegend=False)
            hover_keterangan(fig_k_p, "Berita unik yang masuk Tema Resmi Kepmen ini pada dampak terpilih.")
            st.plotly_chart(fig_k_p, width="stretch")
        else:
            st.info("Tidak ada data Kepmen untuk dampak ini pada filter saat ini.")

        st.markdown("**Indikator resmi Kepmen 361/M/KEP/2025 pada dampak ini**")
        map_rows_p = [
            {
                "Tema dampak berita": LABEL_TOPIC.get(k, k),
                "Tema Resmi Kepmen": meta["topik_kepmen"],
                "Indikator Kepmen": meta["indikator"],
                "Satuan": meta["satuan"],
            }
            for k, meta in TOPIK_KEPMEN_ALL.items() if meta["dampak"] == selected_pilar
        ]
        st.dataframe(pd.DataFrame(map_rows_p), width="stretch", hide_index=True)

    # --- Tab: SDGs Terkait ---
    if mode != "Berdampak":
        with next(tab_iter):
            if len(bs_f_pilar):
                dist_s_p = (
                    bs_f_pilar.groupby("sdg")["url"].nunique().reset_index(name="jumlah")
                    .sort_values("jumlah")
                )
                dist_s_p["label"] = dist_s_p["sdg"].map(lambda s: f"SDG {s}")
                dist_s_p["nama"] = dist_s_p["sdg"].apply(sdg_label)
                fig_s_p = px.bar(
                    dist_s_p, x="label", y="jumlah", color="sdg",
                    title=f"Berita per SDG \u2014 dampak {selected_pilar}",
                    labels={"label": "SDG", "jumlah": "Jumlah berita"},
                    hover_data={"nama": True, "sdg": False, "label": False},
                )
                fig_s_p.update_layout(height=380, showlegend=False,
                                      xaxis=dict(tickangle=-45, tickfont=dict(size=10), automargin=True))
                hover_keterangan(fig_s_p, "Berita unik dampak ini pada klaster SDG tsb.")
                st.plotly_chart(fig_s_p, width="stretch")

                hm_p = (
                    bs_f_pilar.merge(bk_f_pilar[["url", "topik"]], on="url", how="left")
                    .drop_duplicates(subset=["url", "topik", "sdg"])
                )
                if len(hm_p):
                    hm_piv_p = (
                        hm_p.pivot_table(index="topik", columns="sdg", values="url",
                                         aggfunc="nunique", fill_value=0)
                        .reindex(index=TOPIK_TAMPIL_PILAR, fill_value=0)
                    )
                    hm_piv_p2 = hm_piv_p.copy()
                    hm_piv_p2.index = [LABEL_TOPIC.get(i, i) for i in hm_piv_p.index]
                    hm_piv_p2.columns = [f"SDG {c}" for c in hm_piv_p.columns]
                    fig_hm_p = px.imshow(
                        hm_piv_p2, text_auto=True, aspect="auto",
                        title=f"Tema \u00d7 SDG \u2014 dampak {selected_pilar}",
                        labels={"x": "SDG", "y": "Tema", "color": "Berita"},
                        color_continuous_scale="blues",
                    )
                    fig_hm_p.update_xaxes(tickangle=-45, tickfont=dict(size=10), automargin=True)
                    fig_hm_p.update_yaxes(tickfont=dict(size=11), automargin=True)
                    fig_hm_p.update_traces(textfont=dict(size=8))
                    fig_hm_p.update_layout(height=360)
                    hover_keterangan(fig_hm_p, "Berita unik yang masuk tema baris sekaligus SDG kolom, dampak ini.")
                    st.plotly_chart(fig_hm_p, width="stretch")
            else:
                st.info("Tidak ada data SDG untuk dampak ini pada filter saat ini.")

    # --- Tab: Tren & Musiman ---
    with next(tab_iter):
        piv_p_ty = (
            b_t_pilar.pivot_table(index="topik", columns="tahun", values="url",
                                  aggfunc="nunique", fill_value=0)
            .reindex(index=TOPIK_TAMPIL_PILAR, fill_value=0)
        )
        if len(piv_p_ty):
            piv_p_ty2 = piv_p_ty.copy()
            piv_p_ty2.index = [LABEL_TOPIC.get(i, i) for i in piv_p_ty.index]
            fig_h_p = px.imshow(
                piv_p_ty2, text_auto=True, aspect="auto",
                title=f"Tema \u00d7 Tahun \u2014 dampak {selected_pilar}",
                labels={"x": "Tahun", "y": "Tema", "color": "Berita"},
                color_continuous_scale="greens",
            )
            fig_h_p.update_xaxes(tickangle=-45, tickfont=dict(size=10), automargin=True)
            fig_h_p.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_h_p.update_traces(textfont=dict(size=8))
            fig_h_p.update_layout(height=340)
            hover_keterangan(fig_h_p, "Berita unik tema ini pada tahun tsb, dampak terpilih.")
            st.plotly_chart(fig_h_p, width="stretch")
        else:
            st.info("Tidak cukup data untuk heatmap dampak ini.")

        b_t_pilar_bulan = b_t_pilar.copy()
        b_t_pilar_bulan["bulan"] = b_t_pilar_bulan["tanggal"].str[5:7]
        musim_p = b_t_pilar_bulan.groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
        if len(musim_p):
            musim_p["label"] = musim_p["topik"].map(LABEL_TOPIC)
            fig_m_p = px.bar(
                musim_p, x="bulan", y="jumlah", color="label", barmode="stack",
                title=f"Tren bulanan (musiman) \u2014 dampak {selected_pilar}",
                labels={"bulan": "Bulan", "jumlah": "Jumlah berita", "label": "Tema"},
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_m_p.update_layout(height=340)
            hover_keterangan(fig_m_p, "Berita bulan tsb, semua tahun digabung, dampak terpilih.")
            st.plotly_chart(fig_m_p, width="stretch")

    # --- Tab: Kata Kunci & Berita ---
    with next(tab_iter):
        topik_ada_p = sorted(TOPIK_TAMPIL_PILAR, key=lambda k: LABEL_TOPIC.get(k, k))
        if topik_ada_p:
            pilih_kw_p = st.selectbox(
                "Pilih tema (keyword)", options=topik_ada_p,
                format_func=lambda k: LABEL_TOPIC.get(k, k), key="kw_pilar",
            )
            urls_topik_p = set(b_t_pilar.loc[b_t_pilar["topik"] == pilih_kw_p, "url"])
            sub_p = b[b["url"].isin(urls_topik_p)]
            teks_p = (sub_p["judul"].fillna("") + " " + sub_p["deskripsi"].fillna("")).str.lower()
            rows_p = []
            for kw in KEYWORDS_ALL.get(pilih_kw_p, []):
                n = teks_p.str.contains(re.escape(kw), regex=True).sum()
                if n:
                    rows_p.append({"keyword": kw, "jumlah": int(n)})
            if rows_p:
                kw_df_p = pd.DataFrame(rows_p).sort_values("jumlah")
                fig_kw_p = px.bar(
                    kw_df_p, x="jumlah", y="keyword", orientation="h",
                    title=f"Keyword pemicu match \u2014 {LABEL_TOPIC.get(pilih_kw_p, pilih_kw_p)}",
                    labels={"keyword": "Keyword", "jumlah": "Jumlah berita"},
                    color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
                )
                fig_kw_p.update_layout(height=max(300, 30 * len(kw_df_p) + 80),
                                       yaxis=dict(autorange="reversed"), showlegend=False)
                st.plotly_chart(fig_kw_p, width="stretch")
            else:
                st.info("Tidak ada match keyword untuk tema ini.")

            st.markdown("**Kata yang paling sering muncul**")
            freq_p = token_freq(sub_p)
            freq_df_p = pd.DataFrame(freq_p.most_common(15), columns=["kata", "jumlah"])
            if len(freq_df_p):
                fig_wf_p = px.bar(
                    freq_df_p, x="jumlah", y="kata", orientation="h",
                    title=f"15 kata teratas \u2014 {LABEL_TOPIC.get(pilih_kw_p, pilih_kw_p)}",
                    labels={"kata": "Kata", "jumlah": "Frekuensi"},
                    color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
                )
                fig_wf_p.update_layout(height=420, yaxis=dict(autorange="reversed"), showlegend=False)
                st.plotly_chart(fig_wf_p, width="stretch")

        st.markdown("**Daftar berita \u2014 dampak ini**")
        if len(bk_f_pilar):
            kepmen_by_url_p = (
                bk_f_pilar.groupby("url")["topik_kepmen"]
                .apply(lambda s: ", ".join(sorted(set(s)))).to_dict()
            )
        else:
            kepmen_by_url_p = {}
        if len(bs_f_pilar):
            sdg_by_url_p = (
                bs_f_pilar.groupby("url")["sdg"]
                .apply(lambda s: ", ".join(f"SDG {x}" for x in sorted(set(s)))).to_dict()
            )
        else:
            sdg_by_url_p = {}
        df_p = selected_news.copy()
        df_p["Tema Kepmen"] = df_p["url"].map(kepmen_by_url_p).fillna("\u2014")
        df_p["SDG"] = df_p["url"].map(sdg_by_url_p).fillna("\u2014")
        df_p = df_p.sort_values("tanggal", ascending=False)
        if len(df_p):
            tampil_p = df_p[["tanggal", "judul", "Tema Kepmen", "SDG", "sumber"]].copy()
            tampil_p.columns = ["Tanggal", "Judul", "Tema Kepmen", "SDG", "Sumber"]
            st.dataframe(tampil_p, width="stretch", hide_index=True)
        else:
            st.info("Tidak ada berita untuk dampak ini pada filter saat ini.")

    # --- Tab: Fakultas/Unit Kerja ---
    with next(tab_iter):
        # SENGAJA pakai selected_news_tanpa_filter_unit (bukan selected_news)
        # -- kalau pakai selected_news yang sudah dipersempit filter "Fakultas
        # / Unit Kerja" sendiri, unit yang lagi dipilih di sidebar otomatis
        # jadi bar terpanjang (co-occurrence di dalam subset dirinya sendiri),
        # bukan ranking independen yang adil dibandingkan.
        uk_pilar = uk[uk["url"].isin(set(selected_news_tanpa_filter_unit["url"]))].copy()
        if len(uk_pilar):
            dist_uk = (
                uk_pilar.groupby(["unit_kerja", "kategori"])["url"]
                .nunique().reset_index(name="jumlah")
            )
            dist_uk["nama"] = dist_uk["unit_kerja"].map(lambda k: UNIT_KERJA[k]["nama"])
            dist_uk = dist_uk.sort_values("jumlah")
            fig_uk = px.bar(
                dist_uk, x="jumlah", y="nama", orientation="h", color="kategori",
                title=f"Berita per Fakultas/Unit Kerja — dampak {selected_pilar}",
                labels={"nama": "Fakultas/Unit Kerja", "jumlah": "Jumlah berita",
                        "kategori": "Kategori"},
                color_discrete_map=WARNA_KATEGORI,
            )
            fig_uk.update_layout(
                height=max(340, 28 * len(dist_uk) + 90),
                yaxis=dict(autorange="reversed"),
            )
            hover_keterangan(fig_uk, "Berita unik dampak ini yang menyebut nama unit ini.")
            st.plotly_chart(fig_uk, width="stretch")

            n_unit_unik = uk_pilar["unit_kerja"].nunique()
            st.metric("Unit teridentifikasi", f"{n_unit_unik} / {len(UNIT_KERJA)}")
        else:
            st.info("Tidak ada fakultas/unit kerja teridentifikasi untuk dampak ini pada filter saat ini.")

        with st.expander("Berita tanpa unit teridentifikasi (cek manual)"):
            # Sama seperti chart di atas -- basis-nya selected_news_tanpa_filter_unit,
            # bukan selected_news, supaya daftar ini tidak selalu kosong begitu
            # saja saat filter "Fakultas / Unit Kerja" aktif (semua berita di
            # selected_news pasti sudah punya unit kalau filter itu aktif).
            tagged_uk = set(uk_pilar["url"]) if len(uk_pilar) else set()
            belum_uk = selected_news_tanpa_filter_unit[
                ~selected_news_tanpa_filter_unit["url"].isin(tagged_uk)
            ]
            st.write(f"{len(belum_uk)} berita (dampak ini, dalam filter tahun/tema/sumber -- "
                     "TIDAK termasuk filter Fakultas/Unit Kerja) tidak menyebut "
                     "fakultas/unit kerja mana pun.")
            if len(belum_uk):
                st.dataframe(
                    belum_uk[["tanggal", "judul", "url"]].sort_values("tanggal", ascending=False).head(200),
                    width="stretch", hide_index=True,
                )

        penjelasan(
            "Hasil keyword matching nama resmi 44 fakultas/sekolah/unit kerja UGM pada "
            "judul + deskripsi berita -- bersifat lower-bound (banyak berita tidak "
            "eksplisit menyebut nama unit meski relevan), bukan angka final jumlah "
            "kontribusi tiap unit. Chart & metrik di tab ini SENGAJA mengabaikan filter "
            "\"Fakultas / Unit Kerja\" di sidebar (filter tahun/tema/sumber/pilar tetap "
            "berlaku) supaya rankingnya tetap adil dibandingkan antar unit -- kalau ikut "
            "filter itu, unit yang sedang dipilih akan selalu tampak sebagai bar "
            "terpanjang secara semu."
        )

    st.markdown("---")

with st.expander("📂 Analisis Lintas-Dampak (Lanjutan)", expanded=False):
    st.subheader("Ringkasan")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total berita (filter)", len(b))
    c2.metric("Berita bertema dampak", t["url"].nunique() if len(t) else 0)
    c3.metric("Tema terpilih", len(topik_pilih))
    c4.metric("Rentang tahun", f"{tahun_awal}–{tahun_akhir}")

    # ---------- Peta Kepmen & SDGs ----------
    st.subheader("Peta Tema Resmi Kepmen & Klaster SDGs")
    st.caption(
        "Pemetaan Kepmendikti Saintek 361/M/KEP/2025 (UGM Analytics.xlsx — "
        "sheet 'Konten UGM Berdampak' & '#Ref'): 14 tema resmi dampak "
        "dipetakan ke Tema Resmi Kepmen, dampak "
        "Sosial/Ekonomi/Lingkungan, dan klaster SDGs. Filter dampak di sidebar "
        "berlaku untuk grafik di bawah."
    )

    if len(bk_f):
        # Sinkron 14 tema: reindex per tema dulu (0 utk tak ada match), lalu
        # petakan ke nama resmi + pilar dari TOPIK_KEPMEN_ALL.
        dist_k_t = (
            bk_f.groupby("topik")["url"]
            .nunique()
            .reset_index(name="jumlah")
            .set_index("topik")
            .reindex(TOPIK_TAMPIL, fill_value=0)
            .reset_index()
        )
        dist_k_t["dampak"] = dist_k_t["topik"].map(
            lambda k: TOPIK_KEPMEN_ALL[k]["dampak"]
        )
        dist_k_t["topik_kepmen"] = dist_k_t["topik"].map(
            lambda k: TOPIK_KEPMEN_ALL[k]["topik_kepmen"]
        )
        dist_k = (
            dist_k_t.groupby(["dampak", "topik_kepmen"])["jumlah"]
            .sum()
            .reset_index()
            .sort_values("jumlah")
        )
        fig_k = px.bar(
            dist_k, x="jumlah", y="topik_kepmen", color="dampak", orientation="h",
            title="Jumlah berita per Tema Resmi Kepmen (berdasarkan dampak)",
            labels={"topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita",
                    "dampak": "Dampak"},
            color_discrete_map={"Lingkungan": "#2e7d32", "Ekonomi": "#1565c0",
                                "Sosial": "#e65100"},
        )
        fig_k.update_layout(height=380, yaxis=dict(autorange="reversed"))
        hover_keterangan(
            fig_k,
            "Total berita unik yang masuk Tema Resmi Kepmen ini "
            "(dijumlahkan dari tema dampak yang memetakan ke sini).",
        )
        st.plotly_chart(fig_k, width="stretch")
        penjelasan(
            "Distribusi berita ke Tema Resmi Kepmen 361/M/KEP/2025, diwarnai "
            "per dampak. Angka = berita unik dari tema dampak yang dipetakan ke "
            "Tema Resmi ini (pemetaan resmi dari UGM Analytics.xlsx); beberapa "
            "tema dampak bisa memetakan ke Tema Resmi yang sama, jumlahnya "
            "digabung."
        )
    else:
        st.info("Tidak ada data Kepmen untuk filter ini.")

    if mode != "Berdampak" and len(bs_f):
        dist_s = (
            bs_f.groupby("sdg")["url"]
            .nunique()
            .reset_index(name="jumlah")
            .sort_values("jumlah")
        )
        # Label sumbu pendek 'SDG n' biar tidak bertabrakan; nama lengkap di hover.
        dist_s["label"] = dist_s["sdg"].map(lambda s: f"SDG {s}")
        dist_s["nama"] = dist_s["sdg"].apply(sdg_label)
        fig_s = px.bar(
            dist_s, x="label", y="jumlah", color="sdg",
            title="Jumlah berita per SDG (klaster resmi)",
            labels={"label": "SDG", "jumlah": "Jumlah berita"},
            hover_data={"nama": True, "sdg": False, "label": False},
        )
        fig_s.update_layout(height=420, showlegend=False,
                            xaxis=dict(tickangle=-45, tickfont=dict(size=10),
                                       automargin=True))
        hover_keterangan(
            fig_s,
            "Berita unik pada klaster SDG ini; satu berita bisa dihitung di beberapa SDG.",
        )
        st.plotly_chart(fig_s, width="stretch")
        penjelasan(
            "SDG mana yang paling banyak disentuh konten berita bertema. "
            "Angka = berita unik bertema yang temanya memetakan ke klaster SDG "
            "ini (klaster resmi per tema, bukan keyword SDG langsung)."
        )

        # Heatmap tema dampak x SDG
        st.markdown("**Heatmap Tema Dampak × SDG**")
        hm = (
            bs_f.merge(bk_f[["url", "topik"]], on="url", how="left")
            .drop_duplicates(subset=["url", "topik", "sdg"])
        )
        if len(hm):
            hm_piv = (
                hm.pivot_table(index="topik", columns="sdg", values="url",
                               aggfunc="nunique", fill_value=0)
                .reindex(index=TOPIK_TAMPIL, fill_value=0)
            )
            hm_piv2 = hm_piv.copy()
            # index/columns jadi string -> sumbu kategori menampilkan semua label
            hm_piv2.index = [LABEL_TOPIC.get(i, i) for i in hm_piv.index]
            hm_piv2.columns = [f"SDG {c}" for c in hm_piv.columns]
            fig_hm = px.imshow(
                hm_piv2, text_auto=True, aspect="auto",
                title="Berita per kombinasi tema dampak × SDG",
                labels={"x": "SDG", "y": "Tema dampak", "color": "Berita"},
                color_continuous_scale="blues",
            )
            fig_hm.update_xaxes(tickangle=-45, tickfont=dict(size=10),
                                automargin=True)
            fig_hm.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_hm.update_traces(textfont=dict(size=8))
            fig_hm.update_layout(height=400)
            hover_keterangan(fig_hm, "Berita unik yang masuk tema baris sekaligus SDG kolom.")
            st.plotly_chart(fig_hm, width="stretch")
            penjelasan(
                "Kombinasi tema dampak × SDG: sel = jumlah berita unik yang "
                "masuk keduanya; sel kosong (0) = tidak ada berita pada "
                "kombinasi itu. Baris gelap = tema tersebar di banyak SDG; "
                "kolom gelap = SDG yang paling sering tersentuh."
            )

        # Tren SDG per tahun
        st.markdown("**Tren SDG per Tahun**")
        sdg_tahun = (
            bs_f.merge(b[["url", "tahun"]], on="url", how="left")
            .drop_duplicates(subset=["url", "sdg", "tahun"])
            .groupby(["tahun", "sdg"])
            .size()
            .reset_index(name="jumlah")
        )
        if len(sdg_tahun):
            sdg_tahun["label"] = sdg_tahun["sdg"].apply(lambda s: f"SDG {s}")
            fig_st = px.line(
                sdg_tahun, x="tahun", y="jumlah", color="label", markers=True,
                title="Jumlah berita per SDG per tahun",
                labels={"tahun": "Tahun", "jumlah": "Jumlah berita", "label": "SDG"},
            )
            fig_st.update_layout(height=420)
            hover_keterangan(fig_st, "Berita unik bertanda SDG ini pada tahun tsb.")
            st.plotly_chart(fig_st, width="stretch")
            penjelasan(
                "Perkembangan tiap SDG antar tahun: angka = berita unik bertema "
                "yang SDG-nya tercatat pada tahun publikasi tsb; garis naik = "
                "perhatian terhadap SDG makin sering diberitakan."
            )

        # Heatmap pilar x tahun (dari tema Kepmen)
        st.markdown("**Heatmap Dampak × Tahun**")
        bk_tahun = (
            bk_f.merge(b[["url", "tahun"]], on="url", how="left")
            .drop_duplicates(subset=["url", "topik", "tahun"])
        )
        pilar_tahun = (
            bk_tahun.groupby(["dampak", "tahun"])["url"]
            .nunique()
            .reset_index(name="jumlah")
        )
        if len(pilar_tahun):
            piv_p = pilar_tahun.pivot_table(
                index="dampak", columns="tahun", values="jumlah", fill_value=0
            )
            fig_p = px.imshow(
                piv_p, text_auto=True, aspect="auto",
                title="Jumlah berita per dampak per tahun (14 tema Kepmen)",
                labels={"x": "Tahun", "y": "Dampak", "color": "Berita"},
                color_continuous_scale="oranges",
            )
            fig_p.update_xaxes(tickangle=-45, tickfont=dict(size=10),
                               automargin=True)
            fig_p.update_traces(textfont=dict(size=8))
            fig_p.update_layout(height=320)
            hover_keterangan(fig_p, "Berita unik pada dampak ini di tahun tsb.")
            st.plotly_chart(fig_p, width="stretch")
            penjelasan(
                "Dominasi dampak Sosial/Ekonomi/Lingkungan per tahun. Angka = "
                "berita unik dari semua tema yang memetakan ke dampak itu pada "
                "tahun tsb (dari 14 tema resmi Kepmen)."
            )

    st.markdown("**Ringkasan per dampak (Sosial/Ekonomi/Lingkungan)**")
    with st.container(border=True):
        rp_f = rp[rp["dampak"].isin(pilar_pilih)] if pilar_pilih else rp
        if len(rp_f):
            c = rp_f.set_index("dampak")["jumlah_berita"].to_dict()
            cols = st.columns(3)
            for i, p in enumerate(["Lingkungan", "Ekonomi", "Sosial"]):
                if p in pilar_pilih or not pilar_pilih:
                    cols[i].metric(p, c.get(p, 0))
            fig_rp = px.bar(
                rp_f, x="dampak", y="jumlah_berita", color="dampak",
                title="Berita unik per dampak (semua tema Kepmen)",
                labels={"dampak": "Dampak", "jumlah_berita": "Jumlah berita"},
                color_discrete_map=WARNA_PILAR,
            )
            fig_rp.update_layout(height=320, showlegend=False)
            hover_keterangan(fig_rp, "Berita unik di semua tema dalam dampak ini.")
            st.plotly_chart(fig_rp, width="stretch")
            penjelasan(
                "Total berita unik per dampak (semua tema dalam dampak "
                "digabung, URL dideduplikasi per dampak)."
            )
        else:
            st.info("Tidak ada data dampak untuk filter ini.")

    st.markdown("**Lihat tabel pemetaan resmi + indikator Kepmen (14 tema)**")
    with st.container(border=True):
        map_rows = []
        for topik_id, meta in TOPIK_KEPMEN_ALL.items():
            map_rows.append(
                {
                    "Tema dampak berita": LABEL_TOPIC.get(topik_id, topik_id),
                    "Dampak": meta["dampak"],
                    "Tema Resmi Kepmen": meta["topik_kepmen"],
                    "Klaster SDGs": ", ".join(sdg_label(s) for s in meta["sdg"]) or "—",
                    "Indikator Kepmen": meta["indikator"],
                    "Definisi": meta["definisi"],
                    "Kriteria": meta["kriteria"],
                    "Formula": meta["formula"],
                    "Satuan": meta["satuan"],
                }
            )
        st.dataframe(pd.DataFrame(map_rows), width="stretch", hide_index=True)
        st.caption(
            "14 tema resmi Kepmen 361/M/KEP/2025 (klaster SDG dari sheet '#Ref' "
            "UGM Analytics.xlsx). Definisi & "
            "kriteria dari Salinan Kepmen 361/M/KEP/2025 (OCR)."
        )

    # ---------- Heatmap tema x tahun ----------
    st.subheader("Heatmap Tema × Tahun")
    piv = (
        b_t.pivot_table(index="topik", columns="tahun", values="url",
                        aggfunc="nunique", fill_value=0)
        .reindex(index=TOPIK_TAMPIL, fill_value=0)
    )
    if len(piv):
        piv2 = piv.copy()
        piv2.index = [LABEL_TOPIC.get(i, i) for i in piv.index]
        fig_h = px.imshow(
            piv2, text_auto=True, aspect="auto",
            title="Jumlah berita per tema per tahun",
            labels={"x": "Tahun", "y": "Tema", "color": "Berita"},
            color_continuous_scale="greens",
        )
        fig_h.update_xaxes(tickangle=-45, tickfont=dict(size=10),
                           automargin=True)
        fig_h.update_yaxes(tickfont=dict(size=11), automargin=True)
        fig_h.update_traces(textfont=dict(size=8))
        fig_h.update_layout(height=380)
        hover_keterangan(fig_h, "Berita unik tema ini pada tahun tsb.")
        st.plotly_chart(fig_h, width="stretch")
        penjelasan(
            "Kapan tiap tema ramai diberitakan: sel = jumlah berita unik per "
            "tema per tahun publikasi. Baris gelap = tema yang konsisten "
            "diberitakan; kolom gelap = tahun dengan banyak aktivitas dampak."
        )
    else:
        st.info("Tidak cukup data untuk heatmap.")

    # ---------- Tren tahunan ----------
    st.subheader("Tren Tahunan per Tema")
    tren = b_t.groupby(["topik", "tahun"]).size().reset_index(name="jumlah")
    tren["label"] = tren["topik"].map(LABEL_TOPIC)
    fig2 = px.line(
        tren, x="tahun", y="jumlah", color="label", markers=True,
        title="Jumlah berita per tahun",
        labels={"tahun": "Tahun", "jumlah": "Jumlah berita", "label": "Tema"},
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig2.update_layout(height=420)
    hover_keterangan(
        fig2,
        "Jumlah berita pada tahun tsb (per tema; berita multi-tema masuk di tiap tema).",
    )
    st.plotly_chart(fig2, width="stretch")
    penjelasan(
        "Perbandingan pertumbuhan antar tema per tahun. Angka = jumlah berita "
        "per tema-tahun; berita yang masuk beberapa tema dihitung di tiap tema."
    )

    # ---------- Tren bulanan ----------
    st.subheader("Tren Bulanan (musiman)")
    b_t["bulan"] = b_t["tanggal"].str[5:7]
    musim = b_t.groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
    musim["label"] = musim["topik"].map(LABEL_TOPIC)
    fig3 = px.bar(
        musim, x="bulan", y="jumlah", color="label", barmode="stack",
        title="Jumlah berita per bulan kalender (semua tahun digabung)",
        labels={"bulan": "Bulan", "jumlah": "Jumlah berita", "label": "Tema"},
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig3.update_layout(height=400)
    hover_keterangan(fig3, "Jumlah berita pada bulan tsb, semua tahun digabung.")
    st.plotly_chart(fig3, width="stretch")
    penjelasan(
        "Pola musiman: bulan kalender mana yang paling banyak memuat berita "
        "dampak (semua tahun digabung, ditumpuk per tema). Bulan 01-12 = "
        "Januari-Desember."
    )

    # ---------- Cakupan vs total berita UGM ----------
    st.subheader("Cakupan vs Total Berita UGM per Tahun")
    sitemap["tahun"] = sitemap["lastmod"].str[:4]
    tot = sitemap.groupby("tahun").size().reset_index(name="total")
    cakup = b_t.groupby("tahun").size().reset_index(name="bertopik")
    gab = tot.merge(cakup, on="tahun", how="left").fillna(0)
    gab = gab[gab["tahun"].between(tahun_awal, tahun_akhir)]
    fig4 = go.Figure()
    fig4.add_bar(x=gab["tahun"], y=gab["total"], name="Total berita (sitemap)",
                 marker_color="rgba(150,150,150,0.35)")
    fig4.add_scatter(x=gab["tahun"], y=gab["bertopik"], name="Berita bertema dampak",
                     mode="lines+markers", marker_color="#2e7d32", line=dict(width=3))
    fig4.update_layout(
        title="Volume berita UGM vs berita yang terdeteksi tema dampak",
        xaxis_title="Tahun", yaxis_title="Jumlah berita", height=420,
        barmode="overlay",
    )
    hover_keterangan(
        fig4,
        "Abu-abu: seluruh URL sitemap (baseline); hijau: berita yang match tema dampak.",
    )
    st.plotly_chart(fig4, width="stretch")
    st.caption(
        "Tujuan: membandingkan volume konten UGM dengan berita yang "
        "terdeteksi sebagai aktivitas dampak. "
        "Garis abu-abu = seluruh URL di sitemap ugm.ac.id per tahun (baseline). "
        "Garis hijau = berita yang match tema dampak. Proporsi menggambarkan "
        "seberapa besar konten UGM yang tercatat sebagai aktivitas dampak; "
        "nilainya lower-bound karena pencocokan keyword terbatas pada 14 tema "
        "Kepmen yang dideteksi."
    )

    # ---------- Breakdown keyword ----------
    st.subheader("Keyword yang Memicu Match per Tema")
    rows = []
    for topik_name, kws in KEYWORDS_ALL.items():
        if topik_name not in topik_pilih:
            continue
        urls_topik = set(b_t.loc[b_t["topik"] == topik_name, "url"])
        sub = b[b["url"].isin(urls_topik)]
        teks = (sub["judul"].fillna("") + " " + sub["deskripsi"].fillna("")).str.lower()
        for kw in kws:
            n = teks.str.contains(re.escape(kw), regex=True).sum()
            if n:
                rows.append({"topik": topik_name, "keyword": kw, "jumlah": int(n)})
    if rows:
        kw_df = pd.DataFrame(rows)
        kw_df["label"] = kw_df["topik"].map(LABEL_TOPIC)
        # Select per tema biar label keyword tidak menumpuk jadi kecil.
        # Semua 14 tema tampil (TOPIK_TAMPIL — ikut filter sidebar); tema tanpa
        # match keyword menampilkan info kosong, bukan hilang dari dropdown.
        topik_ada = sorted(
            TOPIK_TAMPIL,
            key=lambda k: (TOPIK_KEPMEN_ALL[k]["dampak"], LABEL_TOPIC.get(k, k)),
        )

        def tema_kw_label(k: str) -> str:
            return f"{TOPIK_KEPMEN_ALL[k]['dampak']} - {LABEL_TOPIC.get(k, k)}"

        pilih_kw = st.selectbox(
            "Pilih tema (keyword)",
            options=topik_ada,
            format_func=tema_kw_label,
        )
        sub_kw = kw_df[kw_df["topik"] == pilih_kw].sort_values("jumlah")
        n_kw = len(sub_kw)
        if n_kw:
            fig5 = px.bar(
                sub_kw, x="jumlah", y="keyword", orientation="h",
                title=f"Jumlah berita yang match tiap keyword — {tema_kw_label(pilih_kw)}",
                labels={"keyword": "Keyword", "jumlah": "Jumlah berita"},
                color_discrete_sequence=["#2e7d32"],
            )
            fig5.update_layout(
                height=max(320, 34 * n_kw + 80),
                yaxis=dict(autorange="reversed"),
                showlegend=False,
            )
            hover_keterangan(fig5, "Jumlah berita yang teksnya mengandung keyword ini.")
            st.plotly_chart(fig5, width="stretch")
            penjelasan(
                "Audit keyword: keyword mana yang paling banyak memicu match "
                "pada tema terpilih. Angka = berita yang judul/deskripsinya "
                "mengandung keyword tsb; satu berita bisa match beberapa "
                "keyword, jadi totalnya bisa melebihi jumlah berita tema."
            )
        else:
            st.info("Tidak ada match keyword untuk tema ini.")
    else:
        st.info("Tidak ada match keyword pada filter ini.")

    # ---------- Multi-tema ----------
    st.subheader("Berita Multi-Tema")
    cnt = b_t.groupby("url").size().reset_index(name="n_topik")
    dist_n = cnt["n_topik"].value_counts().sort_index().reset_index()
    dist_n.columns = ["jumlah tema", "berita"]
    fig6 = px.bar(
        dist_n, x="jumlah tema", y="berita",
        title="Berapa banyak tema per berita",
        labels={"jumlah tema": "Jumlah tema", "berita": "Jumlah berita"},
    )
    fig6.update_layout(height=350)
    hover_keterangan(fig6, "Jumlah berita yang masuk N tema sekaligus.")
    st.plotly_chart(fig6, width="stretch")
    penjelasan(
        "Sebaran kompleksitas: berapa banyak berita yang masuk 1 tema, 2 tema, "
        "dst. Bar paling kiri = berita yang hanya masuk satu tema; semakin ke "
        "kanan, semakin lintas-tema berita tersebut."
    )
    multi = cnt[cnt["n_topik"] > 1]
    if len(multi):
        kombo = (
            b_t[b_t["url"].isin(set(multi["url"]))]
            .groupby("url")["topik"]
            .apply(lambda s: ", ".join(sorted(s)))
            .reset_index(name="kombinasi")
        )
        kombo["jumlah"] = kombo["url"].map(cnt.set_index("url")["n_topik"])
        st.dataframe(kombo[["kombinasi", "jumlah"]], width="stretch", hide_index=True)
    else:
        st.caption("Tidak ada berita multi-tema pada filter ini.")

    # ---------- Word frequency ----------
    st.subheader("Kata yang Paling Sering Muncul per Tema")
    topik_wf = st.selectbox(
        "Pilih tema",
        options=[k for k in LABEL_TOPIC if k in t["topik"].unique()],
        format_func=lambda k: LABEL_TOPIC[k],
    )
    urls_wf = set(t.loc[t["topik"] == topik_wf, "url"])
    freq = token_freq(b[b["url"].isin(urls_wf)])
    freq_df = pd.DataFrame(freq.most_common(15), columns=["kata", "jumlah"])
    fig7 = px.bar(
        freq_df, x="jumlah", y="kata", orientation="h",
        title=f"15 kata teratas — {LABEL_TOPIC[topik_wf]}",
        labels={"kata": "Kata", "jumlah": "Frekuensi"},
        color_discrete_sequence=["#2e7d32"],
    )
    fig7.update_layout(height=450, yaxis=dict(autorange="reversed"), showlegend=False)
    hover_keterangan(fig7, "Frekuensi kata ini muncul di judul+deskripsi berita tema tsb.")
    st.plotly_chart(fig7, width="stretch")
    penjelasan(
        "Gambaran topik yang dibicarakan pada tema terpilih: 15 kata teratas "
        "di judul + deskripsi berita tema tsb (stopword dibuang). Kata umum "
        "seperti 'ugm'/'universitas' sengaja dibuang."
    )

    # ---------- Drill-down ----------
    st.subheader("Daftar Berita")
    # Tema Kepmen per url (gabung nama resmi)
    if len(bk_f):
        kepmen_by_url = (
            bk_f.groupby("url")["topik_kepmen"]
            .apply(lambda s: ", ".join(sorted(set(s))))
            .to_dict()
        )
        # Indikator Kepmen per url (gabung nama indikator resmi)
        bk_f = bk_f.copy()
        bk_f["indikator_kepmen"] = bk_f["topik"].map(
            lambda t: TOPIK_KEPMEN_ALL[t]["indikator"]
        )
        indikator_by_url = (
            bk_f.groupby("url")["indikator_kepmen"]
            .apply(lambda s: ", ".join(sorted(set(s))))
            .to_dict()
        )
    else:
        kepmen_by_url = {}
        indikator_by_url = {}
    # SDG per url
    if len(bs_f):
        sdg_by_url = (
            bs_f.groupby("url")["sdg"]
            .apply(lambda s: ", ".join(f"SDG {x}" for x in sorted(set(s))))
            .to_dict()
        )
    else:
        sdg_by_url = {}

    df = b.copy()
    df["Tema Kepmen"] = df["url"].map(kepmen_by_url).fillna("—")
    df["Indikator Kepmen"] = df["url"].map(indikator_by_url).fillna("—")
    df["SDG"] = df["url"].map(sdg_by_url).fillna("—")
    df = df.sort_values("tanggal", ascending=False)

    if len(df):
        tampil = df[["tanggal", "judul", "Tema Kepmen",
                     "Indikator Kepmen", "SDG", "sumber"]].copy()
        tampil.columns = ["Tanggal", "Judul", "Tema Kepmen",
                          "Indikator Kepmen", "SDG", "Sumber"]
        tampil["Tautan"] = df["url"].apply(lambda u: f"[buka]({u})")
        st.dataframe(tampil, width="stretch", hide_index=True)
    else:
        st.info("Tidak ada berita untuk filter ini.")

    # ---------- Cek manual ----------
    st.markdown("**Berita tanpa match tema (cek manual)**")
    with st.container(border=True):
        tagged = set(t["url"])
        belum = b[~b["url"].isin(tagged)]
        st.write(f"{len(belum)} berita (dalam filter) tidak masuk tema mana pun.")
        if len(belum):
            st.dataframe(
                belum[["tanggal", "judul", "url"]].sort_values("tanggal", ascending=False),
                width="stretch", hide_index=True,
            )
