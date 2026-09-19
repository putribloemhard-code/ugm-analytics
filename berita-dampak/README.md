# Berita Dampak — Analisis Dampak Berita UGM

Identifikasi dan pemetaan berita dampak UGM pada **14 tema resmi Kepmen
361/M/KEP/2025** (3 pilar: Lingkungan/Ekonomi/Sosial) + klaster **SDGs**, plus
lapisan independen **44 fakultas/sekolah/unit kerja UGM**. Empat tema awal
(rehabilitasi lingkungan, kewirausahaan, kunjungan akademik, kolaborasi riset)
tetap ada sebagai bagian dari 14 tema itu.

## Isi folder

Database: **MySQL** (bukan DuckDB lagi — migrasi penuh selesai; lihat
"Penyimpanan data" di bawah). Semua tabel berprefix `berita_` (mis.
`berita_sitemap`, `berita_berita`, `berita_berita_kepmen_all`, `berita_ringkasan_*`).

| File / folder | Isi |
|---|---|
| `scripts/db.py` | Koneksi MySQL bersama (engine, retry, upsert) dipakai semua script pipeline |
| `scripts/backfill_sitemap.py` | Ambil daftar URL berita dari sitemap ugm.ac.id → `berita_sitemap` |
| `scripts/ingest.py` | Ambil berita terbaru dari RSS (id + en) → `berita_berita` |
| `scripts/fetch_detail.py` | Filter URL relevan + ambil detail halaman (judul, deskripsi, tanggal) → `berita_berita` |
| `scripts/normalisasi.py` | Bersihkan teks + tanggal, dedup (dalam satu transaksi MySQL) |
| `scripts/keywords.py` | Kamus kata kunci 4 topik inti dampak |
| `scripts/kepmen_sdg.py` | Pemetaan 14 tema → pilar → Topik Resmi Kepmen 361/M/KEP/2025 → klaster SDGs (dari UGM Analytics.xlsx) |
| `scripts/process_nlp.py` | Tagging 4 topik inti + ringkasan per tahun |
| `scripts/tag_kepmen_all.py` | **Utama**: tagging SEMUA berita ke 14 tema Kepmen + SDG (tabel berita_kepmen_all, berita_sdg_all, ringkasan_pilar, ringkasan_sdg_all) |
| `scripts/tag_sdg_langsung.py` | Mode "SDGs saja": mapping langsung seluruh sitemap → 17 SDG |
| `scripts/tag_unit_kerja.py` | Tagging 44 fakultas/sekolah/unit kerja UGM → `berita_unit_kerja` (lapisan independen dari Kepmen/SDG) |
| `scripts/unit_kerja.py` | Daftar resmi 44 fakultas/sekolah/unit kerja + guard leakage lintas-universitas |
| `scripts/fetch_backlog.py` | **Sumber tunggal ekstraksi isi lengkap** (`fetch_full()`, `clean_url()`, `ensure_fetch_columns()`) + backfill besar seluruh sitemap (manual/background, lock sendiri) |
| `scripts/backfill_deskripsi.py` | Isi ulang deskripsi berita sitemap yang kosong (fallback og:description) |
| `scripts/generate_narasi_llm.py` | Rangkai narasi ringkasan/insight via OpenAI API, cache ke `berita_narasi_cache` (opsional; skip aman ke narasi template kalau key kosong) |
| `scripts/laporan_static.py` | Cetak `laporan_berita_dampak.html` (11 chart + tabel 14 tema, JS inline) |
| `scripts/update_mingguan.py` | Update berkala: jalankan pipeline lengkap (sitemap → RSS → fetch → normalisasi → tagging → narasi → laporan) |
| `scripts/count_berita.py` | Helper kecil: cetak jumlah baris `berita_berita` (dipakai `update_mingguan.sh`) |
| `scripts/ocr_kepmen.py` | OCR PDF Kepmen 361 (scan) → `docs/kepmen_361_ocr.txt` |
| `dashboard_berita_dampak.py` | Dashboard Streamlit interaktif (filter sidebar: tahun, 14 tema, sumber, pilar) |
| `laporan_berita_dampak.html` | Laporan statis — buka di browser, render tanpa internet |
| `DASHBOARD.md` | Penjelasan isi dashboard + cara membaca hasil |
| `PIPELINE.md` | Dokumentasi alur + perintah run |

`tag_kepmen_berita.py` dan `tag_kepmen_lengkap.py` (legacy, sudah digantikan
`tag_kepmen_all.py` sejak 2026-08-20) serta `sync_mysql.py` (sinkronisasi
DuckDB→MySQL, sudah tidak relevan setelah migrasi penuh) sudah **dihapus** dari
folder ini.

