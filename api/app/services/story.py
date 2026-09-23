"""Endpoint `/analytics/story`: semua chart + insight dashboard Streamlit lama (berita-dampak/) dalam satu respons.

Port setia dari berita-dampak/page_dampak.py (mode "Berdampak" & "Berdampak × SDGs") dan
berita-dampak/page_sdgs.py (mode "SDGs"). Angka & kalimat insight sama dengan dashboard; narasi
eksekutif/pilar memakai scripts/narasi_logic.py apa adanya (tanpa dependensi Streamlit).

Rancangan:
- `build_story()` FUNGSI MURNI: menerima DataFrame (`StoryFrames`) + filter, mengembalikan dict.
  Jadi bisa diuji tanpa database (lihat tests/test_story.py).
- `StoryService` hanya memuat DataFrame lewat SELECT sederhana (portabel PostgreSQL/MySQL) dan
  men-cache-nya beberapa menit (seperti `ttl=300` di dashboard), lalu memanggil `build_story()`.
- Filter tahun/pilar/tema/unit dikerjakan di pandas, bukan SQL, supaya dialek tidak berpengaruh.

Konvensi urutan bar: bar horizontal dikirim TERBESAR DULU (atas ke bawah); bar vertikal SDG mengikuti
dashboard (naik menurut jumlah). Insight dikirim sebagai teks polos (penanda **tebal** dibuang).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.domain.models import FilterParams
from app.domain.source import kepmen, keywords, load_module, units
from app.services.matkul import KRITERIA_LABEL, MatkulFrames, load_matkul, meta_tema as meta_tema_matkul, tema_dari_kriteria
from app.services.ringkasan_kepmen import CATATAN_METODE_RESMI

logger = logging.getLogger(__name__)

PILLARS = ("Lingkungan", "Ekonomi", "Sosial")
MODE_LABEL = {"impact": "Berdampak", "impact-sdgs": "Berdampak × SDGs"}
MAX_ROWS = 200
# Baris per halaman untuk tabel "Daftar berita" di web (tombol Sebelumnya/Berikutnya).
# Tabel berita panjang (sampai MAX_ROWS) jadi 40 halaman; tabel ringkas tetap tampil utuh.
NEWS_PAGE_SIZE = 5
CACHE_TTL_SECONDS = 300
_CACHE_MAX_ENGINES = 8

# Urutan bab & sub-bab mengikuti LAPORAN DAMPAK SOSIAL, EKONOMI, DAN LINGKUNGAN UGM 2025
# (daftar isi resmi: BAB II Sosial 4 tema, BAB III Ekonomi 5 tema, BAB IV Lingkungan 5 tema).
# Nomor sub-bab dipakai untuk label "2.1", "3.4", dst. di dashboard; angka BAB II-IV karena
# BAB I = Pendahuluan tidak punya tema. Topik di luar daftar ini (tidak ada saat ini) tetap
# ditampilkan sebagai bab tambahan tanpa nomor supaya tidak ada data yang hilang.
CHAPTER_ORDER = {
    "Sosial": {
        "bab": "BAB II", "judul": "Dampak Sosial",
        "topics": [
            ("pendidikan_inklusif", "2.1"),
            ("penelitian_inovasi_sosial", "2.2"),
            ("pengabdian_masyarakat", "2.3"),
            ("instansi_publik", "2.4"),
        ],
    },
    "Ekonomi": {
        "bab": "BAB III", "judul": "Dampak Ekonomi",
        "topics": [
            ("pengajaran_pembelajaran", "3.1"),
            ("kolaborasi_riset", "3.2"),
            ("kewirausahaan", "3.3"),
            ("kunjungan_akademik", "3.4"),
            ("belanja_umkm", "3.5"),
        ],
    },
    "Lingkungan": {
        "bab": "BAB IV", "judul": "Dampak Lingkungan",
        "topics": [
            ("energi", "4.1"),
            ("limbah", "4.2"),
            ("transportasi", "4.3"),
            ("rehabilitasi_lingkungan", "4.4"),
            ("pendidikan_dan_penelitian", "4.5"),
        ],
    },
}

# Judul sub-bab PERSIS seperti daftar isi laporan resmi, dipakai di panel "Daftar isi" supaya
# pembaca bisa mencocokkan 1:1 dengan dokumen. Sebagian berbeda dari nama tema Kepmen
# (`TOPIK_KEPMEN_ALL[...]["topik_kepmen"]`) — mis. laporan memakai "Konsumsi Energi yang
# Bertanggung Jawab" dan "…Pengunjung Nasional" (Kepmen: "Konsumsi yang Bertanggung Jawab",
# "…Pengunjung"). Tema tanpa entri di sini judulnya sama dengan nama resmi Kepmen.
REPORT_SUBSECTION_TITLES = {
    "penelitian_inovasi_sosial": "Penelitian dan Inovasi",
    "pengabdian_masyarakat": "Pengabdian dan Pengembangan Masyarakat",
    "kolaborasi_riset": "Penelitian dan Pertukaran Pengetahuan",
    "kunjungan_akademik": "Kunjungan Akademik dan Pengeluaran Pengunjung Nasional",
    "limbah": "Konsumsi Energi yang Bertanggung Jawab",
}

STOPWORDS = set(
    """dan di ke dari yang untuk dengan pada dalam sebagai oleh ini itu atau
    serta akan telah dapat tidak juga para bagi agar karena antara melalui
    terhadap tentang hingga sampai setelah sebelum ketika saat secara merupakan
    menjadi adalah yaitu yakni tahun baru kembali lebih paling sangat ada bisa
    harus sudah sedang masih semua setiap berbagai sebuah suatu satu dua tiga
    indonesia universitas ugm gadjah mada the and for with from that this are
    was were has have had will its their into about through during after
    before more most also can could should would may of to in is it on at by
    an be as or you your we our they them his her not but what when where how
    why do does did done up out off over under antara""".split()
)

CAVEATS = [
    "Angka bertema adalah lower-bound berbasis keyword dan data yang tersedia.",
    "SDG pada mode Dampak × SDGs berasal dari pemetaan resmi tema Kepmen, bukan keyword SDG langsung.",
]
CAVEATS_SDGS = [
    "Mode SDGs memakai pencocokan langsung pada URL sitemap dan data berita yang tersedia.",
    "Satu URL dapat masuk ke lebih dari satu SDG.",
]


# --------------------------------------------------------------------------------------
# Data mentah
# --------------------------------------------------------------------------------------
@dataclass
class StoryFrames:
    """DataFrame mentah (tidak boleh dimutasi -- selalu .copy() sebelum menambah kolom)."""

    berita: pd.DataFrame      # url, judul, tanggal, deskripsi, sumber
    bk: pd.DataFrame          # url, topik, dampak, topik_kepmen
    bs: pd.DataFrame          # url, sdg   (berita_berita_sdg_all)
    uk: pd.DataFrame          # url, unit_kerja, kategori
    sitemap: pd.DataFrame     # url, lastmod
    ss: pd.DataFrame          # url, sdg   (berita_sitemap_sdg)
    rp: pd.DataFrame          # dampak, jumlah_berita
    data_as_of: str | None = None
    matkul: "MatkulFrames | None" = None   # data mata kuliah (matkul-sustainability)
    # Narasi hasil LLM (berita_narasi_cache, scripts/generate_narasi_llm.py): cache_key -> teks.
    narasi_llm: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Helper kalimat insight (port dari berita-dampak/common.py, tanpa streamlit)
# --------------------------------------------------------------------------------------
def token_freq(df: pd.DataFrame) -> Counter:
    """Frekuensi kata pada judul + deskripsi (stopword dibuang)."""
    counter: Counter = Counter()
    teks = df["judul"].fillna("") + " " + df["deskripsi"].fillna("")
    for item in teks:
        for kata in re.findall(r"[a-z]{3,}", item.lower()):
            if kata not in STOPWORDS:
                counter[kata] += 1
    return counter


def insight_top2(df: pd.DataFrame, label_col: str, value_col: str, satuan: str = "berita") -> str:
    """Kalimat top-1 vs top-2 (dengan penanda **tebal** seperti dashboard; pakai `plain()` untuk teks polos)."""
    d = df.sort_values(value_col, ascending=False, kind="stable").reset_index(drop=True)
    top = d.iloc[0]
    n1 = int(top[value_col])
    if len(d) > 1:
        second = d.iloc[1]
        n2 = int(second[value_col])
        beda_text = f"{(n1 - n2) / n2 * 100:.0f}% lebih tinggi" if n2 else "jauh lebih tinggi"
        return (
            f"**{top[label_col]}** paling dominan dengan {n1:,} {satuan}, "
            f"{beda_text} dari {second[label_col]} ({n2:,} {satuan})."
        )
    return f"**{top[label_col]}** dengan {n1:,} {satuan}."


def insight_heatmap(matrix: pd.DataFrame, satuan: str = "berita") -> str:
    """Kalimat sel tertinggi dari matriks heatmap (index = baris, columns = kolom)."""
    stacked = matrix.stack()
    if not len(stacked):
        return "Belum ada data untuk kombinasi ini."
    (row, col), val = stacked.idxmax(), stacked.max()
    return f"Kombinasi tertinggi: **{row} × {col}** dengan {int(val):,} {satuan}."


def plain(value: str | None) -> str | None:
    """Buang penanda markdown **tebal** tetapi pertahankan katanya."""
    return None if value is None else value.replace("**", "")


def _native(obj: Any) -> Any:
    """Ubah skalar numpy/pandas jadi tipe Python biasa supaya aman di-JSON-kan (NaN -> None)."""
    if isinstance(obj, dict):
        return {str(key): _native(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_native(item) for item in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, float):
        return None if obj != obj else obj
    if obj is pd.NaT or obj is pd.NA:
        return None
    return obj


# --------------------------------------------------------------------------------------
# Pembuat bentuk chart/tabel generik
# --------------------------------------------------------------------------------------
def _chart(chart_id: str, kind: str, title: str, data: Any, insight: str | None = None,
           note: str | None = None, **extra: Any) -> dict[str, Any]:
    chart = {"id": chart_id, "kind": kind, "title": title, "insight": plain(insight), "note": note, "data": data}
    chart.update(extra)
    return chart


def _bar_data(df: pd.DataFrame, label_col: str, value_col: str, group_col: str | None = None,
              detail_col: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for record in df.to_dict("records"):
        item = {
            "label": str(record[label_col]),
            "value": int(record[value_col]),
            "group": None if group_col is None else str(record[group_col]),
        }
        if detail_col:
            item["detail"] = str(record[detail_col])
        rows.append(item)
    return rows


def _heatmap_data(matrix: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": [str(item) for item in matrix.index],
        "cols": [str(item) for item in matrix.columns],
        "values": matrix.astype(int).to_numpy().tolist(),
    }


def _line_data(df: pd.DataFrame, x_col: str, series_col: str, y_col: str,
               series_order: list[str] | None = None) -> dict[str, Any]:
    series = []
    order = series_order if series_order is not None else list(dict.fromkeys(df[series_col]))
    for name in order:
        sub = df[df[series_col] == name].sort_values(x_col, kind="stable")
        if sub.empty:
            continue
        series.append({
            "name": str(name),
            "points": [{"x": str(x), "y": int(y)} for x, y in zip(sub[x_col], sub[y_col])],
        })
    return {"series": series}


def _stacked_data(df: pd.DataFrame, x_col: str, series_col: str, value_col: str,
                  series_order: list[str] | None = None) -> dict[str, Any]:
    piv = df.pivot_table(index=x_col, columns=series_col, values=value_col, aggfunc="sum", fill_value=0)
    piv = piv.sort_index()
    order = [name for name in (series_order or list(piv.columns)) if name in piv.columns]
    return {
        "x": [str(item) for item in piv.index],
        "series": [{"name": str(name), "values": [int(v) for v in piv[name].tolist()]} for name in order],
    }


def _table(table_id: str, title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]],
           note: str | None = None, insight: str | None = None,
           page_size: int | None = None, max_rows: int | None = None) -> dict[str, Any]:
    return {
        "id": table_id,
        "title": title,
        "note": note,
        "insight": plain(insight),
        "columns": [{"key": key, "label": label} for key, label in columns],
        "rows": rows[:max_rows if max_rows is not None else MAX_ROWS],
        # page_size: baris per halaman di UI (tabel daftar berita = NEWS_PAGE_SIZE).
        # None = tabel ditampilkan utuh (tabel ringkas: distribusi, unit kerja, dsb).
        "page_size": page_size,
    }


def _split_first_sentence(text_value: str) -> tuple[str, str | None]:
    """Pecah teks dashboard 'kalimat insight. penjelasan...' menjadi (insight, catatan)."""
    marker = ". "
    index = text_value.find(marker)
    if index < 0:
        return text_value, None
    return text_value[: index + 1], text_value[index + 2:]


# --------------------------------------------------------------------------------------
# Konteks perhitungan bersama untuk mode Berdampak / Berdampak × SDGs
# --------------------------------------------------------------------------------------
@dataclass
class _Ctx:
    mode: str
    mode_label: str
    start: str
    end: str
    b: pd.DataFrame            # berita ter-filter (tahun + unit) dengan kolom `tahun`
    b_nounit: pd.DataFrame     # berita tanpa filter unit kerja
    t: pd.DataFrame            # tag Kepmen ter-filter (== bk_f di dashboard)
    t_nounit: pd.DataFrame
    b_t: pd.DataFrame
    bs_f: pd.DataFrame
    uk: pd.DataFrame
    tampil: list[str]          # TOPIK_TAMPIL (urutan LABEL_TOPIC)
    topik_pilih: tuple[str, ...]
    pillar_set: tuple[str, ...]
    keywords_all: dict[str, list[str]]
    # Narasi LLM yang boleh dipakai (kosong kalau filter bukan default) -- lihat _narasi_llm_aktif.
    narasi_llm: dict[str, str] = field(default_factory=dict)


def _keywords_all() -> dict[str, list[str]]:
    result = dict(keywords().KEYWORDS)
    result.update({key: value["keywords"] for key, value in kepmen().TEMA_KEPMEN_LENGKAP.items()})
    return result


def _narasi_llm_aktif(frames: StoryFrames, filters: FilterParams, mode: str, start: str, end: str) -> dict[str, str]:
    """Narasi LLM hanya valid untuk filter DEFAULT (semua tahun/pilar/tema/SDG, tanpa unit kerja).

    Aturannya sama dengan dashboard Streamlit lama (FILTER_ADALAH_DEFAULT): cache digenerate
    dari angka seluruh data, jadi begitu filter menyempit angkanya tidak cocok lagi dan narasi
    template (narasi_logic.py, dihitung ulang dari data ter-filter) yang dipakai.
    """
    if not frames.narasi_llm:
        return {}
    semua_tahun = (start, end) == _year_range(frames.berita)
    semua_pilar = set(filters.pillars or PILLARS) == set(PILLARS)
    semua_tema = set(filters.topics or kepmen().TOPIK_KEPMEN_ALL) == set(kepmen().TOPIK_KEPMEN_ALL)
    semua_sdg = mode != "impact-sdgs" or set(filters.sdgs or range(1, 18)) == set(range(1, 18))
    if semua_tahun and semua_pilar and semua_tema and semua_sdg and not filters.units:
        return frames.narasi_llm
    return {}


def _year_range(berita: pd.DataFrame) -> tuple[str, str]:
    years = berita["tanggal"].dropna().astype(str).str[:4]
    years = years[years.str.fullmatch(r"\d{4}")]
    if years.empty:
        return "2005", "2026"
    return str(years.min()), str(years.max())


def _add_year(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    out["tahun"] = out[column].fillna("").astype(str).str[:4]
    return out


def _topic_counts_by_url(t: pd.DataFrame, topics: list[str]) -> pd.Series:
    if t.empty:
        return pd.Series(dtype=int)
    return t[t["topik"].isin(topics)].groupby("topik")["url"].nunique()


def _default_topic(t: pd.DataFrame, options: list[str]) -> str | None:
    """Tema dengan berita terbanyak di antara `options` (seri: urutan LABEL_TOPIC)."""
    if not options:
        return None
    counts = _topic_counts_by_url(t, options)
    best, best_n = options[0], -1
    for key in options:
        n = int(counts.get(key, 0))
        if n > best_n:
            best, best_n = key, n
    return best


def _keyword_counts(sub: pd.DataFrame, kws: list[str]) -> pd.DataFrame:
    teks = (sub["judul"].fillna("") + " " + sub["deskripsi"].fillna("")).str.lower()
    rows = []
    for kw in kws:
        n = int(teks.str.contains(kw, regex=False).sum())
        if n:
            rows.append({"keyword": kw, "jumlah": n})
    return pd.DataFrame(rows, columns=["keyword", "jumlah"])


def _keyword_charts(ctx: _Ctx, topic: str, id_prefix: str, kw_title: str, word_title: str) -> list[dict[str, Any]]:
    """Dua chart tema terpilih: keyword pemicu match + 15 kata teratas."""
    urls = set(ctx.t.loc[ctx.t["topik"] == topic, "url"])
    sub = ctx.b[ctx.b["url"].isin(urls)]
    charts = []
    kw_df = _keyword_counts(sub, ctx.keywords_all.get(topic, []))
    if len(kw_df):
        kw_df = kw_df.sort_values("jumlah", ascending=False, kind="stable")
        top = kw_df.iloc[0]
        charts.append(_chart(
            f"{id_prefix}_keyword", "bar", kw_title, _bar_data(kw_df, "keyword", "jumlah"),
            insight=insight_top2(kw_df, "keyword", "jumlah") if id_prefix == "pilar" else
            f"Keyword paling sering memicu match pada tema ini: {top['keyword']} ({int(top['jumlah']):,} berita).",
            note=("Angka = berita yang judul/deskripsinya mengandung keyword tsb; satu berita bisa match beberapa "
                  "keyword, jadi totalnya bisa melebihi jumlah berita tema." if id_prefix == "pilar" else
                  "Satu berita bisa match beberapa keyword, jadi totalnya bisa melebihi jumlah berita tema."),
            orientation="h",
        ))
    freq_df = pd.DataFrame(token_freq(sub).most_common(15), columns=["kata", "jumlah"])
    if len(freq_df):
        top = freq_df.iloc[0]
        charts.append(_chart(
            f"{id_prefix}_kata", "bar", word_title, _bar_data(freq_df, "kata", "jumlah"),
            insight=(insight_top2(freq_df, "kata", "jumlah", satuan="kali") if id_prefix == "pilar" else
                     f"Kata paling sering muncul: {top['kata']} ({int(top['jumlah']):,} kali) di judul + deskripsi berita tema tsb."),
            note=("Kata di judul + deskripsi berita tema tsb (stopword dibuang, kata umum seperti "
                  "'ugm'/'universitas' sengaja dibuang)."),
            orientation="h",
        ))
    return charts


def _news_rows(news: pd.DataFrame, columns: dict[str, str]) -> list[dict[str, Any]]:
    """Baris tabel dari DataFrame berita; `columns` = {kolom_sumber: kunci_tabel}."""
    out = news[list(columns)].copy()
    out.columns = list(columns.values())
    return _native(out.fillna("").to_dict("records"))


# --------------------------------------------------------------------------------------
# Mode Berdampak / Berdampak × SDGs
# --------------------------------------------------------------------------------------
def _story_impact(fr: StoryFrames, filters: FilterParams, mode: str, start: str, end: str,
                  pillar: str | None, topic: str | None,
                  matkul: MatkulFrames | None = None) -> dict[str, Any]:
    mapping = kepmen()
    label_topic = mapping.LABEL_TOPIC_ALL
    meta = mapping.TOPIK_KEPMEN_ALL
    mode_label = MODE_LABEL[mode]
    pillar_set = tuple(p for p in PILLARS if p in (filters.pillars or PILLARS))
    topik_pilih = tuple(filters.topics or meta.keys())

    b = _add_year(fr.berita, "tanggal")
    b = b[b["tahun"].between(start, end)]
    b_nounit = b
    if filters.units:
        b = b[b["url"].isin(set(fr.uk.loc[fr.uk["unit_kerja"].isin(filters.units), "url"]))]

    def build_t(b_df: pd.DataFrame) -> pd.DataFrame:
        t_ = fr.bk[fr.bk["topik"].isin(topik_pilih) & fr.bk["dampak"].isin(pillar_set)]
        return t_[t_["url"].isin(set(b_df["url"]))]

    t = build_t(b)
    t_nounit = build_t(b_nounit)
    tampil = [k for k in label_topic if k in set(topik_pilih) and meta[k]["dampak"] in pillar_set]

    response = {
        "mode": mode,
        "filters": {
            "year_from": start,
            "year_to": end,
            "pillars": list(pillar_set),
            "topics": list(topik_pilih),
            "sdgs": list(filters.sdgs),
            "units": list(filters.units),
        },
        "data_as_of": fr.data_as_of,
        "caveats": list(CAVEATS),
        "executive": {"metrics": [], "narrative": "Tidak ada data untuk filter ini. Ubah filter untuk melihat analisis lain.",
                      "narrative_source": "template"},
        "overview": [],
        "cross": {"title": "Analisis Lintas-Dampak", "charts": [], "tables": []},
        "pillar_detail": None,
        "chapters": [],
        "mata_kuliah": mata_kuliah_blok(matkul, pillar, topic,
                                        sdgs=tuple(filters.sdgs), sdg_mode=mode == "impact-sdgs"),
        "tables": [],
    }
    if b.empty or t.empty:
        return response

    b_t = b.merge(t, on="url", how="inner")
    urls_t = set(b_t["url"])
    bs = fr.bs
    if mode == "impact-sdgs" and filters.sdgs:
        bs = bs[bs["sdg"].isin(filters.sdgs)]
    bs_f = bs[bs["url"].isin(urls_t)]
    ctx = _Ctx(mode, mode_label, start, end, b, b_nounit, t, t_nounit, b_t, bs_f, fr.uk, tampil,
               topik_pilih, pillar_set, _keywords_all(), _narasi_llm_aktif(fr, filters, mode, start, end))

    narasi = load_module("narasi_logic.py")
    ringkasan = narasi.generate_executive_summary(b, t, bs_f, mode_label, start, end)
    delta_label = (
        f"{ringkasan['pilar_top_pct']:+.1f}%" if ringkasan["pilar_top_pct"] is not None
        else (f"+{ringkasan['pilar_top_naik']} berita" if ringkasan["pilar_top_naik"] else None)
    )
    response["executive"] = {
        "metrics": [
            {"label": "Total berita dampak", "value": ringkasan["total_berita"], "note": None},
            {
                "label": "Dampak pertumbuhan tertinggi", "value": ringkasan["pilar_top"], "note": delta_label,
                "help": (f"Dibandingkan sejak {ringkasan['pilar_top_baseline_tahun']} (baseline 5 tahun terakhir, bukan "
                         "dari titik awal rentang filter -- basis awal yang terlalu kecil bisa membuat persentase menyesatkan)."),
            },
            {"label": f"Sorotan {end}", "value": f"{ringkasan['berita_tahun_ini']:,} berita", "note": None},
            {"label": ringkasan["topik_top_kind_label"], "value": ringkasan["topik_top_short"], "note": None},
        ],
        "narrative": ringkasan["narasi"],
        "narrative_source": "template",
    }
    # Cache LLM digenerate untuk ringkasan eksekutif kedua mode (lihat generate_narasi_llm.py).
    exec_key = "exec_berdampak_sdgs" if mode == "impact-sdgs" else "exec_berdampak"
    if ctx.narasi_llm.get(exec_key):
        response["executive"].update(narrative=ctx.narasi_llm[exec_key], narrative_source="llm")
    response["overview"] = overview_rows(b, t, pillar_set)
    response["cross"] = _cross(ctx, fr, topic)
    # Bab laporan resmi: Sosial (BAB II) → Ekonomi (BAB III) → Lingkungan (BAB IV),
    # tiap bab berisi sub-bab per tema sesuai daftar isi LAPORAN DAMPAK UGM 2025.
    response["chapters"] = chapter_rows(ctx)
    response["mata_kuliah"] = mata_kuliah_blok(matkul, pillar, topic,
                                               sdgs=tuple(filters.sdgs), sdg_mode=mode == "impact-sdgs")
    if pillar:
        response["pillar_detail"] = _pillar_detail(ctx, pillar, topic)
    return response


def overview_rows(b: pd.DataFrame, t: pd.DataFrame, pillar_set: tuple[str, ...]) -> list[dict[str, Any]]:
    """Per dampak: total berita unik + tema (label pendek) terbanyak (page_dampak.py:281-337)."""
    label_topic = kepmen().LABEL_TOPIC_ALL
    rows = []
    for pilar in pillar_set:
        pilar_topik = t[t["dampak"] == pilar]
        total = int(b[b["url"].isin(set(pilar_topik["url"]))]["url"].nunique())
        counts = pilar_topik.groupby("topik")["url"].nunique().sort_values(ascending=False, kind="stable").head(1)
        if counts.empty:
            top_topic, top_n = None, 0
        else:
            top_topic, top_n = label_topic.get(counts.index[0], counts.index[0]), int(counts.iloc[0])
        rows.append({"pillar": pilar, "total": total, "top_topic": top_topic, "top_topic_count": top_n})
    return rows


def _chapter_subsection(ctx: _Ctx, topik: str, nomor: str) -> dict[str, Any]:
    """Satu sub-bab laporan = satu tema resmi Kepmen (mis. 2.1 Pendidikan Inklusif).

    Isi sub-bab = daftar indikator resmi (indikator/definisi/kriteria/formula/satuan + klaster SDG)
    ditambah chart yang sudah ada di dashboard untuk tema ini. Chart yang tidak ada datanya tetap
    dikirim (data kosong) supaya tiap sub-bab punya bentuk yang sama.
    """
    mapping = kepmen()
    meta = mapping.TOPIK_KEPMEN_ALL[topik]
    label = mapping.LABEL_TOPIC_ALL.get(topik, topik)

    urls_tema = set(ctx.t.loc[ctx.t["topik"] == topik, "url"])
    urls_nounit = set(ctx.t_nounit.loc[ctx.t_nounit["topik"] == topik, "url"])
    berita_tema = ctx.b[ctx.b["url"].isin(urls_tema)]
    pilar = meta["dampak"]
    # Klaster SDG = atribut resmi TEMA (dari UGM Analytics.xlsx), bukan hasil pencocokan berita.
    sdg_klaster = [int(s) for s in meta.get("sdg", [])]

    charts: list[dict[str, Any]] = []

    # 1. Tren tahunan tema ini (volume pemberitaan) — potret capaian per tahun.
    tren = berita_tema.groupby("tahun")["url"].nunique().reset_index(name="jumlah").sort_values("tahun")
    if len(tren):
        awal, akhir = tren.iloc[0], tren.iloc[-1]
        delta = int(akhir["jumlah"]) - int(awal["jumlah"])
        puncak = tren.loc[tren["jumlah"].idxmax()]
        charts.append(_chart(
            f"chapter_{topik}_tren", "line", f"Tren pemberitaan tema {label} per tahun",
            {"series": [{"name": "Jumlah berita", "points": [
                {"x": str(x), "y": int(y)} for x, y in zip(tren["tahun"], tren["jumlah"])]}]},
            insight=(f"Dari {int(awal['jumlah']):,} berita ({awal['tahun']}) menjadi {int(akhir['jumlah']):,} berita "
                     f"({akhir['tahun']}) — {'naik' if delta >= 0 else 'turun'} {abs(delta):,} berita. "
                     f"Puncak tertinggi: {puncak['tahun']} dengan {int(puncak['jumlah']):,} berita."),
            note="Jumlah berita unik bertema ini per tahun (satu berita dihitung sekali walau match beberapa keyword).",
        ))

    # 2. Klaster SDG resmi tema ini + sebaran berita tema per SDG.
    bs_tema = ctx.bs_f[ctx.bs_f["url"].isin(urls_tema)]
    if len(bs_tema):
        dist = bs_tema.groupby("sdg")["url"].nunique().reset_index(name="jumlah")
        dist["label"] = dist["sdg"].map(lambda s: f"SDG {s}")
        dist["nama"] = dist["sdg"].map(lambda s: mapping.sdg_label(int(s)))
        charts.append(_chart(
            f"chapter_{topik}_sdg", "bar", f"Berita tema {label} per SDG", _bar_data(dist, "label", "jumlah", detail_col="nama"),
            insight=insight_top2(dist, "label", "jumlah"),
            note=("Berita tema ini yang bertanda SDG (pemetaan resmi tema Kepmen → klaster SDGs); satu berita bisa "
                  "masuk lebih dari satu SDG."),
            orientation="v",
        ))

    # 3. Fakultas/unit kerja penyumbang berita tema ini (basis tanpa filter unit, seperti tab unit).
    uk_tema, dist_unit = _unit_dist(ctx.uk, urls_nounit, units().UNIT_KERJA)
    if len(uk_tema):
        charts.append(_chart(
            f"chapter_{topik}_unit", "bar", f"Fakultas/Unit Kerja penyumbang berita — {label}",
            _bar_data(dist_unit, "nama", "jumlah", group_col="kategori"),
            insight=insight_top2(dist_unit, "nama", "jumlah"),
            note=("Hasil keyword matching nama resmi 44 fakultas/sekolah/unit kerja UGM pada judul + deskripsi berita -- "
                  "lower-bound, bukan angka final kontribusi unit. Filter \"Fakultas / Unit Kerja\" di sidebar sengaja "
                  "diabaikan di sini supaya rankingnya adil."),
            orientation="h",
        ))

    latest = berita_tema.sort_values("tanggal", ascending=False, kind="stable").head(MAX_ROWS)
    tables = [_table(
        f"chapter_{topik}_berita", f"Daftar berita — {label}",
        [("tanggal", "Tanggal"), ("judul", "Judul"), ("sumber", "Sumber"), ("url", "Tautan")],
        _news_rows(latest, {"tanggal": "tanggal", "judul": "judul", "sumber": "sumber", "url": "url"}),
        note=(f"{len(latest):,} berita terbaru tema ini (maks. {MAX_ROWS} baris, tampil {NEWS_PAGE_SIZE} per halaman). "
              "Tabel ini dasar penelusuran angka "
              "pada chart di atas."),
        page_size=NEWS_PAGE_SIZE,
    )]
    return {
        "id": topik,
        "number": nomor,
        "topic": topik,
        "label": label,
        "official_topic": meta["topik_kepmen"],
        "report_title": REPORT_SUBSECTION_TITLES.get(topik, meta["topik_kepmen"]),
        "pillar": pilar,
        "indicator": meta.get("indikator", ""),
        "definition": meta.get("definisi", ""),
        "criteria": meta.get("kriteria", ""),
        "formula": meta.get("formula", ""),
        "unit": meta.get("satuan", ""),
        "sdgs": sdg_klaster,
        "sdg_labels": [{"id": s, "label": mapping.sdg_label(s)} for s in sdg_klaster],
        "metrics": [
            {"label": "Berita unik", "value": int(berita_tema["url"].nunique())},
            {"label": "Tahun jangkauan", "value": (f"{berita_tema['tahun'].min()}–{berita_tema['tahun'].max()}"
                                                    if len(berita_tema) else "—")},
            {"label": "SDG terkait", "value": len(sdg_klaster)},
        ],
        "charts": charts,
        "tables": tables,
    }


def chapter_rows(ctx: _Ctx) -> list[dict[str, Any]]:
    """Susun 3 bab laporan (Sosial 4 tema, Ekonomi 5, Lingkungan 5) + sub-bab per tema.

    Urutan bab = urutan daftar isi laporan (Sosial → Ekonomi → Lingkungan), bukan urutan
    internal `PILLARS`. Semua tema yang lolos filter tetap ditampilkan walau berita nol supaya
    bentuk bab/sub-bab tidak berubah-ubah; indikator resmi Kepmen tetap muncul sebagai rujukan
    penilaian. Bab yang tidak punya satu pun sub-bab (mis. semua temanya tersaring filter tema)
    dilewati supaya tidak ada judul bab kosong.
    """
    label_topic = kepmen().LABEL_TOPIC_ALL
    meta = kepmen().TOPIK_KEPMEN_ALL
    urutan_bab = list(CHAPTER_ORDER) + [p for p in ctx.pillar_set if p not in CHAPTER_ORDER]
    chapters: list[dict[str, Any]] = []
    for pilar in urutan_bab:
        if pilar not in ctx.pillar_set:
            continue
        urutan = CHAPTER_ORDER.get(pilar)
        if urutan is None:
            # Pilar tanpa urutan resmi: tetap ditampilkan, sub-bab diurut label, tanpa nomor.
            nomor_map = {k: "" for k in ctx.tampil if meta[k]["dampak"] == pilar}
            bab, judul = pilar, f"Dampak {pilar}"
        else:
            nomor_map = dict(urutan["topics"])
            bab, judul = urutan["bab"], urutan["judul"]
        subsections = [
            _chapter_subsection(ctx, k, nomor_map.get(k, ""))
            for k in sorted((k for k in ctx.tampil if meta[k]["dampak"] == pilar),
                            key=lambda k: (nomor_map.get(k) or "99", label_topic.get(k, k)))
        ]
        if not subsections:
            continue
        urls_bab = set(ctx.t.loc[ctx.t["dampak"] == pilar, "url"])
        charts_bab: list[dict[str, Any]] = []

        # (a) Distribusi tema dalam bab ini — posisi setiap tema satu sama lain.
        tampil_pilar = [s["topic"] for s in subsections]
        counts = ctx.t[ctx.t["dampak"] == pilar].groupby("topik")["url"].nunique().reindex(tampil_pilar, fill_value=0)
        dist_pilar = counts.rename("jumlah").reset_index()
        dist_pilar["label"] = dist_pilar["topik"].map(lambda k: label_topic.get(k, k))
        dist_pilar = dist_pilar.sort_values("jumlah", ascending=False, kind="stable")
        if len(dist_pilar):
            charts_bab.append(_chart(
                f"bab_{pilar.lower()}_tema", "bar", f"Distribusi tema dalam dampak {pilar}",
                _bar_data(dist_pilar, "label", "jumlah"), insight=insight_top2(dist_pilar, "label", "jumlah"),
                note=f"Jumlah berita unik tiap tema dalam dampak {pilar} pada filter saat ini.",
                orientation="h",
            ))

        # (b) Heatmap tema × tahun dalam bab ini — tren relatif antar tema.
        b_t_pilar = ctx.b_t[ctx.b_t["dampak"] == pilar]
        piv = (
            b_t_pilar.groupby(["topik", "tahun"])["url"].nunique().unstack(fill_value=0)
            .reindex(index=tampil_pilar, fill_value=0)
        )
        if piv.shape[1]:
            piv.index = [label_topic.get(i, i) for i in piv.index]
            charts_bab.append(_chart(
                f"bab_{pilar.lower()}_tema_tahun", "heatmap", f"Tema × Tahun — dampak {pilar}",
                _heatmap_data(piv), insight=insight_heatmap(piv),
                note="Baris gelap = tema yang konsisten diberitakan; kolom gelap = tahun dengan banyak aktivitas dampak ini.",
            ))

        chapters.append({
            "pillar": pilar,
            "chapter": bab,
            "title": judul,
            "total": len(urls_bab),
            "charts": charts_bab,
            "metrics": [
                {"label": "Berita dampak", "value": len(urls_bab)},
                {"label": "Tema", "value": len(subsections)},
                {"label": "Tema teratas", "value": max(subsections, key=lambda s: s["metrics"][0]["value"])["label"]},
            ],
            "subsections": subsections,
        })
    return chapters


# ---- Data mata kuliah sustainability (subproyek matkul-sustainability) --------------
CATATAN_MATKUL = (
    "Data mata kuliah berasal dari kurasi manual kurikulum UGM "
    "(matkul-sustainability/data/Deskripsi Matkul Kepmen.csv, 8.465 baris penawaran MK; "
    "tabel status Ringkasan mencatat 8.463 baris karena 2 baris berstatus kosong). "
    "Yang dihitung hanya MK berstatus 'Substansial - dihitung' (Kepmen no. 2: yang "
    "menyinggung sepintas tidak dihitung; 142 baris 'Parsial' tidak masuk angka). "
    "Satu MK dihitung 1 kali walau ditawarkan di >1 kelas/prodi (dedup nama MK - nama sama "
    "di prodi berbeda bisa MK berbeda, verifikasi lewat kode MK/RPS). Deskripsi disusun dari "
    "nama MK, BUKAN bukti; pelaporan resmi tetap butuh kurikulum/RPS/silabus. "
    "Angka acuan: Ringkasan Indikator Kepmen 361/M/KEP/2025 (453 MK unik, 511 substansial, "
    "142 parsial) — lihat matkul-sustainability/data/Ringkasan Indikator Kepmen.md."
)


def _matkul_rows(mk: pd.DataFrame) -> list[dict[str, Any]]:
    """Baris tabel daftar MK: nama, fakultas, prodi, kriteria (label), keyword, deskripsi."""
    rows = []
    for r in mk.to_dict("records"):
        huruf = [h.strip().lower() for h in str(r["kriteria"]).split(",") if h.strip()]
        rows.append({
            "nama_mk": r["nama_mk"],
            "fakultas": r["fakultas"],
            "prodi": r["prodi"],
            "kriteria": ", ".join(KRITERIA_LABEL.get(h, h) for h in huruf),
            "keyword": r["keywords"],
            "deskripsi": r["deskripsi"],
        })
    return rows


def mata_kuliah_section(mf: MatkulFrames, pilar: str | None = None,
                        topik: str | None = None,
                        sdgs: tuple[int, ...] = (), sdg_mode: bool = False) -> dict[str, Any]:
    """Blok data mata kuliah untuk /analytics/story.

    pilar=None -> ringkasan penuh (dipakai mode sdgs); pilar terisi -> MK difilter
    ke tema-tema dalam dampak itu (tema indikator 4.5 hanya ada di Lingkungan, jadi
    blok pilar Sosial/Ekonomi bisa kosong -- itu normal, bukan bug).
    sdg_mode=True (mode Berdampak x SDGs) -> MK difilter ke klaster SDG terpilih dan
    ditambah chart sebaran MK per SDG.
    """
    semua_meta = meta_tema_matkul()
    tema_meta = {tid: m for tid, m in semua_meta.items() if pilar is None or m["dampak"] == pilar}
    tema_aktif = [tid for tid in tema_meta if topik is None or tid == topik]

    # MK terkait tema aktif: tema indikator 4.5 memuat SEMUA MK substansial; tema lain
    # memuat MK yang kriterianya terpetakan ke tema itu (lihat matkul.py).
    def mk_tema(tema_id: str) -> pd.DataFrame:
        if tema_id == "pendidikan_dan_penelitian":
            return mf.mk_unik
        mask = mf.mk_unik["kriteria"].map(lambda k: tema_id in tema_dari_kriteria(k))
        return mf.mk_unik[mask]

    per_tema = {tid: mk_tema(tid) for tid in tema_aktif}
    gabung_ids: set[int] = set()
    for frame in per_tema.values():
        gabung_ids.update(frame.index.tolist())
    mk_gabung = mf.mk_unik.loc[sorted(gabung_ids)]

    # Kaitan ke SDG: tema tiap MK (4.5 selalu + tema lain dari kriteria) -> klaster SDG tema.
    def sdg_mk(kriteria: str) -> list[int]:
        tema_ids = ["pendidikan_dan_penelitian", *tema_dari_kriteria(kriteria)]
        sdg: list[int] = []
        for tid in tema_ids:
            for nomor in semua_meta.get(tid, {}).get("sdg", []):
                if nomor not in sdg:
                    sdg.append(nomor)
        return sorted(sdg)

    if sdg_mode:
        peta_sdg = {idx: sdg_mk(row["kriteria"]) for idx, row in mk_gabung.iterrows()}
        if sdgs:
            mk_gabung = mk_gabung.loc[[idx for idx, daftar in peta_sdg.items() if set(daftar) & set(sdgs)]]
            peta_sdg = {idx: daftar for idx, daftar in peta_sdg.items() if idx in set(mk_gabung.index)}
    else:
        peta_sdg = {}

    # --- metrics ---
    metrics = [
        {"label": "MK unik substansial", "value": int(len(mk_gabung)),
         "help": "Jumlah mata kuliah unik berstatus Substansial yang terkait dampak ini."},
        {"label": "Baris penawaran (substansial)", "value": int(len(mf.substansial)),
         "help": "Sebelum dedup nama MK -- satu MK bisa ditawarkan di beberapa prodi/kelas."},
        {"label": "MK parsial (tak dihitung)", "value": int(mf.parsial),
         "help": "Baris 'Parsial/bergantung topik - verifikasi RPS'; tidak masuk indikator."},
    ]

    # --- charts ---
    charts: list[dict[str, Any]] = []
    if len(mk_gabung):
        # (1) MK unik per kriteria a-j (hanya kriteria yang muncul di MK terpilih).
        hitung_kriteria: Counter = Counter()
        for k in mk_gabung["kriteria"]:
            hitung_kriteria.update(huruf.strip().lower() for huruf in str(k).split(",") if huruf.strip())
        dist_k = pd.DataFrame(
            [{"label": KRITERIA_LABEL.get(h, h), "jumlah": n} for h, n in hitung_kriteria.most_common()]
        )
        charts.append(_chart(
            "matkul_kriteria", "bar", "Mata kuliah per kriteria Kepmen (a-j)",
            _bar_data(dist_k, "label", "jumlah"),
            insight=insight_top2(dist_k, "label", "jumlah", satuan="MK"),
            note=("Kriteria a-j = topik indikator 'Pendidikan dan Penelitian' (tema 4.5): "
                  "pembangunan berkelanjutan, perubahan iklim, energi terbarukan, pengelolaan limbah, "
                  "ekonomi sirkular, konservasi lingkungan, keanekaragaman hayati, rehabilitasi/"
                  "restorasi, pengelolaan SDA, topik lain relevan. Satu MK bisa memuat >1 topik, "
                  "sehingga jumlah per kriteria > jumlah MK unik. Angka pada chart adalah hasil "
                  "hitung MK terpilih; angka resmi seluruh 453 MK per kriteria tercantum di "
                  "kriteria_resmi Ringkasan Indikator Kepmen."),
            orientation="h",
        ))
        # (2) MK unik per tema terkait (pemetaan kriteria -> tema; tema 4.5 = semua).
        dist_t = pd.DataFrame(
            [{"label": semua_meta[tid]["topik_kepmen"], "jumlah": len(frame)}
             for tid, frame in sorted(per_tema.items(), key=lambda kv: -len(kv[1])) if len(frame)]
        )
        if len(dist_t):
            charts.append(_chart(
                "matkul_tema", "bar", "Mata kuliah per tema dampak terkait",
                _bar_data(dist_t, "label", "jumlah"),
                insight=insight_top2(dist_t, "label", "jumlah", satuan="MK"),
                note=("Pemetaan analitik kriteria a-j ke tema dampak lain (c=energi, d/e=limbah, "
                      "f/g/h/i=konservasi & rehabilitasi lingkungan). SEMUA MK substansial adalah "
                      "tema resmi 4.5 'Pendidikan dan Penelitian' (Dampak Lingkungan) -- pemetaan ke "
                      "tema lain adalah perluasan analitik, bukan klaim pelaporan resmi."),
                orientation="h",
            ))
        # (3, khusus mode Berdampak x SDGs) sebaran MK per klaster SDG.
        if sdg_mode:
            hitung_sdg: Counter = Counter()
            for daftar in peta_sdg.values():
                hitung_sdg.update(daftar)
            dist_s = pd.DataFrame(
                [{"label": f"SDG {nomor}", "jumlah": n} for nomor, n in sorted(hitung_sdg.items()) if n]
            )
            if len(dist_s):
                charts.append(_chart(
                    "matkul_sdg", "bar", "Mata kuliah per klaster SDG",
                    _bar_data(dist_s, "label", "jumlah"),
                    insight=insight_top2(dist_s, "label", "jumlah", satuan="MK"),
                    note=("Klaster SDG dihitung dari tema resmi tiap MK (Pendidikan dan Penelitian = "
                          "SDG 4 & 17, plus klaster tema lain dari kriteria a-j). Pemetaan tema-SDG "
                          "mengikuti Kepmen 361/M/KEP/2025, sama seperti mode ini untuk berita."),
                    orientation="v",
                ))

    # --- tables ---
    tables: list[dict[str, Any]] = []
    if len(mk_gabung):
        # Tabel daftar MK tidak dibatasi MAX_ROWS (200): seluruh MK substansial harus
        # tersaji supaya angka "MK unik substansial" dan isi tabel konsisten.
        tables.append(_table(
            "matkul_daftar", "Daftar mata kuliah substansial",
            [("nama_mk", "Mata kuliah"), ("fakultas", "Fakultas/Sekolah"), ("prodi", "Program studi"),
             ("kriteria", "Kriteria Kepmen"), ("keyword", "Keyword match"), ("deskripsi", "Deskripsi")],
            _matkul_rows(mk_gabung.sort_values(["fakultas", "nama_mk"], kind="stable")),
            note=("Seluruh MK unik berstatus Substansial ditampilkan di sini. " + CATATAN_MATKUL),
            page_size=10, max_rows=len(mk_gabung),
        ))
        rekap = (
            mk_gabung.groupby("fakultas").agg(jumlah_mk=("nama_mk", "nunique")).reset_index()
            .sort_values("jumlah_mk", ascending=False, kind="stable")
        )
        tables.append(_table(
            "matkul_rekap_fakultas", "Rekap mata kuliah per fakultas/sekolah",
            [("fakultas", "Fakultas/Sekolah"), ("jumlah_mk", "Jumlah MK unik")],
            [{"fakultas": r["fakultas"], "jumlah_mk": int(r["jumlah_mk"])} for r in rekap.to_dict("records")],
            note=("MK unik per fakultas/sekolah (dedup nama MK lintas prodi dalam fakultas itu). " + CATATAN_MATKUL),
            page_size=5,
        ))

    return {
        "sumber": mf.sumber,
        "total_penawaran": mf.total_penawaran,
        "n_substansial": mf.n_substansial,
        "n_mk_unik": mf.n_mk_unik,
        "parsial": mf.parsial,
        "indikator_tema": "pendidikan_dan_penelitian",
        "kriteria_resmi": dict(mf.kriteria_resmi),
        "catatan_metode": list(CATATAN_METODE_RESMI),
        "note": CATATAN_MATKUL,
        "metrics": metrics,
        "charts": charts,
        "tables": tables,
    }


def mata_kuliah_blok(matkul: MatkulFrames | None, pilar: str | None = None,
                     topik: str | None = None, sdgs: tuple[int, ...] = (),
                     sdg_mode: bool = False) -> dict[str, Any]:
    """Payload `mata_kuliah` respons; kontrak stabil walau data CSV tidak tersedia."""
    if matkul is None:
        return {
            "tersedia": False,
            "sumber": "", "total_penawaran": 0, "n_substansial": 0, "n_mk_unik": 0, "parsial": 0,
            "indikator_tema": "pendidikan_dan_penelitian",
            "kriteria_resmi": {}, "catatan_metode": [],
            "note": "Data mata kuliah belum tersedia (Deskripsi Matkul Kepmen.csv tidak ditemukan).",
            "metrics": [], "charts": [], "tables": [],
        }
    blok = mata_kuliah_section(matkul, pilar, topik, sdgs=sdgs, sdg_mode=sdg_mode)
    blok["tersedia"] = True
    return blok


def _pillar_detail(ctx: _Ctx, pilar: str, topic: str | None) -> dict[str, Any]:
    mapping = kepmen()
    label_topic = mapping.LABEL_TOPIC_ALL
    meta = mapping.TOPIK_KEPMEN_ALL
    narasi = load_module("narasi_logic.py")
    unit_map = units().UNIT_KERJA

    selected_t = ctx.t[ctx.t["dampak"] == pilar]
    selected_news = ctx.b[ctx.b["url"].isin(set(selected_t["url"]))]
    tampil_pilar = [k for k in ctx.tampil if meta[k]["dampak"] == pilar]
    bs_pilar = ctx.bs_f[ctx.bs_f["url"].isin(set(selected_t["url"]))]
    detail = {
        "pillar": pilar, "narrative": "", "metrics": [], "tabs": [],
        "topic_options": [
            {"value": k, "label": label_topic.get(k, k)}
            for k in sorted(tampil_pilar, key=lambda k: label_topic.get(k, k))
        ],
        "selected_topic": "",
    }
    detail["narrative"] = narasi.generate_impact_insight(
        selected_news, pilar, ctx.start, ctx.end, selected_t, ctx.mode_label, bs_pilar,
    )
    detail["narrative_source"] = "template"
    # Insight pilar LLM hanya digenerate untuk mode Dampak x SDGs (key "pilar_<pilar>"),
    # sama seperti dashboard lama -- mode Dampak saja selalu template.
    pilar_key = f"pilar_{pilar.lower()}"
    if ctx.mode == "impact-sdgs" and ctx.narasi_llm.get(pilar_key):
        detail.update(narrative=ctx.narasi_llm[pilar_key], narrative_source="llm")
    if selected_news.empty:
        return detail

    options = [item["value"] for item in detail["topic_options"]]
    pilih = topic if topic in options else _default_topic(selected_t, options)
    detail["selected_topic"] = pilih or ""
    detail["metrics"] = [
        {"label": "Berita unik", "value": int(selected_news["url"].nunique())},
        {"label": "Tema aktif", "value": int(selected_t["topik"].nunique())},
        {"label": "Tahun jangkauan", "value": f"{selected_news['tahun'].min()}–{selected_news['tahun'].max()}"},
    ]
    tabs: list[dict[str, Any]] = []

    # --- Ringkasan & Insight ---
    topik_counts = selected_t.groupby("topik")["url"].nunique().reset_index(name="jumlah")
    topik_counts["label"] = topik_counts["topik"].map(label_topic)
    topik_counts = topik_counts.sort_values("jumlah", ascending=False, kind="stable")
    insight_tema = insight_top2(topik_counts, "label", "jumlah")
    trend = selected_news.groupby("tahun")["url"].nunique().reset_index(name="jumlah")
    awal, akhir = trend.iloc[0], trend.iloc[-1]
    puncak = trend.loc[trend["jumlah"].idxmax()]
    delta = int(akhir["jumlah"]) - int(awal["jumlah"])
    insight_trend = (
        f"Dari {int(awal['jumlah']):,} berita ({awal['tahun']}) menjadi {int(akhir['jumlah']):,} berita "
        f"({akhir['tahun']}) — {'naik' if delta >= 0 else 'turun'} {abs(delta):,} berita. "
        f"Puncak tertinggi: {puncak['tahun']} dengan {int(puncak['jumlah']):,} berita."
    )
    total_tema = int(topik_counts["jumlah"].sum())
    tabs.append({
        "id": "ringkasan", "label": "Ringkasan & Insight",
        "charts": [
            _chart("tema", "bar", f"Distribusi tema dalam dampak {pilar}",
                   _bar_data(topik_counts, "label", "jumlah"), insight=insight_tema,
                   note="Distribusi jumlah berita per tema pada dampak ini.", orientation="h"),
            _chart("tren", "line", f"Tren berita per tahun untuk dampak {pilar}",
                   {"series": [{"name": "Jumlah berita", "points": [
                       {"x": str(x), "y": int(y)} for x, y in zip(trend["tahun"], trend["jumlah"])]}]},
                   insight=insight_trend, note="Tren volume berita dampak ini dari tahun ke tahun."),
        ],
        "tables": [_table(
            "tema", "Daftar tema dalam dampak ini", [("tema", "Tema"), ("jumlah", "Jumlah berita")],
            [{"tema": r["label"], "jumlah": int(r["jumlah"])} for r in topik_counts.to_dict("records")],
            note="Rincian lengkap semua tema dalam dampak ini, data yang sama dengan chart distribusi di atas.",
            insight=f"{insight_tema} Total keseluruhan {total_tema:,} berita di {len(topik_counts)} tema.",
        )],
    })

    # --- Tema Resmi Kepmen ---
    kepmen_charts = []
    dist = (
        selected_t.groupby("topik")["url"].nunique().reindex(tampil_pilar, fill_value=0)
        .rename("jumlah").reset_index()
    )
    dist["topik_kepmen"] = dist["topik"].map(lambda k: meta[k]["topik_kepmen"])
    dist_k = dist.groupby("topik_kepmen")["jumlah"].sum().reset_index().sort_values("jumlah", ascending=False, kind="stable")
    if len(dist_k):
        kepmen_charts.append(_chart(
            "kepmen", "bar", f"Berita per Tema Resmi Kepmen — dampak {pilar}", _bar_data(dist_k, "topik_kepmen", "jumlah"),
            insight=insight_top2(dist_k, "topik_kepmen", "jumlah"),
            note=("Angka = berita unik dari tema dalam dampak ini yang dipetakan ke Tema Resmi Kepmen ini (pemetaan resmi "
                  "dari UGM Analytics.xlsx); beberapa tema bisa memetakan ke Tema Resmi yang sama, jumlahnya digabung."),
            orientation="h",
        ))
    map_rows = [
        {"tema": label_topic.get(k, k), "tema_kepmen": m["topik_kepmen"], "indikator": m["indikator"], "satuan": m["satuan"]}
        for k, m in meta.items() if m["dampak"] == pilar
    ]
    tabs.append({
        "id": "kepmen", "label": "Tema Resmi Kepmen", "charts": kepmen_charts,
        "tables": [_table(
            "indikator", "Indikator resmi Kepmen 361/M/KEP/2025 pada dampak ini",
            [("tema", "Tema dampak berita"), ("tema_kepmen", "Tema Resmi Kepmen"),
             ("indikator", "Indikator Kepmen"), ("satuan", "Satuan")], map_rows,
            note=(f"Mencakup {len(map_rows)} tema resmi Kepmen pada dampak {pilar} -- pemetaan resmi tema dampak ke Tema "
                  "Resmi Kepmen, indikator, dan satuan (UGM Analytics.xlsx & Kepmen 361/M/KEP/2025)."),
        )],
    })

    # --- SDGs Terkait (hanya Berdampak × SDGs) ---
    if ctx.mode != "impact":
        sdg_tab: dict[str, Any] = {"id": "sdgs", "label": "SDGs Terkait", "charts": [], "tables": []}
        if len(bs_pilar):
            sdg_tab["charts"] = _sdg_charts_pilar(bs_pilar, selected_t, tampil_pilar, pilar)
        else:
            sdg_tab["note"] = "Tidak ada data SDG untuk dampak ini pada filter saat ini."
        tabs.append(sdg_tab)

    # --- Tren & Musiman ---
    b_t_pilar = ctx.b_t[ctx.b_t["dampak"] == pilar]
    tren_charts = []
    piv = (
        b_t_pilar.groupby(["topik", "tahun"])["url"].nunique().unstack(fill_value=0)
        .reindex(index=tampil_pilar, fill_value=0)
    )
    if piv.shape[1]:
        piv.index = [label_topic.get(i, i) for i in piv.index]
        tren_charts.append(_chart(
            "tema_tahun", "heatmap", f"Tema × Tahun — dampak {pilar}", _heatmap_data(piv),
            insight=insight_heatmap(piv),
            note="Baris gelap = tema yang konsisten diberitakan; kolom gelap = tahun dengan banyak aktivitas dampak ini.",
        ))
    musim = b_t_pilar.assign(bulan=b_t_pilar["tanggal"].fillna("").astype(str).str[5:7])
    musim = musim.groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
    if len(musim):
        musim["label"] = musim["topik"].map(label_topic)
        bulan_sum = musim.groupby("bulan")["jumlah"].sum().reset_index()
        bulan_sum["label_bulan"] = "Bulan " + bulan_sum["bulan"]
        tren_charts.append(_chart(
            "musiman", "stacked_bar", f"Tren bulanan (musiman) — dampak {pilar}",
            _stacked_data(musim, "bulan", "label", "jumlah", [label_topic[k] for k in tampil_pilar]),
            insight=insight_top2(bulan_sum, "label_bulan", "jumlah"),
            note="Bulan kalender, semua tahun digabung. Bulan 01-12 = Januari-Desember.",
        ))
    tabs.append({"id": "tren", "label": "Tren & Musiman", "charts": tren_charts, "tables": []})

    # --- Kata Kunci & Berita ---
    kata_charts = []
    if pilih:
        tema_label = label_topic.get(pilih, pilih)
        kata_charts = _keyword_charts_pilar(ctx, pilih, f"Keyword pemicu match — {tema_label}", f"15 kata teratas — {tema_label}")
    latest = selected_news.sort_values("tanggal", ascending=False, kind="stable").head(MAX_ROWS)
    latest_urls = set(latest["url"])
    kep_by_url = (
        selected_t[selected_t["url"].isin(latest_urls)].groupby("url")["topik_kepmen"]
        .apply(lambda s: ", ".join(sorted(set(s)))).to_dict()
    )
    sdg_by_url = (
        bs_pilar[bs_pilar["url"].isin(latest_urls)].groupby("url")["sdg"]
        .apply(lambda s: ", ".join(f"SDG {x}" for x in sorted(set(s)))).to_dict()
    )
    news_rows = [
        {
            "tanggal": r["tanggal"] or "", "judul": r["judul"] or "",
            "tema_kepmen": kep_by_url.get(r["url"], "—"), "sdg": sdg_by_url.get(r["url"], "—"),
            "sumber": r["sumber"] or "", "url": r["url"],
        }
        for r in latest.to_dict("records")
    ]
    terbaru = latest.iloc[0]
    tabs.append({
        "id": "kata_kunci", "label": "Kata Kunci & Berita", "charts": kata_charts,
        "tables": [_table(
            "berita", "Daftar berita — dampak ini",
            [("tanggal", "Tanggal"), ("judul", "Judul"), ("tema_kepmen", "Tema Kepmen"), ("sdg", "SDG"),
             ("sumber", "Sumber"), ("url", "Tautan")], news_rows,
            note=(f"Berita terbaru: \"{terbaru['judul']}\" ({terbaru['tanggal']}). Daftar diurutkan dari yang terbaru "
                  f"(maks. {MAX_ROWS} baris, tampil {NEWS_PAGE_SIZE} per halaman), lengkap dengan Tema Kepmen & SDG "
                  "yang terdeteksi -- untuk menelusuri berita sumber di balik angka-angka pada tab lain."),
            page_size=NEWS_PAGE_SIZE,
        )],
    })

    # --- Fakultas/Unit Kerja (tanpa filter unit sidebar) ---
    tabs.append(_unit_tab(ctx, pilar, unit_map))
    detail["tabs"] = tabs
    return detail


def _keyword_charts_pilar(ctx: _Ctx, topic: str, kw_title: str, word_title: str) -> list[dict[str, Any]]:
    return _keyword_charts(ctx, topic, "pilar", kw_title, word_title)


def _sdg_charts_pilar(bs_pilar: pd.DataFrame, selected_t: pd.DataFrame, tampil_pilar: list[str], pilar: str) -> list[dict[str, Any]]:
    mapping = kepmen()
    dist = bs_pilar.groupby("sdg")["url"].nunique().reset_index(name="jumlah").sort_values("jumlah", kind="stable")
    dist["label"] = dist["sdg"].map(lambda s: f"SDG {s}")
    dist["nama"] = dist["sdg"].map(lambda s: mapping.sdg_label(int(s)))
    charts = [_chart(
        "sdg", "bar", f"Berita per SDG — dampak {pilar}", _bar_data(dist, "label", "jumlah", detail_col="nama"),
        insight=insight_top2(dist, "nama", "jumlah"),
        note=("Angka = berita unik dampak ini yang temanya memetakan ke klaster SDG ini "
              "(klaster resmi per tema, bukan keyword SDG langsung)."),
        orientation="v",
    )]
    hm = bs_pilar.merge(selected_t[["url", "topik"]], on="url", how="left").drop_duplicates(subset=["url", "topik", "sdg"])
    piv = (
        hm.groupby(["topik", "sdg"])["url"].nunique().unstack(fill_value=0)
        .reindex(index=tampil_pilar, fill_value=0)
    )
    if piv.shape[1]:
        piv.index = [mapping.LABEL_TOPIC_ALL.get(i, i) for i in piv.index]
        piv.columns = [f"SDG {c}" for c in piv.columns]
        charts.append(_chart(
            "tema_sdg", "heatmap", f"Tema × SDG — dampak {pilar}", _heatmap_data(piv), insight=insight_heatmap(piv),
            note=("Sel kosong (0) = tidak ada berita pada kombinasi itu. Baris gelap = tema tersebar di banyak SDG; "
                  "kolom gelap = SDG yang paling sering tersentuh."),
        ))
    return charts


def _unit_dist(uk: pd.DataFrame, urls: set[str], unit_map: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(uk untuk urls itu, jumlah berita unik per unit + kategori, terbesar dulu)."""
    uk_sub = uk[uk["url"].isin(urls)]
    if uk_sub.empty:
        return uk_sub, pd.DataFrame(columns=["unit_kerja", "kategori", "jumlah", "nama"])
    dist = uk_sub.groupby(["unit_kerja", "kategori"])["url"].nunique().reset_index(name="jumlah")
    dist["nama"] = dist["unit_kerja"].map(lambda k: unit_map.get(k, {}).get("nama", k))
    return uk_sub, dist.sort_values("jumlah", ascending=False, kind="stable")


