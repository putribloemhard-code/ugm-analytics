# FRAMEWORK — Arsitektur & Konvensi UGM Impact Analytics

## Stack

| Lapisan | Teknologi |
|---|---|
| Bahasa | Python 3.11 (venv `venv/` di root workspace) |
| Data | DuckDB (file `*.duckdb` per subproyek) untuk subproyek lokal/belum di-deploy; **MySQL** untuk subproyek yang dideploy ke server produksi (berita-dampak sejak 2026-08-29 — migrasi penuh, tidak ada lagi DuckDB di pipeline-nya, lihat `berita-dampak/PIPELINE.md`) |
| Pustaka | pandas, plotly, streamlit, requests, bs4, openpyxl, pymupdf, rapidocr-onnxruntime, sqlalchemy, pymysql (untuk subproyek MySQL) |
| Output statis | plotly `write_html` (JS inline — render tanpa internet). BUKAN matplotlib/kaleido |
| Scheduling | Hermes cron (`update_berita_dampak.sh` → `update_mingguan.py`) |
| OS | Windows; terminal git-bash (MSYS) |

## Pola folder per subproyek

```
<subproyek>/
├── README.md          # peta file + cara menjalankan
├── PIPELINE.md        # alur processing + perintah run + hasil + caveat
├── DASHBOARD.md       # isi dashboard + cara membaca hasil
├── dashboard_<nama>.py  # Streamlit interaktif
├── laporan_<nama>.html  # laporan statis (plotly inline, offline)
├── data/              # DuckDB + CSV mentah/bersih
└── scripts/           # pipeline: scrape → normalize → tag → aggregate → report
```

## Pipeline umum (pola matkul-sustainability → dipakai berita-dampak)

1. **Scrape/kumpulkan** data mentah → `data/`
2. **Normalisasi** (bersihkan teks, tanggal, dedup) → tabel bersih
3. **Tagging** keyword (substring, case-insensitive, judul+deskripsi;
   token pendek berisiko pakai `\b...\b`) → tabel tag + ringkasan agregat
4. **Output**: `dashboard_<nama>.py` (Streamlit) + `laporan_static.py`
   (plotly `write_html`, `include_plotlyjs='cdn'` atau inline)
5. **Dokumentasi** di PIPELINE.md + README.md

## Pipeline berita-dampak (detail)

Seluruh tabel di MySQL (prefix `berita_`, lihat `berita-dampak/scripts/db.py`)
-- bukan DuckDB lagi.

```
backfill_sitemap.py → berita_sitemap (32.180 URL, ugm.ac.id/wp-sitemap.xml)
ingest.py           → RSS /id/feed/ + /en/feed/ → berita_berita (sumber='rss')
fetch_detail.py     → filter URL sitemap relevan + fetch halaman (8 thread,
                      throttle) → berita_berita (sumber='sitemap')
normalisasi.py      → bersihkan teks, konversi tanggal, dedup URL (mentah→bersih)
process_nlp.py      → tagging 4 tema inti → berita_berita_topik, berita_ringkasan_topik_tahun
tag_kepmen_all.py   → tagging 14 tema Kepmen + SDG → berita_berita_kepmen_all,
                      berita_berita_sdg_all, berita_ringkasan_pilar(_tahun), berita_ringkasan_sdg_all
tag_sdg_langsung.py → mode "SDGs saja" → berita_sitemap_sdg, berita_ringkasan_sdg_sitemap(_tahun)
generate_narasi_llm.py → narasi via Gemini API → berita_narasi_cache (opsional)
laporan_static.py   → laporan_berita_dampak.html (11 chart + tabel 14 tema)
update_mingguan.py  → jalankan seluruh pipeline berurutan (lock file
                      data/.update_lock; dipakai cron + tombol dashboard)
```

Penulisan baris-per-item (sitemap, berita) pakai `upsert()` (INSERT ... ON
DUPLICATE KEY UPDATE) per batch kecil + retry 3x -- lihat "Koneksi MySQL —
aturan penting" di bawah.

## Mapping resmi (satu sumber kebenaran)

