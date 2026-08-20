# Dashboard: Mata Kuliah Terkait Sustainability (Kepmen)

File: `dashboard_matkul_kepmen.py` — dijalankan dengan Streamlit:

```bash
../venv/Scripts/python.exe -m streamlit run dashboard_matkul_kepmen.py
```

Sumber data: `data/elok_matkul_kepmen.csv` + 4 CSV ringkasan
(`ringkasan_fakultas.csv`, `ringkasan_prodi.csv`, `ringkasan_topik.csv`,
`ringkasan_tahun.csv`). Data dimuat dengan cache Streamlit (`@st.cache_data`),
jadi perubahan CSV di disk perlu re-run app.

## Isi Dashboard

### Sidebar: Filter
- Multi-select Fakultas (kosong = semua). Semua chart dan tabel ikut terfilter.
- Menampilkan jumlah fakultas yang sedang dipilih.

### Peringatan
- Data adalah SAMPLE eLOK, bukan data resmi UGM (hanya course yang dipublish
  dosen di eLOK). 41% deskripsi kosong/terpotong → angka lower-bound.

### Metrik (4 kartu)
1. Mata kuliah (tampil) — jumlah matkul setelah dedup sesuai filter.
2. Terkait sustainability — jumlah matkul yang match ≥ 1 topik.
3. Cakupan — persentase terkait sustainability.
4. Fakultas dengan match > 0.

### Bagian 1 — Bar Chart Semua Fakultas
- Horizontal bar, menampilkan SEMUA fakultas terpilih (termasuk yang 0).
- Warna gradasi hijau = persentase matkul terkait (0–100%).
- Label di luar bar: jumlah dan persentase, mis. `10 (58.8%)`.

### Bagian 2 — Treemap: Fakultas → Prodi → Mata Kuliah
- Peta hierarki interaktif dari matkul yang terkait sustainability.
- Level: Semua Fakultas → Fakultas → Program → Nama mata kuliah.
- Warna per fakultas; hover menampilkan topik yang match.
- Klik blok untuk zoom ke level dalam.

### Bagian 3 — Heatmap: Topik Kepmen × Fakultas
- Matriks jumlah matkul per kombinasi topik × fakultas.
- Hanya fakultas yang punya match > 0 (baris/kolom nol dihilangkan).
- Angka tampil di tiap sel; skala warna hijau.

### Bagian 4 — Donut Sebaran per Topik
- Proporsi jumlah matkul per 9 topik resmi Kepmen.

### Bagian 5 — Tren per Tahun (Stacked per Fakultas)
- Bar per tahun, warna per fakultas (stacked).
- Tahun diekstrak dari JUDUL matkul (mis. "Gasal 2024/2025") — hanya
  98/382 judul punya tahun, jadi ini indikasi kasar, bukan data multi-tahun resmi.

### Bagian 6 — Drill-down Mata Kuliah per Prodi
- Selectbox fakultas (default "— Semua Fakultas —").
- Tabel daftar matkul terkait: fakultas, program, nama matkul, topik, tahun.
- Expander: ringkasan semua prodi (fakultas × program) sesuai filter.
- Expander: daftar matkul yang TIDAK match (cek manual) — penyebab utama
  tidak match: deskripsi kosong/terpotong.

## Alur Data

```
elok_matkul_mentah.csv  (388)  scrape_elok.py
        │
        ▼
elok_matkul_bersih.csv  (382)  normalize_matkul.py — normalisasi judul + dedup
        │
        ▼
elok_matkul_kepmen.csv  (382)  tag_kepmen_matkul.py — keyword matching 9 topik
        │
        ├── ringkasan_fakultas.csv
        ├── ringkasan_prodi.csv
        ├── ringkasan_topik.csv
        └── ringkasan_tahun.csv
```

## 9 Topik Resmi (keyword matching)

1. Pembangunan Berkelanjutan
2. Perubahan Iklim
3. Energi Terbarukan
4. Pengelolaan Limbah
5. Ekonomi Sirkular
6. Konservasi Lingkungan
7. Keanekaragaman Hayati
8. Rehabilitasi/Restorasi Lingkungan
9. Pengelolaan Sumber Daya Alam

Keyword Indonesia + Inggris (substring, case-insensitive) dicocokkan ke
judul + deskripsi; token pendek berisiko (mis. "sda") pakai word boundary.

## Cara Membaca Hasil

- Angka 6.0% cakupan artinya: dari sampel eLOK, hanya 23 dari 382 matkul yang
  judul/deskripsinya mengandung kata kunci topik Kepmen. Ini LOWER BOUND —
  banyak matkul relevan tidak terdeteksi karena deskripsi kosong.
- Fakultas dengan 0 bukan berarti tidak punya matkul sustainability, melainkan
  sampelnya tidak terdeteksi (deskripsi kosong/terpotong, atau course tidak
  dipublish di eLOK).
- False positive mungkin terjadi karena data eLOK kadang salah pasang deskripsi
  antar course — cek daftar manual di bagian 6.
