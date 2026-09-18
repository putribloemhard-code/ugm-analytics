from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


class NewsService:
    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _in_clause(values: tuple[str, ...], prefix: str, params: dict[str, Any]) -> str:
        names = []
        for index, value in enumerate(values):
            name = f"{prefix}{index}"
            params[name] = value
            names.append(f":{name}")
        return ", ".join(names) or "NULL"

    def list_news(
        self,
        *,
        page: int,
        page_size: int,
        mode: str,
        year_from: str | None,
        year_to: str | None,
        pillars: tuple[str, ...] = (),
        topics: tuple[str, ...] = (),
        sdgs: tuple[int, ...] = (),
        units: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("page must be positive and page_size must be between 1 and 100")
        params: dict[str, Any] = {
            "year_from": year_from or "0000",
            "year_to": year_to or "9999",
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if mode == "sdgs":
            from_sql = "FROM berita_sitemap s JOIN berita_sitemap_sdg ss ON ss.url = s.url"
            where = ["SUBSTRING(s.lastmod FROM 1 FOR 4) BETWEEN :year_from AND :year_to"]
            if sdgs:
                where.append(f"ss.sdg IN ({self._in_clause(tuple(str(sdg) for sdg in sdgs), 'sdg', params)})")
            if units:
                unit_sql = self._in_clause(units, "unit", params)
                where.append(
                    "EXISTS (SELECT 1 FROM berita_unit_kerja unit_filter "
                    "WHERE unit_filter.unit_kerja IN (" + unit_sql + ") "
                    "AND regexp_replace(split_part(unit_filter.url, '?', 1), '/+$', '') = "
                    "regexp_replace(split_part(s.url, '?', 1), '/+$', ''))"
                )
            where_sql = " AND ".join(where)
            count_sql = f"SELECT COUNT(DISTINCT s.url) AS total {from_sql} WHERE {where_sql}"
            sql = f"SELECT DISTINCT s.url, s.lastmod AS tanggal, ss.sdg {from_sql} WHERE {where_sql} ORDER BY s.lastmod DESC LIMIT :limit OFFSET :offset"
        else:
            from_sql = "FROM berita_berita b JOIN berita_berita_kepmen_all bk ON bk.url = b.url"
            where = ["SUBSTRING(b.tanggal FROM 1 FOR 4) BETWEEN :year_from AND :year_to"]
            if pillars:
                where.append(f"bk.dampak IN ({self._in_clause(pillars, 'pillar', params)})")
            if topics:
                where.append(f"bk.topik IN ({self._in_clause(topics, 'topic', params)})")
            if sdgs:
                sdg_conditions = []
                for index, sdg in enumerate(sdgs):
                    name = f"impact_sdg{index}"
                    params[name] = str(sdg)
                    sdg_conditions.append(f":{name} = ANY(string_to_array(replace(COALESCE(bk.sdg, ''), '|', ','), ','))")
                where.append("(" + " OR ".join(sdg_conditions) + ")")
            if units:
                unit_sql = self._in_clause(units, "unit", params)
                where.append(
                    "EXISTS (SELECT 1 FROM berita_unit_kerja unit_filter "
                    "WHERE unit_filter.unit_kerja IN (" + unit_sql + ") "
                    "AND unit_filter.url = b.url)"
                )
            where_sql = " AND ".join(where)
            count_sql = f"SELECT COUNT(DISTINCT b.url) AS total {from_sql} WHERE {where_sql}"
            sql = f"SELECT b.url, b.judul, b.tanggal, b.sumber, bk.topik, bk.topik_kepmen, bk.sdg {from_sql} WHERE {where_sql} ORDER BY b.tanggal DESC, b.url LIMIT :limit OFFSET :offset"
        total = int(pd.read_sql(text(count_sql), self.engine, params=params).iloc[0]["total"])
        rows = pd.read_sql(text(sql), self.engine, params=params).fillna("").to_dict(orient="records")
        return {"page": page, "page_size": page_size, "total": total, "rows": rows}
