# -*- coding: utf-8 -*-
"""Menulis satu file .xlsx per tabel LED dan LKPS.

Keluaran:
  akreditasi/docs/tabel_xlsx/LED/LED-Tabel <nomor> - <nama>.xlsx     (42 file)
  akreditasi/docs/tabel_xlsx/LKPS/LKPS-Tabel <nomor> - <nama>.xlsx   (38 file)

Tiap file berisi tabel PERSIS seperti di PDF: judul tabel di atas (baris 1), header
bertingkat dengan sel yang di-merge (rowspan/colspan), dan satu baris contoh berisi
"-" (placeholder isi). Baris data asli tidak disalin. Nomor, judul, halaman, dan
header diambil dari modul daftar_tabel_led_lkps — sumber kebenaran yang sama dengan
akreditasi/docs/Daftar_Tabel_LED_dan_LKPS_MEI.md.
"""
import os
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, "D:/ugm-analytics/akreditasi/scripts")
from daftar_tabel_led_lkps import DIR_XLSX, LKPS_TANPA_NOMOR_PAGE, ekstrak

FONT = "Times New Roman"
F_TITLE = Font(name=FONT, size=12, bold=True)
F_HDR = Font(name=FONT, size=11, bold=True)
F_BODY = Font(name=FONT, size=11)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
TIPIS = Side(style="thin", color="000000")
GRID = Border(left=TIPIS, right=TIPIS, top=TIPIS, bottom=TIPIS)

# Windows melarang karakter ini di nama berkas.
ILEGAL = re.compile(r'[\\/:*?"<>|]')
MAKS_JUDUL = 60


def nama_berkas(prefix, judul):
    """'LED-Tabel C1.1 - Indikator sistem tata kelola ....xlsx' (judul dipotong di batas kata)."""
    bersih = re.sub(r"\s+", " ", ILEGAL.sub("-", judul)).strip(" .")
    # buang prefix "Tabel X.Y" dari judul (sudah ada di prefix)
    bersih = re.sub(rf"^Tabel\s+{re.escape(prefix.split()[-1])}\s+", "", bersih)
    if len(bersih) > MAKS_JUDUL:
        potong = bersih[:MAKS_JUDUL]
        bersih = (potong[:potong.rfind(" ")] if " " in potong else potong).strip(" .,-")
    return f"{prefix} - {bersih}.xlsx" if bersih else f"{prefix}.xlsx"


def _merge_dan_isi(ws, r0, c0, r1, c1, nilai, font):
    """Merge blok sel (bila >1 sel) lalu isi nilai + gaya ke seluruh blok."""
    if (r1, c1) != (r0, c0):
        ws.merge_cells(start_row=r0, start_column=c0, end_row=r1, end_column=c1)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = font
            cell.alignment = CENTER
            cell.border = GRID
    ws.cell(row=r0, column=c0, value=nilai)


