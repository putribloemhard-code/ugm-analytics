"""Dashboard Streamlit analisis dampak berita UGM.

Sumber: data/ugm_news.duckdb (tabel berita, berita_topik, ringkasan_topik_tahun, sitemap).
Jalankan: streamlit run dashboard_berita_dampak.py
"""

import re
import sys
from collections import Counter
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

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

DB_PATH = Path(__file__).resolve().parent / "data" / "ugm_news.duckdb"

# Semua keyword (4 topik inti + 9 tema Kepmen lain) untuk breakdown.
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


st.set_page_config(page_title="Analisis Dampak Berita UGM", layout="wide")
st.title("Analisis Dampak Berita UGM")
st.caption("Sumber: berita ugm.ac.id (RSS + sitemap) — data/ugm_news.duckdb")


@st.cache_data(ttl=300)
def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame]:
    con = _connect_db()
    berita = con.execute("SELECT * FROM berita").fetchdf()
    topik = con.execute("SELECT * FROM berita_topik").fetchdf()
    ringkas = con.execute("SELECT * FROM ringkasan_topik_tahun").fetchdf()
    sitemap = con.execute("SELECT url, lastmod FROM sitemap").fetchdf()
    bk = con.execute("SELECT * FROM berita_kepmen_all").fetchdf()
    bs = con.execute("SELECT * FROM berita_sdg_all").fetchdf()
    rp = con.execute("SELECT * FROM ringkasan_pilar").fetchdf()
    rpt = con.execute("SELECT * FROM ringkasan_pilar_tahun").fetchdf()
    rsa = con.execute("SELECT * FROM ringkasan_sdg_all").fetchdf()
    con.close()
    return berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa


def _connect_db():
    """Buka DB read-only dengan retry.

    Di Windows, DuckDB CLI (duckdb.exe) yang dibuka manual dengan mode tulis
    mengunci file total — proses lain tidak bisa membuka apalagi menyalinnya.
    Strategi: coba berkala beberapa detik (kalau CLI ditutup, langsung pulih);
    kalau tetap terkunci, lempar pesan jelas alih-alih traceback mentah.
    """
    import time

    last_err: Exception | None = None
    for _ in range(10):
        try:
            return duckdb.connect(str(DB_PATH), read_only=True)
        except (duckdb.IOException, OSError) as e:
            last_err = e
            time.sleep(1)
    raise RuntimeError(
        "File database terkunci proses lain (kemungkinan DuckDB CLI dibuka "
        "manual dengan mode tulis, atau update berita sedang berjalan di "
        "background). Tutup jendela/terminal duckdb.exe dulu, atau tunggu "
        "update selesai (±10 menit), lalu muat ulang halaman ini. "
        f"Detail: {last_err}"
    ) from last_err


try:
    berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa = load()
except RuntimeError as e:
    st.error(str(e))
    st.info("Tips: jalankan query DuckDB dengan mode read-only agar tidak "
            "mengunci file:\n\n"
            "duckdb -readonly data/ugm_news.duckdb")
    st.stop()

