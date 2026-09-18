"""Halaman Beranda -- landing page dashboard analisis dampak UGM."""

import streamlit as st

from common import data_uri_ikon, inject_css, penjelasan
from data_loader import load_ringkasan_beranda
from pencarian import HALAMAN, parse, simpan_hasil

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
    """
    <style>
    /* Hero Beranda -- gambar static/hero_bg.jpg (sumber: sumber/picture/
       background.png, 2170x725 = rasio ~3:1), warna tetap (tidak ikut tema
       light/dark Streamlit) supaya kontras teks putih selalu aman.

       Hero adalah st.container(key="hero") -> div.st-key-hero, BUKAN <div>
       HTML sendiri: kotak pencarian di dalamnya harus widget Streamlit
       sungguhan (st.form), dan widget tidak bisa ditaruh di dalam string HTML.
       Versi lama memakai <div class="hero"> dgn kotak pencarian palsu.

       - FULL-BLEED: hero membentang selebar SELURUH area utama (tepi sidebar
         s/d tepi kanan layar), lepas dari block-container Streamlit yang
         dibatasi max-width + padding. Caranya: section stMain dijadikan query
         container, hero diberi width 100cqw (= lebar stMain) dan margin-left
         calc(50% - 50cqw) (= minus gutter kiri; block-container selalu di
         tengah stMain, jadi gutter kiri = kanan). Padding kiri-kanan = gutter
         + 32px -> teks tetap SEJAJAR kolom konten di bawahnya. Pakai cqw,
         BUKAN 100vw: 100vw ikut menghitung lebar sidebar & scrollbar sehingga
         hero meluber ke bawah sidebar dan memunculkan scroll horizontal.
       - background-size: cover + position: center -> selalu penuh,
         proporsional (tidak gepeng), kelebihan terpotong rapi.
       - Konten di sisi KIRI (area gambar yang gelap & kosong). Overlay
         gradien tipis dari kiri menjaga kontras teks walau gambar terpotong;
         kanan dibiarkan bening supaya siluet Balairung tetap terlihat.
       - SENGAJA tanpa overflow:hidden: kotak memanjang sendiri kalau konten
         lebih tinggi dari min-height (terbukti perlu di layar sempit). */
    section[data-testid="stMain"] { container-type: inline-size; }
    .st-key-hero {
        position: relative;
        width: 100cqw;
        max-width: none;
        margin-left: calc(50% - 50cqw);
        margin-bottom: 28px;
        min-height: 390px;
        justify-content: center;
        gap: 0.3rem;
        padding: 40px calc(50cqw - 50% + 32px);
        box-sizing: border-box;
        text-align: left;
        background-color: #00214a;
        background-image:
            linear-gradient(90deg, rgba(2,12,40,0.62) 0%, rgba(2,12,40,0.35) 42%, rgba(2,12,40,0) 68%),
            url("app/static/hero_bg.jpg");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        color: #fff;
    }
    /* Isi hero (teks + form pencarian) dibatasi di sisi kiri saja. Form
       dibungkus stLayoutWrapper oleh Streamlit, jadi pembatas lebarnya harus
       dipasang di pembungkus itu -- bukan di [data-testid="stForm"]. */
    .st-key-hero > [data-testid="stElementContainer"],
    .st-key-hero > [data-testid="stLayoutWrapper"] { width: 100%; max-width: 560px; }
    /* Area utama < 1200px: kotak jadi lebih "tinggi" dari rasio gambar (~3:1)
       sehingga cover memotong SISI. Posisi digeser ke KANAN supaya yang
       terpotong adalah sisi kiri gambar yang memang kosong & gelap --
       Balairung & tugu di kanan tetap utuh. (@container = diukur dari lebar
       area utama, bukan layar -- akurat baik sidebar dibuka maupun ditutup.) */
    @container (max-width: 1200px) {
        .st-key-hero { background-position: right center; }
    }
    @container (max-width: 760px) {
        .st-key-hero {
            padding-top: 32px; padding-bottom: 32px;
            background-image:
                linear-gradient(90deg, rgba(2,12,40,0.72), rgba(2,12,40,0.55)),
                url("app/static/hero_bg.jpg");
        }
    }
    .hero-badge img { height: 1.25rem; width: auto; vertical-align: -0.3rem; margin-right: 2px; }
    .hero-badge {
        display: inline-block;
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 999px;
        padding: 5px 16px;
        margin-bottom: 14px;
        color: #fff;
    }
    .hero-title {
        font-size: clamp(1.9rem, 3.1vw, 2.7rem); font-weight: 800; line-height: 1.15;
        margin: 0 0 12px;
        color: #fff;
        text-shadow: 0 2px 14px rgba(0,8,30,0.45);
    }
    .hero-title .accent { color: #ffc72c; }
    .hero-subtitle {
        font-size: 0.98rem; line-height: 1.6;
        margin: 0 0 8px;
        color: rgba(255,255,255,0.9);
        text-shadow: 0 1px 8px rgba(0,8,30,0.5);
    }
    /* Kotak pencarian: st.form (input + tombol) didandani jadi "pil" putih,
       meniru kotak pencarian palsu yang dulu cuma HTML di sini. */
    .st-key-hero [data-testid="stForm"] { border: none; padding: 0; }
    .st-key-hero [data-testid="stTextInputRootElement"] {
        background: #fff; border: none; border-radius: 999px;
        padding-left: 14px; height: 48px;
        box-shadow: 0 14px 34px rgba(0,10,40,0.35);
    }
    .st-key-hero [data-testid="stTextInputRootElement"] input { color: #1a1a1a; }
    .st-key-hero [data-testid="stTextInputRootElement"] input::placeholder { color: #8a8a8a; }
    .st-key-hero [data-testid="stFormSubmitButton"] button {
        background: #ffc72c; border: none; border-radius: 999px;
        height: 48px; font-weight: 700;
        box-shadow: 0 14px 34px rgba(0,10,40,0.3);
    }
    .st-key-hero [data-testid="stFormSubmitButton"] button,
    .st-key-hero [data-testid="stFormSubmitButton"] button * { color: #1a1a1a !important; }
    .st-key-hero [data-testid="stFormSubmitButton"] button:hover { background: #ffd65c; }
    .hero-stat {
        font-size: 0.88rem; margin-top: 12px;
        color: rgba(255,255,255,0.85);
        text-shadow: 0 1px 6px rgba(0,8,30,0.5);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="hero"):
    st.markdown(
        f"""
        <div class="hero-badge"><img src="{data_uri_ikon('LogoUGM.png')}" alt=""> Universitas Gadjah Mada</div>
        <div class="hero-title">Analisis <span class="accent">Dampak</span> UGM</div>
        <div class="hero-subtitle">
            Platform analisis berita untuk memetakan dampak UGM terhadap Lingkungan,
            Ekonomi, dan Sosial (Kepmendikti Saintek 361/M/KEP/2025), keterkaitannya
            dengan 17 SDGs, serta kesiapan data untuk akreditasi.
        </div>
        """,
        unsafe_allow_html=True,
    )
    # st.form: menekan Enter di kotak teks = menekan tombol "Cari" (perilaku
    # bawaan form yang isinya satu text_input), jadi tidak perlu handler
    # keyboard sendiri.
    with st.form("cari_beranda", border=False, clear_on_submit=False):
        kolom_input, kolom_tombol = st.columns([4, 1], vertical_alignment="center")
        query = kolom_input.text_input(
            "Cari analisis",
            placeholder="Coba: 'dampak lingkungan 2024' atau 'SDG 4 pendidikan'",
            label_visibility="collapsed",
        )
        cari = kolom_tombol.form_submit_button("Cari", width="stretch")
    st.markdown(
        f'<div class="hero-stat">👥 {total_berita:,} berita dianalisis &nbsp;·&nbsp; '
        f'{n_dampak:,} bertema dampak &nbsp;·&nbsp; {cakupan_pct:.1f}% cakupan</div>',
        unsafe_allow_html=True,
    )

if cari and query.strip():
    hasil = parse(query)
    simpan_hasil(hasil)  # dibaca halaman tujuan (pencarian.terapkan_filter_awal)
    st.switch_page(HALAMAN[hasil.halaman])
elif cari:
    st.warning("Ketik dulu kata kunci yang ingin dicari.")

st.caption(
    "Pencarian mencocokkan kata kunci (bukan AI): nama dampak "
    "(lingkungan/ekonomi/sosial), tema resmi Kepmen, \"SDG <nomor>\", tahun, "
    "dan kata \"akreditasi\"/\"LED\"/\"LKPS\" — lalu membuka halaman yang "
    "sesuai dengan filternya sudah terpasang."
)

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="medium")
# href = url_path halaman tujuan (lihat dashboard_berita_dampak.py) -- tombol
# "Buka ->" SENGAJA jadi bagian dari SATU blok HTML yang sama dengan kartu
# (bukan st.button terpisah di elemen Streamlit lain) supaya kartu+tombol
# selalu satu kotak yang ukurannya menyesuaikan diri sendiri -- align lintas
# elemen Streamlit (custom div vs st.button) terbukti rapuh lewat CSS murni
# karena banyak lapis div pembungkus antara keduanya tidak meneruskan tinggi.
# Ikon: emoji (str) ATAU logo gambar ("logo", file di shared/assets/logo/ --
# aset yang sama dgn menu sidebar, lihat common.IKON_MENU_SIDEBAR).
kartu = [
    (col1, ("logo", "dampak.png"), "Analisis Dampak Universitas",
     "3 dampak (Lingkungan, Ekonomi, Sosial) & 14 tema resmi Kepmen, "
     "opsional dikombinasikan dengan SDGs.",
     "dampak-sdgs"),
    (col2, ("logo", "sdgs.png"), "SDGs",
     "Mapping langsung seluruh berita UGM ke 17 SDG -- jangkauan paling luas.",
     "sdgs"),
    (col3, ("logo", "certificate.png"), "Akreditasi",
     "Filter data & generate laporan akreditasi siap unduh (Word).",
     "akreditasi"),
]
for col, icon, judul, desk, url_path in kartu:
    if isinstance(icon, tuple):
        # alt kosong: logo dekoratif, judul kartu di bawahnya sudah jadi label.
        icon = (f'<span class="home-card-logo"><img src="{data_uri_ikon(icon[1])}" '
                'alt=""></span>')
    with col:
        st.markdown(
            f"""
            <a class="home-card" href="/{url_path}" target="_self">
                <div class="home-card-icon">{icon}</div>
                <div class="home-card-title">{judul}</div>
                <div class="home-card-desc">{desk}</div>
                <div class="home-card-footer">Buka →</div>
            </a>
            """,
            unsafe_allow_html=True,
        )

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