def _unit_tab(ctx: _Ctx, pilar: str, unit_map: dict[str, Any]) -> dict[str, Any]:
    # SENGAJA basis tanpa filter unit kerja sidebar (lihat komentar panjang di page_dampak.py).
    t_pilar = ctx.t_nounit[ctx.t_nounit["dampak"] == pilar]
    news = ctx.b_nounit[ctx.b_nounit["url"].isin(set(t_pilar["url"]))]
    uk_pilar, dist = _unit_dist(ctx.uk, set(news["url"]), unit_map)
    charts, tables = [], []
    if len(uk_pilar):
        charts.append(_chart(
            "unit", "bar", f"Berita per Fakultas/Unit Kerja — dampak {pilar}",
            _bar_data(dist, "nama", "jumlah", group_col="kategori"),
            insight=insight_top2(dist, "nama", "jumlah"),
            note=("Hasil keyword matching nama resmi 44 fakultas/sekolah/unit kerja UGM pada judul + deskripsi berita -- "
                  "bersifat lower-bound (banyak berita tidak eksplisit menyebut nama unit meski relevan), bukan angka "
                  "final jumlah kontribusi tiap unit. Chart & metrik di tab ini SENGAJA mengabaikan filter "
                  "\"Fakultas / Unit Kerja\" (filter tahun/tema/pilar tetap berlaku) supaya rankingnya tetap adil "
                  "dibandingkan antar unit."),
            orientation="h",
        ))
        tables.append(_table(
            "unit_teridentifikasi", "Unit teridentifikasi", [("metrik", "Metrik"), ("nilai", "Nilai")],
            [{"metrik": "Unit teridentifikasi", "nilai": f"{uk_pilar['unit_kerja'].nunique()} / {len(unit_map)}"}],
        ))
    tagged = set(uk_pilar["url"]) if len(uk_pilar) else set()
    belum = news[~news["url"].isin(tagged)].sort_values("tanggal", ascending=False, kind="stable")
    tables.append(_table(
        "tanpa_unit", "Berita tanpa unit teridentifikasi (cek manual)",
        [("tanggal", "Tanggal"), ("judul", "Judul"), ("url", "Tautan")],
        _news_rows(belum.head(MAX_ROWS), {"tanggal": "tanggal", "judul": "judul", "url": "url"}),
        note=(f"{len(belum):,} berita (dampak ini, dalam filter tahun/tema -- TIDAK termasuk filter Fakultas/Unit Kerja) "
              "tidak menyebut fakultas/unit kerja mana pun."),
    ))
    tab = {"id": "unit", "label": "Fakultas/Unit Kerja", "charts": charts, "tables": tables}
    if not len(uk_pilar):
        tab["note"] = "Tidak ada fakultas/unit kerja teridentifikasi untuk dampak ini pada filter saat ini."
    return tab