# ---------- Sidebar filter global ----------
st.sidebar.header("Filter")
tahun_opsi = sorted(
    berita["tanggal"].dropna().str[:4].unique()
) if len(berita) else ["2005", "2026"]
tahun_awal, tahun_akhir = st.sidebar.select_slider(
    "Rentang tahun",
    options=tahun_opsi,
    value=(tahun_opsi[0], tahun_opsi[-1]),
)
topik_pilih = st.sidebar.multiselect(
    "Topik dampak",
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
    py = Path(__file__).resolve().parents[2] / "venv" / "Scripts" / "python.exe"
    lock = Path(__file__).resolve().parent / "data" / ".update_lock"
    if lock.exists():
        st.warning(
            "Update lain sedang berjalan di background (dari tombol ini atau "
            "cron mingguan). Selama proses berjalan, dashboard tidak bisa "
            "dimuat ulang (file DB terkunci). Tunggu ±10 menit, lalu muat "
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
        "Proses memakan waktu ±10 menit (fetch berita baru dari ugm.ac.id). "
        "Selama update berjalan, jangan muat ulang dashboard ini. "
        "Setelah ±10 menit, muat ulang halaman — data baru otomatis tampil. "
        "Log: logs_update_dashboard.txt"
    )
    st.stop()

# Terapkan filter
b = berita.copy()
b["tahun"] = b["tanggal"].str[:4]
b = b[b["tahun"].between(tahun_awal, tahun_akhir) & b["sumber"].isin(sumber_pilih)]
# t = semua tema Kepmen (13 topik: 4 inti + 9 lengkap) dari tabel gabungan.
# Kalau filter topik/pilar kosong, fallback ke 4 topik inti (topik berita).
t = bk[bk["topik"].isin(topik_pilih)] if topik_pilih else bk
if pilar_pilih:
    t = t[t["dampak"].isin(pilar_pilih)]
if len(b) and len(t):
    t = t[t["url"].isin(set(b["url"]))]

# ---------- Ringkasan ----------
st.subheader("Ringkasan")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total berita (filter)", len(b))
c2.metric("Berita bertopik dampak", t["url"].nunique() if len(t) else 0)
c3.metric("Topik terpilih", len(topik_pilih))
c4.metric("Rentang tahun", f"{tahun_awal}–{tahun_akhir}")

if len(b) == 0 or len(t) == 0:
    st.warning("Tidak ada data untuk filter ini. Ubah filter di sidebar.")
    st.stop()

b_t = b.merge(t, on="url", how="inner")

# Tabel Kepmen/SDG ke berita yang lolos filter
urls_t = set(b_t["url"])
bk_f = t[t["url"].isin(urls_t)].copy()
bs_f = bs[bs["url"].isin(urls_t)].copy()

# ---------- Distribusi per topik ----------
st.subheader("Distribusi per Topik Dampak")
dist = t.groupby("topik")["url"].nunique().reset_index(name="jumlah")
dist["label"] = dist["topik"].map(LABEL_TOPIC)
fig = px.bar(
    dist.sort_values("jumlah"),
    x="jumlah", y="label", orientation="h",
    title="Jumlah berita per topik dampak",
    labels={"label": "Topik", "jumlah": "Jumlah berita"},
    color="label", color_discrete_sequence=px.colors.qualitative.Bold,
)
fig.update_layout(showlegend=False, height=380)
st.plotly_chart(fig, width="stretch")

# ---------- Peta Kepmen & SDGs ----------
st.subheader("Peta Topik Resmi Kepmen & Klaster SDGs")
st.caption(
    "Pemetaan Kepmendikti Saintek 361/M/KEP/2025 (UGM Analytics.xlsx — "
    "sheet 'Konten UGM Berdampak' & '#Ref'): 13 topik dampak berita (4 topik "
    "inti + 9 tema Kepmen lain) dipetakan ke Topik Resmi Kepmen, pilar "
    "Sosial/Ekonomi/Lingkungan, dan klaster SDGs. Filter pilar di sidebar "
    "berlaku untuk grafik di bawah."
)

if len(bk_f):
    dist_k = (
        bk_f.groupby(["dampak", "topik_kepmen"])["url"]
        .nunique()
        .reset_index(name="jumlah")
        .sort_values("jumlah")
    )
    fig_k = px.bar(
        dist_k, x="jumlah", y="topik_kepmen", color="dampak", orientation="h",
        title="Jumlah berita per Topik Resmi Kepmen (berdasarkan pilar dampak)",
        labels={"topik_kepmen": "Topik Resmi Kepmen", "jumlah": "Jumlah berita",
                "dampak": "Pilar"},
        color_discrete_map={"Lingkungan": "#2e7d32", "Ekonomi": "#1565c0",
                            "Sosial": "#e65100"},
    )
    fig_k.update_layout(height=380, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_k, width="stretch")
else:
    st.info("Tidak ada data Kepmen untuk filter ini.")

if len(bs_f):
    dist_s = (
        bs_f.groupby("sdg")["url"]
        .nunique()
        .reset_index(name="jumlah")
        .sort_values("jumlah")
    )
    dist_s["label"] = dist_s["sdg"].apply(sdg_label)
    fig_s = px.bar(
        dist_s, x="label", y="jumlah", color="sdg",
        title="Jumlah berita per SDG (klaster resmi)",
        labels={"label": "SDG", "jumlah": "Jumlah berita"},
    )
    fig_s.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_s, width="stretch")

    # Heatmap topik dampak x SDG
    st.markdown("**Heatmap Topik Dampak × SDG**")
    hm = (
        bs_f.merge(bk_f[["url", "topik"]], on="url", how="left")
        .drop_duplicates(subset=["url", "topik", "sdg"])
    )
    if len(hm):
        hm_piv = (
            hm.pivot_table(index="topik", columns="sdg", values="url",
                           aggfunc="nunique", fill_value=0)
            .reindex(index=[k for k in LABEL_TOPIC if k in hm["topik"].unique()])
        )
        fig_hm = px.imshow(
            hm_piv, text_auto=True, aspect="auto",
            title="Berita per kombinasi topik dampak × SDG",
            labels={"x": "SDG", "y": "Topik dampak", "color": "Berita"},
            color_continuous_scale="blues",
        )
        fig_hm.update_xaxes(
            ticktext=[f"SDG {c}" for c in hm_piv.columns],
            tickvals=list(range(len(hm_piv.columns))),
        )
        fig_hm.update_yaxes(
            ticktext=[LABEL_TOPIC.get(i, i) for i in hm_piv.index],
            tickvals=list(range(len(hm_piv))),
        )
        fig_hm.update_layout(height=340)
        st.plotly_chart(fig_hm, width="stretch")

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
        st.plotly_chart(fig_st, width="stretch")

    # Heatmap pilar x tahun (dari topik Kepmen)
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
            title="Jumlah berita per pilar dampak per tahun (13 topik Kepmen)",
            labels={"x": "Tahun", "y": "Pilar", "color": "Berita"},
            color_continuous_scale="oranges",
        )
        fig_p.update_layout(height=300)
        st.plotly_chart(fig_p, width="stretch")

