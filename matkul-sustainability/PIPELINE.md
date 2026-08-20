# Pipeline: Mata Kuliah Terkait Sustainability (Kepmen 361/M/KEP/2025)

## Cara Processing

### 1. Scrape/kumpulkan deskripsi tiap mata kuliah
- Sumber: eLOK UGM (https://elok.ugm.ac.id), index course publik (guest access).
- Script: `scripts/scrape_elok.py` → `data/elok_matkul_mentah.csv`
  - Walk: halaman kategori (Fakultas/Sekolah) → subkategori (Program) → kartu course.
  - Kolom: `judul_course`, `deskripsi` (ringkasan kartu, sering terpotong "..."), `fakultas`, `program`.
- Catatan: 41% deskripsi kosong dan 51% terpotong karena eLOK hanya menampilkan
  ringkasan kartu untuk guest. Full summary ada di halaman `course/view.php?id=X`
  tetapi perlu course_id (belum disimpan scraper). Untuk meningkatkan cakupan,
  langkah lanjutan: simpan course_id di scraper, lalu scrape full summary per course.

### 2. Normalisasi
- Script: `scripts/normalize_matkul.py` → `data/elok_matkul_bersih.csv`
  - Hapus penanda kelas/dosen dari judul: "Kelas A", kode matkul (BISB211525),
    kode dalam kurung (BIA 10001), nama dosen setelah `_`/`-`.
  - Dedup course sama (nama_normal + fakultas + program), ambil deskripsi terpanjang.
  - Hasil: 388 → 382 baris.

### 3. Keyword matching ke topik resmi Kepmen
- Script: `scripts/tag_kepmen_matkul.py` → `data/elok_matkul_kepmen.csv`
- 9 topik resmi (Dampak Lingkungan, Tema 5 — Pendidikan dan Penelitian):
  1. Pembangunan Berkelanjutan
  2. Perubahan Iklim
  3. Energi Terbarukan
  4. Pengelolaan Limbah
  5. Ekonomi Sirkular
  6. Konservasi Lingkungan
  7. Keanekaragaman Hayati
  8. Rehabilitasi/Restorasi Lingkungan
  9. Pengelolaan Sumber Daya Alam
- Metode: substring matching (case-insensitive) keyword Indonesia + Inggris ke
  judul + deskripsi. Token pendek berisiko (mis. "sda") pakai word boundary regex.
- Matkul match ≥ 1 topik → `terkait_sustainability = True`.
- Ringkasan tersimpan: `ringkasan_fakultas.csv`, `ringkasan_prodi.csv`,
  `ringkasan_topik.csv`, `ringkasan_tahun.csv`.

### 4. Output
- Dashboard interaktif: `dashboard_matkul_kepmen.py` (Streamlit)
  - Bar chart jumlah matkul terkait sustainability per fakultas.
  - Tabel drill-down per prodi (pilih fakultas → daftar matkul + topik).
  - Tren per tahun (tahun diekstrak dari judul — indikasi kasar).
  - Sebaran per topik + daftar matkul yang tidak match (cek manual).
- Laporan statis: `scripts/laporan_static.py` → `laporan_matkul_kepmen.html`
  (buka langsung di browser, tanpa server).

## Hasil (sampel eLOK, 382 matkul bersih)
- 23 matkul terkait sustainability (6.0%).
- Top fakultas: Kehutanan (10 dari 17, 58.8%), Kedokteran Hewan (4, 22.2%).
- Top topik: Keanekaragaman Hayati (10), Pengelolaan SDA (10), Pengelolaan Limbah (3).
- Tren: hanya 98/382 judul mengandung tahun → chart tren indikatif, bukan resmi.

## Menjalankan ulang (offline, tanpa scrape)
```
../venv/Scripts/python.exe scripts/normalize_matkul.py
../venv/Scripts/python.exe scripts/tag_kepmen_matkul.py
../venv/Scripts/python.exe scripts/laporan_static.py
```

## Caveat
- Sample bias: hanya course yang di-publish dosen di eLOK.
- Deskripsi kosong/terpotong → angka lower-bound.
- Data eLOK kadang salah pasang deskripsi antar course (mis. "Pekerti" berisi
  deskripsi perikanan) → false positive, cek daftar manual di dashboard.
