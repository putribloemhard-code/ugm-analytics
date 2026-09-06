"""Halaman Beranda -- landing page dashboard analisis dampak UGM."""

import streamlit as st

from common import inject_css, penjelasan
from data_loader import load_ringkasan_beranda

inject_css()

try:
    ringkasan_beranda = load_ringkasan_beranda()
except Exception as e:
    st.error(f"Gagal membaca ringkasan data dari MySQL: {e}")
    st.stop()

total_berita = ringkasan_beranda["total_berita"]
n_dampak = ringkasan_beranda["n_dampak"]
total_sitemap = ringkasan_beranda["total_sitemap"]
cakupan_pct = (100 * n_dampak / total_sitemap) if total_sitemap else 0.0

st.markdown(
    f"""
    <style>
    /* Hero Beranda -- gradient biru-emas UGM, warna tetap (tidak ikut tema
       light/dark Streamlit) supaya kontras teks putih selalu aman. CSS ini
       SENGAJA dibundel di sini (bukan di common.py) supaya render-nya tidak
       bergantung pada tag <style> global yang di-inject terpisah sebelumnya
       -- lebih tahan banting terhadap isu cache/urutan render browser. */
    .hero {{
        position: relative;
        overflow: hidden;
        border-radius: 24px;
        padding: 52px 32px 40px;
        margin-bottom: 28px;
        text-align: center;
        background: linear-gradient(135deg, #001a4d 0%, #00308f 48%, #0a5ca8 100%);
        color: #fff;
    }}
    .hero::before {{
        content: "";
        position: absolute;
        top: -70px; right: -70px;
        width: 240px; height: 240px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,199,44,0.35), transparent 70%);
    }}
    .hero::after {{
        content: "";
        position: absolute;
        bottom: -90px; left: -60px;
        width: 220px; height: 220px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.08), transparent 70%);
    }}
    .hero-badge {{
        position: relative;
        display: inline-block;
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 999px;
        padding: 5px 16px;
        margin-bottom: 18px;
        color: #fff;
    }}
    .hero-title {{
        position: relative;
        font-size: 2.5rem; font-weight: 800; line-height: 1.18;
        margin: 0 0 14px;
        color: #fff;
    }}
    .hero-title .accent {{ color: #ffc72c; }}
    .hero-subtitle {{
        position: relative;
        font-size: 1.02rem; line-height: 1.65; opacity: 0.92;
        max-width: 620px; margin: 0 auto 32px;
        color: #fff;
    }}
    .hero-search {{
        position: relative;
        max-width: 620px; margin: 0 auto; display: flex; align-items: center;
        background: #fff; border-radius: 999px;
        padding: 6px 6px 6px 22px;
        box-shadow: 0 14px 34px rgba(0,10,40,0.35);
    }}
    .hero-search-icon {{ color: #8a8a8a; margin-right: 12px; font-size: 1.05rem; }}
    .hero-search-placeholder {{
        flex: 1; text-align: left; color: #8a8a8a; font-size: 0.92rem;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }}
    .hero-search-btn {{
        background: #ffc72c; color: #1a1a1a; font-weight: 700;
        padding: 12px 26px; border-radius: 999px; font-size: 0.85rem;
        white-space: nowrap;
    }}
    .hero-stat {{
        position: relative;
        margin-top: 20px; font-size: 0.88rem; opacity: 0.85;
        color: #fff;
    }}
    </style>
    <div class="hero">
        <div class="hero-badge">🎓 Universitas Gadjah Mada</div>
        <div class="hero-title">Analisis <span class="accent">Dampak</span> UGM</div>
        <div class="hero-subtitle">
            Platform analisis berita untuk memetakan dampak UGM terhadap Lingkungan,
            Ekonomi, dan Sosial (Kepmendikti Saintek 361/M/KEP/2025), keterkaitannya
            dengan 17 SDGs, serta kesiapan data untuk akreditasi.
        </div>
        <div class="hero-search">
            <span class="hero-search-icon">🔍</span>
            <span class="hero-search-placeholder">Mau analisis apa? mis. "dampak lingkungan 2024", "SDG 4 pendidikan"...</span>
            <span class="hero-search-btn">Cari</span>
        </div>
        <div class="hero-stat">👥 {total_berita:,} berita dianalisis &nbsp;·&nbsp; {n_dampak:,} bertema dampak &nbsp;·&nbsp; {cakupan_pct:.1f}% cakupan</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Pencarian pintar belum aktif di versi ini (segera hadir) -- gunakan menu "
    "navigasi di sidebar atau kartu pintasan di bawah untuk sekarang."
)

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="medium")
kartu = [
    (col1, "🌍", "Analisis Dampak Universitas",
     "3 dampak (Lingkungan, Ekonomi, Sosial) & 14 tema resmi Kepmen, "
     "opsional dikombinasikan dengan SDGs.",
     "pages_app/dampak_sdgs.py"),
    (col2, "🎯", "SDGs",
     "Mapping langsung seluruh berita UGM ke 17 SDG -- jangkauan paling luas.",
     "pages_app/sdgs.py"),
    (col3, "📄", "Akreditasi",
     "Filter data & generate laporan akreditasi siap unduh (Word).",
     "pages_app/akreditasi.py"),
]
for col, icon, judul, desk, target in kartu:
    with col:
        st.markdown(
            f"""
            <div class="home-card">
                <div class="home-card-icon">{icon}</div>
                <div class="home-card-title">{judul}</div>
                <div class="home-card-desc">{desk}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Buka →", key=f"home_{judul}", use_container_width=True):
            st.switch_page(target)

st.markdown("---")
st.subheader("Sekilas Data")

c1, c2, c3 = st.columns(3)
c1.metric("Total berita dianalisis", f"{total_berita:,}")
c2.metric("Berita bertema dampak", f"{n_dampak:,}")
c3.metric("Cakupan dampak", f"{cakupan_pct:.1f}%")
penjelasan(
    "Total berita = seluruh berita RSS+sitemap di database. Berita bertema "
    "dampak = berita unik yang match salah satu dari 14 tema resmi Kepmen "
    "361/M/KEP/2025. Cakupan dampak = proporsi berita bertema dampak "
    "terhadap seluruh URL sitemap ugm.ac.id (lower-bound, sama seperti "
    "chart \"Cakupan vs Total Berita UGM\" di halaman Analisis Dampak Universitas)."
)