# ---- Analisis Lintas-Dampak --------------------------------------------------------
def _cross(ctx: _Ctx, fr: StoryFrames, topic: str | None) -> dict[str, Any]:
    mapping = kepmen()
    label_topic = mapping.LABEL_TOPIC_ALL
    meta = mapping.TOPIK_KEPMEN_ALL
    b, t, b_t, bs_f = ctx.b, ctx.t, ctx.b_t, ctx.bs_f
    charts: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    start, end = ctx.start, ctx.end

    tables.append(_table(
        "ringkasan_filter", "Ringkasan", [("metrik", "Metrik"), ("nilai", "Nilai")],
        [
            {"metrik": "Total berita (filter)", "nilai": int(len(b))},
            {"metrik": "Berita bertema dampak", "nilai": int(t["url"].nunique())},
            {"metrik": "Tema terpilih", "nilai": len(ctx.topik_pilih)},
            {"metrik": "Rentang tahun", "nilai": f"{start}–{end}"},
        ],
        note="Ringkasan parameter filter yang sedang aktif untuk semua chart di bagian 'Analisis Lintas-Dampak' ini.",
    ))

    # 1. Tema Resmi Kepmen (group = dampak)
    dist_t = (
        t.groupby("topik")["url"].nunique().reindex(ctx.tampil, fill_value=0).rename("jumlah").reset_index()
    )
    dist_t["dampak"] = dist_t["topik"].map(lambda k: meta[k]["dampak"])
    dist_t["topik_kepmen"] = dist_t["topik"].map(lambda k: meta[k]["topik_kepmen"])
    dist_k = (
        dist_t.groupby(["dampak", "topik_kepmen"])["jumlah"].sum().reset_index()
        .sort_values("jumlah", ascending=False, kind="stable")
    )
    top = dist_k.iloc[0]
    charts.append(_chart(
        "kepmen", "bar", "Jumlah berita per Tema Resmi Kepmen (berdasarkan dampak)",
        _bar_data(dist_k, "topik_kepmen", "jumlah", group_col="dampak"),
        insight=(f"Tema Resmi Kepmen teratas: {top['topik_kepmen']} (dampak {top['dampak']}) dengan "
                 f"{int(top['jumlah']):,} berita."),
        note=("Angka = berita unik dari tema dampak yang dipetakan ke Tema Resmi ini (pemetaan resmi dari UGM Analytics.xlsx); "
              "beberapa tema dampak bisa memetakan ke Tema Resmi yang sama, jumlahnya digabung."),
        orientation="h",
    ))

    # 2. Khusus Berdampak × SDGs
    if ctx.mode != "impact" and len(bs_f):
        charts.extend(_cross_sdg_charts(ctx))

    # 3. Berita unik per dampak (tabel ringkasan, hanya ikut filter dampak)
    rp = fr.rp[fr.rp["dampak"].isin(ctx.pillar_set)]
    if len(rp):
        top_rp = rp.loc[rp["jumlah_berita"].idxmax()]
        charts.append(_chart(
            "per_dampak", "bar", "Berita unik per dampak (semua tema Kepmen)",
            _bar_data(rp, "dampak", "jumlah_berita", group_col="dampak"),
            insight=f"Dampak dengan berita terbanyak: {top_rp['dampak']} ({int(top_rp['jumlah_berita']):,} berita).",
            note=("Total berita unik per dampak (semua tema dalam dampak digabung, URL dideduplikasi per dampak). "
                  "Angka ini ringkasan seluruh periode: hanya mengikuti filter dampak, tidak mengikuti filter tahun/tema/unit."),
            orientation="v",
        ))

    # 4. Heatmap tema x tahun
    piv = b_t.groupby(["topik", "tahun"])["url"].nunique().unstack(fill_value=0).reindex(index=ctx.tampil, fill_value=0)
    if piv.shape[1]:
        piv.index = [label_topic.get(i, i) for i in piv.index]
        rows_sum, cols_sum = piv.sum(axis=1), piv.sum(axis=0)
        charts.append(_chart(
            "tema_tahun", "heatmap", "Jumlah berita per tema per tahun", _heatmap_data(piv),
            insight=(f"Tema paling konsisten diberitakan: {rows_sum.idxmax()} ({int(rows_sum.max()):,} berita total); "
                     f"tahun paling aktif: {cols_sum.idxmax()} ({int(cols_sum.max()):,} berita)."),
        ))

    # 5. Tren tahunan per tema
    tren = b_t.groupby(["topik", "tahun"]).size().reset_index(name="jumlah")
    tren["label"] = tren["topik"].map(label_topic)
    tren_total = tren.groupby("label")["jumlah"].sum()
    charts.append(_chart(
        "tren_tema", "line", "Jumlah berita per tahun",
        _line_data(tren, "tahun", "label", "jumlah", [label_topic[k] for k in ctx.tampil]),
        insight=(f"Tema dengan total berita tertinggi sepanjang periode: {tren_total.idxmax()} "
                 f"({int(tren_total.max()):,} berita)."),
        note="Angka = jumlah berita per tema-tahun; berita yang masuk beberapa tema dihitung di tiap tema.",
    ))

    # 6. Tren bulanan
    musim = b_t.assign(bulan=b_t["tanggal"].fillna("").astype(str).str[5:7]).groupby(["bulan", "topik"]).size().reset_index(name="jumlah")
    musim["label"] = musim["topik"].map(label_topic)
    bulan_sum = musim.groupby("bulan")["jumlah"].sum()
    charts.append(_chart(
        "musiman", "stacked_bar", "Jumlah berita per bulan kalender (semua tahun digabung)",
        _stacked_data(musim, "bulan", "label", "jumlah", [label_topic[k] for k in ctx.tampil]),
        insight=f"Bulan paling ramai (semua tema & tahun): {bulan_sum.idxmax()} dengan {int(bulan_sum.max()):,} berita.",
        note="Bulan 01-12 = Januari-Desember.",
    ))

    # 7. Cakupan vs total berita UGM per tahun
    sitemap = fr.sitemap.assign(tahun=fr.sitemap["lastmod"].fillna("").astype(str).str[:4])
    tot = sitemap.groupby("tahun").size().reset_index(name="total")
    cakup = b_t.groupby("tahun")["url"].nunique().reset_index(name="bertopik")
    gab = tot.merge(cakup, on="tahun", how="left").fillna(0)
    gab = gab[gab["tahun"].between(start, end)].sort_values("tahun")
    if len(gab):
        total_all, total_matched = int(gab["total"].sum()), int(gab["bertopik"].sum())
        pct = 100 * total_matched / total_all if total_all else 0
        charts.append(_chart(
            "cakupan", "combo", "Volume berita UGM vs berita yang terdeteksi tema dampak",
            {
                "x": [str(x) for x in gab["tahun"]],
                "bars": {"name": "Total berita (sitemap)", "values": [int(v) for v in gab["total"]]},
                "line": {"name": "Berita bertema dampak", "values": [int(v) for v in gab["bertopik"]]},
            },
            insight=(f"Sepanjang {start}–{end}: dari {total_all:,} total berita UGM, {total_matched:,} ({pct:.1f}%) "
                     "terdeteksi tema dampak."),
            note=("Batang abu-abu = seluruh URL di sitemap ugm.ac.id per tahun (baseline). Garis = berita unik yang match "
                  "tema dampak; nilainya lower-bound karena pencocokan keyword terbatas pada 14 tema Kepmen yang dideteksi."),
        ))

    # 8-9. Keyword & kata teratas untuk satu tema
    options = [k for k in sorted(ctx.tampil, key=lambda k: (meta[k]["dampak"], label_topic.get(k, k)))]
    pilih = topic if topic in options else _default_topic(t, ctx.tampil)
    cross_topic_options = [{"value": k, "label": f"{meta[k]['dampak']} - {label_topic.get(k, k)}"} for k in options]
    if pilih:
        kw_label = f"{meta[pilih]['dampak']} - {label_topic.get(pilih, pilih)}"
        charts.extend(_keyword_charts(
            ctx, pilih, "lintas", f"Jumlah berita yang match tiap keyword — {kw_label}",
            f"15 kata teratas — {label_topic[pilih]}",
        ))

    # 10. Multi-tema
    cnt = b_t.groupby("url").size().reset_index(name="n_topik")
    dist_n = cnt["n_topik"].value_counts().sort_index().reset_index()
    dist_n.columns = ["jumlah_tema", "berita"]
    total_n = int(dist_n["berita"].sum())
    single_n = int(dist_n.loc[dist_n["jumlah_tema"] == 1, "berita"].sum())
    multi_pct = 100 * (total_n - single_n) / total_n if total_n else 0
    dist_n["label"] = dist_n["jumlah_tema"].astype(str)
    charts.append(_chart(
        "multi_tema", "bar", "Berapa banyak tema per berita", _bar_data(dist_n, "label", "berita"),
        insight=f"{multi_pct:.1f}% berita masuk lebih dari satu tema (lintas-tema).",
        note=("Bar paling kiri = berita yang hanya masuk satu tema; semakin ke kanan, semakin lintas-tema berita tersebut."),
        orientation="v",
    ))
    multi = cnt[cnt["n_topik"] > 1]
    if len(multi):
        sub = b_t[b_t["url"].isin(set(multi["url"]))]
        combos = (
            sub.groupby("url")["topik"].apply(lambda s: " + ".join(sorted(label_topic.get(x, x) for x in s)))
            .rename("kombinasi").reset_index()
        )
        combos["n_tema"] = combos["kombinasi"].str.count(r" \+ ") + 1
        agg = (
            combos.groupby(["kombinasi", "n_tema"]).size().reset_index(name="berita")
            .sort_values(["n_tema", "berita"], ascending=[False, False], kind="stable")
        )
        top_combo = agg.iloc[0]
        tables.append(_table(
            "multi_tema", "Kombinasi tema pada berita multi-tema",
            [("kombinasi", "Kombinasi tema"), ("n_tema", "Jumlah tema"), ("berita", "Jumlah berita")],
            _native(agg.to_dict("records")),
            note=(f"Berita dengan tema terbanyak sekaligus: {int(top_combo['n_tema'])} tema ({top_combo['kombinasi']}). "
                  "Satu baris = satu kombinasi tema; diurutkan dari kombinasi dengan tema terbanyak."),
        ))

    # 11. Pemetaan resmi Kepmen
    map_rows = [
        {
            "tema": label_topic.get(k, k), "dampak": m["dampak"], "tema_kepmen": m["topik_kepmen"],
            "sdg": ", ".join(mapping.sdg_label(s) for s in m["sdg"]) or "—", "indikator": m["indikator"],
            "definisi": m["definisi"], "kriteria": m["kriteria"], "formula": m["formula"], "satuan": m["satuan"],
        }
        for k, m in meta.items()
    ]
    tables.append(_table(
        "pemetaan", "Pemetaan resmi + indikator Kepmen (14 tema)",
        [("tema", "Tema dampak berita"), ("dampak", "Dampak"), ("tema_kepmen", "Tema Resmi Kepmen"),
         ("sdg", "Klaster SDGs"), ("indikator", "Indikator Kepmen"), ("definisi", "Definisi"),
         ("kriteria", "Kriteria"), ("formula", "Formula"), ("satuan", "Satuan")],
        map_rows,
        note=("14 tema resmi Kepmen 361/M/KEP/2025 (klaster SDG dari sheet '#Ref' UGM Analytics.xlsx). Definisi & kriteria "
              "dari Salinan Kepmen 361/M/KEP/2025 (OCR)."),
    ))

    # Berita tanpa match tema (cek manual)
    belum = b[~b["url"].isin(set(t["url"]))].sort_values("tanggal", ascending=False, kind="stable")
    tables.append(_table(
        "tanpa_tema", "Berita tanpa match tema (cek manual)",
        [("tanggal", "Tanggal"), ("judul", "Judul"), ("url", "Tautan")],
        _news_rows(belum.head(MAX_ROWS), {"tanggal": "tanggal", "judul": "judul", "url": "url"}),
        note=f"{len(belum):,} berita (dalam filter) tidak masuk tema mana pun.",
    ))

    return {
        "title": "Analisis Lintas-Dampak", "charts": charts, "tables": tables,
        "topic_options": cross_topic_options, "selected_topic": pilih or "",
    }


