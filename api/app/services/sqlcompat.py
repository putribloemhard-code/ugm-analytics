"""Potongan SQL yang berbeda antar dialek (PostgreSQL vs MySQL vs SQLite).

API ditulis untuk PostgreSQL, sedangkan mode lokal (web/dev_api_mysql.py) memakai MySQL
hasil pipeline, dan uji memakai SQLite. Helper ini menjaga perilaku identik di ketiganya.
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


def index_ddl(engine: Engine, table: str, columns: list[str], *, name: str, unique: bool = False) -> str:
    """CREATE INDEX yang bisa dijalankan berulang di semua dialek.

    `CREATE INDEX IF NOT EXISTS` hanya dikenal PostgreSQL; MySQL menolak (error 1064) sehingga
    DDL yang memakainya mematikan seluruh endpoint yang memanggilnya. Di MySQL cukup tanpa
    klausa itu -- index yang sudah ada memunculkan error 1061 yang ditangani pemanggil lewat
    `is_duplicate_index_error`.
    """
    if engine.dialect.name == "postgresql":
        prefix = "CREATE UNIQUE INDEX" if unique else "CREATE INDEX"
        return f"{prefix} IF NOT EXISTS {name} ON {table} ({', '.join(columns)})"
    return f"CREATE INDEX {name} ON {table} ({', '.join(columns)})"


def is_duplicate_index_error(exc: Exception) -> bool:
    """True bila kegagalan CREATE INDEX hanya karena index-nya sudah ada.

    Pesannya beda per dialek: MySQL 1061 "Duplicate key name", SQLite "index ... already exists",
    PostgreSQL sudah ditangani klausa IF NOT EXISTS.
    """
    asal = str(getattr(exc, "orig", exc)).lower()
    return "1061" in asal or "duplicate key name" in asal or "already exists" in asal


def is_duplicate_entry_error(exc: Exception) -> bool:
    """True bila INSERT gagal karena nilai kolom unik sudah terpakai.

    Pesannya beda per dialek: PostgreSQL "duplicate key value violates unique constraint",
    MySQL "Duplicate entry ... for key", SQLite "UNIQUE constraint failed".
    """
    pesan = str(getattr(exc, "orig", exc)).lower()
    return "duplicate" in pesan or "unique" in pesan
