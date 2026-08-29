"""Dashboard Streamlit analisis dampak berita UGM.

Sumber: MySQL ugm_analytics (tabel berita_berita, berita_berita_topik,
berita_ringkasan_topik_tahun, berita_sitemap, dst. — prefix "berita_" hasil
migrasi dari data/ugm_news.duckdb, lihat migrasi_ke_mysql.py).
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


def generate_impact_insight(
    df: pd.DataFrame,
    pilar: str,
    tahun_awal: str,
    tahun_akhir: str,
    selected_t: pd.DataFrame,
    mode: str,
    sdg_df: pd.DataFrame | None = None,
) -> str:
    """Narasi dinamis pilar -- dihitung ulang tiap render dari data ter-filter.

    Bukan animasi: tiap dashboard dimuat ulang (mis. setelah update berita
    mingguan menambah data baru), angka & kalimat di sini otomatis mengikuti.
    """
    if df.empty:
        return f"Belum ada data untuk pilar {pilar} pada rentang {tahun_awal}–{tahun_akhir}."

    total_berita = int(df["url"].nunique())
    tahun_df = df.groupby("tahun")["url"].nunique().reset_index(name="jumlah")
    if len(tahun_df) > 1:
        awal = int(tahun_df.iloc[0]["jumlah"])
        akhir = int(tahun_df.iloc[-1]["jumlah"])
        y_awal, y_akhir = tahun_df.iloc[0]["tahun"], tahun_df.iloc[-1]["tahun"]
        if awal >= 5:
            # Persentase hanya bermakna kalau basis awalnya cukup besar --
            # basis <5 berita bisa menghasilkan persentase ratusan/ribuan % yang menyesatkan.
            delta = (akhir - awal) / awal * 100
            trend_text = f"dengan tren {akhir - awal:+d} berita dari {y_awal} ke {y_akhir} ({delta:+.1f}%)"
        elif akhir != awal:
            trend_text = f"meningkat dari {awal} menjadi {akhir} berita antara {y_awal} dan {y_akhir}" if akhir > awal else f"menurun dari {awal} menjadi {akhir} berita antara {y_awal} dan {y_akhir}"
        else:
            trend_text = f"dengan konsistensi {akhir} berita antara {y_awal} dan {y_akhir}"
    else:
        trend_text = "dengan konsistensi volume yang stabil di rentang waktu tersebut"

    tema_df = (
        selected_t.groupby("topik")["url"].nunique().reset_index(name="jumlah")
        .sort_values("jumlah", ascending=False)
    )
    if not tema_df.empty:
        topik_teratas = tema_df.iloc[0]["topik"]
        tema_jumlah = int(tema_df.iloc[0]["jumlah"])
        label_teratas = LABEL_TOPIC.get(topik_teratas, topik_teratas)
        meta_teratas = TOPIK_KEPMEN_ALL.get(topik_teratas, {})
        nama_resmi = meta_teratas.get("topik_kepmen", label_teratas)
        indikator_resmi = meta_teratas.get("indikator", "")
        tema_display = f"{nama_resmi} ({label_teratas})" if nama_resmi != label_teratas else label_teratas
    else:
        tema_display, tema_jumlah, indikator_resmi = "tema utama", 0, ""

    indikator_text = (
        f" Tema ini searah dengan indikator resmi Kepmen 361/M/KEP/2025: “{indikator_resmi}”."
        if indikator_resmi else ""
    )

    total_tema_pilar = sum(1 for v in TOPIK_KEPMEN_ALL.values() if v["dampak"] == pilar)
    tema_aktif = selected_t["topik"].nunique() if len(selected_t) else 0
    cakupan_text = (
        f"Dari {total_tema_pilar} tema resmi Kepmen pada pilar ini, {tema_aktif} di antaranya "
        f"sudah terekam aktivitasnya dalam pemberitaan."
    )

    sdg_text = ""
    if mode != "Berdampak" and sdg_df is not None and len(sdg_df):
        n_sdg = sdg_df["sdg"].nunique()
        top_sdg = int(sdg_df.groupby("sdg")["url"].nunique().sort_values(ascending=False).index[0])
        sdg_text = (
            f" Aktivitas pada pilar ini turut menyentuh {n_sdg} klaster SDG, dengan {sdg_label(top_sdg)} "
            f"sebagai yang paling banyak disentuh."
        )

    pilar_intro = {
        "Ekonomi": "kinerja program, kolaborasi riset, serta penguatan ekosistem ekonomi berbasis inovasi",
        "Sosial": "peningkatan akses, kesejahteraan, edukasi, dan pemberdayaan masyarakat",
        "Lingkungan": "pengelolaan lingkungan, keberlanjutan, dan adaptasi ekosistem alam",
    }[pilar]
    lead = {
        "Ekonomi": "UGM menunjukkan kinerja ekonomi yang konsisten dan terukur",
        "Sosial": "UGM memperlihatkan kontribusi sosial yang luas dan berdampak nyata",
        "Lingkungan": "UGM menegaskan komitmen lingkungan yang kuat dalam agenda keberlanjutan",
    }[pilar]
    penutup = {
        "Ekonomi": "UGM berfungsi sebagai enabler bagi penguatan kewirausahaan, hilirisasi riset, "
                   "dan kolaborasi ekonomi berbasis inovasi kampus",
        "Sosial": "UGM berfungsi sebagai enabler pemberdayaan masyarakat dan perluasan akses "
                  "pendidikan yang inklusif",
        "Lingkungan": "UGM berfungsi sebagai enabler transisi menuju kampus dan masyarakat yang "
                      "berkelanjutan",
    }[pilar]

    return (
        f"{lead} pada pilar {pilar}. Dalam rentang {tahun_awal}–{tahun_akhir}, terdapat {total_berita:,} berita unik yang mencerminkan "
        f"{pilar_intro}. {tema_display} menjadi tema paling dominan dengan {tema_jumlah:,} berita, {trend_text}.{indikator_text} "
        f"{cakupan_text}{sdg_text} Kondisi ini menunjukkan bahwa fokus narasi media dan program akademik UGM secara konsisten "
        f"bergerak pada isu yang memberi dampak nyata, di mana {penutup}."
    )


def generate_executive_summary(
    b: pd.DataFrame,
    t: pd.DataFrame,
    bs_f: pd.DataFrame,
    mode: str,
    tahun_awal: str,
    tahun_akhir: str,
) -> dict:
    """Ringkasan naratif lintas-pilar untuk bagian paling atas dashboard.

    Sama seperti generate_impact_insight: dihitung ulang dari data ter-filter
    saat render, jadi otomatis ter-update begitu ada berita baru masuk.
    """
    bt = b.merge(t, on="url", how="inner")
    total_berita = int(bt["url"].nunique())
    if total_berita == 0:
        return {
            "total_berita": 0,
            "pilar_top": "-",
            "pilar_top_naik": 0,
            "pilar_top_pct": None,
            "topik_top_label": "-",
            "berita_tahun_ini": 0,
            "narasi": f"Belum ada data pada rentang {tahun_awal}–{tahun_akhir} untuk filter ini.",
        }

    # Pilar "pertumbuhan tertinggi" dipilih dari kenaikan ABSOLUT (bukan %) --
    # basis awal yang sangat kecil (mis. 2 berita) bisa membuat persentase
    # meledak jadi ribuan % dan menyesatkan pembaca laporan. Persentase cuma
    # ditampilkan kalau basis awalnya cukup besar (>=5) supaya bermakna.
    pilar_tahun = bt.groupby(["dampak", "tahun"])["url"].nunique().reset_index(name="jumlah")
    pilar_top, pilar_top_naik, pilar_top_pct = "-", None, None
    for pilar in ["Lingkungan", "Ekonomi", "Sosial"]:
        sub = pilar_tahun[pilar_tahun["dampak"] == pilar].sort_values("tahun")
        if len(sub) > 1:
            awal, akhir = int(sub.iloc[0]["jumlah"]), int(sub.iloc[-1]["jumlah"])
            naik = akhir - awal
            pct = (naik / awal * 100) if awal >= 5 else None
        else:
            naik, pct = 0, None
        if pilar_top_naik is None or naik > pilar_top_naik:
            pilar_top, pilar_top_naik, pilar_top_pct = pilar, naik, pct
    pilar_top_naik = pilar_top_naik or 0

    if mode != "Berdampak" and len(bs_f):
        sdg_counts = bs_f.groupby("sdg")["url"].nunique().sort_values(ascending=False)
        topik_top_label = sdg_label(int(sdg_counts.index[0]))
        topik_top_n = int(sdg_counts.iloc[0])
        topik_kind = "SDG"
    else:
        tema_counts = t.groupby("topik_kepmen")["url"].nunique().sort_values(ascending=False)
        topik_top_label = tema_counts.index[0] if len(tema_counts) else "-"
        topik_top_n = int(tema_counts.iloc[0]) if len(tema_counts) else 0
        topik_kind = "tema resmi Kepmen"

    berita_tahun_ini = int(bt[bt["tahun"] == tahun_akhir]["url"].nunique())
    if pilar_top_pct is not None:
        delta_text = f"tumbuh {pilar_top_pct:+.1f}% ({pilar_top_naik:+d} berita) dari {tahun_awal} ke {tahun_akhir}"
    elif pilar_top_naik:
        delta_text = f"bertambah {pilar_top_naik} berita dari {tahun_awal} ke {tahun_akhir}"
    else:
        delta_text = "menunjukkan volume pemberitaan yang stabil"

    narasi = (
        f"Sepanjang {tahun_awal}–{tahun_akhir}, UGM mencatat {total_berita:,} berita dampak yang tersebar di tiga pilar "
        f"Lingkungan, Ekonomi, dan Sosial. Pilar {pilar_top} mencatat pertumbuhan tercepat, {delta_text}. "
        f"Pada sisi capaian resmi, {topik_top_label} menjadi {topik_kind} yang paling banyak disentuh dengan {topik_top_n:,} berita. "
        f"Di tahun terbaru pada rentang ini ({tahun_akhir}), tercatat {berita_tahun_ini:,} berita dampak — mencerminkan "
        f"konsistensi UGM menjalankan tridarma yang memberi dampak nyata bagi masyarakat, ekonomi, dan lingkungan."
    )

    return {
        "total_berita": total_berita,
        "pilar_top": pilar_top,
        "pilar_top_naik": pilar_top_naik,
        "pilar_top_pct": pilar_top_pct,
        "topik_top_label": topik_top_label,
        "berita_tahun_ini": berita_tahun_ini,
        "narasi": narasi,
    }


st.set_page_config(page_title="Analisis Dampak Berita UGM", layout="wide")
st.title("Analisis Dampak Berita UGM")
st.caption("Sumber: berita ugm.ac.id (RSS + sitemap) — MySQL ugm_analytics")


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
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=300)
def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
    return berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt


try:
    berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt = load()
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
    ["Berdampak", "Berdampak × SDGs", "SDGs saja"],
    index=1,
    help="Berdampak: 3 pilar & 14 tema Kepmen (tanpa bagian SDG). "
         "Berdampak × SDGs: tampilan sekarang (tema + SDG dari berita bertema). "
         "SDGs saja: mapping langsung seluruh 32.130 URL berita ke SDG "
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
topik_pilih: list = []
sumber_pilih: list = []
pilar_pilih: list = []
if mode == "SDGs saja":
    # Mode SDG: filter berdasarkan SDG, bukan tema dampak.
    sdg_pilih = st.sidebar.multiselect(
        "SDG (17)",
        options=list(range(1, 18)),
        default=list(range(1, 18)),
        format_func=lambda s: f"SDG {s} — {SDG_NAMA.get(s, s)}",
    )
else:
    sdg_pilih = list(range(1, 18))
    topik_pilih = st.sidebar.multiselect(
        "Tema dampak",
        options=list(LABEL_TOPIC.keys()),
        format_func=lambda k: LABEL_TOPIC[k],
        default=list(LABEL_TOPIC.keys()),
    )
    sumber_pilih = st.sidebar.multiselect(
        "Sumber", options=["sitemap", "rss"], default=["sitemap", "rss"]
    )
    pilar_pilih = st.sidebar.multiselect(
        "Pilar dampak (Kepmen)",
        options=["Lingkungan", "Ekonomi", "Sosial"],
        default=["Lingkungan", "Ekonomi", "Sosial"],
    )

# ---------- Tombol update berita terbaru ----------
# TODO(migrasi MySQL): scripts/update_mingguan.py masih menulis hasil fetch-nya
# ke DuckDB (data/ugm_news.duckdb), belum ke MySQL. Sampai script itu ikut
# dimigrasi supaya menulis ke tabel berprefix "berita_" di MySQL, tombol ini
# dinonaktifkan dulu -- kalau dijalankan sekarang, datanya akan masuk ke file
# DuckDB lama yang sudah tidak dibaca dashboard ini, bukan ke MySQL.
st.sidebar.divider()
st.sidebar.caption(
    "🔧 Update otomatis belum tersedia: script fetch berita masih menulis ke "
    "DuckDB, belum dimigrasi ke MySQL."
)
st.sidebar.button(
    "🔄 Update Berita Terbaru", use_container_width=True, disabled=True,
    help="Nonaktif sementara -- scripts/update_mingguan.py belum dimigrasi ke MySQL.",
)

# ---------- Mode "SDGs saja": mapping langsung seluruh 32.130 URL ke SDG ----------
if mode == "SDGs saja":
    st.subheader("Analisis SDGs — Seluruh Berita UGM (32.130 URL)")
    st.caption(
        "Mapping langsung url berita sitemap ke 17 SDG (tanpa tema dampak Kepmen): "
        "kata-kata slug URL untuk yang belum di-fetch + judul & deskripsi untuk "
        "4.787 yang sudah. Satu berita bisa masuk beberapa SDG. Filter SDG di "
        "sidebar berlaku di sini."
    )
    sitemap["tahun"] = sitemap["lastmod"].str[:4]
    sm = sitemap[sitemap["tahun"].between(tahun_awal, tahun_akhir)].copy()
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
# t = semua tema Kepmen (14 tema resmi) dari tabel gabungan.
# Kalau filter tema/pilar kosong, fallback ke 4 tema inti (tema berita).
t = bk[bk["topik"].isin(topik_pilih)] if topik_pilih else bk
if pilar_pilih:
    t = t[t["dampak"].isin(pilar_pilih)]
if len(b) and len(t):
    t = t[t["url"].isin(set(b["url"]))]

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
if mode != "SDGs saja":
    st.subheader("Ringkasan Eksekutif")
    ringkasan = generate_executive_summary(b, t, bs_f, mode, tahun_awal, tahun_akhir)
    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Total berita dampak", f"{ringkasan['total_berita']:,}")
    _pilar_delta_label = (
        f"{ringkasan['pilar_top_pct']:+.1f}%" if ringkasan["pilar_top_pct"] is not None
        else (f"+{ringkasan['pilar_top_naik']} berita" if ringkasan["pilar_top_naik"] else None)
    )
    rc2.metric("Pilar pertumbuhan tertinggi", ringkasan["pilar_top"], _pilar_delta_label)
    rc3.metric(f"Sorotan {tahun_akhir}", f"{ringkasan['berita_tahun_ini']:,} berita")
    rc4.metric("Paling banyak disentuh", ringkasan["topik_top_label"])
    st.info(ringkasan["narasi"])
    penjelasan(
        "Ringkasan ini dihitung ulang tiap dashboard dimuat dari data ter-filter saat itu \u2014 "
        "otomatis ikut berubah begitu ada berita baru masuk lewat update mingguan, bukan teks statis."
    )

    # ---------- Overview: 3 pilar dampak, klik satu untuk drill-down ----------
    st.subheader("Overview Dampak UGM")
    st.caption("Klik salah satu pilar di bawah untuk melihat detail tema, tren, dan insight otomatis.")
    st.session_state.setdefault("selected_pilar", "Ekonomi")

    pilar_order = ["Lingkungan", "Ekonomi", "Sosial"]
    pilar_cards = st.columns(3)
    for idx, pilar in enumerate(pilar_order):
        pilar_topik = t[t["dampak"] == pilar].copy()
        pilar_urls = set(pilar_topik["url"])
        pilar_news = b[b["url"].isin(pilar_urls)]
        pilar_total = int(pilar_news["url"].nunique())
        tema_terbanyak = (
            pilar_topik.groupby("topik")["url"].nunique().sort_values(ascending=False).head(1)
        )
        top_theme_name = LABEL_TOPIC.get(tema_terbanyak.index[0], tema_terbanyak.index[0]) if not tema_terbanyak.empty else "-"
        with pilar_cards[idx]:
            is_active = st.session_state["selected_pilar"] == pilar
            button_type = "primary" if is_active else "secondary"
            if st.button(
                f"{pilar}\n{pilar_total:,} berita\nTema utama: {top_theme_name}",
                key=f"pilar_{pilar}",
                use_container_width=True,
                type=button_type,
            ):
                st.session_state["selected_pilar"] = pilar

    selected_pilar = st.session_state["selected_pilar"]
    selected_t = t[t["dampak"] == selected_pilar].copy()
    selected_news = b[b["url"].isin(set(selected_t["url"]))].copy()
    selected_news["tahun"] = selected_news["tanggal"].str[:4]
    bk_f_pilar = bk_f[bk_f["dampak"] == selected_pilar].copy()
    bs_f_pilar = bs_f[bs_f["url"].isin(set(bk_f_pilar["url"]))].copy()
    b_t_pilar = b_t[b_t["url"].isin(set(bk_f_pilar["url"]))].copy()
    TOPIK_TAMPIL_PILAR = [k for k in TOPIK_TAMPIL if TOPIK_KEPMEN_ALL[k]["dampak"] == selected_pilar]

    st.markdown("---")
    st.subheader(f"Detail Pilar: {selected_pilar}")

    tab_labels = ["Ringkasan & Insight", "Tema Resmi Kepmen"]
    if mode != "Berdampak":
        tab_labels.append("SDGs Terkait")
    tab_labels += ["Tren & Musiman", "Kata Kunci & Berita"]
    tabs = st.tabs(tab_labels)
    tab_iter = iter(tabs)

    # --- Tab: Ringkasan & Insight ---
    with next(tab_iter):
        st.info(generate_impact_insight(
            selected_news, selected_pilar, tahun_awal, tahun_akhir, selected_t, mode, bs_f_pilar,
        ))

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
            title=f"Distribusi tema dalam pilar {selected_pilar}",
            labels={"label": "Tema", "jumlah": "Jumlah berita"},
            color="label", color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_detail.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig_detail, width="stretch")

        trend_detail = selected_news.groupby("tahun")["url"].nunique().reset_index(name="jumlah")
        fig_trend = px.line(
            trend_detail, x="tahun", y="jumlah", markers=True,
            title=f"Tren berita per tahun untuk pilar {selected_pilar}",
            labels={"tahun": "Tahun", "jumlah": "Jumlah berita"},
        )
        fig_trend.update_layout(height=360)
        st.plotly_chart(fig_trend, width="stretch")

        st.markdown("**Daftar tema dalam pilar ini**")
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
                title=f"Berita per Tema Resmi Kepmen \u2014 pilar {selected_pilar}",
                labels={"topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita"},
                color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
            )
            fig_k_p.update_layout(height=340, showlegend=False)
            hover_keterangan(fig_k_p, "Berita unik yang masuk Tema Resmi Kepmen ini pada pilar terpilih.")
            st.plotly_chart(fig_k_p, width="stretch")
        else:
            st.info("Tidak ada data Kepmen untuk pilar ini pada filter saat ini.")

        st.markdown("**Indikator resmi Kepmen 361/M/KEP/2025 pada pilar ini**")
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
                    title=f"Berita per SDG \u2014 pilar {selected_pilar}",
                    labels={"label": "SDG", "jumlah": "Jumlah berita"},
                    hover_data={"nama": True, "sdg": False, "label": False},
                )
                fig_s_p.update_layout(height=380, showlegend=False,
                                      xaxis=dict(tickangle=-45, tickfont=dict(size=10), automargin=True))
                hover_keterangan(fig_s_p, "Berita unik pilar ini pada klaster SDG tsb.")
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
                        title=f"Tema \u00d7 SDG \u2014 pilar {selected_pilar}",
                        labels={"x": "SDG", "y": "Tema", "color": "Berita"},
                        color_continuous_scale="blues",
                    )
                    fig_hm_p.update_xaxes(tickangle=-45, tickfont=dict(size=10), automargin=True)
                    fig_hm_p.update_yaxes(tickfont=dict(size=11), automargin=True)
                    fig_hm_p.update_traces(textfont=dict(size=8))
                    fig_hm_p.update_layout(height=360)
                    hover_keterangan(fig_hm_p, "Berita unik yang masuk tema baris sekaligus SDG kolom, pilar ini.")
                    st.plotly_chart(fig_hm_p, width="stretch")
            else:
                st.info("Tidak ada data SDG untuk pilar ini pada filter saat ini.")

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
                title=f"Tema \u00d7 Tahun \u2014 pilar {selected_pilar}",
                labels={"x": "Tahun", "y": "Tema", "color": "Berita"},
                color_continuous_scale="greens",
            )
            fig_h_p.update_xaxes(tickangle=-45, tickfont=dict(size=10), automargin=True)
            fig_h_p.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_h_p.update_traces(textfont=dict(size=8))
            fig_h_p.update_layout(height=340)
            hover_keterangan(fig_h_p, "Berita unik tema ini pada tahun tsb, pilar terpilih.")
            st.plotly_chart(fig_h_p, width="stretch")
        else:
            st.info("Tidak cukup data untuk heatmap pilar ini.")

        b_t_pilar_bulan = b_t_pilar.copy()
        b_t_pilar_bulan["bulan"] = b_t_pilar_bulan["tanggal"].str[5:7]
        musim_p = b_t_pilar_bulan.groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
        if len(musim_p):
            musim_p["label"] = musim_p["topik"].map(LABEL_TOPIC)
            fig_m_p = px.bar(
                musim_p, x="bulan", y="jumlah", color="label", barmode="stack",
                title=f"Tren bulanan (musiman) \u2014 pilar {selected_pilar}",
                labels={"bulan": "Bulan", "jumlah": "Jumlah berita", "label": "Tema"},
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_m_p.update_layout(height=340)
            hover_keterangan(fig_m_p, "Berita bulan tsb, semua tahun digabung, pilar terpilih.")
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

        st.markdown("**Daftar berita \u2014 pilar ini**")
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
            st.info("Tidak ada berita untuk pilar ini pada filter saat ini.")

    st.markdown("---")

with st.expander("📂 Analisis Lintas-Pilar (Lanjutan)", expanded=False):
    st.subheader("Ringkasan")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total berita (filter)", len(b))
    c2.metric("Berita bertema dampak", t["url"].nunique() if len(t) else 0)
    c3.metric("Tema terpilih", len(topik_pilih))
    c4.metric("Rentang tahun", f"{tahun_awal}–{tahun_akhir}")

    # ---------- Distribusi per tema ----------
    st.subheader("Distribusi per Tema Dampak")
    dist = t.groupby("topik")["url"].nunique().reset_index(name="jumlah")
    # Sinkron 14 tema: tema tanpa match (mis. Pengajaran & Pembelajaran) tetap
    # tampil dengan jumlah 0, bukan hilang dari chart.
    dist = dist.set_index("topik").reindex(TOPIK_TAMPIL, fill_value=0).reset_index()
    dist["label"] = dist["topik"].map(LABEL_TOPIC)
    fig = px.bar(
        dist.sort_values("jumlah"),
        x="jumlah", y="label", orientation="h",
        title="Jumlah berita per tema dampak",
        labels={"label": "Tema", "jumlah": "Jumlah berita"},
        color="label", color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_layout(showlegend=False, height=380)
    hover_keterangan(
        fig,
        "Berita unik yang match keyword tema ini; satu URL dihitung sekali per tema.",
    )
    st.plotly_chart(fig, width="stretch")
    penjelasan(
        "Tujuan: melihat tema dampak mana yang paling banyak diberitakan. "
        "Angka = jumlah berita unik (URL) yang judul/deskripsinya mengandung "
        "keyword tema; satu berita dihitung sekali per tema. Tema tanpa match "
        "tetap tampil dengan 0."
    )

    # ---------- Peta Kepmen & SDGs ----------
    st.subheader("Peta Tema Resmi Kepmen & Klaster SDGs")
    st.caption(
        "Pemetaan Kepmendikti Saintek 361/M/KEP/2025 (UGM Analytics.xlsx — "
        "sheet 'Konten UGM Berdampak' & '#Ref'): 14 tema resmi dampak "
        "dipetakan ke Tema Resmi Kepmen, pilar "
        "Sosial/Ekonomi/Lingkungan, dan klaster SDGs. Filter pilar di sidebar "
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
            title="Jumlah berita per Tema Resmi Kepmen (berdasarkan pilar dampak)",
            labels={"topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita",
                    "dampak": "Pilar"},
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
            "per pilar. Angka = berita unik dari tema dampak yang dipetakan ke "
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
        st.markdown("**Heatmap Pilar Dampak × Tahun**")
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
                title="Jumlah berita per pilar dampak per tahun (14 tema Kepmen)",
                labels={"x": "Tahun", "y": "Pilar", "color": "Berita"},
                color_continuous_scale="oranges",
            )
            fig_p.update_xaxes(tickangle=-45, tickfont=dict(size=10),
                               automargin=True)
            fig_p.update_traces(textfont=dict(size=8))
            fig_p.update_layout(height=320)
            hover_keterangan(fig_p, "Berita unik pada pilar ini di tahun tsb.")
            st.plotly_chart(fig_p, width="stretch")
            penjelasan(
                "Dominasi pilar Sosial/Ekonomi/Lingkungan per tahun. Angka = "
                "berita unik dari semua tema yang memetakan ke pilar itu pada "
                "tahun tsb (dari 14 tema resmi Kepmen)."
            )

    st.markdown("**Ringkasan per pilar dampak (Sosial/Ekonomi/Lingkungan)**")
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
                title="Berita unik per pilar dampak (semua tema Kepmen)",
                labels={"dampak": "Pilar", "jumlah_berita": "Jumlah berita"},
                color_discrete_map=WARNA_PILAR,
            )
            fig_rp.update_layout(height=320, showlegend=False)
            hover_keterangan(fig_rp, "Berita unik di semua tema dalam pilar ini.")
            st.plotly_chart(fig_rp, width="stretch")
            penjelasan(
                "Total berita unik per pilar dampak (semua tema dalam pilar "
                "digabung, URL dideduplikasi per pilar)."
            )
        else:
            st.info("Tidak ada data pilar untuk filter ini.")

    st.markdown("**Lihat tabel pemetaan resmi + indikator Kepmen (14 tema)**")
    with st.container(border=True):
        map_rows = []
        for topik_id, meta in TOPIK_KEPMEN_ALL.items():
            map_rows.append(
                {
                    "Tema dampak berita": LABEL_TOPIC.get(topik_id, topik_id),
                    "Pilar": meta["dampak"],
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