def _cross_sdg_charts(ctx: _Ctx) -> list[dict[str, Any]]:
    mapping = kepmen()
    label_topic = mapping.LABEL_TOPIC_ALL
    b, bs_f, bk_f = ctx.b, ctx.bs_f, ctx.t
    charts: list[dict[str, Any]] = []

    dist = bs_f.groupby("sdg")["url"].nunique().reset_index(name="jumlah").sort_values("jumlah", kind="stable")
    dist["label"] = dist["sdg"].map(lambda s: f"SDG {s}")
    dist["nama"] = dist["sdg"].map(lambda s: mapping.sdg_label(int(s)))
    top = dist.loc[dist["jumlah"].idxmax()]
    charts.append(_chart(
        "sdg", "bar", "Jumlah berita per SDG (klaster resmi)", _bar_data(dist, "label", "jumlah", detail_col="nama"),
        insight=f"SDG paling banyak disentuh: {top['nama']} dengan {int(top['jumlah']):,} berita.",
        note=("Angka = berita unik bertema yang temanya memetakan ke klaster SDG ini (klaster resmi per tema, bukan keyword "
              "SDG langsung). Satu berita bisa dihitung di beberapa SDG."),
        orientation="v",
    ))

    hm = bs_f.merge(bk_f[["url", "topik"]], on="url", how="left").drop_duplicates(subset=["url", "topik", "sdg"])
    if len(hm):
        piv = (
            hm.groupby(["topik", "sdg"])["url"].nunique().unstack(fill_value=0)
            .reindex(index=ctx.tampil, fill_value=0)
        )
        piv.index = [label_topic.get(i, i) for i in piv.index]
        piv.columns = [f"SDG {c}" for c in piv.columns]
        charts.append(_chart(
            "tema_sdg", "heatmap", "Berita per kombinasi tema dampak × SDG", _heatmap_data(piv),
            insight=insight_heatmap(piv),
            note=("Sel kosong (0) = tidak ada berita pada kombinasi itu. Baris gelap = tema tersebar di banyak SDG; "
                  "kolom gelap = SDG yang paling sering tersentuh."),
        ))

    sdg_tahun = (
        bs_f.merge(b[["url", "tahun"]], on="url", how="left").drop_duplicates(subset=["url", "sdg", "tahun"])
        .groupby(["tahun", "sdg"]).size().reset_index(name="jumlah")
    )
    if len(sdg_tahun):
        sdg_tahun["label"] = sdg_tahun["sdg"].map(lambda s: f"SDG {s}")
        total = sdg_tahun.groupby("label")["jumlah"].sum()
        order = [f"SDG {s}" for s in sorted(sdg_tahun["sdg"].unique())]
        charts.append(_chart(
            "sdg_tahun", "line", "Jumlah berita per SDG per tahun",
            _line_data(sdg_tahun, "tahun", "label", "jumlah", order),
            insight=(f"SDG dengan total tertinggi sepanjang periode: {total.idxmax()} ({int(total.max()):,} berita)."),
            note=("Angka = berita unik bertema yang SDG-nya tercatat pada tahun publikasi tsb; garis naik = perhatian "
                  "terhadap SDG makin sering diberitakan."),
        ))

    bk_tahun = bk_f.merge(b[["url", "tahun"]], on="url", how="left").drop_duplicates(subset=["url", "topik", "tahun"])
    pilar_tahun = bk_tahun.groupby(["dampak", "tahun"])["url"].nunique().unstack(fill_value=0)
    if pilar_tahun.shape[1]:
        rows_sum, cols_sum = pilar_tahun.sum(axis=1), pilar_tahun.sum(axis=0)
        charts.append(_chart(
            "dampak_tahun", "heatmap", "Jumlah berita per dampak per tahun (14 tema Kepmen)", _heatmap_data(pilar_tahun),
            insight=(f"Dampak paling dominan: {rows_sum.idxmax()} ({int(rows_sum.max()):,} berita total); tahun paling "
                     f"aktif: {cols_sum.idxmax()} ({int(cols_sum.max()):,} berita)."),
        ))
    return charts


