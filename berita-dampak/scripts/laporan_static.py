"""Laporan statis HTML analisis dampak berita UGM (plotly write_html).

Hasil: laporan_berita_dampak.html di root subproject.
Plotly JS di-embed inline (include_plotlyjs=True) agar render tanpa internet.
"""

import html
import re
import sys
from collections import Counter
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.keywords import KEYWORDS  # noqa: E402
from scripts.kepmen_sdg import (  # noqa: E402
    TOPIK_KEPMEN,
    TOPIK_KEPMEN_ALL,
    TEMA_KEPMEN_LENGKAP,
    WARNA_PILAR,
    sdg_label,
)
from scripts.kepmen_sdg import LABEL_TOPIC_ALL as LABEL_TOPIC  # noqa: E402

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"
OUT = Path(__file__).resolve().parents[1] / "laporan_berita_dampak.html"

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
    c: Counter = Counter()
    teks = df["judul"].fillna("") + " " + df["deskripsi"].fillna("")
    for t in teks:
        for kata in re.findall(r"[a-z]{3,}", t.lower()):
            if kata not in STOPWORDS:
                c[kata] += 1
    return c


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    berita = con.execute("SELECT * FROM berita").fetchdf()
    topik = con.execute("SELECT * FROM berita_topik").fetchdf()
    sitemap = con.execute("SELECT url, lastmod FROM sitemap").fetchdf()
    bk = con.execute("SELECT * FROM berita_kepmen_all").fetchdf()
    bs = con.execute("SELECT * FROM berita_sdg_all").fetchdf()
    rp = con.execute("SELECT * FROM ringkasan_pilar").fetchdf()
    rsa = con.execute("SELECT * FROM ringkasan_sdg_all").fetchdf()
    con.close()

    berita["tahun"] = berita["tanggal"].str[:4]
    berita["bulan"] = berita["tanggal"].str[5:7]
    b_t = berita.merge(bk, on="url", how="inner")
    b_t["label"] = b_t["topik"].map(LABEL_TOPIC)

    # 1. Distribusi per topik (14 tema, warna pilar)
    dist = bk.groupby(["topik", "dampak"])["url"].nunique().reset_index(name="jumlah")
    dist["label"] = dist["topik"].map(LABEL_TOPIC)
    fig1 = px.bar(
        dist.sort_values("jumlah"), x="jumlah", y="label", orientation="h",
        title="Jumlah berita per topik dampak (14 tema Kepmen)",
        labels={"label": "Topik", "jumlah": "Jumlah berita"},
        color="dampak", color_discrete_map=WARNA_PILAR,
    )
    fig1.update_layout(showlegend=True)

    # 2. Heatmap topik x tahun
    piv = (
        b_t.pivot_table(index="topik", columns="tahun", values="url",
                        aggfunc="nunique", fill_value=0)
        .reindex(index=[k for k in LABEL_TOPIC if k in b_t["topik"].unique()])
    )
    fig2 = px.imshow(
        piv, text_auto=True, aspect="auto",
        title="Jumlah berita per topik per tahun",
        labels={"x": "Tahun", "y": "Topik", "color": "Berita"},
        color_continuous_scale="greens",
    )
    fig2.update_yaxes(ticktext=[LABEL_TOPIC.get(i, i) for i in piv.index],
                      tickvals=list(range(len(piv))))
    fig2.update_layout(height=320)

    # 3. Tren tahunan
    tren = b_t.groupby(["topik", "tahun"]).size().reset_index(name="jumlah")
    tren["label"] = tren["topik"].map(LABEL_TOPIC)
    fig3 = px.line(
        tren, x="tahun", y="jumlah", color="label", markers=True,
        title="Tren tahunan per topik",
        labels={"tahun": "Tahun", "jumlah": "Jumlah berita", "label": "Topik"},
        color_discrete_sequence=px.colors.qualitative.Bold,
    )

    # 4. Cakupan vs total berita UGM
    sitemap["tahun"] = sitemap["lastmod"].str[:4]
    tot = sitemap.groupby("tahun").size().reset_index(name="total")
    cakup = b_t.groupby("tahun").size().reset_index(name="bertopik")
    gab = tot.merge(cakup, on="tahun", how="left").fillna(0)
    fig4 = go.Figure()
    fig4.add_bar(x=gab["tahun"], y=gab["total"], name="Total berita (sitemap)",
                 marker_color="rgba(150,150,150,0.35)")
    fig4.add_scatter(x=gab["tahun"], y=gab["bertopik"],
                     name="Berita bertopik dampak", mode="lines+markers",
                     marker_color="#2e7d32", line=dict(width=3))
    fig4.update_layout(title="Volume berita UGM vs berita bertopik dampak per tahun",
                       xaxis_title="Tahun", yaxis_title="Jumlah berita", barmode="overlay")

    # 5. Keyword yang match per topik
    kw_rows = []
    for topik_name, kws in KEYWORDS_ALL.items():
        urls_t = set(b_t.loc[b_t["topik"] == topik_name, "url"])
        sub = berita[berita["url"].isin(urls_t)]
        teks = (sub["judul"].fillna("") + " " + sub["deskripsi"].fillna("")).str.lower()
        for kw in kws:
            n = teks.str.contains(re.escape(kw), regex=True).sum()
            if n:
                kw_rows.append({"topik": topik_name, "keyword": kw, "jumlah": int(n)})
    kw_df = pd.DataFrame(kw_rows)
    kw_df["label"] = kw_df["topik"].map(LABEL_TOPIC)
    fig5 = px.bar(
        kw_df.sort_values("jumlah"), x="jumlah", y="keyword", color="label",
        orientation="h", title="Jumlah berita yang match tiap keyword",
        labels={"keyword": "Keyword", "jumlah": "Jumlah berita", "label": "Topik"},
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig5.update_layout(yaxis=dict(autorange="reversed"))

    # 6. Multi-topik
    cnt = b_t.groupby("url").size().reset_index(name="n_topik")
    dist_n = cnt["n_topik"].value_counts().sort_index().reset_index()
    dist_n.columns = ["jumlah topik", "berita"]
    fig6 = px.bar(
        dist_n, x="jumlah topik", y="berita",
        title="Berapa banyak topik per berita",
        labels={"jumlah topik": "Jumlah topik", "berita": "Jumlah berita"},
    )

    # 7. Peta Topik Resmi Kepmen (14 tema)
    dist_k = (
        bk.groupby(["dampak", "topik_kepmen"])["url"]
        .nunique()
        .reset_index(name="jumlah")
        .sort_values("jumlah")
    )
    fig7 = px.bar(
        dist_k, x="jumlah", y="topik_kepmen", color="dampak", orientation="h",
        title="Jumlah berita per Topik Resmi Kepmen (Kepmen 361/M/KEP/2025)",
        labels={"topik_kepmen": "Topik Resmi Kepmen", "jumlah": "Jumlah berita",
                "dampak": "Pilar"},
        color_discrete_map=WARNA_PILAR,
    )
    fig7.update_layout(height=420, yaxis=dict(autorange="reversed"))

    # 7b. Ringkasan per pilar
    fig7b = px.bar(
        rp, x="dampak", y="jumlah_berita", color="dampak",
        title="Berita unik per pilar dampak (Sosial/Ekonomi/Lingkungan)",
        labels={"dampak": "Pilar", "jumlah_berita": "Jumlah berita"},
        color_discrete_map=WARNA_PILAR,
    )
    fig7b.update_layout(height=320, showlegend=False)

    # 8. Klaster SDGs (semua tema)
    dist_s = (
        bs.groupby("sdg")["url"]
        .nunique()
        .reset_index(name="jumlah")
        .sort_values("jumlah")
    )
    dist_s["label"] = dist_s["sdg"].apply(sdg_label)
    fig8 = px.bar(
        dist_s, x="label", y="jumlah", color="sdg",
        title="Jumlah berita per SDG (klaster resmi semua tema)",
        labels={"label": "SDG", "jumlah": "Jumlah berita"},
    )
    fig8.update_layout(height=400, showlegend=False)

    # 8b. Tren SDG per tahun
    sdg_tahun = (
        bs.merge(berita[["url", "tahun"]], on="url", how="left")
        .drop_duplicates(subset=["url", "sdg", "tahun"])
        .groupby(["tahun", "sdg"])
        .size()
        .reset_index(name="jumlah")
    )
    sdg_tahun["label"] = sdg_tahun["sdg"].apply(lambda s: f"SDG {s}")
    fig8b = px.line(
        sdg_tahun, x="tahun", y="jumlah", color="label", markers=True,
        title="Jumlah berita per SDG per tahun",
        labels={"tahun": "Tahun", "jumlah": "Jumlah berita", "label": "SDG"},
    )
    fig8b.update_layout(height=420)

    # 8c. Heatmap pilar x tahun
    bk_tahun = (
        bk.merge(berita[["url", "tahun"]], on="url", how="left")
        .drop_duplicates(subset=["url", "topik", "tahun"])
    )
    piv_p = (
        bk_tahun.groupby(["dampak", "tahun"])["url"]
        .nunique()
        .reset_index(name="jumlah")
        .pivot_table(index="dampak", columns="tahun", values="jumlah", fill_value=0)
    )
    fig8c = px.imshow(
        piv_p, text_auto=True, aspect="auto",
        title="Jumlah berita per pilar dampak per tahun (14 tema Kepmen)",
        labels={"x": "Tahun", "y": "Pilar", "color": "Berita"},
        color_continuous_scale="oranges",
    )
    fig8c.update_layout(height=300)

    # 9. Word frequency per topik (10 kata teratas)
    wf_figs = []
    for topik_name, label in LABEL_TOPIC.items():
        urls_t = set(b_t.loc[b_t["topik"] == topik_name, "url"])
        freq = token_freq(berita[berita["url"].isin(urls_t)])
        wf = pd.DataFrame(freq.most_common(10), columns=["kata", "jumlah"])
        f = px.bar(
            wf, x="jumlah", y="kata", orientation="h",
            title=f"{label} — 10 kata teratas",
            labels={"kata": "Kata", "jumlah": "Frekuensi"},
            color_discrete_sequence=["#2e7d32"],
        )
        f.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
        wf_figs.append(f.to_html(full_html=False, include_plotlyjs=False))

    # Tabel detail topik (5 contoh per topik)
    tabel_rows = []
    for topik_name in LABEL_TOPIC:
        urls = set(bk.loc[bk["topik"] == topik_name, "url"])
        sub = berita[berita["url"].isin(urls)].sort_values("tanggal", ascending=False)
        for _, r in sub.head(5).iterrows():
            tabel_rows.append(
                f"<tr><td>{LABEL_TOPIC[topik_name]}</td><td>{r['tanggal'] or '-'}</td>"
                f"<td><a href='{html.escape(r['url'])}'>{html.escape(str(r['judul']))}</a></td></tr>"
            )
    tabel = "<table border='1' cellpadding='6' style='border-collapse:collapse;width:100%'>"
    tabel += "<tr style='background:#eee'><th>Topik</th><th>Tanggal</th><th>Judul</th></tr>"
    tabel += "".join(tabel_rows) + "</table>"

    # Tabel indikator resmi Kepmen (14 tema)
    ind_rows = []
    for topik_id, meta in TOPIK_KEPMEN_ALL.items():
        ind_rows.append(
            "<tr>"
            f"<td>{LABEL_TOPIC[topik_id]}</td>"
            f"<td>{meta['dampak']}</td>"
            f"<td>{meta['topik_kepmen']}</td>"
            f"<td>{', '.join(sdg_label(s) for s in meta['sdg']) or '—'}</td>"
            f"<td>{meta['indikator']}</td>"
            f"<td>{meta['definisi']}</td>"
            f"<td>{meta['kriteria']}</td>"
            f"<td>{meta['formula']}</td>"
            f"<td>{meta['satuan']}</td>"
            "</tr>"
        )
    tabel_ind = (
        "<table border='1' cellpadding='6' style='border-collapse:collapse;width:100%'>"
        "<tr style='background:#eee'><th>Topik berita</th><th>Pilar</th>"
        "<th>Topik Resmi Kepmen</th><th>Klaster SDGs</th><th>Indikator</th>"
        "<th>Definisi</th><th>Kriteria</th><th>Formula</th><th>Satuan</th></tr>"
        + "".join(ind_rows) + "</table>"
    )

    # Gabung semua chart; JS plotly di-embed sekali di fig1
    figs = [fig1, fig2, fig3, fig4, fig5, fig6, fig7, fig7b, fig8, fig8b, fig8c]
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Laporan Analisis Dampak Berita UGM</title></head><body>",
        "<h1>Laporan Analisis Dampak Berita UGM</h1>",
        f"<p>Total berita: {len(berita)} &middot; Berita bertopik dampak (14 tema Kepmen): "
        f"{bk['url'].nunique()} &middot; Sumber: ugm.ac.id (RSS + sitemap)</p>",
        figs[0].to_html(full_html=False, include_plotlyjs=True),
        figs[1].to_html(full_html=False, include_plotlyjs=False),
        figs[2].to_html(full_html=False, include_plotlyjs=False),
        figs[3].to_html(full_html=False, include_plotlyjs=False),
        figs[4].to_html(full_html=False, include_plotlyjs=False),
        figs[5].to_html(full_html=False, include_plotlyjs=False),
        "<h2>Peta Topik Resmi Kepmen &amp; Klaster SDGs</h2>",
        figs[6].to_html(full_html=False, include_plotlyjs=False),
        figs[7].to_html(full_html=False, include_plotlyjs=False),
        figs[8].to_html(full_html=False, include_plotlyjs=False),
        figs[9].to_html(full_html=False, include_plotlyjs=False),
        figs[10].to_html(full_html=False, include_plotlyjs=False),
        "<h2>Indikator resmi Kepmen per topik (14 tema)</h2>",
        tabel_ind,
        "<h2>Kata yang paling sering muncul per topik</h2>",
        *wf_figs,
        "<h2>Contoh berita per topik</h2>",
        tabel,
        "</body></html>",
    ]
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"Laporan tersimpan: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
