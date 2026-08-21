# UGM Impact Analytics

Analisis dampak UGM berdasarkan Kepmendikti Saintek **361/M/KEP/2025**
(Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi) dan
klaster **SDGs** — berbasis data publik yang bisa diambil offline.

## Subproyek

| Subproyek | Fokus | Status |
|---|---|---|
| `berita-dampak/` | Analisis berita dampak ugm.ac.id (14 tema Kepmen, 3 pilar, SDG) | **Aktif** — pipeline + dashboard + laporan + update mingguan |
| `matkul-sustainability/` | Mata kuliah terkait sustainability per fakultas/prodi | Selesai (2026-08-12) |
| `kkn-desa-binaan/` | Sebaran KKN & desa binaan (data dari eLOK — belum ada) | Kosong, butuh akses eLOK |
| `mahasiswa-afirmasi/` | Analisis kelompok afirmasi (data sensitif — belum ada) | Kosong, butuh akses resmi |

## Mulai cepat (berita-dampak)

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\streamlit run dashboard_berita_dampak.py     # buka http://localhost:8766
..\venv\Scripts\python.exe scripts\laporan_static.py          # regenerate laporan HTML
..\venv\Scripts\python.exe scripts\update_mingguan.py         # update data dari ugm.ac.id
```

Dashboard: http://localhost:8766 (LAN: http://10.73.0.218:8766).
Laporan statis (tanpa server): `berita-dampak/laporan_berita_dampak.html`.

## Dokumentasi

- `docs/PERENCANAAN.md` — tujuan, backlog ide, milestone, status per subproyek
- `docs/FRAMEWORK.md` — arsitektur, pipeline, konvensi, struktur folder, stack
- `docs/OUTPUT.md` — output yang dihasilkan (dashboard, laporan, tabel DB, angka)
- `berita-dampak/README.md` — peta file subproyek berita-dampak
- `berita-dampak/PIPELINE.md` — alur processing + perintah run
- `berita-dampak/DASHBOARD.md` — isi dashboard + cara membaca
- `matkul-sustainability/README.md` + `PIPELINE.md` + `DASHBOARD.md` — subproyek matkul

## Referensi resmi (folder `sumber/`)

- `sumber/UGM Analytics.xlsx` — template resmi pengumpulan data Kepmen 361
  (sheet "Konten UGM Berdampak" = 7 baris template; sheet "#Ref" = pemetaan
  Dampak → Topik Kepmen → SDGs). SUMBER KEBENARAN mapping topik→Kepmen→SDG.
- `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` — Kepmen asli (scan;
  OCR: `docs/kepmen_361_ocr.txt`)
- `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf` — 12 IKU (14 tema sama dgn Kepmen; jangan campur hitungan: 12 IKU ≠ 14 tema)

## Lingkungan

- Python venv: `venv/` (pandas, plotly, streamlit, requests, bs4, duckdb,
  openpyxl, pymupdf, rapidocr-onnxruntime). Bukan matplotlib/kaleido —
  output statis pakai plotly `write_html`.
- OS: Windows; terminal pakai git-bash (MSYS).
