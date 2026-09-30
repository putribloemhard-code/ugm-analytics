# -*- coding: utf-8 -*-
"""Menulis satu file .xlsx per tabel LED dan LKPS.

Keluaran:
  akreditasi/docs/tabel_xlsx/LED/LED-Tabel <nomor> - <nama>.xlsx     (42 file)
  akreditasi/docs/tabel_xlsx/LKPS/LKPS-Tabel <nomor> - <nama>.xlsx   (38 file)

Tiap file berisi identitas tabel (dokumen, nomor, nama, halaman, jumlah kolom) dan
daftar header kolomnya. Nomor, judul, halaman, dan header diambil dari modul
daftar_tabel_led_lkps — sumber kebenaran yang sama dengan
akreditasi/docs/Daftar_Tabel_LED_dan_LKPS_MEI.md.
"""
import os
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, "D:/ugm-analytics/akreditasi/scripts")
from daftar_tabel_led_lkps import DIR_XLSX, LKPS_TANPA_NOMOR_PAGE, ekstrak

FONT = "Arial"
LABEL = Font(name=FONT, size=10, bold=True)
VALUE = Font(name=FONT, size=10)
TITLE = Font(name=FONT, size=12, bold=True)
GREY = PatternFill("solid", fgColor="F2F2F2")
WRAP = Alignment(wrap_text=True, vertical="top")

DOC_LED = "LED — Laporan Evaluasi Diri"
DOC_LKPS = "LKPS — Laporan Kinerja Program Studi"

# Windows melarang karakter ini di nama berkas.
ILEGAL = re.compile(r'[\\/:*?"<>|]')
MAKS_JUDUL = 60

CATATAN_LED = ("Nomor dan judul dari DAFTAR TABEL LED; posisi tabel dan header kolom dari "
               "caption bernomor di badan LED (baris header bertingkat digabung).")
CATATAN_LKPS = ("Nomor dan judul dari caption bernomor di badan LKPS; header kolom digabung "
                "dari baris header bertingkat blok tabel di bawah caption.")
CATATAN_LKPS_TANPA_NOMOR = "Tabel tanpa nomor di awal LKPS (daftar program studi di UPPS)."


def nama_berkas(prefix, judul):
    """'LED-Tabel C1.1 - Indikator sistem tata kelola ....xlsx' (judul dipotong di batas kata)."""
    bersih = re.sub(r"\s+", " ", ILEGAL.sub("-", judul)).strip(" .")
    if len(bersih) > MAKS_JUDUL:
        potong = bersih[:MAKS_JUDUL]
        bersih = (potong[:potong.rfind(" ")] if " " in potong else potong).strip(" .,-")
    return f"{prefix} - {bersih}.xlsx" if bersih else f"{prefix}.xlsx"


def tulis_xlsx(path, dokumen, nomor, judul, hal_label, hal_nilai, hal_pdf, header, catatan):
    """Satu tabel -> satu workbook. Header ditulis mendatar (1 kolom = 1 sel)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Tabel"

    ws["A1"] = "Dokumen"
    ws["B1"] = dokumen
    ws["A2"] = "Nomor tabel"
    ws["B2"] = nomor
    ws["A3"] = "Nama tabel"
    ws["B3"] = judul
    ws["A4"] = hal_label
    ws["B4"] = hal_nilai
    ws["A5"] = "Halaman PDF"
    ws["B5"] = hal_pdf if hal_pdf else "-"
    ws["A6"] = "Jumlah kolom"
    ws["B6"] = len(header)

    for r in range(1, 7):
        ws.cell(row=r, column=1).font = LABEL
        ws.cell(row=r, column=1).fill = GREY
        ws.cell(row=r, column=2).font = VALUE
    ws["B3"].font = TITLE
    ws["B3"].alignment = WRAP

    ws["A8"] = "Header tabel"
    ws["A8"].font = LABEL
    ws["A8"].fill = GREY
    for i, h in enumerate(header, start=1):
        c = ws.cell(row=9, column=i, value=i)
        c.font = VALUE
        c.fill = GREY
        c.alignment = Alignment(horizontal="center")
        c = ws.cell(row=10, column=i, value=h)
        c.font = VALUE
        c.alignment = WRAP

    ws["A12"] = "Catatan"
    ws["A12"].font = LABEL
    ws["A12"].fill = GREY
    ws["B12"] = catatan
    ws["B12"].font = VALUE
    ws["B12"].alignment = WRAP

    ws.column_dimensions["A"].width = 16
    for i in range(2, max(len(header), 2) + 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 26
    ws.row_dimensions[10].height = 60
    ws.row_dimensions[12].height = 30
    ws.freeze_panes = "A9"

    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)


def main():
    d = ekstrak()
    baris = []
    tanpa_header = []

    for r in d["led_rows"]:
        header = r["header"] or ["-"]
        if not r["header"]:
            tanpa_header.append(r["nomor"])
        baris.append({
            "path": os.path.join(DIR_XLSX, "LED", nama_berkas(f"LED-Tabel {r['nomor']}", r["judul"])),
            "dokumen": DOC_LED, "nomor": r["nomor"], "judul": r["judul"],
            "hal_label": "Halaman cetak", "hal_nilai": r["hal_cetak"],
            "hal_pdf": r["hal_pdf"], "header": header, "catatan": CATATAN_LED,
        })

    for r in d["lkps_rows"]:
        baris.append({
            "path": os.path.join(DIR_XLSX, "LKPS", nama_berkas(f"LKPS-Tabel {r['nomor']}", r["judul"])),
            "dokumen": DOC_LKPS, "nomor": r["nomor"], "judul": r["judul"],
            "hal_label": "Halaman PDF", "hal_nilai": r["hal"],
            "hal_pdf": r["hal"], "header": r["header"] or ["-"], "catatan": CATATAN_LKPS,
        })

    for t in d["lkps_tanpa_nomor"]:
        judul = "Daftar Program Studi di UPPS (tabel tanpa nomor)"
        baris.append({
            "path": os.path.join(DIR_XLSX, "LKPS", nama_berkas("LKPS-Tabel Tanpa Nomor", judul)),
            "dokumen": DOC_LKPS, "nomor": "Tanpa nomor", "judul": judul,
            "hal_label": "Halaman PDF", "hal_nilai": LKPS_TANPA_NOMOR_PAGE + 1,
            "hal_pdf": LKPS_TANPA_NOMOR_PAGE + 1, "header": t["header"],
            "catatan": CATATAN_LKPS_TANPA_NOMOR,
        })

    for b in baris:
        tulis_xlsx(b["path"], b["dokumen"], b["nomor"], b["judul"], b["hal_label"],
                   b["hal_nilai"], b["hal_pdf"], b["header"], b["catatan"])

    n_led = len(d["led_rows"])
    print(f"xlsx ditulis: LED={n_led} | LKPS={len(baris) - n_led} | total={len(baris)}")
    print("LED tanpa header terdeteksi:", ", ".join(tanpa_header) if tanpa_header else "tidak ada")
    print("folder:", DIR_XLSX)
    return baris


if __name__ == "__main__":
    main()
