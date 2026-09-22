"""Uji helper SQL lintas dialek (services/sqlcompat.py)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError

from app.services.sqlcompat import (
    desc_nulls_last,
    index_ddl,
    is_duplicate_entry_error,
    is_duplicate_index_error,
    pipe_list_contains,
    url_key,
)

MYSQL = create_engine("mysql+pymysql://u:p@localhost/db")
POSTGRES = create_engine("postgresql+psycopg://u:p@localhost/db")
SQLITE = create_engine("sqlite+pysqlite:///:memory:")


def test_index_ddl_tanpa_if_not_exists_di_mysql():
    """`CREATE INDEX IF NOT EXISTS` ditolak MySQL (error 1064) -> DDL apa pun yang memakainya
    mematikan endpoint yang memanggilnya (bug registrasi Analisis Dampak, 2026-09-22)."""
    ddl = index_ddl(MYSQL, "dampak_sessions", ["user_id"], name="dampak_sessions_user_idx")
    assert ddl == "CREATE INDEX dampak_sessions_user_idx ON dampak_sessions (user_id)"
    assert "IF NOT EXISTS" not in ddl


def test_index_ddl_memakai_if_not_exists_di_postgres():
    ddl = index_ddl(POSTGRES, "dampak_sessions", ["expires_at"], name="idx_exp", unique=True)
    assert ddl == "CREATE UNIQUE INDEX IF NOT EXISTS idx_exp ON dampak_sessions (expires_at)"


def test_pengenalan_error_duplikat_per_dialek():
    mysql_duplikat = ProgrammingError("CREATE INDEX x", {}, Exception(
        "(1061, \"Duplicate key name 'dampak_sessions_user_idx'\")"))
    sqlite_duplikat = ProgrammingError("CREATE INDEX x", {}, Exception(
        "index dampak_sessions_user_idx already exists"))
    lain = ProgrammingError("SELECT 1", {}, Exception("You have an error in your SQL syntax; near 'IF NOT EXISTS'"))
    assert is_duplicate_index_error(mysql_duplikat) is True
    assert is_duplicate_index_error(sqlite_duplikat) is True
    assert is_duplicate_index_error(lain) is False

    # Pesan email duplikat: PostgreSQL "duplicate key value violates unique constraint",
    # MySQL "Duplicate entry ... for key", SQLite "UNIQUE constraint failed".
    for pesan in (
        'duplicate key value violates unique constraint "users_email_key"',
        "Duplicate entry 'a@ugm.ac.id' for key 'email'",
        "UNIQUE constraint failed: dampak_users.email",
    ):
        assert is_duplicate_entry_error(ProgrammingError("INSERT", {}, Exception(pesan))) is True
    assert is_duplicate_entry_error(ProgrammingError("INSERT", {}, Exception("connection reset"))) is False


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