# --------------------------------------------------------------------------------------
# Mode SDGs (page_sdgs.py)
# --------------------------------------------------------------------------------------
def _url_bersih(series: pd.Series) -> pd.Series:
    """URL tanpa query string dan tanpa garis miring di ujung (bentuk yang dipakai berita_unit_kerja)."""
    return series.str.split("?").str[0].str.rstrip("/")


def _story_sdgs(fr: StoryFrames, filters: FilterParams, start: str, end: str,
                matkul: MatkulFrames | None = None) -> dict[str, Any]:
    mapping = kepmen()
    narasi = load_module("narasi_logic.py")
    unit_map = units().UNIT_KERJA
    sdg_pilih = list(filters.sdgs or range(1, 18))

    sm = fr.sitemap.assign(tahun=fr.sitemap["lastmod"].fillna("").astype(str).str[:4])
    sm = sm[sm["tahun"].between(start, end)]
    if filters.units:
        unit_urls = set(fr.uk.loc[fr.uk["unit_kerja"].isin(filters.units), "url"])
        sm = sm[_url_bersih(sm["url"]).isin(unit_urls)]
    ss_f = fr.ss[fr.ss["sdg"].isin(sdg_pilih) & fr.ss["url"].isin(set(sm["url"]))]
    n_url, n_tag = len(sm), int(ss_f["url"].nunique())

    response = {
        "mode": "sdgs",
        "filters": {
            "year_from": start, "year_to": end, "pillars": [], "topics": [],
            "sdgs": list(filters.sdgs), "units": list(filters.units),
        },
        "data_as_of": fr.data_as_of,
        "caveats": list(CAVEATS_SDGS),
        "executive": {
            "metrics": [
                {"label": "Total berita (sitemap)", "value": n_url, "note": None},
                {"label": "Berita bertanda SDG", "value": n_tag, "note": None},
                {"label": "Cakupan", "value": f"{100 * n_tag / n_url:.1f}%" if n_url else "—", "note": None},
            ],
            "narrative": "Tidak ada data SDG untuk rentang tahun ini.",
        },
        "overview": [],
        "cross": {"title": "Analisis SDGs", "charts": [], "tables": []},
        "pillar_detail": None,
        "chapters": [],
        "mata_kuliah": mata_kuliah_blok(matkul),
        "tables": [],
    }
    if not len(ss_f):
        return response
    response["executive"]["narrative"] = narasi.generate_sdg_saja_summary(sm, ss_f, start, end)

    charts: list[dict[str, Any]] = []
    dist = ss_f.groupby("sdg")["url"].nunique().reset_index(name="jumlah")
    dist["label"] = dist["sdg"].map(lambda s: f"SDG {s}")
    dist["nama"] = dist["sdg"].map(lambda s: mapping.SDG_NAMA.get(int(s)))
    asc = dist.sort_values("jumlah", kind="stable")
    top = dist.loc[dist["jumlah"].idxmax()]
    charts.append(_chart(
        "sdg", "bar", "Jumlah berita per SDG (seluruh URL sitemap)", _bar_data(asc, "label", "jumlah", detail_col="nama"),
        insight=f"SDG paling banyak disentuh: {top['label']} — {top['nama']} dengan {int(top['jumlah']):,} berita.",
        note=("Jangkauan tiap SDG: jumlah URL unik sitemap yang teksnya (slug URL / judul / deskripsi) mengandung keyword "
              "SDG tsb. Satu URL bisa dihitung di beberapa SDG."),
        orientation="v",
    ))

    sdg_tahun = (
        ss_f.merge(sm[["url", "tahun"]], on="url", how="left").drop_duplicates(subset=["url", "sdg", "tahun"])
        .groupby(["tahun", "sdg"]).size().reset_index(name="jumlah")
    )
    if len(sdg_tahun):
        sdg_tahun["label"] = sdg_tahun["sdg"].map(lambda s: f"SDG {s}")
        total = sdg_tahun.groupby("label")["jumlah"].sum()
        order = [f"SDG {s}" for s in sorted(sdg_tahun["sdg"].unique())]
        charts.append(_chart(
            "sdg_tahun", "line", "Jumlah berita bertanda SDG per tahun",
            _line_data(sdg_tahun, "tahun", "label", "jumlah", order),
            insight=f"SDG dengan total tertinggi sepanjang periode: {total.idxmax()} ({int(total.max()):,} berita).",
            note="Angka = URL unik yang match keyword SDG pada tahun itu (berdasar lastmod sitemap).",
        ))
        piv = sdg_tahun.groupby(["sdg", "tahun"])["jumlah"].sum().unstack(fill_value=0)
        piv.index = [f"SDG {c}" for c in piv.index]
        stacked = piv.stack()
        row, col = stacked.idxmax()
        charts.append(_chart(
            "sdg_tahun_heatmap", "heatmap", "Jumlah berita per kombinasi SDG × tahun", _heatmap_data(piv),
            insight=f"Kombinasi tertinggi: {row}, tahun {col} dengan {int(stacked.max()):,} berita.",
            note="Sel kosong (0) = tidak ada berita.",
        ))

    ss_b = ss_f.assign(url_b=_url_bersih(ss_f["url"]))
    uk_b = fr.uk.assign(url_b=_url_bersih(fr.uk["url"]))[["url_b", "unit_kerja", "kategori"]]
    uk_sdg = ss_b.merge(uk_b, on="url_b", how="inner")
    if len(uk_sdg):
        dist_unit = uk_sdg.groupby(["unit_kerja", "kategori"])["url_b"].nunique().reset_index(name="jumlah")
        dist_unit["nama"] = dist_unit["unit_kerja"].map(lambda k: unit_map.get(k, {}).get("nama", k))
        dist_unit = dist_unit.sort_values("jumlah", ascending=False, kind="stable")
        charts.append(_chart(
            "unit", "bar", "Berita bertanda SDG per Fakultas/Unit Kerja",
            _bar_data(dist_unit, "nama", "jumlah", group_col="kategori"),
            insight=insight_top2(dist_unit, "nama", "jumlah"),
            note=("Fakultas/unit kerja diidentifikasi lewat keyword matching nama resmi pada judul/deskripsi berita -- "
                  "bersifat lower-bound, bukan angka final kontribusi tiap unit."),
            orientation="h",
        ))
    response["cross"]["charts"] = charts

    ring = dist.sort_values("jumlah", ascending=False, kind="stable")
    top_ring = ring.iloc[0]
    tables = [
        _table(
            "ringkasan_sdg", "Ringkasan per SDG", [("sdg", "SDG"), ("nama", "Nama"), ("jumlah", "Jumlah berita")],
            [{"sdg": r["label"], "nama": r["nama"], "jumlah": int(r["jumlah"])} for r in ring.to_dict("records")],
            note=("Angka yang sama dengan chart Distribusi Berita per SDG di atas, terurut dari SDG paling banyak disentuh."),
            insight=f"Teratas: {top_ring['label']} — {top_ring['nama']} ({int(top_ring['jumlah']):,} berita).",
        ),
    ]
    sdg_keywords = load_module("sdg_keywords.py").SDG_KEYWORDS
    tables.append(_table(
        "keyword_sdg", "Keyword per SDG (dasar mapping)", [("sdg", "SDG"), ("nama", "Nama"), ("keyword", "Keyword")],
        [{"sdg": f"SDG {s}", "nama": mapping.SDG_NAMA.get(s, s), "keyword": ", ".join(kws)} for s, kws in sdg_keywords.items()],
        note=("Daftar keyword yang jadi dasar pencocokan tiap SDG pada mapping 'SDGs saja' ini -- referensi metodologi, "
              "bukan hasil analisis."),
    ))
    belum = sm[~sm["url"].isin(set(ss_f["url"]))].sort_values("lastmod", ascending=False, kind="stable")
    tables.append(_table(
        "tanpa_sdg", "Berita tanpa tanda SDG (cek manual)", [("url", "Tautan"), ("lastmod", "Lastmod")],
        _native(belum[["url", "lastmod"]].head(MAX_ROWS).fillna("").to_dict("records")),
        note=f"{len(belum):,} berita (dalam rentang tahun) tidak masuk SDG mana pun.",
    ))
    response["tables"] = tables
    return response


