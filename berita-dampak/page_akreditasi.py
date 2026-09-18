"""Logika + UI halaman "Akreditasi" (berita-dampak).

Dashboard kelengkapan data LED & LKPS (49 item, registry
`akreditasi/docs/Data_Requirements_LED_LKPS_MEI.md`), dipisah sebagai dua MODE dokumen
(selector LED/LKPS -- LED per Kriteria A-D, LKPS per Bagian 1-6, lihat
docstring registry_kebutuhan_data.py poin 6) -- REUSE LANGSUNG modul dari
subproyek akreditasi/ (../akreditasi/scripts/dashboard_render.py,
registry_kebutuhan_data.py, generate_template.py) lewat sys.path, BUKAN
disalin -- supaya satu sumber kebenaran & satu tabel MySQL
(akreditasi_data_manual): data yang diisi lewat halaman ini ATAU lewat
app akreditasi/ yang berdiri sendiri sama-sama muncul di keduanya.

Urutan halaman: Lingkup akreditasi -> Fakultas & Program Studi -> Pilihan
laporan (LED/LKPS) -> Upload file -> Kelengkapan data -> Generate laporan.
Semua dropdown WAJIB diisi (tidak ada default otomatis) sebelum konten
kelengkapan data ditampilkan.

Section "Lampiran: Data Dampak & SDG" (dulu ada di halaman ini) sudah
DIHAPUS -- fitur unduh hasil analisis per unit/fakultas sekarang ada
langsung di halaman Dampak/Dampak x SDGs/SDGs (tab "Fakultas/Unit Kerja"),
bukan lagi dilampirkan di sini.
"""

import sys
from pathlib import Path

import streamlit as st

_AKREDITASI_SCRIPTS = Path(__file__).resolve().parents[1] / "akreditasi" / "scripts"
sys.path.insert(0, str(_AKREDITASI_SCRIPTS))

_PILIH_LINGKUP_SENTINEL = "-- Pilih Lingkup --"
_PILIH_DOKUMEN_SENTINEL = "-- Pilih Dokumen --"

# Titipan dari tombol "Lanjutkan" di halaman Profil: {"fakultas", "prodi",
# "dokumen"}. Key biasa (bukan key widget) supaya selamat saat pindah halaman;
# baru dipindah ke key widget di awal render(), SEBELUM widget-nya dibuat.
KEY_LANJUTKAN = "_akreditasi_lanjutkan"


def _terapkan_lanjutkan() -> None:
    lanjut = st.session_state.pop(KEY_LANJUTKAN, None)
    if not lanjut:
        return
    st.session_state["akreditasi_scope"] = "Akreditasi Program Studi"
    st.session_state["akreditasi_fakultas_pilih"] = lanjut["fakultas"]
    st.session_state["akreditasi_prodi_pilih"] = lanjut["prodi"]
    st.session_state["akreditasi_dokumen"] = lanjut["dokumen"]


