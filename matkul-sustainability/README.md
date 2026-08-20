# matkul-sustainability

Analisis mata kuliah UGM terkait sustainability berdasarkan topik resmi
Kepmen 361/M/KEP/2025 (Dampak Lingkungan, Tema 5 — Pendidikan dan Penelitian).
Sumber data: eLOK UGM (https://elok.ugm.ac.id).

## Isi folder

```
matkul-sustainability/
├── dashboard_matkul_kepmen.py   # Dashboard interaktif (Streamlit) — OUTPUT UTAMA
├── laporan_matkul_kepmen.html   # Laporan statis, buka langsung di browser (offline)
├── PIPELINE.md                  # Dokumentasi cara processing + hasil + caveat
├── data/
│   ├── elok_matkul_mentah.csv    # 388 baris hasil scrape eLOK
│   ├── elok_matkul_bersih.csv    # 382 baris setelah normalisasi + dedup
│   ├── elok_matkul_kepmen.csv    # Hasil tagging: topik per matkul, flag sustainability
│   ├── ringkasan_fakultas.csv    # Agregat per fakultas
│   ├── ringkasan_prodi.csv       # Agregat per prodi (drill-down)
│   ├── ringkasan_topik.csv       # Agregat per topik Kepmen
│   └── ringkasan_tahun.csv       # Agregat per tahun (indikatif, dari judul)
└── scripts/
    ├── scrape_elok.py            # Scrape eLOK (butuh network) → mentah.csv
    ├── normalize_matkul.py       # Normalisasi judul + dedup → bersih.csv
    ├── tag_kepmen_matkul.py      # Keyword matching 9 topik Kepmen → kepmen.csv
    └── laporan_static.py         # Generate laporan_matkul_kepmen.html
```

## Cara menjalankan (dari folder ini, pakai venv proyek)

```bash
# Dashboard interaktif
../venv/Scripts/python.exe -m streamlit run dashboard_matkul_kepmen.py

# Regenerate laporan HTML statis
../venv/Scripts/python.exe scripts/laporan_static.py

# Ulang pipeline dari awal (offline, tanpa scrape ulang)
../venv/Scripts/python.exe scripts/normalize_matkul.py
../venv/Scripts/python.exe scripts/tag_kepmen_matkul.py
../venv/Scripts/python.exe scripts/laporan_static.py

# Scrape ulang eLOK (butuh akses network ke elok.ugm.ac.id)
../venv/Scripts/python.exe scripts/scrape_elok.py
```

## Hasil (sampel eLOK)

- 382 matkul bersih; 23 terkait sustainability (6.0%).
- Top fakultas: Kehutanan 10/17 (58.8%), Kedokteran Hewan 4/18 (22.2%), Biologi 4/78 (5.1%).
- Top topik: Keanekaragaman Hayati (10), Pengelolaan SDA (10), Pengelolaan Limbah (3).

## Catatan

- Data adalah SAMPLE (hanya course yang dipublish dosen di eLOK), bukan data resmi UGM.
- 41% deskripsi kosong + sebagian terpotong → hasil lower-bound.
- Untuk cakupan lebih baik: simpan course_id di scraper lalu scrape full summary
  dari halaman course/view.php?id=X (lihat PIPELINE.md).
