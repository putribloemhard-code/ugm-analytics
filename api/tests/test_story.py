"""Uji fungsi murni services/story.py dengan DataFrame kecil buatan tangan (tanpa database)."""
from __future__ import annotations

import json

import pandas as pd

from app.domain.models import FilterParams
from app.services.story import (
    StoryFrames,
    build_story,
    insight_heatmap,
    insight_top2,
    overview_rows,
    plain,
)


def make_frames() -> StoryFrames:
    berita = pd.DataFrame([
        {"url": "u1", "judul": "Restorasi hutan mangrove UGM", "tanggal": "2023-03-01", "deskripsi": "konservasi energi surya", "sumber": "rss"},
        {"url": "u2", "judul": "Reboisasi lahan kritis", "tanggal": "2024-03-10", "deskripsi": "hutan kota", "sumber": "sitemap"},
        {"url": "u3", "judul": "Kewirausahaan mahasiswa", "tanggal": "2024-05-02", "deskripsi": "startup", "sumber": "sitemap"},
        {"url": "u4", "judul": "Beasiswa afirmasi disabilitas", "tanggal": "2025-01-20", "deskripsi": "pendidikan inklusif", "sumber": "sitemap"},
        {"url": "u5", "judul": "Difabel kuliah", "tanggal": "2025-02-11", "deskripsi": "inklusi", "sumber": "sitemap"},
        {"url": "u6", "judul": "Berita biasa", "tanggal": "2025-06-30", "deskripsi": "tanpa tema", "sumber": "sitemap"},
    ])
    bk = pd.DataFrame([
        # u1 masuk DUA tema Lingkungan -> tetap 1 berita unik untuk dampak Lingkungan
        {"url": "u1", "topik": "rehabilitasi_lingkungan", "dampak": "Lingkungan", "topik_kepmen": "Keanekaragaman Hayati"},
        {"url": "u1", "topik": "energi", "dampak": "Lingkungan", "topik_kepmen": "Energi"},
        {"url": "u2", "topik": "rehabilitasi_lingkungan", "dampak": "Lingkungan", "topik_kepmen": "Keanekaragaman Hayati"},
        {"url": "u3", "topik": "kewirausahaan", "dampak": "Ekonomi", "topik_kepmen": "Ekosistem Kewirausahaan"},
        {"url": "u4", "topik": "pendidikan_inklusif", "dampak": "Sosial", "topik_kepmen": "Pendidikan Inklusif"},
        {"url": "u5", "topik": "pendidikan_inklusif", "dampak": "Sosial", "topik_kepmen": "Pendidikan Inklusif"},
    ])
    bs = pd.DataFrame([
        {"url": "u1", "sdg": 13}, {"url": "u1", "sdg": 7}, {"url": "u2", "sdg": 13},
        {"url": "u3", "sdg": 8}, {"url": "u4", "sdg": 4}, {"url": "u5", "sdg": 4}, {"url": "u5", "sdg": 1},
    ])
    uk = pd.DataFrame([
        {"url": "u1", "unit_kerja": "fakultas_kehutanan", "kategori": "Fakultas"},
        {"url": "u4", "unit_kerja": "fakultas_teknik", "kategori": "Fakultas"},
    ])
    sitemap = pd.DataFrame([
        {"url": f"https://x/{i}/", "lastmod": f"{year}-01-01T00:00:00+00:00"}
        for i, year in enumerate([2023, 2023, 2024, 2024, 2024, 2025, 2025, 2025])
    ])
    ss = pd.DataFrame([
        {"url": "https://x/0/", "sdg": 3}, {"url": "https://x/0/", "sdg": 4},
        {"url": "https://x/2/", "sdg": 3}, {"url": "https://x/5/", "sdg": 4},
    ])
    rp = pd.DataFrame([{"dampak": "Ekonomi", "jumlah_berita": 10}, {"dampak": "Lingkungan", "jumlah_berita": 7},
                       {"dampak": "Sosial", "jumlah_berita": 3}])
    return StoryFrames(berita, bk, bs, uk, sitemap, ss, rp, data_as_of="2025-06-30")


