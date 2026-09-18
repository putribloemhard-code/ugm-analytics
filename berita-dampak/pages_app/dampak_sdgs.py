"""Halaman Analisis Dampak Universitas -> Dampak x SDGs.

Identik dengan mode "Berdampak × SDGs" pada dashboard_berita_dampak.py versi
lama (dropdown "Mode analisis", mode default sebelumnya) -- logikanya ada di
page_dampak.render(), dipakai bareng dengan halaman "Dampak Saja" (lihat
dampak_saja.py).
"""

import streamlit as st

import pencarian
from common import inject_css, judul_halaman
from page_dampak import render

inject_css()

judul_halaman("Analisis Dampak Universitas — Dampak × SDGs", "dampakXsdgs.png")
st.caption(
    "3 dampak & 14 tema resmi Kepmen, dikombinasikan dengan SDGs dari "
    "berita bertema."
)

pencarian.banner()

render(mode="Berdampak × SDGs")
