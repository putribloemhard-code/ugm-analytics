"""Halaman Analisis Dampak Universitas -> Dampak Saja.

Identik dengan mode "Berdampak" pada dashboard_berita_dampak.py versi lama
(dropdown "Mode analisis") -- logikanya ada di page_dampak.render(), dipakai
bareng dengan halaman "Dampak x SDGs" (lihat dampak_sdgs.py).
"""

import streamlit as st

from common import inject_css
from page_dampak import render

inject_css()

st.title("📊 Analisis Dampak Universitas — Dampak")
st.caption(
    "3 dampak (Lingkungan, Ekonomi, Sosial) & 14 tema resmi Kepmen "
    "361/M/KEP/2025 — tanpa bagian SDG."
)

render(mode="Berdampak")
