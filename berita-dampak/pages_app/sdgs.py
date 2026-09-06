"""Halaman SDGs.

Identik dengan mode "SDGs" pada dashboard_berita_dampak.py versi lama
(dropdown "Mode analisis") -- mapping langsung seluruh URL sitemap ke 17
SDG, tanpa tema dampak Kepmen. Logikanya ada di page_sdgs.render().
"""

import streamlit as st

from common import inject_css
from page_sdgs import render

inject_css()

st.title("🎯 SDGs")

render()
