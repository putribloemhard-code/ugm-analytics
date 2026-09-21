from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.domain.models import FilterParams
from app.domain.source import kepmen, units
from app.services.sqlcompat import url_key


class AnalyticsService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _read(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        return pd.read_sql(text(sql), self.engine, params=params or {})

    @staticmethod
    def _params(values: tuple[str, ...], prefix: str, params: dict[str, Any]) -> str:
        names = []
        for index, value in enumerate(values):
            name = f"{prefix}{index}"
            params[name] = value
            names.append(f":{name}")
        return ", ".join(names) or "NULL"

    @staticmethod
    def _sdg_values(value: Any) -> list[int]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return []
        return [int(item) for item in re.findall(r"\d+", str(value))]

    def years(self) -> tuple[str, str]:
        row = self._read(
            "SELECT MIN(SUBSTRING(tanggal FROM 1 FOR 4)) AS year_min, "
            "MAX(SUBSTRING(tanggal FROM 1 FOR 4)) AS year_max "
            "FROM berita_berita WHERE tanggal IS NOT NULL AND tanggal <> ''"
        ).iloc[0]
        return str(row["year_min"] or "2005"), str(row["year_max"] or "2026")

    def metadata(self) -> dict[str, Any]:
        mapping = kepmen()
        unit_map = units().UNIT_KERJA
        year_min, year_max = self.years()
        topics = []
        for topic_id, meta in mapping.TOPIK_KEPMEN_ALL.items():
            topics.append({
                "id": topic_id,
                "label": mapping.LABEL_TOPIC_ALL[topic_id],
                "pillar": meta["dampak"],
                "official_topic": meta["topik_kepmen"],
                "sdgs": meta["sdg"],
                "indicator": meta.get("indikator", ""),
                "formula": meta.get("formula", ""),
                "unit": meta.get("satuan", ""),
            })
        return {
            "years": {"min": year_min, "max": year_max},
            "pillars": list(mapping.WARNA_PILAR.keys()),
            "topics": topics,
            "sdgs": [{"id": number, "label": mapping.SDG_NAMA[number]} for number in range(1, 18)],
            "units": [
                {"id": key, "label": value["nama"], "category": value["kategori"]}
                for key, value in unit_map.items()
            ],
            "updated_at": self._last_update(),
        }

    def _last_update(self) -> str | None:
        try:
            row = self._read("SELECT MAX(lastmod) AS lastmod FROM berita_sitemap").iloc[0]
            value = row["lastmod"]
            return None if pd.isna(value) else str(value)
        except Exception:
            return None

    def home_summary(self) -> dict[str, Any]:
        rows = self._read(
            "SELECT "
            "(SELECT COUNT(*) FROM berita_berita) AS total_berita, "
            "(SELECT COUNT(DISTINCT url) FROM berita_berita_kepmen_all) AS n_dampak, "
            "(SELECT COUNT(DISTINCT url) FROM berita_sitemap) AS total_sitemap"
        ).iloc[0]
        total = int(rows["total_berita"])
        impact = int(rows["n_dampak"])
        sitemap = int(rows["total_sitemap"])
        return {
            "total_berita": total,
            "n_dampak": impact,
            "total_sitemap": sitemap,
            "cakupan_pct": (100 * impact / sitemap) if sitemap else 0.0,
            "updated_at": self._last_update(),
        }

    def _impact_frames(self, filters: FilterParams) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
        default_start, default_end = self.years()
        start, end = filters.year_bounds(default_start, default_end)
        mapping = kepmen()
        pillars = filters.pillars or tuple(mapping.WARNA_PILAR.keys())
        topics = filters.topics or tuple(mapping.TOPIK_KEPMEN_ALL.keys())
        params: dict[str, Any] = {"year_from": start, "year_to": end}
        pillar_sql = self._params(pillars, "pillar", params)
        topic_sql = self._params(topics, "topic", params)
        unit_clause = ""
        if filters.units:
            unit_sql = self._params(filters.units, "unit", params)
            unit_clause = (
                " AND EXISTS (SELECT 1 FROM berita_unit_kerja unit_filter "
                "WHERE unit_filter.url = b.url AND unit_filter.unit_kerja IN (" + unit_sql + "))"
            )
        sql = (
            "SELECT b.url, b.judul, b.tanggal, b.deskripsi, b.sumber, "
            "bk.topik, bk.dampak, bk.topik_kepmen, bk.sdg "
            "FROM berita_berita b JOIN berita_berita_kepmen_all bk ON bk.url = b.url "
            "WHERE SUBSTRING(b.tanggal FROM 1 FOR 4) BETWEEN :year_from AND :year_to "
            f"AND bk.dampak IN ({pillar_sql}) AND bk.topik IN ({topic_sql})"
            + unit_clause
        )
        rows = self._read(sql, params)
        if rows.empty:
            return rows, rows.copy(), start, end
        news = rows[["url", "judul", "tanggal", "deskripsi", "sumber"]].drop_duplicates("url")
        news["tahun"] = news["tanggal"].astype(str).str[:4]
        return news, rows, start, end

    def impact(self, filters: FilterParams, mode: str) -> dict[str, Any]:
        news, tagged, start, end = self._impact_frames(filters)
        mapping = kepmen()
        selected_topics = filters.topics or tuple(mapping.TOPIK_KEPMEN_ALL.keys())
        selected_pillars = filters.pillars or tuple(mapping.WARNA_PILAR.keys())
        empty = news.empty or tagged.empty
        topic_counts = tagged.groupby("topik")["url"].nunique().to_dict() if not tagged.empty else {}
        topic_distribution = [
            {
                "id": topic_id,
                "label": mapping.LABEL_TOPIC_ALL[topic_id],
                "pillar": mapping.TOPIK_KEPMEN_ALL[topic_id]["dampak"],
                "count": int(topic_counts.get(topic_id, 0)),
            }
            for topic_id in selected_topics
            if mapping.TOPIK_KEPMEN_ALL[topic_id]["dampak"] in selected_pillars
        ]
        pillar_counts = []
        for pillar in selected_pillars:
            urls = tagged.loc[tagged["dampak"] == pillar, "url"].nunique() if not tagged.empty else 0
            pillar_counts.append({"id": pillar, "label": pillar, "count": int(urls)})
        yearly = []
        monthly = []
        if not news.empty:
            yearly = [
                {"year": str(year), "count": int(count)}
                for year, count in news.groupby("tahun")["url"].nunique().items()
            ]
            tagged_for_month = tagged.merge(news[["url", "tahun"]], on="url", how="left")
            tagged_for_month["month"] = tagged_for_month["tanggal"].astype(str).str[5:7]
            monthly = [
                {"month": str(month), "topic": mapping.LABEL_TOPIC_ALL.get(topic, topic), "count": int(count)}
                for (month, topic), count in tagged_for_month.groupby(["month", "topik"]).size().items()
            ]
        sdg_counts: dict[int, int] = {}
        sdg_rows = []
        if mode == "impact-sdgs" and not tagged.empty:
            for _, row in tagged.iterrows():
                for sdg in self._sdg_values(row["sdg"]):
                    sdg_rows.append({"url": row["url"], "sdg": sdg})
            if sdg_rows:
                sdg_frame = pd.DataFrame(sdg_rows).drop_duplicates(["url", "sdg"])
                if filters.sdgs:
                    sdg_frame = sdg_frame[sdg_frame["sdg"].isin(filters.sdgs)]
                sdg_counts = sdg_frame.groupby("sdg")["url"].nunique().astype(int).to_dict()
        news_rows = self._news_rows(news, tagged, mapping) if not empty else []
        narrative = self._impact_narrative(news, tagged, start, end, mode, sdg_rows)
        return {
            "mode": mode,
            "filters": {
                "year_from": start,
                "year_to": end,
                "pillars": list(selected_pillars),
                "topics": list(selected_topics),
                "sdgs": list(filters.sdgs),
                "units": list(filters.units),
            },
            "data_as_of": self._last_update(),
            "summary": {
                "total_news": int(news["url"].nunique()) if not news.empty else 0,
                "matched_news": int(tagged["url"].nunique()) if not tagged.empty else 0,
                "selected_topics": len(selected_topics),
                "year_range": f"{start}–{end}",
            },
            "narrative": narrative,
            "charts": {
                "pillars": pillar_counts,
                "topics": topic_distribution,
                "yearly": yearly,
                "monthly": monthly,
                "sdgs": [{"id": sdg, "label": mapping.sdg_label(sdg), "count": count} for sdg, count in sorted(sdg_counts.items())],
            },
            "tables": {"news": news_rows, "unmatched": []},
            "caveats": [
                "Angka bertema adalah lower-bound berbasis keyword dan data yang tersedia.",
                "SDG pada mode Dampak × SDGs berasal dari pemetaan resmi tema Kepmen, bukan keyword SDG langsung.",
            ],
        }

    def _news_rows(self, news: pd.DataFrame, tagged: pd.DataFrame, mapping: Any) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for _, row in news.iterrows():
            grouped[str(row["url"])] = {
                "url": str(row["url"]),
                "title": str(row["judul"] or ""),
                "date": str(row["tanggal"] or ""),
                "source": str(row["sumber"] or ""),
                "topics": [],
                "official_topics": [],
                "sdgs": [],
            }
        for _, row in tagged.iterrows():
            item = grouped.get(str(row["url"]))
            if item is None:
                continue
            topic_id = str(row["topik"])
            item["topics"].append(mapping.LABEL_TOPIC_ALL.get(topic_id, topic_id))
            item["official_topics"].append(str(row["topik_kepmen"] or ""))
            item["sdgs"].extend(self._sdg_values(row["sdg"]))
        for item in grouped.values():
            item["topics"] = sorted(set(item["topics"]))
            item["official_topics"] = sorted(set(item["official_topics"]))
            item["sdgs"] = sorted(set(item["sdgs"]))
        return list(grouped.values())

    def _impact_narrative(self, news: pd.DataFrame, tagged: pd.DataFrame, start: str, end: str, mode: str, sdg_rows: list[dict[str, Any]]) -> str:
        if news.empty or tagged.empty:
            return f"Belum ada data untuk filter {start}–{end}. Ubah filter untuk melihat analisis lain."
        try:
            narrative_module = __import__("app.domain.source", fromlist=["load_module"]).load_module("narasi_logic.py")
            b = news.copy()
            t = tagged.copy()
            bs = pd.DataFrame(sdg_rows)
            result = narrative_module.generate_executive_summary(b, t, bs, "Berdampak × SDGs" if mode == "impact-sdgs" else "Berdampak", start, end)
            return result["narasi"]
        except Exception:
            return f"Dalam rentang {start}–{end}, terdapat {news['url'].nunique():,} berita unik yang masuk filter analisis."

    def sdgs(self, filters: FilterParams) -> dict[str, Any]:
        default_start, default_end = self.years()
        start, end = filters.year_bounds(default_start, default_end)
        params: dict[str, Any] = {"year_from": start, "year_to": end}
        sdgs = filters.sdgs or tuple(range(1, 18))
        sdg_sql = self._params(tuple(str(sdg) for sdg in sdgs), "sdg", params)
        unit_clause = ""
        if filters.units:
            unit_sql = self._params(filters.units, "unit", params)
            unit_clause = (
                " AND EXISTS (SELECT 1 FROM berita_unit_kerja uk "
                "WHERE uk.unit_kerja IN (" + unit_sql + ") "
                f"AND {url_key(self.engine, 'uk.url')} = {url_key(self.engine, 's.url')})"
            )
        sitemap_sql = (
            "SELECT s.url, s.lastmod FROM berita_sitemap s "
            "WHERE SUBSTRING(s.lastmod FROM 1 FOR 4) BETWEEN :year_from AND :year_to" + unit_clause
        )
        sitemap = self._read(sitemap_sql, params)
        tagged_params = dict(params)
        tagged = self._read(
            "SELECT s.url, s.lastmod, ss.sdg FROM berita_sitemap s "
            "JOIN berita_sitemap_sdg ss ON ss.url = s.url "
            "WHERE SUBSTRING(s.lastmod FROM 1 FOR 4) BETWEEN :year_from AND :year_to "
            f"AND ss.sdg IN ({sdg_sql})" + unit_clause,
            tagged_params,
        )
        dist = tagged.groupby("sdg")["url"].nunique().astype(int).to_dict() if not tagged.empty else {}
        yearly = []
        if not tagged.empty:
            tagged["year"] = tagged["lastmod"].astype(str).str[:4]
            yearly = [
                {"year": str(year), "sdg": int(sdg), "count": int(count)}
                for (year, sdg), count in tagged.drop_duplicates(["url", "sdg", "year"]).groupby(["year", "sdg"]).size().items()
            ]
        narrative = (
            f"Dalam rentang {start}–{end}, {tagged['url'].nunique():,} URL sitemap bertanda sedikitnya satu SDG."
            if not tagged.empty else f"Belum ada data SDG untuk rentang {start}–{end}."
        )
        return {
            "mode": "sdgs",
            "filters": {"year_from": start, "year_to": end, "sdgs": list(sdgs), "units": list(filters.units)},
            "data_as_of": self._last_update(),
            "summary": {
                "total_sitemap": int(sitemap["url"].nunique()) if not sitemap.empty else 0,
                "tagged_urls": int(tagged["url"].nunique()) if not tagged.empty else 0,
                "coverage_pct": (100 * tagged["url"].nunique() / sitemap["url"].nunique()) if len(sitemap) else 0.0,
                "year_range": f"{start}–{end}",
            },
            "narrative": narrative,
            "charts": {
                "sdgs": [
                    {"id": int(sdg), "label": f"SDG {int(sdg)}", "count": int(dist.get(sdg, 0))}
                    for sdg in sdgs
                ],
                "yearly": yearly,
            },
            "tables": {
                "summary": [
                    {"sdg": f"SDG {int(sdg)}", "name": mapping_name, "count": int(dist.get(sdg, 0))}
                    for sdg, mapping_name in [(sdg, kepmen().SDG_NAMA[int(sdg)]) for sdg in sdgs]
                ]
            },
            "caveats": [
                "Mode SDGs memakai pencocokan langsung pada URL sitemap dan data berita yang tersedia.",
                "Satu URL dapat masuk ke lebih dari satu SDG.",
            ],
        }
