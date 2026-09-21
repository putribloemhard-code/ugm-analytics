"""Uji helper SQL lintas dialek (services/sqlcompat.py)."""
from __future__ import annotations

from sqlalchemy import create_engine

from app.services.sqlcompat import desc_nulls_last, pipe_list_contains, url_key

MYSQL = create_engine("mysql+pymysql://u:p@localhost/db")
POSTGRES = create_engine("postgresql+psycopg://u:p@localhost/db")


def test_pipe_list_contains_memakai_find_in_set_di_mysql():
    sql = pipe_list_contains(MYSQL, "bk.sdg", "impact_sdg0")
    assert sql == "FIND_IN_SET(:impact_sdg0, REPLACE(COALESCE(bk.sdg, ''), '|', ',')) > 0"
    # string_to_array tidak ada di MySQL -> tidak boleh muncul.
    assert "string_to_array" not in sql


def test_pipe_list_contains_memakai_string_to_array_di_postgres():
    sql = pipe_list_contains(POSTGRES, "bk.sdg", "impact_sdg0")
    assert sql == ":impact_sdg0 = ANY(string_to_array(REPLACE(COALESCE(bk.sdg, ''), '|', ','), ','))"
    assert "FIND_IN_SET" not in sql


def test_url_key_dan_desc_nulls_last_per_dialek():
    assert "SUBSTRING_INDEX" in url_key(MYSQL, "s.url")
    assert "split_part" in url_key(POSTGRES, "s.url")
    # NULLS LAST tidak dikenal MySQL, jadi diurut lewat ekspresi boolean.
    assert desc_nulls_last("uploaded_at") == "(uploaded_at IS NULL), uploaded_at DESC"
