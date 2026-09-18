"""Halaman Akreditasi.

Dashboard kelengkapan data LED & LKPS (registry 49 item, form input manual,
generate dokumen Word) -- SATU sumber kebenaran dengan app akreditasi/ yang
berdiri sendiri (tabel MySQL sama). Logikanya ada di page_akreditasi.render().
"""

import streamlit as st

import pencarian
from common import inject_css, judul_halaman
from page_akreditasi import render

inject_css()

judul_halaman("Akreditasi", "certificate.png")

# Sebelum wajib_login(): kalau user datang dari kotak pencarian Beranda,
# penjelasan "kenapa saya mendarat di sini" harus tetap terlihat walau
# halamannya berhenti di form login.
pencarian.banner()

from auth_akreditasi import wajib_login  # noqa: E402  (akreditasi/scripts, sys.path diset page_akreditasi)

wajib_login()

st.caption(
    "Kelengkapan data LED & LKPS (dua dokumen terpisah). Pilih lingkup, fakultas & "
    "program studi, lalu isi form input manual di tiap item dan generate laporan Word."
)


render()
