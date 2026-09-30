# Excel Daftar Tabel LED & LKPS — Prodi S2 MEI

Satu file `.xlsx` per tabel, berisi **nama tabel dan header kolomnya** (bukan isi data).
Total **80 file**:

- `LED/` — 42 file, sesuai DAFTAR TABEL resmi LED (hal. cetak xi–xii)
- `LKPS/` — 38 file: 37 tabel bernomor + 1 tabel tanpa nomor (daftar program studi, hal. PDF 2)

## Penamaan berkas

```
LED-Tabel <nomor> - <nama tabel>.xlsx        contoh: LED-Tabel C1.1 - Indikator sistem ....xlsx
LKPS-Tabel <nomor> - <nama tabel>.xlsx       contoh: LKPS-Tabel 2.A.1 - Data Mahasiswa ....xlsx
```

Judul pada nama berkas dipotong maks. 60 karakter (dipotong di batas kata); nama lengkap
tetap ada di sel "Nama tabel" di dalam file.

## Isi tiap file

Sheet `Tabel`: identitas (dokumen, nomor, nama tabel, halaman cetak/PDF, jumlah kolom),
baris nomor kolom, dan daftar header kolom (1 kolom tabel = 1 sel, dibaca mendatar).
Sel header kosong di PDF asli ditulis `-`.

## Regenerasi

```bash
./venv/Scripts/python.exe akreditasi/scripts/generate_xlsx_tabel_led_lkps.py
```

Sumber kebenaran = modul `akreditasi/scripts/daftar_tabel_led_lkps.py` yang juga dipakai
menulis `../Daftar_Tabel_LED_dan_LKPS_MEI.md` — nomor, judul, halaman, dan header di xlsx
dijamin sama dengan dokumen Markdown itu. Sumber mentah:
`akreditasi/docs/sumber/{LED,LKPS}_Prodi_S2_Elektronika_dan_Instrumentasi.pdf`.

## Catatan ekstraksi (ringkas)

- Header LKPS/LED digabung dari baris header bertingkat (merged cells) hasil deteksi tabel
  pymupdf; baris spanduk "Roadmap ..." dan baris berisi angka tidak dihitung header.
- Nomor tabel LED dicari dari caption bernomor di badan dokumen; rujukan silang di prosa
  dibedakan dari caption asli lewat kecocokan teks sesudahnya dengan judul DAFTAR TABEL.
- Nomor 2.A.5 dan 2.A.6 memang tidak ada di LKPS; PDF menulis "Tabel 2.A..7" (titik ganda)
  yang dinormalkan menjadi 2.A.7. Detail lengkap: `../Daftar_Tabel_LED_dan_LKPS_MEI.md` §B.2.
