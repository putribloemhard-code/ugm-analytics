# Berita Dampak — Analisis Dampak Berita UGM

Identifikasi dan pemetaan berita dampak UGM pada 4 topik:
**rehabilitasi lingkungan, kewirausahaan, kunjungan akademik, kolaborasi riset**.

## Isi folder

| File / folder | Isi |
|---|---|
| `data/ugm_news.duckdb` | Database utama (tabel: sitemap, berita, berita_topik, berita_kepmen_all, berita_sdg_all, ringkasan_* ) |
| `scripts/backfill_sitemap.py` | Ambil daftar URL berita dari sitemap ugm.ac.id |
| `scripts/ingest.py` | Ambil berita terbaru dari RSS (id + en) |
| `scripts/fetch_detail.py` | Filter URL relevan + ambil detail halaman (judul, deskripsi, tanggal) |
| `scripts/normalisasi.py` | Bersihkan teks + tanggal, dedup |
| `scripts/keywords.py` | Kamus kata kunci 4 topik inti dampak |
| `scripts/kepmen_sdg.py` | Pemetaan 14 tema → pilar → Topik Resmi Kepmen 361/M/KEP/2025 → klaster SDGs (dari UGM Analytics.xlsx) |
| `scripts/process_nlp.py` | Tagging 4 topik inti + ringkasan per tahun |
| `scripts/tag_kepmen_all.py` | **Utama**: tagging SEMUA berita ke 14 tema Kepmen + SDG (tabel berita_kepmen_all, berita_sdg_all, ringkasan_pilar, ringkasan_sdg_all) |
| `scripts/tag_kepmen_berita.py` | Legacy: tagging 4 topik inti saja (tabel berita_kepmen, berita_sdg) |
| `scripts/tag_kepmen_lengkap.py` | Legacy: eksplorasi 9 tema Kepmen lain (tabel berita_kepmen_lengkap) |
| `scripts/laporan_static.py` | Cetak `laporan_berita_dampak.html` (11 chart + tabel 14 tema, JS inline) |
| `scripts/update_mingguan.py` | Update berkala: jalankan pipeline lengkap (sitemap → RSS → fetch → normalisasi → tagging → laporan) |
| `scripts/ocr_kepmen.py` | OCR PDF Kepmen 361 (scan) → `../docs/kepmen_361_ocr.txt` |
| `dashboard_berita_dampak.py` | Dashboard Streamlit interaktif (filter sidebar: tahun, 14 tema, sumber, pilar) |
| `laporan_berita_dampak.html` | Laporan statis — buka di browser, render tanpa internet |
| `DASHBOARD.md` | Penjelasan isi dashboard + cara membaca hasil |
| `PIPELINE.md` | Dokumentasi alur + perintah run |

## Mengubah tampilan dashboard

File yang diubah: `dashboard_berita_dampak.py` (buka di VS Code). Setelah edit,
simpan lalu restart: tekan Ctrl+C di terminal streamlit, jalankan lagi:

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\streamlit run dashboard_berita_dampak.py
```

Peta baris (cek dengan Ctrl+G di VS Code):

| Baris | Mengubah apa |
|---|---|
| 56–58 | Judul halaman, judul besar, caption sumber |
| 111–140 | Sidebar filter (tahun, topik, sumber, pilar) — label + default pilihan |
| 144–165 | Bagian Ringkasan (angka statistik) |
| 167–178 | Chart distribusi per topik |
| 181–295 | Peta Kepmen & SDGs + tabel indikator |
| 296–357 | Expander eksplorasi tema Kepmen lain |
| 359–378 | Heatmap topik × tahun |
| 380–390 | Tren tahunan per topik |
| 393–404 | Tren bulanan (musiman) |
| 407–423 | Cakupan vs total berita UGM |
| 432–458 | Keyword pemicu match per topik |
| 460–470 | Berita multi-topik |
| 485–501 | Word frequency per topik |
| 504–558 | Daftar berita (tabel) |
| 559+ | Expander berita tanpa match (cek manual) |

Tips umum:
- Warna chart diatur per-`fig` (argumen `color_discrete_sequence` / `marker_color`
  di tiap bagian) — cari `px.` di baris itu.
- Teks/emoji label tinggal ganti string di `st.title`, `st.subheader`, `st.caption`.
- `width="stretch"` di `st.plotly_chart` membuat chart selebar layar; ganti ke
  angka tetap (mis. `width=800`) kalau mau sempit.
- Urutan bagian = urutan baris di file. Mau pindah/ hapus bagian, potong blok
  `st.subheader(...)` sampai `st.plotly_chart(...)`-nya.

Laporan statis `laporan_berita_dampak.html` dihasilkan dari `scripts/laporan_static.py`
— isi chart-nya diset di situ, bukan di file HTML (file HTML jangan diedit manual,
nanti tertimpa saat regenerate).

## Menjalankan dashboard

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\streamlit run dashboard_berita_dampak.py
```

## Menjalankan laporan statis

```bash
..\venv\Scripts\python.exe scripts\laporan_static.py
```

Lalu buka `laporan_berita_dampak.html`. Laporan memakai plotly.js yang di-embed,
jadi chart tetap tampil walau offline.

## Update data berkala

Data diambil dari ugm.ac.id (RSS + sitemap). Dua cara update:

1. **Tombol di dashboard** — sidebar → "🔄 Update Berita Terbaru". Menjalankan
   seluruh pipeline (sitemap → RSS → fetch detail baru → normalisasi → tagging
   → laporan), lalu dashboard reload sendiri. Butuh internet + beberapa menit.
2. **Cron mingguan** — otomatis setiap Sabtu 06:00 (job Hermes `update_berita_dampak.sh`
   → `scripts/update_mingguan.sh` → `scripts/update_mingguan.py`). Jalankan
   manual kapan saja:
   ```bash
   ..\venv\Scripts\python.exe scripts\update_mingguan.py
   ```

Update bersifat incremental: URL yang sudah ada di tabel `berita` di-skip
(INSERT OR IGNORE), jadi hanya berita baru yang di-fetch. Log: `logs_update.txt`.

## Sumber data

- RSS: `https://ugm.ac.id/id/feed/` dan `https://ugm.ac.id/en/feed/`
- Sitemap: `https://ugm.ac.id/wp-sitemap.xml` (~32.000 URL berita, 2007–2026)
- REST API wp-json diblokir (401) — tidak dipakai.
- Pemetaan Kepmen & SDG: `../sumber/UGM Analytics.xlsx` (sheet "Konten UGM Berdampak"
  & "#Ref"); dokumen resmi: `../sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf`
  dan `../sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf`.

Detail alur lengkap: lihat `PIPELINE.md`. Detail isi dashboard: lihat `DASHBOARD.md`.
