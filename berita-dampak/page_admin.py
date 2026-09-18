"""Halaman "Admin" (menu Akreditasi): kelola akun pengguna.

Pengamanan berlapis:
1. Menu "Admin" disembunyikan dari non-admin (dashboard_berita_dampak.py).
2. Halaman ini SENDIRI menolak non-admin -- menyembunyikan menu saja tidak
   cukup karena URL /admin tetap bisa diketik langsung.
3. Setiap aksi dicek ulang di akun_akreditasi (pelaku harus admin aktif &
   bukan akun sendiri), jadi tidak bergantung pada tombol yang di-disable.
"""

import pandas as pd
import streamlit as st

import page_akreditasi  # noqa: F401  (memasang sys.path ke akreditasi/scripts)

_KEY_KONFIRMASI_HAPUS = "_admin_konfirmasi_hapus"
_KEY_PESAN = "_admin_pesan"


def _tgl(nilai) -> str:
    if nilai is None or pd.isna(nilai):
        return "-"
    return pd.Timestamp(nilai).strftime("%d %b %Y, %H:%M")


def _jalankan(fungsi, *args, sukses: str) -> None:
    from akun_akreditasi import AksiDitolak  # bare import

    try:
        fungsi(*args)
    except AksiDitolak as e:
        st.session_state[_KEY_PESAN] = ("error", str(e))
    else:
        st.session_state[_KEY_PESAN] = ("success", sukses)
    st.session_state.pop(_KEY_KONFIRMASI_HAPUS, None)
    st.rerun()


def _render_kartu(r, admin: dict) -> None:
    from akun_akreditasi import hapus_user, set_admin, set_blokir  # bare import
    from auth_akreditasi import md_aman  # bare import

    uid = int(r["id"])
    diri_sendiri = uid == admin["id"]
    nama = md_aman(r["nama"])
    with st.container(border=True):
        kiri, tengah, kanan = st.columns([4, 3, 4])
        kiri.markdown(
            f"**{nama}**" + (" &nbsp;`ADMIN`" if r["is_admin"] else "")
            + (" &nbsp;_(akun Anda)_" if diri_sendiri else "")
            + f"  \n{md_aman(r['email'])}"
            + f"  \nDaftar: {_tgl(r['created_at'])} · Login terakhir: {_tgl(r['last_login_at'])}"
        )
        tengah.markdown(
            ("🔴 **Diblokir**" if r["is_blocked"] else "🟢 **Aktif**")
            + f"  \n{int(r['n_generate'])} dokumen digenerate"
        )
        b1, b2, b3 = kanan.columns(3)
        if r["is_blocked"]:
            if b1.button("Buka Blokir", key=f"unblok_{uid}", disabled=diri_sendiri):
                _jalankan(set_blokir, admin["id"], uid, False, sukses=f"Blokir {r['email']} dibuka.")
        elif b1.button("Blokir", key=f"blok_{uid}", disabled=diri_sendiri):
            _jalankan(set_blokir, admin["id"], uid, True, sukses=f"{r['email']} diblokir.")

        if r["is_admin"]:
            if b2.button("Cabut Admin", key=f"cabut_{uid}", disabled=diri_sendiri):
                _jalankan(set_admin, admin["id"], uid, False,
                          sukses=f"Status admin {r['email']} dicabut.")
        elif b2.button("Jadikan Admin", key=f"jadikan_{uid}", disabled=diri_sendiri):
            _jalankan(set_admin, admin["id"], uid, True, sukses=f"{r['email']} sekarang admin.")

        if b3.button("Hapus", key=f"hapus_{uid}", disabled=diri_sendiri):
            st.session_state[_KEY_KONFIRMASI_HAPUS] = uid
            st.rerun()

        if st.session_state.get(_KEY_KONFIRMASI_HAPUS) == uid:
            st.warning(f"Hapus akun **{md_aman(r['email'])}** secara permanen? Riwayat "
                       "generate-nya ikut terhapus; data yang sudah ia konfirmasi tetap ada.")
            y, t = st.columns([1, 5])
            if y.button("Ya, hapus", key=f"hapus_ya_{uid}", type="primary"):
                _jalankan(hapus_user, admin["id"], uid, sukses=f"Akun {r['email']} dihapus.")
            if t.button("Batal", key=f"hapus_batal_{uid}"):
                st.session_state.pop(_KEY_KONFIRMASI_HAPUS, None)
                st.rerun()


def render() -> None:
    from akun_akreditasi import daftar_user  # bare import
    from auth_akreditasi import user_aktif  # bare import

    admin = user_aktif()
    if not admin or not admin["is_admin"]:
        st.error("⛔ Akses ditolak — halaman ini khusus admin.")
        st.stop()

    pesan = st.session_state.pop(_KEY_PESAN, None)
    if pesan:
        (st.success if pesan[0] == "success" else st.error)(pesan[1])

    df = daftar_user()
    m1, m2, m3 = st.columns(3)
    m1.metric("Total akun", len(df))
    m2.metric("Admin", int(df["is_admin"].sum()))
    m3.metric("Diblokir", int(df["is_blocked"].sum()))

    st.subheader("Semua pengguna")
    tampil = pd.DataFrame({
        "Nama": df["nama"],
        "Email": df["email"],
        "Terdaftar": df["created_at"].map(_tgl),
        "Login terakhir": df["last_login_at"].map(_tgl),
        "Status": df["is_blocked"].map(lambda b: "🔴 Diblokir" if b else "🟢 Aktif"),
        "Admin": df["is_admin"].map(lambda a: "⭐ Admin" if a else ""),
        "Dokumen digenerate": df["n_generate"].astype(int),
    })
    st.dataframe(tampil, hide_index=True, width="stretch")

    st.subheader("Kelola akun")
    st.caption("Akun Anda sendiri tidak bisa diblokir, dihapus, atau dicabut status "
               "adminnya — supaya sistem tidak pernah kehilangan admin.")
    for _, r in df.iterrows():
        _render_kartu(r, admin)