def chart_by_id(charts, chart_id):
    return next(chart for chart in charts if chart["id"] == chart_id)


# ---------------------------------------------------------------- helper kalimat insight
def test_insight_top2_single_row_and_plain_text():
    df = pd.DataFrame({"label": ["Energi"], "jumlah": [1234]})
    text = insight_top2(df, "label", "jumlah")
    assert text == "**Energi** dengan 1,234 berita."
    assert plain(text) == "Energi dengan 1,234 berita."


def test_insight_top2_sorts_and_compares_to_runner_up():
    df = pd.DataFrame({"label": ["A", "B", "C"], "jumlah": [5, 20, 10]})
    text = insight_top2(df, "label", "jumlah")
    assert text == "**B** paling dominan dengan 20 berita, 100% lebih tinggi dari C (10 berita)."


def test_insight_top2_zero_runner_up_and_custom_unit():
    df = pd.DataFrame({"label": ["A", "B"], "jumlah": [3, 0]})
    assert insight_top2(df, "label", "jumlah", satuan="kali") == "**A** paling dominan dengan 3 kali, jauh lebih tinggi dari B (0 kali)."


def test_insight_heatmap_picks_highest_cell():
    matrix = pd.DataFrame([[1, 4], [7, 2]], index=["T1", "T2"], columns=["2023", "2024"])
    assert insight_heatmap(matrix) == "Kombinasi tertinggi: **T2 × 2023** dengan 7 berita."
    assert insight_heatmap(pd.DataFrame()) == "Belum ada data untuk kombinasi ini."


# ---------------------------------------------------------------- overview & hitung unik
def test_overview_counts_unique_urls_not_rows():
    frames = make_frames()
    rows = overview_rows(frames.berita, frames.bk, ("Lingkungan", "Ekonomi", "Sosial"))
    by_pillar = {row["pillar"]: row for row in rows}
    # u1 punya 2 baris tema Lingkungan, tapi hanya 1 berita unik; u1+u2 = 2 berita
    assert by_pillar["Lingkungan"]["total"] == 2
    assert by_pillar["Lingkungan"]["top_topic"] == "Keanekaragaman Hayati"
    assert by_pillar["Lingkungan"]["top_topic_count"] == 2
    assert by_pillar["Sosial"]["total"] == 2 and by_pillar["Sosial"]["top_topic_count"] == 2
    assert by_pillar["Ekonomi"]["total"] == 1


def test_overview_empty_pillar_has_no_top_topic():
    frames = make_frames()
    rows = overview_rows(frames.berita, frames.bk[frames.bk["dampak"] == "Sosial"], ("Lingkungan",))
    assert rows == [{"pillar": "Lingkungan", "total": 0, "top_topic": None, "top_topic_count": 0}]


# ---------------------------------------------------------------- build_story: impact
def test_impact_story_top_level_contract_and_json():
    story = build_story(make_frames(), FilterParams(), "impact")
    json.dumps(story)  # tidak boleh ada tipe numpy
    assert set(story) == {"mode", "filters", "data_as_of", "caveats", "executive", "overview",
                          "cross", "pillar_detail", "chapters", "tables"}
    assert story["filters"]["year_from"] == "2023" and story["filters"]["year_to"] == "2025"
    metrics = {m["label"]: m for m in story["executive"]["metrics"]}
    assert metrics["Total berita dampak"]["value"] == 5  # u1..u5 unik, u6 tak bertema
    assert metrics["Sorotan 2025"]["value"] == "2 berita"
    assert "Tema Kepmen terbanyak" in metrics
    assert story["executive"]["narrative"].startswith("Sepanjang 2023–2025")
    assert story["pillar_detail"] is None


