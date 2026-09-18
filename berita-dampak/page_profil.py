"""Halaman "Profil Saya" (menu Akreditasi): identitas akun, pekerjaan yang
sedang berjalan, dan riwayat laporan Word yang pernah di-generate. Tiap user
hanya melihat datanya sendiri (semua query difilter email user yang login)."""

import pandas as pd
import streamlit as st

from page_akreditasi import KEY_LANJUTKAN  # juga memasang sys.path ke akreditasi/scripts

_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MAX_RIWAYAT = 50


def _tgl(nilai) -> str:
    if nilai is None or pd.isna(nilai):
        return "-"
    return pd.Timestamp(nilai).strftime("%d %b %Y, %H:%M")


def _render_ongoing(user: dict) -> None:
    from akun_akreditasi import pekerjaan_ongoing  # bare import
    from auth_akreditasi import md_aman  # bare import
    from dashboard_render import teks_kelengkapan  # bare import

    daftar = pekerjaan_ongoing(user["email"])
    if not daftar:
        st.info("Belum ada pekerjaan. Item yang Anda konfirmasi (klik Simpan) di halaman "
                "Akreditasi akan muncul di sini.")
        return
    for k in daftar:
        with st.container(border=True):
            kiri, kanan = st.columns([4, 1])
            kiri.markdown(f"**{md_aman(k['nama_prodi'])}** · {k['dokumen']}")
            pct, teks = teks_kelengkapan(k["ringkasan"], "Kelengkapan")
            kiri.progress(pct, text=teks)
            kiri.caption(f"{k['item_milik_user']} item di antaranya dikonfirmasi oleh Anda")
            bisa = k["nama_fakultas"] is not None
            if kanan.button("Lanjutkan ➜", key=f"lanjut_{k['prodi_id']}_{k['dokumen']}",
                            disabled=not bisa, type="primary"):
                st.session_state[KEY_LANJUTKAN] = {
                    "fakultas": k["nama_fakultas"], "prodi": k["nama_prodi"],
                    "dokumen": k["dokumen"],
                }
                st.switch_page("pages_app/akreditasi.py")
            if not bisa:
                kanan.caption("Prodi tidak terhubung ke fakultas.")


def _render_riwayat(user: dict) -> None:
    from akun_akreditasi import baca_file_riwayat, riwayat_generate_user  # bare import
    from auth_akreditasi import md_aman  # bare import

    df = riwayat_generate_user(user["email"])
    if df.empty:
        st.info("Belum ada laporan yang Anda generate.")
        return
    if len(df) > _MAX_RIWAYAT:
        st.caption(f"Menampilkan {_MAX_RIWAYAT} laporan terbaru dari {len(df)}.")
    kepala = st.columns([3, 1, 2, 2])
    for col, judul in zip(kepala, ["Program Studi", "Dokumen", "Digenerate", ""]):
        col.markdown(f"**{judul}**")
    for _, r in df.head(_MAX_RIWAYAT).iterrows():
        c1, c2, c3, c4 = st.columns([3, 1, 2, 2])
        c1.write(md_aman(r["nama_prodi"]))
        c2.write(r["jenis_dokumen"])
        c3.write(_tgl(r["generated_at"]))
        isi = baca_file_riwayat(r["file_path"])
        if isi is None:
            c4.caption("File tidak ditemukan")
        else:
            stempel = pd.Timestamp(r["generated_at"]).strftime("%Y%m%d_%H%M")
            c4.download_button(
                "⬇️ Unduh", data=isi, key=f"unduh_riwayat_{r['id']}", mime=_MIME_DOCX,
                file_name=f"Laporan_{r['jenis_dokumen']}_{r['prodi_id']}_{stempel}.docx",
            )


def render() -> None:
    from auth_akreditasi import md_aman, user_aktif  # bare import

    user = user_aktif()
    if not user:  # pages_app/profil.py sudah memasang wajib_login(); ini jaga-jaga
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**Nama**  \n{md_aman(user['nama'])}")
    c2.markdown(f"**Email**  \n{md_aman(user['email'])}")
    c3.markdown(f"**Terdaftar sejak**  \n{_tgl(user['created_at'])}")
    c4.markdown(f"**Login terakhir**  \n{_tgl(user['last_login_at'])}")

    st.markdown("---")
    tab_ongoing, tab_riwayat = st.tabs(["🛠️ Sedang Dikerjakan", "🗂️ Riwayat Dokumen"])
    with tab_ongoing:
        _render_ongoing(user)
    with tab_riwayat:
        _render_riwayat(user)
