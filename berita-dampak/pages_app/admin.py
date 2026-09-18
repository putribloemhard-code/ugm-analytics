"""Halaman Admin (menu Akreditasi). Logika & penolakan non-admin di
page_admin.render()."""

import streamlit as st

from common import inject_css
from page_admin import render

inject_css()

st.title("🛡️ Admin")

from auth_akreditasi import wajib_login  # noqa: E402  (sys.path diset page_akreditasi)

wajib_login()
render()
