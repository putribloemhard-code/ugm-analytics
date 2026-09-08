"""Dashboard Streamlit -- kelengkapan data akreditasi (LED & LKPS), berdiri sendiri.

Sumber kebutuhan data: docs/Data_Requirements_LED_LKPS_MEI.md, terdaftar di
scripts/registry_kebutuhan_data.py (SATU SUMBER KEBENARAN). Input manual
disimpan ke MySQL ugm_analytics, tabel akreditasi_data_manual (lihat
scripts/migrasi_tabel_akreditasi.py). Generator dokumen: scripts/generate_template.py.

LED dan LKPS adalah dua dokumen terpisah dengan navigasi berbeda (LED per
Kriteria A-D, LKPS per Bagian 1-6) -- dipilih lewat selector di bawah judul,
lihat docstring registry_kebutuhan_data.py poin 6.

UI dashboard ini (ringkasan atas, tab per Kriteria/Bagian, form input manual)
ada di scripts/dashboard_render.py -- dipakai BARENG oleh menu "Akreditasi" di
dashboard_berita_dampak.py (berita-dampak/page_akreditasi.py), jadi data
yang diisi lewat salah satu entry point otomatis muncul di entry point
lainnya (satu tabel MySQL yang sama).

Jalankan: streamlit run dashboard_akreditasi.py
"""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, utk shared/

from shared.style import apply_custom_css  # noqa: E402
from scripts import dashboard_render as dr  # noqa: E402
from scripts.generate_template import generate_led_docx, generate_lkps_docx  # noqa: E402
from scripts.registry_kebutuhan_data import led_items_by_kriteria, lkps_items_by_bagian  # noqa: E402

st.set_page_config(page_title="Kelengkapan Data Akreditasi", layout="wide", page_icon="🎓")
apply_custom_css()
st.markdown(
    """
    <style>
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1200px; }
    div[data-testid="stMetric"] {
        background: rgba(128,128,128,0.07);
        border: 1px solid rgba(128,128,128,0.16);
        border-radius: 12px;
        padding: 14px 16px 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("🎓 Kelengkapan Data Akreditasi")
st.caption("Kelengkapan data LED & LKPS — instrumen akreditasi Program Studi (LAM-INFOKOM)")

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

dr.consume_pending_switch()
mode = st.selectbox(
    "Pilih dokumen",
    options=["LED", "LKPS"],
    key="akreditasi_dokumen",
    format_func=lambda m: "📘 LED — Laporan Evaluasi Diri" if m == "LED" else "📗 LKPS — Laporan Kinerja Program Studi",
)

if not dr.ensure_ready():
    st.stop()

engine = dr.get_engine()
df_manual = dr.load_data_manual()

if mode == "LED":
    grouped = led_items_by_kriteria()
else:
    grouped = lkps_items_by_bagian()
item_ids = [item["id"] for items in grouped.values() for item in items]
ringkasan, filled_ids = dr.render_ringkasan_atas(df_manual, item_ids=item_ids)

st.markdown("---")
if mode == "LED":
    st.subheader(f"Kelengkapan Data LED ({ringkasan['total']} item)")
    st.caption(
        "Narasi evaluatif per Kriteria A-D (siklus PPEPP), sesuai dokumen kebutuhan data yang terdaftar "
        "di registry. Tiap tab Kriteria A/B/C1-C6 juga menampilkan cuplikan tabel LKPS terkait sebagai bukti evaluasi."
    )
    dr.render_tabs_led(engine, df_manual, filled_ids)
else:
    st.subheader(f"Kelengkapan Data LKPS ({ringkasan['total']} item)")
    st.caption(
        "Tabel data mentah per Bagian 1-6, sesuai dokumen kebutuhan data yang terdaftar di registry. "
        "Isi form di tiap tabel berstatus \"perlu input manual\" -- tersimpan langsung ke MySQL."
    )
    dr.render_tabs_lkps(engine, df_manual, filled_ids)

st.markdown("---")
st.subheader(f"📄 Generate Dokumen {mode}")
st.caption(
    f"Menghasilkan dokumen Word (.docx) {'narasi LED per Kriteria, ditutup cuplikan tabel LKPS terkait' if mode == 'LED' else 'tabel LKPS per Bagian'}. "
    "Section/tabel yang datanya belum ada tetap dibuat, ditandai \"⚠️ Data belum tersedia\" -- dokumen selalu jadi template lengkap."
)
if st.button(f"🔄 Generate Dokumen Template {mode}", type="primary"):
    with st.spinner("Membuat dokumen..."):
        docx_bytes = generate_led_docx(engine) if mode == "LED" else generate_lkps_docx(engine)
    st.download_button(
        f"⬇️ Unduh template_{mode}.docx",
        data=docx_bytes,
        file_name=f"template_{mode}_{datetime.now().strftime('%Y%m%d')}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
