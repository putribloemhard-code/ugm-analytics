# -*- coding: utf-8 -*-
"""Menulis akreditasi/docs/Daftar_Tabel_LED_dan_LKPS_MEI.md dari modul ekstraksi."""
import sys

sys.path.insert(0, "D:/ugm-analytics/akreditasi/scripts")
from daftar_tabel_led_lkps import MD, SEP, LKPS_TANPA_NOMOR_PAGE, ekstrak

d = ekstrak()

L = []
A = L.append
A("# Daftar Tabel — LED dan LKPS")
A("")
A("Program Studi Magister (S2) Elektronika dan Instrumentasi (MEI), Departemen Ilmu Komputer")
A("dan Elektronika, FMIPA UGM.")
A("")
A("Sumber (di repo, `akreditasi/docs/sumber/`):")
A("")
A("- `LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf` — 168 halaman")
A("- `LKPS_Prodi_S2_Elektronika_dan_Instrumentasi.pdf` — 106 halaman")
A("")
A("Nomor halaman di dokumen ini = halaman PDF (halaman 1 = lembar pertama berkas), bukan")
A("nomor halaman tercetak. LED memakai angka romawi di bagian depan sehingga nomor cetak")
A("bergeser dari nomor PDF.")
A("")
A("---")
A("")
A("## BAGIAN A — LED (Laporan Evaluasi Diri)")
A("")
A(f"### A.1 Daftar tabel resmi menurut DAFTAR TABEL dokumen (hal. cetak xi–xii) — {len(d['led_toc'])} tabel")
A("")
A("Badan LED tidak menaruh caption bernomor di atas tiap tabel; penomoran resminya hanya ada")
A("di DAFTAR TABEL. Daftar berikut = daftar resmi tersebut (halaman = nomor cetak, seperti")
A("tertulis di dokumen).")
A("")
A("| Nomor | Judul | Hal. cetak |")
A("|---|---|---|")
for k, title, hal in d["led_toc"]:
    A(f"| {k} | {title} | {hal} |")
A("")
total_blok = sum(len(p) for p in d["led_pages"])
A(f"### A.2 Blok tabel terdeteksi di badan LED — {total_blok} blok ({len(d['led_sig'])} ragam kolom, {d['led_tanpa_header']} blok tanpa header dikenali)")
A("")
A("Tabel LED umumnya matriks IKU/IKT: Referensi × Indikator × Sasaran/Target × Capaian Kinerja.")
A("Blok di bawah hasil deteksi geometris (pymupdf `find_tables`), jadi jumlahnya tidak sama")
A("dengan 42 tabel resmi: satu tabel resmi bisa terpecah antar halaman, dan blok tanpa header")
A("dikenali (halaman tanda tangan, pecahan baris) dipisahkan. Nama kolom dirapikan ke kosakata")
A("kolom; teks indikator yang bocor ke baris header dibuang.")
A("")
A("| Kolom (kanonik) | Jumlah blok | Halaman PDF |")
A("|---|---|---|")
for hdr, pages in sorted(d["led_sig"].items(), key=lambda kv: -len(kv[1])):
    A(f"| {SEP.join(hdr)} | {len(pages)} | {', '.join(str(p) for p in sorted(set(pages)))} |")
A("")
A("---")
A("")
A(f"## BAGIAN B — LKPS (Laporan Kinerja Program Studi) — {len(d['lkps_rows'])} tabel bernomor + 1 tabel tanpa nomor")
A("")
A("| Nomor | Judul | Hal. PDF | Header kolom (digabung) |")
A("|---|---|---|---|")
for r in d["lkps_rows"]:
    A(f"| {r['nomor']} | {r['judul']} | {r['hal']} | {SEP.join(r['header'])} |")
A("")
A("### B.1 Tabel tanpa nomor (halaman 2 LKPS)")
A("")
A("Tabel daftar program studi di UPPS: tanpa nomor tabel, muncul langsung di awal dokumen.")
A("")
for t in d["lkps_tanpa_nomor"]:
    A(f"- Hal. PDF {LKPS_TANPA_NOMOR_PAGE + 1} ({t['nbaris']} baris): {SEP.join(t['header'])}")
A("")
A("### B.2 Catatan ekstraksi")
A("")
A("- Nomor tabel LKPS diambil dari caption di badan dokumen (`Tabel 2.A.4 …`); header dipasangkan")
A("  ke blok tabel pertama yang berada di bawah caption tersebut.")
A("- Nomor 2.A.5 dan 2.A.6 tidak ada di seluruh berkas (dicek: nol kemunculan).")
A("- PDF menulis satu caption dengan titik ganda (\"Tabel 2.A..7\"); di dokumen ini dinormalkan")
A("  menjadi 2.A.7.")
A("- Sel header yang benar-benar kosong ditulis \"-\"; baris header ditentukan oleh pendeteksi")
A("  tabel pymupdf, dengan cadangan heuristik bila pendeteksi gagal.")
A("")

with open(MD, "w", encoding="utf-8") as f:
    f.write("\n".join(L))

print("ditulis:", MD)
print(f"LED resmi={len(d['led_toc'])} | blok LED={total_blok} ragam={len(d['led_sig'])}"
      f" tanpa_header={d['led_tanpa_header']} | LKPS bernomor={len(d['lkps_rows'])}")