def render() -> None:
    import dashboard_render as dr  # dari akreditasi/scripts (bare import, lihat sys.path di atas)
    from registry_kebutuhan_data import led_items_by_kriteria, lkps_items_by_bagian  # bare import

    from auth_akreditasi import user_aktif  # bare import

    user = user_aktif()
    if not user:  # pages_app/akreditasi.py sudah memasang wajib_login(); ini jaga-jaga
        st.stop()

    if not dr.ensure_ready():
        st.stop()

    # Email = identitas unik & stabil; dicatat di diisi_oleh / diupload_oleh.
    diisi_oleh = user["email"]
    _terapkan_lanjutkan()

    # ---------- Semua field WAJIB ditampilkan sekaligus (tidak reveal bertahap) ----------
    scope = st.selectbox(
        "Lingkup akreditasi (wajib)",
        options=[_PILIH_LINGKUP_SENTINEL, "Akreditasi Program Studi", "Akreditasi Universitas"],
        index=0,
        key="akreditasi_scope",
    )

    prodi_id = dr.render_prodi_selector()

    dr.consume_pending_switch()
    mode = st.selectbox(
        "Pilihan laporan yang mau disusun (wajib)",
        options=[_PILIH_DOKUMEN_SENTINEL, "LED", "LKPS"],
        index=0,
        key="akreditasi_dokumen",
        format_func=lambda m: (
            "📘 LED — Laporan Evaluasi Diri" if m == "LED"
            else "📗 LKPS — Laporan Kinerja Program Studi" if m == "LKPS"
            else m
        ),
    )
    st.caption("Semua pilihan bertanda (wajib) harus diisi.")

    if scope == "Akreditasi Universitas":
        st.info(
            "Instrumen akreditasi Universitas (BAN-PT — LED APT/LKPT) berbeda struktur dari "
            "instrumen Program Studi (LAM-INFOKOM — LED/LKPS) yang sudah dibangun di sini. "
            "Dokumen requirement untuk instrumen institusi ini belum tersedia di "
            "akreditasi/docs/. Fitur ini akan dikembangkan setelah dokumen requirement "
            "LED APT/LKPT disiapkan."
        )
        st.stop()

    lengkap = (
        scope == "Akreditasi Program Studi"
        and prodi_id is not None
        and mode in ("LED", "LKPS")
    )

    # ---------- Upload file (selalu tampil; aktif begitu field wajib di atas lengkap) ----------
    st.markdown("---")
    from upload_akreditasi import render_upload_section  # dari akreditasi/scripts (bare import)

    if lengkap:
        render_upload_section(prodi_id, mode, diupload_oleh=diisi_oleh)
    else:
        st.subheader("📤 Upload File Pendukung")
        st.caption("Lengkapi semua pilihan bertanda (wajib) di atas untuk mengaktifkan upload file.")

    st.markdown("---")

    if not lengkap:
        st.info("Lengkapi semua pilihan bertanda (wajib) di atas untuk melihat data.")
        st.stop()

    engine = dr.get_engine()
    df_manual = dr.load_data_manual(prodi_id)

    from ekstraksi_akreditasi import deteksi_konflik, load_pending_ekstraksi  # bare import

    pending = deteksi_konflik(load_pending_ekstraksi(prodi_id))

    grouped = led_items_by_kriteria() if mode == "LED" else lkps_items_by_bagian()
    item_ids = [item["id"] for items in grouped.values() for item in items]
    _ringkasan, filled_ids = dr.render_ringkasan_atas(df_manual, item_ids=item_ids)

    if len(pending):
        n_item_pending = pending["item_id"].nunique()
        st.warning(
            f"🟡 Ada hasil ekstraksi AI utk **{n_item_pending} item** yang belum direview -- "
            "cek highlight kuning di dalam tiap item pada tab Kelengkapan Data di bawah, lalu "
            "klik Simpan setelah dicek untuk mengonfirmasi."
        )

    st.markdown("---")
    if mode == "LED":
        st.subheader(f"Kelengkapan Data LED ({_ringkasan['total']} item)")
        st.caption(
            "Narasi evaluatif per Kriteria A-D (siklus PPEPP), sesuai dokumen kebutuhan data yang terdaftar "
            "di registry. Tiap tab Kriteria A/B/C1-C6 juga menampilkan cuplikan tabel LKPS terkait sebagai bukti evaluasi."
        )
        dr.render_tabs_led(engine, df_manual, filled_ids, prodi_id, pending, diisi_oleh)
    else:
        st.subheader(f"Kelengkapan Data LKPS ({_ringkasan['total']} item)")
        st.caption(
            "Tabel data mentah per Bagian 1-6, sesuai dokumen kebutuhan data yang terdaftar di registry. "
            "Isi form di tiap tabel berstatus \"perlu input manual\" -- tersimpan langsung ke MySQL "
            "(tabel bersama dengan app akreditasi/)."
        )
        dr.render_tabs_lkps(engine, df_manual, filled_ids, prodi_id, pending, diisi_oleh)

    st.markdown("---")
    st.subheader(f"📄 Generate Laporan {mode} (Word)")
    st.caption(
        f"Satu dokumen: kelengkapan data {mode} (cover, ringkasan & to-do, isi per "
        f"{'Kriteria' if mode == 'LED' else 'Bagian'})."
    )
    if st.button(f"🔄 Generate Laporan {mode} (Word)", type="primary"):
        from generate_template import generate_led_docx, generate_lkps_docx  # dari akreditasi/scripts (bare import)

        from akun_akreditasi import simpan_riwayat_generate  # bare import

        with st.spinner("Membuat dokumen..."):
            docx_bytes = (generate_led_docx(engine, prodi_id) if mode == "LED"
                          else generate_lkps_docx(engine, prodi_id))
        simpan_riwayat_generate(user["email"], prodi_id, mode, docx_bytes)
        st.download_button(
            f"⬇️ Unduh Laporan_Akreditasi_{mode}.docx",
            data=docx_bytes,
            file_name=f"Laporan_Akreditasi_{mode}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
