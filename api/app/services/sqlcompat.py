"""Potongan SQL yang berbeda antar dialek (PostgreSQL vs MySQL).

API ditulis untuk PostgreSQL, sedangkan pratinjau lokal memakai MySQL yang sama dengan dashboard
Streamlit. Helper ini menjaga perilaku identik di keduanya.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine


def url_key(engine: Engine, column: str) -> str:
    """URL tanpa query string dan tanpa garis miring di ujung, untuk mencocokkan sitemap dengan tabel unit kerja."""
    if engine.dialect.name == "mysql":
        return f"TRIM(TRAILING '/' FROM SUBSTRING_INDEX({column}, '?', 1))"
    return f"regexp_replace(split_part({column}, '?', 1), '/+$', '')"


def pipe_list_contains(engine: Engine, column: str, param: str) -> str:
    """True bila `param` termasuk daftar yang dipisah '|' di `column` (mis. bk.sdg = '4|7|13').

    `string_to_array(...)` hanya ada di PostgreSQL; MySQL memakai FIND_IN_SET. Dipakai jalur
    /analytics/news mode=impact + filter SDG, yang sebelumnya 503 di MySQL.
    """
    bersih = f"REPLACE(COALESCE({column}, ''), '|', ',')"
    if engine.dialect.name == "mysql":
        return f"FIND_IN_SET(:{param}, {bersih}) > 0"
    return f":{param} = ANY(string_to_array({bersih}, ','))"


def desc_nulls_last(column: str) -> str:
    """ORDER BY <column> DESC dengan NULL di akhir; `NULLS LAST` tidak dikenal MySQL."""
    return f"({column} IS NULL), {column} DESC"