def test_impact_story_cross_charts_and_kinds():
    story = build_story(make_frames(), FilterParams(), "impact")
    charts = story["cross"]["charts"]
    titles = [c["title"] for c in charts]
    assert titles[0] == "Jumlah berita per Tema Resmi Kepmen (berdasarkan dampak)"
    assert "Jumlah berita per SDG (klaster resmi)" not in titles  # khusus impact-sdgs
    assert {"Jumlah berita per tema per tahun", "Jumlah berita per tahun",
            "Jumlah berita per bulan kalender (semua tahun digabung)",
            "Volume berita UGM vs berita yang terdeteksi tema dampak",
            "Berapa banyak tema per berita"} <= set(titles)
    kepmen = chart_by_id(charts, "kepmen")
    values = [row["value"] for row in kepmen["data"]]
    assert values == sorted(values, reverse=True)  # bar horizontal: terbesar dulu
    assert {row["group"] for row in kepmen["data"]} == {"Lingkungan", "Ekonomi", "Sosial"}
    assert kepmen["data"][0]["label"] == "Keanekaragaman Hayati" and kepmen["data"][0]["value"] == 2
    assert "**" not in kepmen["insight"]
    combo = chart_by_id(charts, "cakupan")["data"]
    # total sitemap per tahun 2, 3, 3; berita unik bertema per tahun: 1 (u1), 2 (u2,u3), 2 (u4,u5)
    assert combo["x"] == ["2023", "2024", "2025"]
    assert combo["bars"]["values"] == [2, 3, 3]
    assert combo["line"]["values"] == [1, 2, 2]
    dist = chart_by_id(charts, "multi_tema")["data"]
    assert {row["label"]: row["value"] for row in dist} == {"1": 4, "2": 1}  # hanya u1 masuk 2 tema
    multi = next(t for t in story["cross"]["tables"] if t["id"] == "multi_tema")
    assert multi["rows"] == [{"kombinasi": "Energi + Keanekaragaman Hayati", "n_tema": 2, "berita": 1}]


def test_impact_story_pillar_detail_tabs_and_semantics():
    story = build_story(make_frames(), FilterParams(), "impact", pillar="Lingkungan")
    detail = story["pillar_detail"]
    assert [tab["id"] for tab in detail["tabs"]] == ["ringkasan", "kepmen", "tren", "kata_kunci", "unit"]
    metrics = {m["label"]: m["value"] for m in detail["metrics"]}
    assert metrics == {"Berita unik": 2, "Tema aktif": 2, "Tahun jangkauan": "2023–2024"}
    tab = detail["tabs"][0]
    tema = chart_by_id(tab["charts"], "tema")
    assert tema["title"] == "Distribusi tema dalam dampak Lingkungan"
    assert [row["value"] for row in tema["data"]] == [2, 1]
    tren = chart_by_id(tab["charts"], "tren")
    assert tren["title"] == "Tren berita per tahun untuk dampak Lingkungan"
    assert tren["insight"] == ("Dari 1 berita (2023) menjadi 1 berita (2024) — naik 0 berita. "
                               "Puncak tertinggi: 2023 dengan 1 berita.")
    # tab tren: hanya tema milik dampak ini pada heatmap dan stacked bar
    tren_tab = next(t for t in detail["tabs"] if t["id"] == "tren")
    heat = chart_by_id(tren_tab["charts"], "tema_tahun")["data"]
    assert set(heat["rows"]) == {"Keanekaragaman Hayati", "Energi", "Transportasi",
                                 "Konsumsi yang Bertanggung Jawab", "Pendidikan & Penelitian"}
    assert heat["cols"] == ["2023", "2024"]
    # kata kunci: default = tema dengan berita terbanyak, opsi terbatas pada dampak ini
    assert detail["selected_topic"] == "rehabilitasi_lingkungan"
    assert all(opt["value"] in {"rehabilitasi_lingkungan", "energi", "transportasi", "limbah", "pendidikan_dan_penelitian"}
               for opt in detail["topic_options"])
    kata = next(t for t in detail["tabs"] if t["id"] == "kata_kunci")
    kw = chart_by_id(kata["charts"], "pilar_keyword")
    assert kw["title"] == "Keyword pemicu match — Keanekaragaman Hayati"
    assert {row["label"]: row["value"] for row in kw["data"]}["hutan"] == 2  # u1 + u2
    assert kata["tables"][0]["rows"][0]["tanggal"] == "2024-03-10"  # terbaru dulu