- `scripts/kepmen_sdg.py` — dict `TOPIK_KEPMEN` (4 tema inti),
  `TEMA_KEPMEN_LENGKAP` (10 tema lain, `sdg` diisi dari sheet "#Ref"),
  `TOPIK_KEPMEN_ALL` (gabungan 14), `LABEL_TOPIC_ALL`, `WARNA_PILAR`,
  `SDG_NAMA`. Dashboard + laporan + tagging semua import dari sini.
- Sumber: `sumber/UGM Analytics.xlsx` sheet "Konten UGM Berdampak" (7 baris resmi)
  + "#Ref" (Dampak→Tema→SDG, sparse/merged — baca per-sel dengan koordinat),
  PDF Kepmen 361 (OCR: `docs/kepmen_361_ocr.txt`).
- Pitfall konseptual: klaster SDG adalah atribut tema (semua berita dalam
  satu tema membawa SDG sama), bukan hasil matching per berita.

## Konvensi tagging

- Substring match case-insensitive pada judul + deskripsi (ID + EN).
- Berita bisa multi-tema (multi-tag by design); SDG di-dedup per url.
- Keyword dipilih berbasis bukti: simulasi jumlah match di data + validasi
  sampel judul; kandidat false-positive (delegation, desa/village,
  kebijakan/policy, nuclear) DITOLAK — catatan di PIPELINE.md.
- Selalu sediakan daftar "tidak match" di dashboard untuk cek manual.

## DuckDB di Windows — aturan penting

Berlaku untuk subproyek yang MASIH pakai DuckDB lokal (mis. usulan
matkul-sustainability) -- **tidak berlaku lagi untuk berita-dampak** sejak
migrasi penuh ke MySQL (2026-08-29).

- Satu koneksi tulis mengunci file TOTAl; dashboard harus `read_only=True`
  dengan retry 10×1s (`_connect_db` di dashboard_berita_dampak.py).
- Jangan buka `duckdb` CLI mode tulis saat dashboard/update jalan; kalau
  perlu query manual: `duckdb -readonly data/ugm_news.duckdb`.
- Update data menulis DB → dashboard tidak bisa dibuka selama update
  (sudah ada pesan ramah + lock file mencegah update ganda).

## Koneksi MySQL — aturan penting (berita-dampak)

- Engine SQLAlchemy WAJIB `pool_pre_ping=True` + `pool_recycle=3600` (lihat
  `berita-dampak/scripts/db.py::get_engine()`) -- tanpa ini, proses panjang
  (`fetch_detail.py` bisa jalan berjam-jam) akan crash dengan "MySQL server
  has gone away" begitu koneksi idle/putus.
- Penulisan baris-per-item (bukan tabel ringkasan/agregat) WAJIB upsert
  (`INSERT ... ON DUPLICATE KEY UPDATE`, helper `db.upsert()`) per batch
  kecil (~100 baris/transaksi), bukan satu transaksi raksasa -- supaya
  proses yang berhenti di tengah jalan tidak kehilangan data yang sudah
  masuk, dan running ulang tidak menghasilkan duplikat. Tabel dasar
  (`berita_sitemap`, `berita_berita`) punya PRIMARY KEY pada `url` untuk ini.
- Semua baca/tulis dibungkus retry 3x (`db.with_retry()` / `db.read_sql_retry()`);
  satu item/batch yang gagal total di-log dan DILEWATI, tidak menghentikan
  seluruh pipeline.
- Tabel ringkasan/agregat (hasil hitung ulang total tiap run, bukan data
  yang diakumulasi) tetap full-replace (`to_sql(if_exists="replace")`).
- Jangan pakai nama variabel `t` di script yang juga `import db` -- `db.t()`
  adalah helper prefix tabel; variabel lokal bernama sama akan men-shadow-nya
  untuk seluruh fungsi (bug nyata yang ditemukan saat migrasi 2026-08-29).

## Jaringan & akses

- ugm.ac.id: wp-json diblokir (401); sitemap + RSS adalah sumber sah;
  situs sering timeout → retry wajib di semua fetch.
- Dashboard dari laptop lain: firewall rule port 8766
  (`buka_akses_dashboard_admin.bat`), atau Tailscale untuk lintas jaringan.
- Laporan HTML statis bisa dikirim tanpa server (render offline).
