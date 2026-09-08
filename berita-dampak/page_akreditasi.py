"""Logika + UI halaman "Akreditasi" (berita-dampak) -- versi gabungan.

Konten UTAMA: dashboard kelengkapan data LED & LKPS (49 item, registry
`akreditasi/docs/Data_Requirements_LED_LKPS_MEI.md`), dipisah sebagai dua MODE dokumen
(selector LED/LKPS di atas -- LED per Kriteria A-D, LKPS per Bagian 1-6,
lihat docstring registry_kebutuhan_data.py poin 6) -- REUSE LANGSUNG modul
dari subproyek akreditasi/ (../akreditasi/scripts/dashboard_render.py,
registry_kebutuhan_data.py, generate_template.py) lewat sys.path, BUKAN
disalin -- supaya satu sumber kebenaran & satu tabel MySQL
(akreditasi_data_manual): data yang diisi lewat halaman ini ATAU lewat
app akreditasi/ yang berdiri sendiri sama-sama muncul di keduanya.

Konten TAMBAHAN: "Lampiran: Data Dampak & SDG" -- ringkasan eksekutif +
chart per pilar + chart SDG dari data dampak/SDG milik berita-dampak
sendiri (filter tahun/dampak/fakultas sendiri, inline di dalam bagian ini
-- BUKAN di sidebar, supaya tidak tercampur dengan filter halaman lain),
dilampirkan di bawah dashboard LED/LKPS dan ikut disisipkan ke dokumen
Word yang digenerate.
"""

import sys
from pathlib import Path

import streamlit as st

from common import PILAR_ICON_SIDEBAR, WARNA_PILAR, UNIT_KERJA, hover_keterangan, load_data_or_stop, penjelasan
from scripts.narasi_logic import generate_executive_summary

_FAKULTAS_OPSI = sorted(
    (k for k, v in UNIT_KERJA.items() if v["kategori"] in ("Fakultas", "Sekolah")),
    key=lambda k: UNIT_KERJA[k]["nama"],
)

_AKREDITASI_SCRIPTS = Path(__file__).resolve().parents[1] / "akreditasi" / "scripts"
sys.path.insert(0, str(_AKREDITASI_SCRIPTS))

CATATAN_METODOLOGI = """\
Angka pada bagian Dampak & SDG adalah hasil keyword matching (substring, case-insensitive) pada judul, deskripsi, dan isi lengkap berita terhadap 14 tema resmi Kepmen 361/M/KEP/2025 dan pemetaan SDG resmi per tema -- BUKAN hasil sensus/audit lengkap seluruh aktivitas dampak UGM.

Sifat lower-bound: berita yang secara substansi relevan tapi tidak menyebut kata kunci yang terdaftar TIDAK ikut terhitung. Cakupan aktual dampak UGM kemungkinan lebih besar dari angka yang ditampilkan di sini.

Klaster SDG pada bagian ini adalah atribut TEMA (seluruh berita dalam satu tema membawa SDG yang sama sesuai pemetaan resmi UGM Analytics.xlsx), bukan hasil pencocokan kata kunci SDG langsung ke teks tiap berita -- lihat halaman "SDGs" untuk mapping langsung berbasis teks.

Sumber data: RSS (ugm.ac.id/id/feed, ugm.ac.id/en/feed) dan sitemap (ugm.ac.id/wp-sitemap.xml). Data diperbarui mingguan; angka merefleksikan kondisi data saat laporan digenerate, bukan snapshot statis.
"""