def test_impact_sdgs_story_adds_sdg_tab_and_cross_charts():
    story = build_story(make_frames(), FilterParams(), "impact-sdgs", pillar="Sosial")
    ids = [tab["id"] for tab in story["pillar_detail"]["tabs"]]
    assert ids == ["ringkasan", "kepmen", "sdgs", "tren", "kata_kunci", "unit"]
    sdg_tab = next(t for t in story["pillar_detail"]["tabs"] if t["id"] == "sdgs")
    bars = chart_by_id(sdg_tab["charts"], "sdg")
    assert bars["title"] == "Berita per SDG — dampak Sosial" and bars["orientation"] == "v"
    assert {row["label"]: row["value"] for row in bars["data"]} == {"SDG 4": 2, "SDG 1": 1}
    titles = [c["title"] for c in story["cross"]["charts"]]
    assert "Jumlah berita per SDG (klaster resmi)" in titles
    assert "Berita per kombinasi tema dampak × SDG" in titles
    assert "Jumlah berita per SDG per tahun" in titles
    assert "Jumlah berita per dampak per tahun (14 tema Kepmen)" in titles
    assert next(m for m in story["executive"]["metrics"] if m["label"].endswith("terbanyak") and m["label"].startswith("SDG"))


def test_units_filter_narrows_news_but_unit_tab_ignores_it():
    story = build_story(make_frames(), FilterParams(units=("fakultas_teknik",)), "impact", pillar="Sosial")
    assert story["executive"]["metrics"][0]["value"] == 1  # hanya u4
    assert {row["pillar"]: row["total"] for row in story["overview"]} == {"Lingkungan": 0, "Ekonomi": 0, "Sosial": 1}
    unit_tab = next(t for t in story["pillar_detail"]["tabs"] if t["id"] == "unit")
    # basis tab unit tanpa filter unit: u4 & u5 (Sosial) -> yang punya unit hanya u4 (Fakultas Teknik)
    chart = chart_by_id(unit_tab["charts"], "unit")
    assert chart["data"] == [{"label": "Fakultas Teknik", "value": 1, "group": "Fakultas"}]
    no_unit = next(t for t in unit_tab["tables"] if t["id"] == "tanpa_unit")
    assert [row["url"] for row in no_unit["rows"]] == ["u5"]


def test_news_tables_are_paginated_but_summary_tables_are_not():
    """Daftar berita tampil 5 baris per halaman; tabel ringkas tetap utuh (tanpa pager)."""
    story = build_story(make_frames(), FilterParams(), "impact")

    # Sub-bab laporan: daftar berita bertema.
    sub = {s["topic"]: s for s in story["chapters"][0]["subsections"]}["pendidikan_inklusif"]
    daftar = sub["tables"][0]
    assert daftar["page_size"] == 5
    assert "5 per halaman" in daftar["note"]
    assert len(daftar["rows"]) == 2  # fixture: lebih sedikit dari page_size

    # Tab "Kata Kunci & Berita" (mode impact, pillar_detail terisi saat pilar dipilih).
    with_pillar = build_story(make_frames(), FilterParams(), "impact", pillar="Sosial")
    detail = with_pillar["pillar_detail"]
    kata_kunci = next(t for t in detail["tabs"] if t["id"] == "kata_kunci")
    assert kata_kunci["tables"][0]["page_size"] == 5

    # Tabel ringkas (lintas-dampak, SDG, dsb.) TIDAK ber-paginasi — tampil utuh.
    ringkas = list(story["tables"]) + list(story["cross"]["tables"])
    assert ringkas, "tidak ada tabel ringkas untuk diuji"
    for table in ringkas:
        assert table["page_size"] is None, table["id"]


def test_year_range_and_empty_result():
    story = build_story(make_frames(), FilterParams(year_from="2030", year_to="2031"), "impact")
    assert story["executive"]["metrics"] == [] and story["cross"]["charts"] == []
    assert story["chapters"] == []  # tidak ada data -> tidak ada bab palsu
    assert "Tidak ada data" in story["executive"]["narrative"]
    narrow = build_story(make_frames(), FilterParams(year_from="2024", year_to="2024"), "impact")
    assert narrow["executive"]["metrics"][0]["value"] == 2  # u2, u3


