"""Logika + UI untuk halaman "SDGs" (mapping langsung seluruh URL sitemap ke
17 SDG, tanpa tema dampak Kepmen).

Pemindahan PERSIS dari mode "SDGs" pada dashboard_berita_dampak.py versi lama
(dropdown "Mode analisis") -- logika, filter, dan angka tidak diubah, cuma
dipindah dari cabang dropdown jadi halaman terpisah.
"""

import os
import subprocess
import sys
import time as _time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from common import (
    LABEL_TOPIC,
    SDG_NAMA,
    UNIT_KERJA_OPSI,
    hover_keterangan,
    load_data_or_stop,
    penjelasan,
)
from scripts.narasi_logic import generate_sdg_saja_summary
from scripts.sdg_keywords import SDG_KEYWORDS
from scripts.unit_kerja import UNIT_KERJA


def render() -> None:
    (berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt, uk), NARASI_CACHE = (
        load_data_or_stop()
    )

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

    # Mode SDG: filter berdasarkan SDG, bukan tema dampak.
    sdg_pilih = st.sidebar.multiselect(
        "SDG (17)",
        options=list(range(1, 18)),
        default=list(range(1, 18)),
        format_func=lambda s: f"SDG {s} — {SDG_NAMA.get(s, s)}",
    )
    topik_pilih: list = []
    pilar_pilih: list = []

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

    # Narasi LLM ter-cache (lihat load_narasi_cache di data_loader.py) cuma
    # valid utk posisi filter DEFAULT -- begitu user ganti tahun/tema/pilar/SDG,
    # angka2 dalam narasi cache jadi gak sesuai lagi, jadi WAJIB balik ke
    # template pandas yang dihitung ulang dari data ter-filter
    # (generate_sdg_saja_summary). CATATAN: sama seperti versi lama, topik_pilih
    # & pilar_pilih SELALU kosong di halaman ini (tidak pernah diisi UI apa
    # pun di sini) sehingga dibandingkan ke set(LABEL_TOPIC.keys()) / 3 pilar
    # ini SELALU False -- FILTER_ADALAH_DEFAULT jadi selalu False, sama
    # persis seperti perilaku mode "SDGs" di dashboard lama (bukan disengaja
    # dioptimalkan di sini, dipertahankan apa adanya).
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
    st.sidebar.divider()
    update_log = Path(__file__).resolve().parent / "logs_update_dashboard.txt"
    if update_log.exists():
        mtime = update_log.stat().st_mtime
        st.sidebar.caption(f"Update terakhir: {_time.strftime('%Y-%m-%d %H:%M', _time.localtime(mtime))}")
    else:
        st.sidebar.caption("Data terakhir diambil dari ugm.ac.id.")

    if st.sidebar.button("🔄 Update Berita Terbaru", use_container_width=True, key="update_btn"):
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
    st.subheader("Analisis SDGs — Seluruh Berita UGM (32.130 URL)")
    st.caption(
        "Mapping langsung url berita sitemap ke 17 SDG (tanpa tema dampak Kepmen): "
        "kata-kata slug URL untuk yang belum di-fetch + judul & deskripsi untuk "
        "4.787 yang sudah. Satu berita bisa masuk beberapa SDG. Filter SDG & "
        "Fakultas/Unit Kerja di sidebar berlaku di sini."
    )
    sitemap = sitemap.copy()
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