def _render_lampiran_dampak_sdg():
    """Render preview di halaman + return semua data yang dibutuhkan untuk
    disisipkan ke dokumen Word (lihat pemanggil di render())."""
    import plotly.express as px

    (berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt, uk), _NARASI_CACHE = (
        load_data_or_stop()
    )

    st.caption("Filter Lampiran Dampak & SDG:")
    tahun_opsi = sorted(
        berita["tanggal"].dropna().str[:4].unique()
    ) if len(berita) else ["2005", "2026"]
    fcol1, fcol2, fcol3 = st.columns([1.3, 1.6, 1.3])
    with fcol1:
        tahun_awal, tahun_akhir = st.select_slider(
            "Rentang tahun (Lampiran)",
            options=tahun_opsi,
            value=(tahun_opsi[0], tahun_opsi[-1]),
        )
    with fcol2:
        pilar_pilih = st.multiselect(
            "Dampak (Lampiran)",
            options=["Lingkungan", "Ekonomi", "Sosial"],
            default=["Lingkungan", "Ekonomi", "Sosial"],
            format_func=lambda p: f"{PILAR_ICON_SIDEBAR[p]} {p}",
        )
    with fcol3:
        fakultas_pilih = st.selectbox(
            "Fakultas/Sekolah (Lampiran)",
            options=["Seluruh Universitas"] + _FAKULTAS_OPSI,
            format_func=lambda k: k if k == "Seluruh Universitas" else UNIT_KERJA[k]["nama"],
        )

    b = berita.copy()
    b["tahun"] = b["tanggal"].str[:4]
    b = b[b["tahun"].between(tahun_awal, tahun_akhir)]
    if fakultas_pilih != "Seluruh Universitas":
        # uk = berita_unit_kerja (url<->unit_kerja, lihat scripts/tag_unit_kerja.py) --
        # sama pola dengan filter "Fakultas / Unit Kerja" di page_dampak.py.
        b = b[b["url"].isin(set(uk.loc[uk["unit_kerja"] == fakultas_pilih, "url"]))]
    t = bk[bk["dampak"].isin(pilar_pilih)] if pilar_pilih else bk
    if len(b) and len(t):
        t = t[t["url"].isin(set(b["url"]))]

    if len(b) == 0 or len(t) == 0:
        st.warning("Tidak ada data Dampak/SDG untuk filter Lampiran ini. Ubah filter di atas.")
        return None

    urls_t = set(b.merge(t, on="url", how="inner")["url"])
    bk_f = t[t["url"].isin(urls_t)].copy()
    bs_f = bs[bs["url"].isin(urls_t)].copy()
    # rp_f DIREKONSTRUKSI dari bk_f (url-level, sudah kena filter tahun+pilar+
    # fakultas), BUKAN dipotong dari tabel pre-agregat statis `rp` -- rp tidak
    # punya kolom tahun/fakultas, jadi kalau tetap dipakai, filter Fakultas
    # (dan tahun) di atas TIDAK akan tercermin di chart "Dampak per Pilar".
    if len(bk_f):
        rp_f = bk_f.groupby("dampak")["url"].nunique().reset_index(name="jumlah_berita")
    else:
        rp_f = rp.iloc[0:0]

    ringkasan = generate_executive_summary(b, t, bs_f, "Berdampak × SDGs", tahun_awal, tahun_akhir)

    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Total berita dampak", f"{ringkasan['total_berita']:,}")
    rc2.metric("Dampak pertumbuhan tertinggi", ringkasan["pilar_top"])
    rc3.metric(f"Sorotan {tahun_akhir}", f"{ringkasan['berita_tahun_ini']:,} berita")
    rc4.metric(ringkasan["topik_top_kind_label"], ringkasan["topik_top_short"])
    st.info(ringkasan["narasi"])
    penjelasan(
        "Ringkasan ini dihitung ulang dari data ter-filter saat halaman dimuat -- "
        "sama seperti Ringkasan Eksekutif di halaman Dampak/Dampak × SDGs."
    )

    st.markdown("**Dampak per Pilar**")
    if len(rp_f):
        fig_rp = px.bar(
            rp_f, x="dampak", y="jumlah_berita", color="dampak",
            title="Berita unik per dampak (semua tema Kepmen)",
            labels={"dampak": "Dampak", "jumlah_berita": "Jumlah berita"},
            color_discrete_map=WARNA_PILAR,
        )
        fig_rp.update_layout(height=340, showlegend=False)
        hover_keterangan(fig_rp, "Berita unik di semua tema dalam dampak ini.")
        st.plotly_chart(fig_rp, width="stretch")
    else:
        st.info("Tidak ada data dampak untuk filter ini.")

    st.markdown("**Keterkaitan dengan SDGs**")
    if len(bs_f):
        dist_s = bs_f.groupby("sdg")["url"].nunique().reset_index(name="jumlah").sort_values("jumlah")
        dist_s["label"] = dist_s["sdg"].map(lambda s: f"SDG {s}")
        fig_s = px.bar(
            dist_s, x="label", y="jumlah", color="sdg",
            title="Jumlah berita per SDG (klaster resmi)",
            labels={"label": "SDG", "jumlah": "Jumlah berita"},
        )
        fig_s.update_layout(height=340, showlegend=False,
                            xaxis=dict(tickangle=-45, tickfont=dict(size=10)))
        hover_keterangan(fig_s, "Berita unik pada klaster SDG ini.")
        st.plotly_chart(fig_s, width="stretch")
    else:
        st.info("Tidak ada data SDG untuk filter ini.")

    with st.expander("📋 Catatan Metodologi & Batasan (Dampak & SDG)"):
        st.markdown(CATATAN_METODOLOGI)

    return {
        "b": b, "bk_f": bk_f, "bs_f": bs_f, "rp_f": rp_f,
        "tahun_awal": tahun_awal, "tahun_akhir": tahun_akhir, "pilar_pilih": pilar_pilih,
        "fakultas_pilih": fakultas_pilih, "ringkasan": ringkasan,
    }