# ---------------------------------------------------------------- bab laporan (daftar isi)
def test_chapters_follow_report_table_of_contents():
    """Urutan bab/sub-bab harus sama dengan daftar isi LAPORAN DAMPAK UGM 2025."""
    story = build_story(make_frames(), FilterParams(), "impact")
    chapters = story["chapters"]
    assert [c["pillar"] for c in chapters] == ["Sosial", "Ekonomi", "Lingkungan"]
    assert [c["chapter"] for c in chapters] == ["BAB II", "BAB III", "BAB IV"]
    assert [c["title"] for c in chapters] == ["Dampak Sosial", "Dampak Ekonomi", "Dampak Lingkungan"]

    sosial = chapters[0]
    assert [(s["number"], s["label"]) for s in sosial["subsections"]] == [
        ("2.1", "Pendidikan Inklusif"), ("2.2", "Penelitian & Inovasi"),
        ("2.3", "Pengabdian Masyarakat"), ("2.4", "Kebijakan Publik"),
    ]
    ekonomi = chapters[1]
    assert [(s["number"], s["label"]) for s in ekonomi["subsections"]] == [
        ("3.1", "Pengajaran & Pembelajaran"), ("3.2", "Kolaborasi Riset"), ("3.3", "Kewirausahaan"),
        ("3.4", "Kunjungan Akademik"), ("3.5", "Pengeluaran Institusi"),
    ]
    lingkungan = chapters[2]
    assert [(s["number"], s["label"]) for s in lingkungan["subsections"]] == [
        ("4.1", "Energi"), ("4.2", "Konsumsi yang Bertanggung Jawab"), ("4.3", "Transportasi"),
        ("4.4", "Keanekaragaman Hayati"), ("4.5", "Pendidikan & Penelitian"),
    ]

    # Tiap bab punya 2 chart level-bab (distribusi tema + heatmap tema × tahun), id unik per bab.
    for chapter in chapters:
        ids = [chart["id"] for chart in chapter["charts"]]
        assert ids == [f"bab_{chapter['pillar'].lower()}_tema", f"bab_{chapter['pillar'].lower()}_tema_tahun"]
    assert {m["label"]: m["value"] for m in chapters[2]["metrics"]}["Berita dampak"] == 2


def test_chapter_subsection_carries_indicator_and_keeps_zero_topics():
    """Tiap sub-bab membawa indikator resmi Kepmen walau beritanya nol."""
    story = build_story(make_frames(), FilterParams(), "impact")
    lingkungan = story["chapters"][2]
    by_topic = {s["topic"]: s for s in lingkungan["subsections"]}

    # 4.4 Keanekaragaman Hayati: u1 + u2 (u1 juga masuk tema Energi, tetap 1 berita unik per tema)
    hayati = by_topic["rehabilitasi_lingkungan"]
    assert hayati["official_topic"] == "Keanekaragaman Hayati"
    assert hayati["unit"] == "Program" and hayati["sdgs"] == [13, 14, 15]
    assert hayati["indicator"].startswith("Jumlah program rehabilitasi")
    assert hayati["definition"] and hayati["criteria"] and hayati["formula"]
    assert {m["label"]: m["value"] for m in hayati["metrics"]}["Berita unik"] == 2
    assert hayati["tables"][0]["rows"][0]["tanggal"] == "2024-03-10"  # terbaru dulu
    assert all(chart["id"].startswith("chapter_rehabilitasi_lingkungan_") for chart in hayati["charts"])

    # 4.2 Konsumsi Energi yang Bertanggung Jawab (limbah) tidak punya berita -> tetap tampil +
    # indikatornya. Judul di daftar isi = judul laporan, nama tema Kepmen tetap yang resmi.
    limbah = by_topic["limbah"]
    assert {m["label"]: m["value"] for m in limbah["metrics"]}["Berita unik"] == 0
    assert limbah["official_topic"] == "Konsumsi yang Bertanggung Jawab"
    assert limbah["report_title"] == "Konsumsi Energi yang Bertanggung Jawab"
    assert limbah["charts"] == [] and limbah["tables"][0]["rows"] == []
    assert limbah["indicator"] and limbah["unit"]

    # Judul laporan untuk tema yang berbeda dari nama Kepmen (uji daftar isi 1:1 dengan PDF).
    assert by_topic["rehabilitasi_lingkungan"]["report_title"] == "Keanekaragaman Hayati"
    ekonomi = {s["topic"]: s for s in story["chapters"][1]["subsections"]}
    assert ekonomi["kunjungan_akademik"]["report_title"] == "Kunjungan Akademik dan Pengeluaran Pengunjung Nasional"
    assert ekonomi["kolaborasi_riset"]["report_title"] == "Penelitian dan Pertukaran Pengetahuan"
    assert ekonomi["kolaborasi_riset"]["official_topic"] == "Penelitian dan Pertukaran Pengetahuan"

    # 2.1 Pendidikan Inklusif: u4 + u5
    inklusif = {s["topic"]: s for s in story["chapters"][0]["subsections"]}["pendidikan_inklusif"]
    assert {m["label"]: m["value"] for m in inklusif["metrics"]}["Berita unik"] == 2
    assert inklusif["sdgs"] == [1, 4, 10]


