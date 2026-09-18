"""Halaman Analisis Dampak Universitas -> Dampak Saja.

Identik dengan mode "Berdampak" pada dashboard_berita_dampak.py versi lama
(dropdown "Mode analisis") -- logikanya ada di page_dampak.render(), dipakai
bareng dengan halaman "Dampak x SDGs" (lihat dampak_sdgs.py).
"""

import streamlit as st

import pencarian
from common import inject_css, judul_halaman
from page_dampak import render

inject_css()

judul_halaman("Analisis Dampak Universitas — Dampak", "dampak.png")
st.caption(
    "3 dampak (Lingkungan, Ekonomi, Sosial) & 14 tema resmi Kepmen "
    "361/M/KEP/2025 — tanpa bagian SDG."
)

pencarian.banner()

render(mode="Berdampak")