with st.expander("Ringkasan per pilar dampak (Sosial/Ekonomi/Lingkungan)"):
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
        st.plotly_chart(fig_rp, width="stretch")
    else:
        st.info("Tidak ada data pilar untuk filter ini.")

with st.expander("Lihat tabel pemetaan resmi + indikator Kepmen (13 topik)"):
    map_rows = []
    for topik_id, meta in TOPIK_KEPMEN_ALL.items():
        map_rows.append(
            {
                "Topik dampak berita": LABEL_TOPIC.get(topik_id, topik_id),
                "Pilar": meta["dampak"],
                "Topik Resmi Kepmen": meta["topik_kepmen"],
                "Klaster SDGs": ", ".join(sdg_label(s) for s in meta["sdg"]) or "—",
                "Indikator Kepmen": meta["indikator"],
                "Formula": meta["formula"],
                "Satuan": meta["satuan"],
            }
        )
    st.dataframe(pd.DataFrame(map_rows), width="stretch", hide_index=True)
    st.caption(
        "13 topik = 4 topik inti berita (resmi, sheet 'Konten UGM Berdampak') "
        "+ 9 tema Kepmen lain (klaster SDG dari sheet '#Ref'). Indikator dari "
        "Salinan Kepmen 361/M/KEP/2025 (OCR)."
    )

# ---------- Heatmap topik x tahun ----------
st.subheader("Heatmap Topik × Tahun")
piv = (
    b_t.pivot_table(index="topik", columns="tahun", values="url",
                    aggfunc="nunique", fill_value=0)
    .reindex(index=[k for k in LABEL_TOPIC if k in b_t["topik"].unique()])
)
if len(piv):
    fig_h = px.imshow(
        piv, text_auto=True, aspect="auto",
        title="Jumlah berita per topik per tahun",
        labels={"x": "Tahun", "y": "Topik", "color": "Berita"},
        color_continuous_scale="greens",
    )
    fig_h.update_yaxes(ticktext=[LABEL_TOPIC.get(i, i) for i in piv.index],
                       tickvals=list(range(len(piv))))
    fig_h.update_layout(height=320)
    st.plotly_chart(fig_h, width="stretch")
else:
    st.info("Tidak cukup data untuk heatmap.")

# ---------- Tren tahunan ----------
st.subheader("Tren Tahunan per Topik")
tren = b_t.groupby(["topik", "tahun"]).size().reset_index(name="jumlah")
tren["label"] = tren["topik"].map(LABEL_TOPIC)
fig2 = px.line(
    tren, x="tahun", y="jumlah", color="label", markers=True,
    title="Jumlah berita per tahun",
    labels={"tahun": "Tahun", "jumlah": "Jumlah berita", "label": "Topik"},
    color_discrete_sequence=px.colors.qualitative.Bold,
)
fig2.update_layout(height=420)
st.plotly_chart(fig2, width="stretch")

# ---------- Tren bulanan ----------
st.subheader("Tren Bulanan (musiman)")
b_t["bulan"] = b_t["tanggal"].str[5:7]
musim = b_t.groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
musim["label"] = musim["topik"].map(LABEL_TOPIC)
fig3 = px.bar(
    musim, x="bulan", y="jumlah", color="label", barmode="stack",
    title="Jumlah berita per bulan kalender (semua tahun digabung)",
    labels={"bulan": "Bulan", "jumlah": "Jumlah berita", "label": "Topik"},
    color_discrete_sequence=px.colors.qualitative.Bold,
)
fig3.update_layout(height=400)
st.plotly_chart(fig3, width="stretch")

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
fig4.add_scatter(x=gab["tahun"], y=gab["bertopik"], name="Berita bertopik dampak",
                 mode="lines+markers", marker_color="#2e7d32", line=dict(width=3))
