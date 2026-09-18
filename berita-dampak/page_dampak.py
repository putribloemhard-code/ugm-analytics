"""Logika + UI bersama untuk halaman "Dampak Saja" dan "Dampak x SDGs".

Dipanggil dari pages_app/dampak_saja.py (mode="Berdampak") dan
pages_app/dampak_sdgs.py (mode="Berdampak × SDGs") -- SATU fungsi dipakai
bareng oleh kedua halaman (bukan disalin ke masing-masing file) supaya
tidak mungkin diam-diam jadi beda perilaku antara keduanya seiring waktu.
Ini adalah pemindahan PERSIS dari mode "Berdampak" / "Berdampak x SDGs"
pada dashboard_berita_dampak.py versi lama (dropdown "Mode analisis") --
logika, filter, dan angka tidak diubah, cuma `mode` yang tadinya dipilih
lewat st.sidebar.radio sekarang jadi parameter tetap per halaman.
"""

import os
import re
import subprocess
import sys
import time as _time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (
    KEYWORDS_ALL,
    PILAR_ICON_SIDEBAR,
    TOPIK_PER_PILAR,
    UNIT_KERJA_OPSI,
    WARNA_KATEGORI,
    hover_keterangan,
    insight_heatmap,
    insight_top2,
    load_data_or_stop,
    penjelasan,
    token_freq,
)
import laporan_word
import pencarian
from scripts.kepmen_sdg import TOPIK_KEPMEN_ALL, WARNA_PILAR, sdg_label
from scripts.kepmen_sdg import LABEL_TOPIC_ALL as LABEL_TOPIC
from scripts.narasi_logic import generate_executive_summary, generate_impact_insight
from scripts.unit_kerja import UNIT_KERJA


