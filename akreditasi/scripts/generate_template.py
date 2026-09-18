"""Generator dokumen template akreditasi (.docx) -- python-docx.

Dua entry point terpisah -- generate_led_docx() dan generate_lkps_docx() --
sesuai pemisahan mode dashboard (LED per Kriteria A-D, LKPS per Bagian 1-6),
lihat docstring registry_kebutuhan_data.py poin 6. Prinsip WAJIB (tidak
berubah): SETIAP item registry di dokumen masing-masing selalu punya
section/tabel, bahkan kalau datanya belum ada -- ditandai placeholder italic
"Data belum tersedia" (bukan section yang dihilangkan), supaya dokumen tetap
berfungsi sebagai template lengkap yang tinggal dilengkapi tim penyusun.
"""

import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

import db  # noqa: E402
from registry_kebutuhan_data import (  # noqa: E402
    KEBUTUHAN_DATA,
    LABEL_BAGIAN_LKPS,
    LABEL_KRITERIA,
    URUTAN_BAGIAN_LKPS,
    URUTAN_KRITERIA,
    led_items_by_kriteria,
    lkps_cuplikan_untuk_kriteria,
    lkps_items_by_bagian,
    ringkasan_status,
)

WARNA_PLACEHOLDER = RGBColor(0x99, 0x33, 0x33)


def _load_data_manual(engine, prodi_id: str = "mei") -> pd.DataFrame:
    """`prodi_id` WAJIB di-filter (2026-09-11, lihat scripts/migrasi_prodi_id.py)
    -- tabel data_manual sekarang multi-tenant, tanpa filter ini dokumen yang
    digenerate akan mencampur data semua prodi jadi satu."""
    if not db.table_exists(engine, db.t("data_manual")):
        return pd.DataFrame(columns=["item_id", "baris_ke", "kolom", "tahun", "nilai", "link_bukti"])
    return db.read_sql_retry(
        engine, f"SELECT item_id, baris_ke, kolom, tahun, nilai, link_bukti FROM `{db.t('data_manual')}` "
                f"WHERE prodi_id = :prodi_id",
        label="load data_manual (generate_template)", params={"prodi_id": prodi_id},
    )


def _rows_for_item(item_id: str, df: pd.DataFrame) -> list[dict]:
    """Kembalikan list baris (dict kolom->nilai) untuk satu item, dari bentuk
    long (satu baris df = satu sel) dipivot balik ke wide per baris_ke."""
    sub = df[df["item_id"] == item_id]
    if not len(sub):
        return []
    rows: dict[int, dict] = {}
    for _, r in sub.iterrows():
        rows.setdefault(int(r["baris_ke"]), {})[r["kolom"]] = r["nilai"] or ""
        if r.get("link_bukti") and "Link Bukti" not in rows[int(r["baris_ke"])]:
            rows[int(r["baris_ke"])].setdefault("_link_bukti", r["link_bukti"])
    return [rows[k] for k in sorted(rows)]


def _placeholder_paragraph(doc: Document, sumber: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"⚠️ Data belum tersedia — sumber data seharusnya: {sumber}")
    run.italic = True
    run.font.color.rgb = WARNA_PLACEHOLDER


def _add_tabel_item(doc: Document, item: dict, rows: list[dict]) -> None:
    kolom = item["kolom_dibutuhkan"]
    if not rows:
        _placeholder_paragraph(doc, item["sumber_data"])
        return
    table = doc.add_table(rows=1, cols=len(kolom))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, k in enumerate(kolom):
        hdr[i].text = k
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.font.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, k in enumerate(kolom):
            cells[i].text = str(row.get(k, ""))