def tulis_xlsx(path, judul, hdr_rows, example):
    """Satu tabel -> satu workbook, persis bentuk PDF: judul, header bertingkat
    di-merge, satu baris contoh '-'."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Tabel"

    hdr_rows = hdr_rows or [["-"]]
    n_hdr = len(hdr_rows)
    n_cols = max(len(r) for r in hdr_rows)
    hdr = [list(r) + [""] * (n_cols - len(r)) for r in hdr_rows]

    # --- judul tabel (baris 1, merge selebar tabel, center bold) ---
    _merge_dan_isi(ws, 1, 1, 1, n_cols, judul, F_TITLE)
    ws.row_dimensions[1].height = 20

    # --- grid merge: sel kosong diserap ke sel berisi terdekat (kiri dulu, lalu atas) ---
    pemilik = {}  # (ri, ci) -> (r0, c0, r1, c1) blok yang menaunginya
    for ri in range(n_hdr):
        for ci in range(n_cols):
            if (ri, ci) in pemilik:
                continue
            if hdr[ri][ci]:
                r1, c1 = ri, ci
                # serap sel kosong di bawah (rowspan), satu kolom saja dulu
                while r1 + 1 < n_hdr and not hdr[r1 + 1][ci] and (r1 + 1, ci) not in pemilik:
                    r1 += 1
                # serap sel kosong di kanan (colspan) pada rentang baris blok
                while c1 + 1 < n_cols and all(
                        not hdr[r][c1 + 1] and (r, c1 + 1) not in pemilik
                        for r in range(ri, r1 + 1)):
                    c1 += 1
                for r in range(ri, r1 + 1):
                    for c in range(ci, c1 + 1):
                        pemilik[(r, c)] = (ri, ci, r1, c1)

    # tulis header + merge
    ditulis = set()
    for (ri, ci), (r0, c0, r1, c1) in sorted(pemilik.items()):
        if (r0, c0) in ditulis:
            continue
        ditulis.add((r0, c0))
        _merge_dan_isi(ws, r0 + 2, c0 + 1, r1 + 2, c1 + 1, hdr[r0][c0], F_HDR)
    # sel yang tidak tertutup (seharusnya tidak ada) -> tetap diberi border
    for ri in range(n_hdr):
        for ci in range(n_cols):
            if (ri, ci) not in pemilik:
                _merge_dan_isi(ws, ri + 2, ci + 1, ri + 2, ci + 1, "", F_HDR)

    # --- baris contoh: placeholder "-" di tiap kolom ---
    r_contoh = n_hdr + 2
    for c in range(n_cols):
        cell = ws.cell(row=r_contoh, column=c + 1, value="-")
        cell.font = F_BODY
        cell.alignment = CENTER
        cell.border = GRID

    # --- lebar kolom dari header terpanjang ---
    for c in range(n_cols):
        kandidat = [len(str(hdr[r][c])) for r in range(n_hdr)]
        lebar = min(max(kandidat) * 1.05 + 2, 50)
        ws.column_dimensions[get_column_letter(c + 1)].width = max(lebar, 8)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)


def main():
    d = ekstrak()
    baris = []

    for r in d["led_rows"]:
        baris.append({
            "path": os.path.join(DIR_XLSX, "LED", nama_berkas(f"LED-Tabel {r['nomor']}", r["judul_raw"])),
            "dokumen": "LED", "nomor": r["nomor"], "judul": r["judul"],
            "hdr_rows": r["hdr_rows"], "example": r["example"],
        })

    for r in d["lkps_rows"]:
        baris.append({
            "path": os.path.join(DIR_XLSX, "LKPS", nama_berkas(f"LKPS-Tabel {r['nomor']}", r["judul_raw"])),
            "dokumen": "LKPS", "nomor": r["nomor"], "judul": r["judul"],
            "hdr_rows": r["hdr_rows"], "example": r["example"],
        })

    for t in d["lkps_tanpa_nomor"]:
        judul = "Daftar Program Studi di UPPS (tabel tanpa nomor)"
        baris.append({
            "path": os.path.join(DIR_XLSX, "LKPS", nama_berkas("LKPS-Tabel Tanpa Nomor", judul)),
            "dokumen": "LKPS", "nomor": "Tanpa nomor", "judul": judul,
            "hdr_rows": t["hdr_rows"], "example": t["example"],
        })

    tanpa_header = []
    for b in baris:
        if not b["hdr_rows"] or all(not any(str(c or "").strip() for c in r) for r in b["hdr_rows"]):
            tanpa_header.append(b["nomor"])
            b["hdr_rows"] = [["-"]]
        try:
            tulis_xlsx(b["path"], b["judul"], b["hdr_rows"], b["example"])
        except PermissionError:
            print(f"SKIP (terbuka di Excel): {os.path.basename(b['path'])}")

    n_led = len(d["led_rows"])
    print(f"xlsx ditulis: LED={n_led} | LKPS={len(baris) - n_led} | total={len(baris)}")
    print("Tanpa header terdeteksi:", ", ".join(tanpa_header) if tanpa_header else "tidak ada")
    print("folder:", DIR_XLSX)
    return baris


if __name__ == "__main__":
    main()
