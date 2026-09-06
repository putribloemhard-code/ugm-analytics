"""Halaman Analisis Dampak Universitas -> Dampak x SDGs.

Identik dengan mode "Berdampak × SDGs" pada dashboard_berita_dampak.py versi
lama (dropdown "Mode analisis", mode default sebelumnya) -- logikanya ada di
page_dampak.render(), dipakai bareng dengan halaman "Dampak Saja" (lihat
dampak_saja.py).
"""

import streamlit as st

from common import inject_css
from page_dampak import render

inject_css()

st.title("🌍 Analisis Dampak Universitas — Dampak × SDGs")
st.caption(
    "3 dampak & 14 tema resmi Kepmen, dikombinasikan dengan SDGs dari "
    "berita bertema."
)

render(mode="Berdampak × SDGs")