def _add_narasi_item(doc: Document, item: dict, rows: list[dict]) -> None:
    if not rows:
        _placeholder_paragraph(doc, item["sumber_data"])
        return
    row = rows[0]
    for k in item["kolom_dibutuhkan"]:
        nilai = row.get(k, "")
        p = doc.add_paragraph()
        p.add_run(f"{k}: ").bold = True
        if nilai:
            p.add_run(str(nilai))
        else:
            run = p.add_run("⚠️ Data belum tersedia")
            run.italic = True
            run.font.color.rgb = WARNA_PLACEHOLDER


def _add_cover(doc: Document, judul: str, ringkasan: dict) -> None:
    title = doc.add_heading(judul, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run("Template digenerate otomatis — akreditasi/ (UGM Analytics)").italic = True
    p_tgl = doc.add_paragraph()
    p_tgl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tgl.add_run(f"Digenerate: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph()
    p_stat = doc.add_paragraph()
    p_stat.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_stat.add_run(
        f"Kelengkapan data: {ringkasan['lengkap']}/{ringkasan['total']} item "
        f"({100 * ringkasan['lengkap'] / ringkasan['total']:.0f}%) — "
        f"{ringkasan['tersedia_otomatis']} tersedia otomatis, "
        f"{ringkasan['perlu_manual_terisi']}/{ringkasan['perlu_manual_total']} input manual terisi, "
        f"{ringkasan['belum_tersedia']} belum tersedia."
    )
    doc.add_page_break()


def _add_todo(doc: Document, item_ids: list[str], filled_ids: set) -> None:
    doc.add_heading("Ringkasan & To-Do — Item Data Belum Lengkap", level=1)
    doc.add_paragraph(
        "Daftar berikut adalah checklist untuk tim penyusun: seluruh item data yang "
        "masih berstatus belum tersedia atau perlu input manual tapi belum diisi."
    )
    todo_kolom = ["Nama", "Tabel LKPS", "Kriteria", "Sumber Data Seharusnya"]
    todo_table = doc.add_table(rows=1, cols=len(todo_kolom))
    todo_table.style = "Light Grid Accent 1"
    for i, k in enumerate(todo_kolom):
        todo_table.rows[0].cells[i].text = k
        for r in todo_table.rows[0].cells[i].paragraphs[0].runs:
            r.font.bold = True
    for item_id in item_ids:
        item = KEBUTUHAN_DATA[item_id]
        belum_lengkap = (
            item["status_ketersediaan"] == "belum_tersedia"
            or (item["status_ketersediaan"] == "perlu_input_manual" and item_id not in filled_ids)
        )
        if belum_lengkap:
            cells = todo_table.add_row().cells
            cells[0].text = item["nama"]
            cells[1].text = item["tabel_lkps"] or "—"
            cells[2].text = LABEL_KRITERIA.get(item["kriteria_led"], item["kriteria_led"])
            cells[3].text = item["sumber_data"]
    doc.add_page_break()


def _add_item_section(doc: Document, item: dict, df_manual: pd.DataFrame) -> None:
    heading_text = item["nama"]
    if item["tabel_lkps"]:
        heading_text = f"Tabel {item['tabel_lkps']} — {item['nama']}"
    doc.add_heading(heading_text, level=2)
    if item["deskripsi_singkat"]:
        desc_p = doc.add_paragraph()
        desc_p.add_run(item["deskripsi_singkat"]).italic = True
    rows = _rows_for_item(item["id"], df_manual)
    if item["tipe"] == "tabel":
        _add_tabel_item(doc, item, rows)
    else:
        _add_narasi_item(doc, item, rows)
    doc.add_paragraph()


def _add_cuplikan_lkps(doc: Document, kriteria: str, filled_ids: set) -> None:
    """Sub-tabel ringkas (nama, no. tabel, status saja -- BUKAN isi penuh) di
    dokumen LED, dipakai untuk Kriteria A/B/C1-C6 -- isi lengkap ada di
    dokumen LKPS, jangan duplikasi data (lihat registry poin 6)."""
    cuplikan = lkps_cuplikan_untuk_kriteria(kriteria)
    if not cuplikan:
        return
    doc.add_heading("Tabel LKPS Terkait (ringkasan)", level=3)
    doc.add_paragraph(
        "Isi lengkap tabel-tabel berikut ada di Dokumen LKPS -- dicantumkan di sini "
        "sebagai ringkasan bukti evaluasi PPEPP."
    ).italic = True
    kolom = ["Tabel LKPS", "Nama", "Status"]
    table = doc.add_table(rows=1, cols=len(kolom))
    table.style = "Light Grid Accent 1"
    for i, k in enumerate(kolom):
        table.rows[0].cells[i].text = k
        for r in table.rows[0].cells[i].paragraphs[0].runs:
            r.font.bold = True
    for item in cuplikan:
        cells = table.add_row().cells
        cells[0].text = item["tabel_lkps"]
        cells[1].text = item["nama"]
        cells[2].text = "Terisi" if item["id"] in filled_ids else "Belum terisi"
    doc.add_paragraph()


def generate_led_docx(engine=None, prodi_id: str = "mei") -> bytes:
    """Dokumen "Laporan Evaluasi Diri (LED)" -- isi per Kriteria (Umum/A/B/C1-C6/D),
    lihat led_items_by_kriteria(). Kriteria A/B/C1-C6 ditutup sub-tabel ringkas
    tabel LKPS terkait (cuplikan, bukan isi penuh)."""
    engine = engine or db.get_engine()
    df_manual = _load_data_manual(engine, prodi_id)
    filled_ids = set(df_manual["item_id"].unique()) if len(df_manual) else set()
    grouped = led_items_by_kriteria()
    item_ids = [item["id"] for items in grouped.values() for item in items]
    ringkasan = ringkasan_status(item_ids=item_ids, terisi_ids=filled_ids)

    doc = Document()
    _add_cover(doc, "Laporan Evaluasi Diri (LED)", ringkasan)
    _add_todo(doc, item_ids, filled_ids)

    for kriteria in URUTAN_KRITERIA:
        items = grouped.get(kriteria, [])
        if not items:
            continue
        doc.add_heading(LABEL_KRITERIA[kriteria], level=1)
        for item in items:
            _add_item_section(doc, item, df_manual)
        if kriteria not in ("Umum", "D"):
            _add_cuplikan_lkps(doc, kriteria, filled_ids)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_lkps_docx(engine=None, prodi_id: str = "mei") -> bytes:
    """Dokumen "Laporan Kinerja Program Studi (LKPS)" -- isi per Bagian 1-6,
    lihat lkps_items_by_bagian(). Rendering tabel sama persis seperti
    sebelumnya, cuma dikelompok ulang per Bagian bukan per Kriteria."""
    engine = engine or db.get_engine()
    df_manual = _load_data_manual(engine, prodi_id)
    filled_ids = set(df_manual["item_id"].unique()) if len(df_manual) else set()
    grouped = lkps_items_by_bagian()
    item_ids = [item["id"] for items in grouped.values() for item in items]
    ringkasan = ringkasan_status(item_ids=item_ids, terisi_ids=filled_ids)

    doc = Document()
    _add_cover(doc, "Laporan Kinerja Program Studi (LKPS)", ringkasan)
    _add_todo(doc, item_ids, filled_ids)

    for bagian in URUTAN_BAGIAN_LKPS:
        items = grouped.get(bagian, [])
        if not items:
            continue
        doc.add_heading(LABEL_BAGIAN_LKPS[bagian], level=1)
        for item in items:
            _add_item_section(doc, item, df_manual)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parents[1]
    (out_dir / "template_LED.docx").write_bytes(generate_led_docx())
    (out_dir / "template_LKPS.docx").write_bytes(generate_lkps_docx())
    print(f"OK -- {out_dir / 'template_LED.docx'}")
    print(f"OK -- {out_dir / 'template_LKPS.docx'}")