def render() -> None:
    scope = st.selectbox(
        "Lingkup akreditasi",
        options=["Akreditasi Program Studi", "Akreditasi Universitas"],
        key="akreditasi_scope",
    )
    if scope == "Akreditasi Universitas":
        st.info(
            "Instrumen akreditasi Universitas (BAN-PT — LED APT/LKPT) berbeda struktur dari "
            "instrumen Program Studi (LAM-INFOKOM — LED/LKPS) yang sudah dibangun di sini. "
            "Dokumen requirement untuk instrumen institusi ini belum tersedia di "
            "akreditasi/docs/. Fitur ini akan dikembangkan setelah dokumen requirement "
            "LED APT/LKPT disiapkan."
        )
        st.stop()

    import dashboard_render as dr  # dari akreditasi/scripts (bare import, lihat sys.path di atas)
    from registry_kebutuhan_data import led_items_by_kriteria, lkps_items_by_bagian  # bare import

    if not dr.ensure_ready():
        st.stop()

    engine = dr.get_engine()
    df_manual = dr.load_data_manual()

    dr.consume_pending_switch()
    mode = st.selectbox(
        "Pilih dokumen",
        options=["LED", "LKPS"],
        key="akreditasi_dokumen",
        format_func=lambda m: "📘 LED — Laporan Evaluasi Diri" if m == "LED" else "📗 LKPS — Laporan Kinerja Program Studi",
    )
    grouped = led_items_by_kriteria() if mode == "LED" else lkps_items_by_bagian()
    item_ids = [item["id"] for items in grouped.values() for item in items]
    _ringkasan, filled_ids = dr.render_ringkasan_atas(df_manual, item_ids=item_ids)

    st.markdown("---")
    if mode == "LED":
        st.subheader(f"Kelengkapan Data LED ({_ringkasan['total']} item)")
        st.caption(
            "Narasi evaluatif per Kriteria A-D (siklus PPEPP), sesuai dokumen kebutuhan data yang terdaftar "
            "di registry. Tiap tab Kriteria A/B/C1-C6 juga menampilkan cuplikan tabel LKPS terkait sebagai bukti evaluasi."
        )
        dr.render_tabs_led(engine, df_manual, filled_ids)
    else:
        st.subheader(f"Kelengkapan Data LKPS ({_ringkasan['total']} item)")
        st.caption(
            "Tabel data mentah per Bagian 1-6, sesuai dokumen kebutuhan data yang terdaftar di registry. "
            "Isi form di tiap tabel berstatus \"perlu input manual\" -- tersimpan langsung ke MySQL "
            "(tabel bersama dengan app akreditasi/)."
        )
        dr.render_tabs_lkps(engine, df_manual, filled_ids)

    st.markdown("---")
    st.subheader("📎 Lampiran: Data Dampak & SDG (Berita-Dampak)")
    st.caption(
        "Data dampak/SDG yang sudah dianalisis berita-dampak -- dilampirkan sebagai konteks "
        "pendukung tambahan (relevan mis. untuk narasi Kriteria A, C3 Penelitian, C4 PkM), "
        "terlepas dari mode LED/LKPS yang aktif di atas."
    )
    lampiran_data = _render_lampiran_dampak_sdg()

    st.markdown("---")
    st.subheader(f"📄 Generate Laporan {mode} (Word)")
    st.caption(
        f"Satu dokumen: kelengkapan data {mode} (cover, ringkasan & to-do, isi per "
        f"{'Kriteria' if mode == 'LED' else 'Bagian'}) + Lampiran Data Dampak & SDG di bagian akhir."
    )
    if st.button(f"🔄 Generate Laporan {mode} (Word)", type="primary"):
        from generate_template import generate_led_docx, generate_lkps_docx  # dari akreditasi/scripts (bare import)

        with st.spinner("Membuat dokumen (termasuk render chart)..."):
            docx_bytes = generate_led_docx(engine) if mode == "LED" else generate_lkps_docx(engine)
            if lampiran_data is not None:
                from scripts.generate_akreditasi_docx import append_lampiran  # scripts/ milik berita-dampak sendiri

                docx_bytes = append_lampiran(docx_bytes, catatan_metodologi=CATATAN_METODOLOGI, **lampiran_data)
        st.download_button(
            f"⬇️ Unduh Laporan_Akreditasi_{mode}.docx",
            data=docx_bytes,
            file_name=f"Laporan_Akreditasi_{mode}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
