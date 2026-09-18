"""Halaman Profil Saya (menu Akreditasi). Logika di page_profil.render()."""

import streamlit as st

from common import inject_css
from page_profil import render

inject_css()

st.title("👤 Profil Saya")

from auth_akreditasi import wajib_login  # noqa: E402  (sys.path diset page_akreditasi)

wajib_login()
render()