## Struktur dashboard (multipage sejak 2026-09-06)

`dashboard_berita_dampak.py` sekarang hanya **shell navigasi** (78 baris). Isi tiap
halaman dipisah supaya tiap file kecil dan mudah diedit:

| Halaman | File | Isi |
|---|---|---|
| Beranda | `pages_app/beranda.py` | ringkasan lintas halaman + kartu shortcut |
| Dampak | `pages_app/dampak_saja.py` → `page_dampak.py` | mode "Berdampak" (pilar + 14 tema) |
| Dampak × SDGs | `pages_app/dampak_sdgs.py` → `page_dampak.py` | mode penuh (pilar + tema + klaster SDG) |
| SDGs | `pages_app/sdgs.py` → `page_sdgs.py` | mode "SDGs saja" (17 SDG, tanpa tema) |
| Akreditasi | `pages_app/akreditasi.py` → `page_akreditasi.py` | kelengkapan LED/LKPS + upload |
| Admin | `pages_app/admin.py` → `page_admin.py` | status data/update |
| Profil | `pages_app/profil.py` → `page_profil.py` | info proyek |

File pendukung: `common.py` (header/style/tema), `data_loader.py` (load data bersama),
`pencarian.py` (pencarian bebas → rute + filter), `laporan_word.py` (ekspor .docx).
`page_dampak.py` adalah file terbesar (~1.460 baris) — di dalamnya urutan bagian
mengikuti urutan blok `st.subheader(...)`.

**Mengubah tampilan:** buka file halaman yang relevan di VS Code, simpan, lalu
restart Streamlit (Ctrl+C di terminal, jalankan ulang perintah di bawah).

Tips umum:
- Warna chart diatur per-`fig` (`color_discrete_sequence` / `marker_color`) — cari `px.`.
- Teks/emoji label tinggal ganti string di `st.title`, `st.subheader`, `st.caption`.
- Tiap chart wajib punya caption `💡 penjelasan(...)` + tooltip `hover_keterangan()`
  (helper ada di `dashboard_berita_dampak.py`, sebelum `st.set_page_config`).
- `width="stretch"` membuat chart selebar layar; ganti ke angka tetap kalau mau sempit.
- Jangan me-rename identifier/kolom DB (mis. `topik` → `tema`) — hanya teks yang
  tampil memakai istilah "tema"; nama tabel/kolom tetap `topik`.

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

Update bersifat incremental: URL yang sudah ada di-upsert (INSERT ... ON
DUPLICATE KEY UPDATE, bukan dilewati begitu saja — baris lama ikut diperbarui
kalau datanya berubah), jadi proses tetap murah walau tidak ada berita baru.
Log: `logs_update.txt`.

## Penyimpanan data

**MySQL** (database `ugm_analytics`, tabel berprefix `berita_`) — bukan
DuckDB lagi. Kredensial dibaca dari `.env` di root project (`MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`; lihat `.env.example`).
Koneksi dibuat lewat `scripts/db.py` (`get_engine()`), dengan:

- `pool_pre_ping=True` + `pool_recycle=3600` — koneksi idle/putus otomatis
  di-reconnect (penting untuk `fetch_detail.py` yang bisa jalan berjam-jam).
- Semua penulisan baris-per-berita pakai `upsert()` (INSERT ... ON DUPLICATE
  KEY UPDATE) dalam batch kecil (~100 baris/transaksi), bukan satu transaksi
  raksasa — kalau proses berhenti di tengah jalan, baris yang sudah masuk
  tetap tersimpan, dan running ulang tidak menghasilkan duplikat.
- Setiap baca/tulis dibungkus retry (`with_retry()`, 3×, jeda 5 detik); satu
  item yang gagal total di-log dan dilewati, tidak menghentikan seluruh
  pipeline.

Tabel ringkasan/agregat (`berita_ringkasan_*`, `berita_berita_kepmen_all`, dst.)
tetap full-replace tiap run (`to_sql(if_exists="replace")`) karena memang
hasil hitung ulang dari nol setiap kali, bukan data yang diakumulasi.

## Sumber data

- RSS: `https://ugm.ac.id/id/feed/` dan `https://ugm.ac.id/en/feed/`
- Sitemap: `https://ugm.ac.id/wp-sitemap.xml` (~32.000 URL berita, 2007–2026)
- REST API wp-json diblokir (401) — tidak dipakai.
- Pemetaan Kepmen & SDG: `../sumber/UGM Analytics.xlsx` (sheet "Konten UGM Berdampak"
  & "#Ref"); dokumen resmi: `../sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf`
  dan `../sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf`.

Detail alur lengkap: lihat `PIPELINE.md`. Detail isi dashboard: lihat `DASHBOARD.md`.