fig4.update_layout(
    title="Volume berita UGM vs berita yang terdeteksi topik dampak",
    xaxis_title="Tahun", yaxis_title="Jumlah berita", height=420,
    barmode="overlay",
)
st.plotly_chart(fig4, width="stretch")
st.caption(
    "Garis abu-abu = seluruh URL di sitemap ugm.ac.id per tahun (baseline). "
    "Garis hijau = berita yang match topik dampak. Proporsi menggambarkan "
    "seberapa besar konten UGM yang tercatat sebagai aktivitas dampak; "
    "nilainya lower-bound karena pencocokan keyword terbatas pada 13 topik "
    "Kepmen yang dideteksi."
)

# ---------- Breakdown keyword ----------
st.subheader("Keyword yang Memicu Match per Topik")
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
    # Select per topik biar label keyword tidak menumpuk jadi kecil.
    topik_ada = [
        t for t in KEYWORDS_ALL
        if t in topik_pilih and t in kw_df["topik"].unique()
    ]
    pilih_kw = st.selectbox(
        "Pilih topik (keyword)",
        options=topik_ada,
        format_func=lambda k: LABEL_TOPIC.get(k, k),
    )
    sub_kw = kw_df[kw_df["topik"] == pilih_kw].sort_values("jumlah")
    n_kw = len(sub_kw)
    if n_kw:
        fig5 = px.bar(
            sub_kw, x="jumlah", y="keyword", orientation="h",
            title=f"Jumlah berita yang match tiap keyword — {LABEL_TOPIC.get(pilih_kw, pilih_kw)}",
            labels={"keyword": "Keyword", "jumlah": "Jumlah berita"},
            color_discrete_sequence=["#2e7d32"],
        )
        fig5.update_layout(
            height=max(320, 34 * n_kw + 80),
            yaxis=dict(autorange="reversed"),
            showlegend=False,
        )
        st.plotly_chart(fig5, width="stretch")
    else:
        st.info("Tidak ada match keyword untuk topik ini.")
else:
    st.info("Tidak ada match keyword pada filter ini.")

# ---------- Multi-topik ----------
st.subheader("Berita Multi-Topik")
cnt = b_t.groupby("url").size().reset_index(name="n_topik")
dist_n = cnt["n_topik"].value_counts().sort_index().reset_index()
dist_n.columns = ["jumlah topik", "berita"]
fig6 = px.bar(
    dist_n, x="jumlah topik", y="berita",
    title="Berapa banyak topik per berita",
    labels={"jumlah topik": "Jumlah topik", "berita": "Jumlah berita"},
)
fig6.update_layout(height=350)
st.plotly_chart(fig6, width="stretch")
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
    st.caption("Tidak ada berita multi-topik pada filter ini.")

# ---------- Word frequency ----------
st.subheader("Kata yang Paling Sering Muncul per Topik")
topik_wf = st.selectbox(
    "Pilih topik",
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
st.plotly_chart(fig7, width="stretch")

# ---------- Drill-down ----------
st.subheader("Daftar Berita")
label_by_url = (
    t.assign(label=t["topik"].map(LABEL_TOPIC))
    .groupby("url")["label"]
    .apply(lambda s: ", ".join(sorted(s)))
    .to_dict()
)
# Topik Kepmen per url (gabung nama resmi)
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
df["Topik"] = df["url"].map(label_by_url).fillna("—")
df["Topik Kepmen"] = df["url"].map(kepmen_by_url).fillna("—")
df["Indikator Kepmen"] = df["url"].map(indikator_by_url).fillna("—")
df["SDG"] = df["url"].map(sdg_by_url).fillna("—")
df = df.sort_values("tanggal", ascending=False)

if len(df):
    tampil = df[["tanggal", "judul", "Topik", "Topik Kepmen",
                 "Indikator Kepmen", "SDG", "sumber"]].copy()
    tampil.columns = ["Tanggal", "Judul", "Topik", "Topik Kepmen",
                      "Indikator Kepmen", "SDG", "Sumber"]
    tampil["Tautan"] = df["url"].apply(lambda u: f"[buka]({u})")
    st.dataframe(tampil, width="stretch", hide_index=True)
else:
    st.info("Tidak ada berita untuk filter ini.")

# ---------- Cek manual ----------
with st.expander("Berita tanpa match topik (cek manual)"):
    tagged = set(t["url"])
    belum = b[~b["url"].isin(tagged)]
    st.write(f"{len(belum)} berita (dalam filter) tidak masuk topik mana pun.")
    if len(belum):
        st.dataframe(
            belum[["tanggal", "judul", "url"]].sort_values("tanggal", ascending=False),
            width="stretch", hide_index=True,
        )