def test_chapters_respect_pillar_and_topic_filters():
    story = build_story(make_frames(), FilterParams(pillars=("Sosial",)), "impact")
    assert [c["pillar"] for c in story["chapters"]] == ["Sosial"]
    # hanya sub-bab Sosial, urut tetap sesuai daftar isi
    assert [s["number"] for s in story["chapters"][0]["subsections"]] == ["2.1", "2.2", "2.3", "2.4"]

    sempit = build_story(make_frames(), FilterParams(topics=("energi",)), "impact")
    assert [c["pillar"] for c in sempit["chapters"]] == ["Lingkungan"]
    assert [s["number"] for s in sempit["chapters"][0]["subsections"]] == ["4.1"]


def test_sdgs_mode_has_no_chapters():
    story = build_story(make_frames(), FilterParams(), "sdgs")
    assert story["chapters"] == []


# ---------------------------------------------------------------- mode sdgs
def test_sdgs_story():
    story = build_story(make_frames(), FilterParams(), "sdgs")
    json.dumps(story)
    metrics = {m["label"]: m["value"] for m in story["executive"]["metrics"]}
    assert metrics == {"Total berita (sitemap)": 8, "Berita bertanda SDG": 3, "Cakupan": "37.5%"}
    assert story["overview"] == [] and story["cross"]["title"] == "Analisis SDGs"
    bars = chart_by_id(story["cross"]["charts"], "sdg")
    assert bars["title"] == "Jumlah berita per SDG (seluruh URL sitemap)"
    assert {row["label"]: row["value"] for row in bars["data"]} == {"SDG 3": 2, "SDG 4": 2}
    heat = chart_by_id(story["cross"]["charts"], "sdg_tahun_heatmap")["data"]
    assert heat["rows"] == ["SDG 3", "SDG 4"] and heat["cols"] == ["2023", "2024", "2025"]
    assert [t["title"] for t in story["tables"]] == [
        "Ringkasan per SDG", "Keyword per SDG (dasar mapping)", "Berita tanpa tanda SDG (cek manual)",
    ]
    assert "32.130" not in json.dumps(story)
    untagged = story["tables"][2]
    assert len(untagged["rows"]) == 8 - 3


def test_sdgs_story_year_filter_and_no_data():
    story = build_story(make_frames(), FilterParams(year_from="2024", year_to="2024"), "sdgs")
    assert story["executive"]["metrics"][0]["value"] == 3
    empty = build_story(make_frames(), FilterParams(year_from="2024", year_to="2024", sdgs=(17,)), "sdgs")
    assert empty["cross"]["charts"] == [] and empty["tables"] == []