# --------------------------------------------------------------------------------------
# Titik masuk
# --------------------------------------------------------------------------------------
def build_story(frames: StoryFrames, filters: FilterParams, mode: str = "impact",
                pillar: str | None = None, topic: str | None = None,
                matkul: MatkulFrames | None = None) -> dict[str, Any]:
    """Susun seluruh chart + insight untuk satu kombinasi filter (fungsi murni; tanpa database).

    `matkul` opsional: data mata kuliah (subproyek matkul-sustainability). Kalau None,
    blok `mata_kuliah` diisi ringkasan kosong bertanda `tersedia: False` supaya kontrak
    respons tetap sama untuk semua pemanggil.
    """
    if mode not in ("impact", "impact-sdgs", "sdgs"):
        raise ValueError("mode must be impact, impact-sdgs or sdgs")
    start, end = filters.year_bounds(*_year_range(frames.berita))
    if mode == "sdgs":
        result = _story_sdgs(frames, filters, start, end, matkul)
    else:
        result = _story_impact(frames, filters, mode, start, end, pillar, topic, matkul)
    return _native(result)


class StoryService:
    """Memuat data (SELECT sederhana, portabel) dan memanggil `build_story()`."""

    # Kunci cache = objek engine itu sendiri, bukan id(engine): id() bisa didaur ulang Python
    # setelah engine lama di-GC, sehingga permintaan bisa menyajikan data dari engine lain
    # (mis. MySQL pratinjau vs Postgres produksi).
    _cache: dict[Any, tuple[float, StoryFrames]] = {}
    _lock = threading.Lock()

    def __init__(self, engine: Engine):
        self.engine = engine

    @classmethod
    def clear_cache(cls) -> None:
        """Buang cache semua engine -- dipakai test dan saat pindah sumber data."""
        with cls._lock:
            cls._cache.clear()

    def _read(self, sql: str) -> pd.DataFrame:
        return pd.read_sql(text(sql), self.engine)

    def _load(self) -> StoryFrames:
        sitemap = self._read("SELECT url, lastmod FROM berita_sitemap")
        last = sitemap["lastmod"].dropna()
        bs = self._read("SELECT url, sdg FROM berita_berita_sdg_all")
        ss = self._read("SELECT url, sdg FROM berita_sitemap_sdg")
        bs["sdg"] = bs["sdg"].astype(int)
        ss["sdg"] = ss["sdg"].astype(int)
        # Data mata kuliah (CSV kurasi, bukan DB) dimuat di sini supaya ikut cache frame;
        # kegagalan file tidak boleh mematikan seluruh endpoint berita.
        try:
            matkul = load_matkul()
        except FileNotFoundError as exc:
            logger.warning("Data mata kuliah dilewati: %s", exc)
            matkul = None
        return StoryFrames(
            berita=self._read("SELECT url, judul, tanggal, deskripsi, sumber FROM berita_berita"),
            bk=self._read("SELECT url, topik, dampak, topik_kepmen FROM berita_berita_kepmen_all"),
            bs=bs,
            uk=self._read("SELECT url, unit_kerja, kategori FROM berita_unit_kerja"),
            sitemap=sitemap,
            ss=ss,
            rp=self._read("SELECT dampak, jumlah_berita FROM berita_ringkasan_pilar"),
            data_as_of=None if last.empty else str(last.max()),
            matkul=matkul,
            narasi_llm=self._narasi_llm(),
        )

    def _narasi_llm(self) -> dict[str, str]:
        """Cache narasi LLM; tabel belum ada / gagal baca = kosong (narasi template dipakai)."""
        try:
            df = self._read("SELECT cache_key, narasi FROM berita_narasi_cache")
        except Exception:  # noqa: BLE001 -- fitur opsional, tidak boleh mematikan /story
            return {}
        return {str(k): str(v) for k, v in zip(df["cache_key"], df["narasi"]) if v and str(v).strip()}

    def frames(self) -> StoryFrames:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(self.engine)
            if cached and now - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]
            frames = self._load()
            self._cache[self.engine] = (now, frames)
            # Aplikasi hanya punya satu engine (get_engine() di-cache), jadi batas ini sekadar
            # jaring supaya cache tidak menumpuk kalau engine dibuat berulang (mis. di test).
            while len(self._cache) > _CACHE_MAX_ENGINES:
                tertua = min(self._cache, key=lambda key: self._cache[key][0])
                self._cache.pop(tertua, None)
            return frames

    def story(self, filters: FilterParams, mode: str, pillar: str | None = None, topic: str | None = None) -> dict[str, Any]:
        frames = self.frames()
        return build_story(frames, filters, mode, pillar, topic, matkul=frames.matkul)