def render(mode: str) -> None:
    """mode: "Berdampak" atau "Berdampak × SDGs"."""
    (berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt, uk), NARASI_CACHE = (
        load_data_or_stop()
    )

    # ---------- Sidebar filter global ----------
    st.sidebar.header("Filter")
    tahun_opsi = sorted(
        berita["tanggal"].dropna().str[:4].unique()
    ) if len(berita) else ["2005", "2026"]
    # Hasil pencarian Beranda (kalau ada) dipasang sbg nilai AWAL widget di
    # bawah ini -- WAJIB sebelum widget-nya dibuat, lihat pencarian.py.
    pencarian.terapkan_filter_awal(list(tahun_opsi))
    tahun_awal, tahun_akhir = st.sidebar.select_slider(
        "Rentang tahun",
        options=tahun_opsi,
        value=(tahun_opsi[0], tahun_opsi[-1]),
        key=pencarian.WIDGET_TAHUN,
    )
    # Semua berita (RSS + sitemap) selalu ikut dihitung -- bukan pilihan yang
    # perlu diputuskan user, cuma dua cara pengambilan data yang saling melengkapi
    # (RSS = berita terbaru, sitemap = arsip). Tidak ada lagi filter "Sumber" di UI.
    sumber_pilih = ["sitemap", "rss"]

    sdg_pilih = list(range(1, 18))
    # 1) Pilih dampak (pilar) dulu ...
    pilar_pilih = st.sidebar.multiselect(
        "Dampak",
        options=["Lingkungan", "Ekonomi", "Sosial"],
        default=["Lingkungan", "Ekonomi", "Sosial"],
        format_func=lambda p: f"{PILAR_ICON_SIDEBAR[p]} {p}",
        key=pencarian.WIDGET_PILAR,
    )
    # 2) ... baru tema Kepmen-nya, satu dropdown TERPISAH per dampak terpilih
    #    (bukan 1 dropdown gabungan isi 14 tema sekaligus).
    topik_pilih: list = []
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

    # Filter fakultas/unit kerja (independen dari tema/pilar Kepmen). Default
    # kosong = tidak memfilter apa pun sampai user pilih (lihat
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
    # valid utk posisi filter DEFAULT -- begitu user ganti tahun/tema/pilar,
    # angka2 dalam narasi cache jadi gak sesuai lagi, jadi WAJIB balik ke
    # template pandas yang dihitung ulang dari data ter-filter
    # (generate_executive_summary / generate_impact_insight).
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
    st.subheader("Ringkasan Eksekutif")
    ringkasan = generate_executive_summary(b, t, bs_f, mode, tahun_awal, tahun_akhir)
    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Total berita dampak", f"{ringkasan['total_berita']:,}")
    _pilar_delta_label = (
        f"{ringkasan['pilar_top_pct']:+.1f}%" if ringkasan["pilar_top_pct"] is not None
        else (f"+{ringkasan['pilar_top_naik']} berita" if ringkasan["pilar_top_naik"] else None)
    )
    rc2.metric(
        "Dampak pertumbuhan tertinggi", ringkasan["pilar_top"], _pilar_delta_label,
        help=f"Dibandingkan sejak {ringkasan['pilar_top_baseline_tahun']} (baseline 5 tahun terakhir, "
             "bukan dari titik awal rentang filter -- basis awal yang terlalu kecil bisa membuat "
             "persentase menyesatkan).",
    )
    rc3.metric(f"Sorotan {tahun_akhir}", f"{ringkasan['berita_tahun_ini']:,} berita")
    rc4.metric(ringkasan["topik_top_kind_label"], ringkasan["topik_top_short"])
    _exec_cache_key = "exec_berdampak_sdgs" if mode == "Berdampak × SDGs" else "exec_berdampak"
    _narasi_eksekutif = narasi_llm_atau_fallback(_exec_cache_key, ringkasan["narasi"])
    st.info(_narasi_eksekutif)
    penjelasan(
        "Ringkasan ini dihitung ulang tiap dashboard dimuat dari data ter-filter saat itu — "
        "otomatis ikut berubah begitu ada berita baru masuk lewat update mingguan, bukan teks statis."
    )

    # Filter aktif -- dipakai laporan Word (baseline di bawah & versi lengkap
    # setelah drill-down pilar, lihat laporan_word.tombol_unduh_laporan).
    _filter_lines_dampak = [
        f"Mode: {mode}",
        f"Rentang tahun: {tahun_awal}–{tahun_akhir}",
        "Dampak: " + (", ".join(pilar_pilih) if pilar_pilih else "(tidak ada dipilih)"),
        "Tema Kepmen: " + (
            "semua (14 tema)" if len(topik_pilih) == len(LABEL_TOPIC)
            else ", ".join(LABEL_TOPIC.get(k, k) for k in topik_pilih) if topik_pilih
            else "(tidak ada dipilih)"
        ),
    ]
    if unit_pilih:
        _filter_lines_dampak.append(
            "Fakultas/Unit Kerja: " + ", ".join(UNIT_KERJA[k]["nama"] for k in unit_pilih)
        )
    _ringkasan_metrik_df = pd.DataFrame([
        {"Metrik": "Total berita dampak", "Nilai": ringkasan["total_berita"]},
        {"Metrik": "Dampak pertumbuhan tertinggi",
         "Nilai": f"{ringkasan['pilar_top']} ({_pilar_delta_label or 'stabil'})"},
        {"Metrik": f"Sorotan {tahun_akhir}", "Nilai": f"{ringkasan['berita_tahun_ini']:,} berita"},
        {"Metrik": ringkasan["topik_top_kind_label"], "Nilai": ringkasan["topik_top_short"]},
    ])

    # ---------- Overview: 3 pilar dampak, klik satu untuk drill-down ----------
    st.subheader("Overview Dampak UGM")
    st.caption("Klik salah satu dampak di bawah untuk melihat detail tema, tren, dan insight otomatis.")
    st.caption(
        f"📈 Dampak **{ringkasan['pilar_top']}** tumbuh paling cepat "
        f"({_pilar_delta_label or 'stabil'}) sejak {ringkasan['pilar_top_baseline_tahun']} -- "
        "lihat Ringkasan Eksekutif di atas untuk insight lengkapnya."
    )
    st.session_state.setdefault("selected_pilar", None)

    PILAR_ICON = {"Lingkungan": "🌳", "Ekonomi": "💼", "Sosial": "🤝"}
    pilar_order = ["Lingkungan", "Ekonomi", "Sosial"]
    pilar_cards = st.columns(3, gap="medium")
    _overview_pilar_rows = []
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
        _overview_pilar_rows.append({
            "Dampak": pilar, "Total berita": pilar_total,
            "Tema terbanyak": top_theme_name, "Jumlah tema terbanyak": top_theme_n,
        })
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
        # Laporan versi DASAR (Ringkasan Eksekutif + Overview 3 Pilar) -- belum
        # ada drill-down tema/tren karena user belum klik salah satu kartu
        # dampak. Begitu satu dampak dipilih, tombol yang sama muncul lagi di
        # akhir halaman dengan section jauh lebih lengkap (lihat bawah).
        laporan_word.tombol_unduh_laporan(
            key="laporan_dampak_dasar",
            judul=f"Laporan Analisis {mode}",
            subjudul="UGM Analytics -- Analisis Dampak Berita UGM",
            filter_lines=_filter_lines_dampak,
            ringkasan_eksekutif=_narasi_eksekutif,
            seksi=[
                laporan_word.SeksiLaporan("Ringkasan Eksekutif (metrik)", _ringkasan_metrik_df),
                laporan_word.SeksiLaporan(
                    "Overview 3 Pilar Dampak", pd.DataFrame(_overview_pilar_rows),
                    catatan="Klik salah satu kartu dampak di halaman untuk laporan yang lebih lengkap "
                            "(distribusi tema, tren, Kepmen/SDG, dst).",
                ),
            ],
            nama_file_bagian=["Laporan", mode.replace("Berdampak", "Dampak"), tahun_awal, tahun_akhir],
        )
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
        c3.metric("Tahun jangkauan", f"{selected_news['tahun'].min()}–{selected_news['tahun'].max()}")

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
        _insight_topik_p = insight_top2(topik_counts, "label", "jumlah")
        st.info(_insight_topik_p)
        penjelasan("Distribusi jumlah berita per tema pada dampak ini.")

        trend_detail = selected_news.groupby("tahun")["url"].nunique().reset_index(name="jumlah")
        fig_trend = px.line(
            trend_detail, x="tahun", y="jumlah", markers=True,
            title=f"Tren berita per tahun untuk dampak {selected_pilar}",
            labels={"tahun": "Tahun", "jumlah": "Jumlah berita"},
        )
        fig_trend.update_layout(height=360)
        st.plotly_chart(fig_trend, width="stretch")
        _awal_td, _akhir_td = trend_detail.iloc[0], trend_detail.iloc[-1]
        _peak_td = trend_detail.loc[trend_detail["jumlah"].idxmax()]
        _delta_td = int(_akhir_td["jumlah"]) - int(_awal_td["jumlah"])
        _insight_trend_p = (
            f"Dari {int(_awal_td['jumlah']):,} berita ({_awal_td['tahun']}) menjadi "
            f"{int(_akhir_td['jumlah']):,} berita ({_akhir_td['tahun']}) -- "
            f"{'naik' if _delta_td >= 0 else 'turun'} {abs(_delta_td):,} berita. "
            f"Puncak tertinggi: {_peak_td['tahun']} dengan {int(_peak_td['jumlah']):,} berita."
        )
        st.info(_insight_trend_p)
        penjelasan("Tren volume berita dampak ini dari tahun ke tahun.")

        st.markdown("**Daftar tema dalam dampak ini**")
        st.dataframe(
            topik_counts[["label", "jumlah"]].rename(columns={"label": "Tema", "jumlah": "Jumlah berita"}),
            width="stretch", hide_index=True,
        )
        _total_tema_p = int(topik_counts["jumlah"].sum())
        st.info(
            f"{insight_top2(topik_counts, 'label', 'jumlah')} Total keseluruhan "
            f"{_total_tema_p:,} berita di {len(topik_counts)} tema."
        )
        penjelasan(
            "Rincian lengkap semua tema dalam dampak ini, data yang sama dengan "
            "chart distribusi di atas."
        )

    # --- Tab: Tema Resmi Kepmen ---
    dist_k_p = None
    _insight_kepmen_p = ""
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
                title=f"Berita per Tema Resmi Kepmen — dampak {selected_pilar}",
                labels={"topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita"},
                color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
            )
            fig_k_p.update_layout(height=340, showlegend=False)
            hover_keterangan(fig_k_p, "Berita unik yang masuk Tema Resmi Kepmen ini pada dampak terpilih.")
            st.plotly_chart(fig_k_p, width="stretch")
            _insight_kepmen_p = insight_top2(dist_k_p, "topik_kepmen", "jumlah")
            st.info(_insight_kepmen_p)
            penjelasan(
                "Angka = berita unik dari tema dalam dampak ini yang dipetakan ke "
                "Tema Resmi Kepmen ini (pemetaan resmi dari UGM Analytics.xlsx); "
                "beberapa tema bisa memetakan ke Tema Resmi yang sama, jumlahnya digabung."
            )
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
        penjelasan(
            f"Mencakup {len(map_rows_p)} tema resmi Kepmen pada dampak {selected_pilar} -- "
            "pemetaan resmi tema dampak ke Tema Resmi Kepmen, indikator, dan satuan "
            "(UGM Analytics.xlsx & Kepmen 361/M/KEP/2025)."
        )

    # --- Tab: SDGs Terkait ---
    dist_s_p = None
    _insight_sdg_p = ""
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
                    title=f"Berita per SDG — dampak {selected_pilar}",
                    labels={"label": "SDG", "jumlah": "Jumlah berita"},
                    hover_data={"nama": True, "sdg": False, "label": False},
                )
                fig_s_p.update_layout(height=380, showlegend=False,
                                      xaxis=dict(tickangle=-45, tickfont=dict(size=10), automargin=True))
                hover_keterangan(fig_s_p, "Berita unik dampak ini pada klaster SDG tsb.")
                st.plotly_chart(fig_s_p, width="stretch")
                _insight_sdg_p = insight_top2(dist_s_p, "nama", "jumlah")
                st.info(_insight_sdg_p)
                penjelasan(
                    "Angka = berita unik dampak ini yang temanya memetakan ke klaster "
                    "SDG ini (klaster resmi per tema, bukan keyword SDG langsung)."
                )

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
                        title=f"Tema × SDG — dampak {selected_pilar}",
                        labels={"x": "SDG", "y": "Tema", "color": "Berita"},
                        color_continuous_scale="blues",
                    )
                    fig_hm_p.update_xaxes(tickangle=-45, tickfont=dict(size=10), automargin=True)
                    fig_hm_p.update_yaxes(tickfont=dict(size=11), automargin=True)
                    fig_hm_p.update_traces(textfont=dict(size=8))
                    fig_hm_p.update_layout(height=360)
                    hover_keterangan(fig_hm_p, "Berita unik yang masuk tema baris sekaligus SDG kolom, dampak ini.")
                    st.plotly_chart(fig_hm_p, width="stretch")
                    st.info(insight_heatmap(hm_piv_p2))
                    penjelasan(
                        "Sel kosong (0) = tidak ada berita pada kombinasi itu. Baris "
                        "gelap = tema tersebar di banyak SDG; kolom gelap = SDG yang "
                        "paling sering tersentuh."
                    )
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
                title=f"Tema × Tahun — dampak {selected_pilar}",
                labels={"x": "Tahun", "y": "Tema", "color": "Berita"},
                color_continuous_scale="greens",
            )
            fig_h_p.update_xaxes(tickangle=-45, tickfont=dict(size=10), automargin=True)
            fig_h_p.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_h_p.update_traces(textfont=dict(size=8))
            fig_h_p.update_layout(height=340)
            hover_keterangan(fig_h_p, "Berita unik tema ini pada tahun tsb, dampak terpilih.")
            st.plotly_chart(fig_h_p, width="stretch")
            st.info(insight_heatmap(piv_p_ty2))
            penjelasan(
                "Baris gelap = tema yang konsisten diberitakan; kolom gelap = "
                "tahun dengan banyak aktivitas dampak ini."
            )
        else:
            st.info("Tidak cukup data untuk heatmap dampak ini.")

        b_t_pilar_bulan = b_t_pilar.copy()
        b_t_pilar_bulan["bulan"] = b_t_pilar_bulan["tanggal"].str[5:7]
        musim_p = b_t_pilar_bulan.groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
        if len(musim_p):
            musim_p["label"] = musim_p["topik"].map(LABEL_TOPIC)
            fig_m_p = px.bar(
                musim_p, x="bulan", y="jumlah", color="label", barmode="stack",
                title=f"Tren bulanan (musiman) — dampak {selected_pilar}",
                labels={"bulan": "Bulan", "jumlah": "Jumlah berita", "label": "Tema"},
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_m_p.update_layout(height=340)
            hover_keterangan(fig_m_p, "Berita bulan tsb, semua tahun digabung, dampak terpilih.")
            st.plotly_chart(fig_m_p, width="stretch")
            _bulan_sum_p = musim_p.groupby("bulan")["jumlah"].sum().reset_index()
            _bulan_sum_p["label_bulan"] = "Bulan " + _bulan_sum_p["bulan"]
            st.info(insight_top2(_bulan_sum_p, "label_bulan", "jumlah"))
            penjelasan("Bulan kalender, semua tahun digabung. Bulan 01-12 = Januari-Desember.")

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
                    title=f"Keyword pemicu match — {LABEL_TOPIC.get(pilih_kw_p, pilih_kw_p)}",
                    labels={"keyword": "Keyword", "jumlah": "Jumlah berita"},
                    color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
                )
                fig_kw_p.update_layout(height=max(300, 30 * len(kw_df_p) + 80),
                                       yaxis=dict(autorange="reversed"), showlegend=False)
                st.plotly_chart(fig_kw_p, width="stretch")
                st.info(insight_top2(kw_df_p, "keyword", "jumlah"))
                penjelasan(
                    "Angka = berita yang judul/deskripsinya mengandung keyword tsb; "
                    "satu berita bisa match beberapa keyword, jadi totalnya bisa "
                    "melebihi jumlah berita tema."
                )
            else:
                st.info("Tidak ada match keyword untuk tema ini.")

            st.markdown("**Kata yang paling sering muncul**")
            freq_p = token_freq(sub_p)
            freq_df_p = pd.DataFrame(freq_p.most_common(15), columns=["kata", "jumlah"])
            if len(freq_df_p):
                fig_wf_p = px.bar(
                    freq_df_p, x="jumlah", y="kata", orientation="h",
                    title=f"15 kata teratas — {LABEL_TOPIC.get(pilih_kw_p, pilih_kw_p)}",
                    labels={"kata": "Kata", "jumlah": "Frekuensi"},
                    color_discrete_sequence=[WARNA_PILAR[selected_pilar]],
                )
                fig_wf_p.update_layout(height=420, yaxis=dict(autorange="reversed"), showlegend=False)
                st.plotly_chart(fig_wf_p, width="stretch")
                st.info(insight_top2(freq_df_p, "kata", "jumlah", satuan="kali"))
                penjelasan(
                    "Kata di judul + deskripsi berita tema tsb (stopword dibuang, "
                    "kata umum seperti 'ugm'/'universitas' sengaja dibuang)."
                )

        st.markdown("**Daftar berita — dampak ini**")
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
        df_p["Tema Kepmen"] = df_p["url"].map(kepmen_by_url_p).fillna("—")
        df_p["SDG"] = df_p["url"].map(sdg_by_url_p).fillna("—")
        df_p = df_p.sort_values("tanggal", ascending=False)
        if len(df_p):
            tampil_p = df_p[["tanggal", "judul", "Tema Kepmen", "SDG", "sumber"]].copy()
            tampil_p.columns = ["Tanggal", "Judul", "Tema Kepmen", "SDG", "Sumber"]
            st.dataframe(tampil_p, width="stretch", hide_index=True)
            _terbaru_p = df_p.iloc[0]
            penjelasan(
                f"Berita terbaru: \"{_terbaru_p['judul']}\" ({_terbaru_p['tanggal']}). "
                "Daftar diurutkan dari yang terbaru, lengkap dengan Tema Kepmen & SDG "
                "yang terdeteksi -- untuk menelusuri berita sumber di balik "
                "angka-angka pada tab lain."
            )
        else:
            st.info("Tidak ada berita untuk dampak ini pada filter saat ini.")

    # --- Tab: Fakultas/Unit Kerja ---
    dist_uk = None
    _insight_uk_p = ""
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
            _insight_uk_p = insight_top2(dist_uk, "nama", "jumlah")
            st.info(_insight_uk_p)

            n_unit_unik = uk_pilar["unit_kerja"].nunique()
            st.metric("Unit teridentifikasi", f"{n_unit_unik} / {len(UNIT_KERJA)}")

            _csv_uk_p = (
                dist_uk[["nama", "kategori", "jumlah"]]
                .rename(columns={"nama": "Fakultas/Unit Kerja", "kategori": "Kategori", "jumlah": "Jumlah berita"})
                .sort_values("Jumlah berita", ascending=False)
                .to_csv(index=False)
                .encode("utf-8")
            )
            st.download_button(
                "⬇️ Unduh hasil per Fakultas/Unit Kerja (CSV)",
                data=_csv_uk_p,
                file_name=f"berita_per_unit_kerja_dampak_{selected_pilar.lower()}.csv",
                mime="text/csv",
                key=f"dl_unit_{selected_pilar}_{mode}",
            )
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

    # Default None -- diisi di dalam expander di bawah kalau datanya ada;
    # dipakai laporan Word lengkap di akhir fungsi (lihat laporan_word di bawah).
    dist_k = dist_s = rp_f = piv2 = tren = musim_sum = gab = None
    _insight_kepmen = _insight_sdg = _insight_rp = _insight_tematahun = ""
    _insight_trentahunan = _insight_musiman = _insight_cakupan = ""
    with st.expander("📂 Analisis Lintas-Dampak (Lanjutan)", expanded=False):
        st.subheader("Ringkasan")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total berita (filter)", len(b))
        c2.metric("Berita bertema dampak", t["url"].nunique() if len(t) else 0)
        c3.metric("Tema terpilih", len(topik_pilih))
        c4.metric("Rentang tahun", f"{tahun_awal}–{tahun_akhir}")
        penjelasan(
            "Ringkasan parameter filter yang sedang aktif untuk semua chart di "
            "bagian 'Analisis Lintas-Dampak' ini."
        )

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
            _top_k = dist_k.loc[dist_k["jumlah"].idxmax()]
            _insight_kepmen = (
                f"Tema Resmi Kepmen teratas: **{_top_k['topik_kepmen']}** (dampak "
                f"{_top_k['dampak']}) dengan {int(_top_k['jumlah']):,} berita. Angka = "
                "berita unik dari tema dampak yang dipetakan ke Tema Resmi ini "
                "(pemetaan resmi dari UGM Analytics.xlsx); beberapa tema dampak bisa "
                "memetakan ke Tema Resmi yang sama, jumlahnya digabung."
            )
            penjelasan(_insight_kepmen)
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
            _top_sdg = dist_s.loc[dist_s["jumlah"].idxmax()]
            _insight_sdg = (
                f"SDG paling banyak disentuh: **{_top_sdg['nama']}** "
                f"dengan {int(_top_sdg['jumlah']):,} berita. Angka = berita unik bertema "
                "yang temanya memetakan ke klaster SDG ini (klaster resmi per tema, "
                "bukan keyword SDG langsung)."
            )
            penjelasan(_insight_sdg)

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
                _stack = hm_piv2.stack()
                _max_idx = _stack.idxmax()
                penjelasan(
                    f"Kombinasi tertinggi: **{_max_idx[0]} × {_max_idx[1]}** dengan "
                    f"{int(_stack.max()):,} berita. Sel kosong (0) = tidak ada berita "
                    "pada kombinasi itu. Baris gelap = tema tersebar di banyak SDG; "
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
                _sdg_total = sdg_tahun.groupby("label")["jumlah"].sum()
                penjelasan(
                    f"SDG dengan total tertinggi sepanjang periode: **{_sdg_total.idxmax()}** "
                    f"({int(_sdg_total.max()):,} berita). Angka = berita unik bertema yang "
                    "SDG-nya tercatat pada tahun publikasi tsb; garis naik = perhatian "
                    "terhadap SDG makin sering diberitakan."
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
                _row_sums_dt = piv_p.sum(axis=1)
                _col_sums_dt = piv_p.sum(axis=0)
                penjelasan(
                    f"Dampak paling dominan: **{_row_sums_dt.idxmax()}** "
                    f"({int(_row_sums_dt.max()):,} berita total); tahun paling aktif: "
                    f"**{_col_sums_dt.idxmax()}** ({int(_col_sums_dt.max()):,} berita)."
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
                _top_rp = rp_f.loc[rp_f["jumlah_berita"].idxmax()]
                _insight_rp = (
                    f"Dampak dengan berita terbanyak: **{_top_rp['dampak']}** "
                    f"({int(_top_rp['jumlah_berita']):,} berita). Total berita unik per "
                    "dampak (semua tema dalam dampak digabung, URL dideduplikasi per dampak)."
                )
                penjelasan(_insight_rp)
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
            _row_sums2 = piv2.sum(axis=1)
            _col_sums2 = piv2.sum(axis=0)
            _insight_tematahun = (
                f"Tema paling konsisten diberitakan: **{_row_sums2.idxmax()}** "
                f"({int(_row_sums2.max()):,} berita total); tahun paling aktif: "
                f"**{_col_sums2.idxmax()}** ({int(_col_sums2.max()):,} berita)."
            )
            penjelasan(_insight_tematahun)
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
        _tren_total = tren.groupby("label")["jumlah"].sum()
        _insight_trentahunan = (
            f"Tema dengan total berita tertinggi sepanjang periode: "
            f"**{_tren_total.idxmax()}** ({int(_tren_total.max()):,} berita). Angka = "
            "jumlah berita per tema-tahun; berita yang masuk beberapa tema dihitung "
            "di tiap tema."
        )
        penjelasan(_insight_trentahunan)

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
        musim_sum = musim.groupby(["bulan", "label"])["jumlah"].sum().reset_index()
        _bulan_sum = musim.groupby("bulan")["jumlah"].sum()
        _insight_musiman = (
            f"Bulan paling ramai (semua tema & tahun): **{_bulan_sum.idxmax()}** "
            f"dengan {int(_bulan_sum.max()):,} berita. Bulan 01-12 = Januari-Desember."
        )
        penjelasan(_insight_musiman)

        # ---------- Cakupan vs total berita UGM ----------
        st.subheader("Cakupan vs Total Berita UGM per Tahun")
        sitemap = sitemap.copy()
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
        _total_all = int(gab["total"].sum())
        _total_matched = int(gab["bertopik"].sum())
        _pct_matched = 100 * _total_matched / _total_all if _total_all else 0
        _insight_cakupan = (
            f"Sepanjang {tahun_awal}–{tahun_akhir}: dari {_total_all:,} total berita "
            f"UGM, {_total_matched:,} ({_pct_matched:.1f}%) terdeteksi tema dampak. "
            "Garis abu-abu = seluruh URL di sitemap ugm.ac.id per tahun (baseline). "
            "Garis hijau = berita yang match tema dampak; nilainya lower-bound karena "
            "pencocokan keyword terbatas pada 14 tema Kepmen yang dideteksi."
        )
        st.caption(f"💡 {_insight_cakupan}")

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
                _top_kw = sub_kw.iloc[-1]
                penjelasan(
                    f"Keyword paling sering memicu match pada tema ini: "
                    f"**{_top_kw['keyword']}** ({int(_top_kw['jumlah']):,} berita). Satu "
                    "berita bisa match beberapa keyword, jadi totalnya bisa melebihi "
                    "jumlah berita tema."
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
        _single_n = int(dist_n.loc[dist_n["jumlah tema"] == 1, "berita"].sum()) if 1 in dist_n["jumlah tema"].values else 0
        _total_n = int(dist_n["berita"].sum())
        _multi_pct = 100 * (_total_n - _single_n) / _total_n if _total_n else 0
        penjelasan(
            f"{_multi_pct:.1f}% berita masuk lebih dari satu tema (lintas-tema). Bar "
            "paling kiri = berita yang hanya masuk satu tema; semakin ke kanan, "
            "semakin lintas-tema berita tersebut."
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
            _top_kombo = kombo.loc[kombo["jumlah"].idxmax()]
            penjelasan(
                f"Berita dengan tema terbanyak sekaligus: {int(_top_kombo['jumlah'])} tema "
                f"({_top_kombo['kombinasi']}) -- rincian aktual dari bar multi-tema di atas."
            )
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
        _top_kata = freq_df.iloc[0]
        penjelasan(
            f"Kata paling sering muncul: **{_top_kata['kata']}** "
            f"({int(_top_kata['jumlah']):,} kali) di judul + deskripsi berita tema tsb "
            "(stopword dibuang, kata umum seperti 'ugm'/'universitas' sengaja dibuang)."
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
            _terbaru = df.iloc[0]
            penjelasan(
                f"Berita terbaru: \"{_terbaru['judul']}\" ({_terbaru['tanggal']}). Daftar "
                "seluruh berita pada filter saat ini, diurutkan dari yang terbaru, "
                "lengkap dengan Tema Kepmen, Indikator Kepmen, dan SDG yang terdeteksi "
                "-- untuk menelusuri berita sumber di balik semua angka pada halaman ini."
            )
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

    # ---------- Unduh Laporan (Word) -- versi LENGKAP (drill-down + lintas-dampak) ----------
    _seksi_dampak = [
        laporan_word.SeksiLaporan("Ringkasan Eksekutif (metrik)", _ringkasan_metrik_df),
        laporan_word.SeksiLaporan(
            "Overview 3 Pilar Dampak", pd.DataFrame(_overview_pilar_rows)),
        laporan_word.SeksiLaporan(
            f"Distribusi Tema — Dampak {selected_pilar}",
            topik_counts[["label", "jumlah"]].rename(
                columns={"label": "Tema", "jumlah": "Jumlah berita"}),
            _insight_topik_p,
        ),
        laporan_word.SeksiLaporan(
            f"Tren per Tahun — Dampak {selected_pilar}",
            trend_detail.rename(columns={"tahun": "Tahun", "jumlah": "Jumlah berita"}),
            _insight_trend_p,
        ),
    ]
    if dist_k_p is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            f"Tema Resmi Kepmen — Dampak {selected_pilar}",
            dist_k_p.rename(columns={"topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita"})
            .sort_values("Jumlah berita", ascending=False),
            _insight_kepmen_p,
        ))
    if dist_s_p is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            f"SDG Terkait — Dampak {selected_pilar}",
            dist_s_p[["label", "nama", "jumlah"]].rename(
                columns={"label": "SDG", "nama": "Nama", "jumlah": "Jumlah berita"}
            ).sort_values("Jumlah berita", ascending=False),
            _insight_sdg_p,
        ))
    if dist_uk is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            f"Fakultas/Unit Kerja — Dampak {selected_pilar}",
            dist_uk[["nama", "kategori", "jumlah"]].rename(
                columns={"nama": "Fakultas/Unit Kerja", "kategori": "Kategori", "jumlah": "Jumlah berita"}
            ).sort_values("Jumlah berita", ascending=False),
            _insight_uk_p,
        ))
    if dist_k is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Peta Tema Resmi Kepmen (lintas-dampak)",
            dist_k.rename(columns={"dampak": "Dampak", "topik_kepmen": "Tema Resmi Kepmen", "jumlah": "Jumlah berita"})
            .sort_values("Jumlah berita", ascending=False),
            _insight_kepmen,
        ))
    if dist_s is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Klaster SDGs (lintas-dampak)",
            dist_s[["label", "nama", "jumlah"]].rename(
                columns={"label": "SDG", "nama": "Nama", "jumlah": "Jumlah berita"}
            ).sort_values("Jumlah berita", ascending=False),
            _insight_sdg,
        ))
    if rp_f is not None and len(rp_f):
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Ringkasan per Dampak (Sosial/Ekonomi/Lingkungan)",
            rp_f.rename(columns={"dampak": "Dampak", "jumlah_berita": "Jumlah berita"}),
            _insight_rp,
        ))
    if piv2 is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Heatmap Tema × Tahun (semua dampak)",
            piv2.reset_index(names="Tema"), _insight_tematahun,
        ))
    if tren is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Tren Tahunan per Tema (semua dampak)",
            tren[["tahun", "label", "jumlah"]].rename(
                columns={"tahun": "Tahun", "label": "Tema", "jumlah": "Jumlah berita"}),
            _insight_trentahunan,
        ))
    if musim_sum is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Tren Bulanan / Musiman (semua dampak)",
            musim_sum.rename(columns={"bulan": "Bulan", "label": "Tema", "jumlah": "Jumlah berita"}),
            _insight_musiman,
        ))
    if gab is not None:
        _seksi_dampak.append(laporan_word.SeksiLaporan(
            "Cakupan vs Total Berita UGM per Tahun",
            gab.rename(columns={"tahun": "Tahun", "total": "Total berita (sitemap)",
                                 "bertopik": "Berita bertema dampak"}),
            _insight_cakupan,
        ))

    laporan_word.tombol_unduh_laporan(
        key="laporan_dampak_lengkap",
        judul=f"Laporan Analisis {mode}",
        subjudul=f"Dampak {selected_pilar} -- UGM Analytics",
        filter_lines=_filter_lines_dampak + [f"Dampak dipilih (drill-down): {selected_pilar}"],
        ringkasan_eksekutif=_narasi_eksekutif,
        seksi=_seksi_dampak,
        nama_file_bagian=["Laporan", mode.replace("Berdampak", "Dampak"), selected_pilar, tahun_awal, tahun_akhir],
    )
