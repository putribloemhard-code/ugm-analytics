"""Halaman SDGs.

Identik dengan mode "SDGs" pada dashboard_berita_dampak.py versi lama
(dropdown "Mode analisis") -- mapping langsung seluruh URL sitemap ke 17
SDG, tanpa tema dampak Kepmen. Logikanya ada di page_sdgs.render().
"""

import pencarian
from common import inject_css, judul_halaman
from page_sdgs import render

inject_css()

judul_halaman("SDGs", "sdgs.png")

pencarian.banner()

render()
