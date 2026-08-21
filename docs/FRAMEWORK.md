# FRAMEWORK — Arsitektur & Konvensi UGM Impact Analytics

## Stack

| Lapisan | Teknologi |
|---|---|
| Bahasa | Python 3.11 (venv `venv/` di root workspace) |
| Data | DuckDB (file `*.duckdb` per subproyek) |
| Pustaka | pandas, plotly, streamlit, requests, bs4, openpyxl, pymupdf, rapidocr-onnxruntime |
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

```
backfill_sitemap.py → sitemap (32.130 URL, ugm.ac.id/wp-sitemap.xml)
ingest.py           → RSS /id/feed/ + /en/feed/ → tabel berita (sumber='rss')
fetch_detail.py     → filter URL sitemap relevan + fetch halaman (8 thread,
                      throttle) → tabel berita (sumber='sitemap')
normalisasi.py      → bersihkan teks, konversi tanggal, dedup URL (mentah→bersih)
process_nlp.py      → tagging 4 topik inti → berita_topik, ringkasan_topik_tahun
tag_kepmen_all.py   → tagging 14 tema Kepmen + SDG → berita_kepmen_all,
                      berita_sdg_all, ringkasan_pilar(_tahun), ringkasan_sdg_all
laporan_static.py   → laporan_berita_dampak.html (11 chart + tabel 14 tema)
update_mingguan.py  → jalankan seluruh pipeline berurutan (lock file
                      data/.update_lock; dipakai cron + tombol dashboard)
```

## Mapping resmi (satu sumber kebenaran)

- `scripts/kepmen_sdg.py` — dict `TOPIK_KEPMEN` (4 topik inti),
  `TEMA_KEPMEN_LENGKAP` (9 tema lain, `sdg` diisi dari sheet "#Ref"),
  `TOPIK_KEPMEN_ALL` (gabungan 14), `LABEL_TOPIC_ALL`, `WARNA_PILAR`,
  `SDG_NAMA`. Dashboard + laporan + tagging semua import dari sini.
- Sumber: `sumber/UGM Analytics.xlsx` sheet "Konten UGM Berdampak" (7 baris resmi)
  + "#Ref" (Dampak→Topik→SDG, sparse/merged — baca per-sel dengan koordinat),
  PDF Kepmen 361 (OCR: `docs/kepmen_361_ocr.txt`).
- Pitfall konseptual: klaster SDG adalah atribut TOPIK (semua berita dalam
  satu topik membawa SDG sama), bukan hasil matching per berita.

## Konvensi tagging

- Substring match case-insensitive pada judul + deskripsi (ID + EN).
- Berita bisa multi-topik (multi-tag by design); SDG di-dedup per url.
- Keyword dipilih berbasis bukti: simulasi jumlah match di data + validasi
  sampel judul; kandidat false-positive (delegation, desa/village,
  kebijakan/policy, nuclear) DITOLAK — catatan di PIPELINE.md.
- Selalu sediakan daftar "tidak match" di dashboard untuk cek manual.

## DuckDB di Windows — aturan penting

- Satu koneksi tulis mengunci file TOTAl; dashboard harus `read_only=True`
  dengan retry 10×1s (`_connect_db` di dashboard_berita_dampak.py).
- Jangan buka `duckdb` CLI mode tulis saat dashboard/update jalan; kalau
  perlu query manual: `duckdb -readonly data/ugm_news.duckdb`.
- Update data menulis DB → dashboard tidak bisa dibuka selama update
  (sudah ada pesan ramah + lock file mencegah update ganda).

## Jaringan & akses

- ugm.ac.id: wp-json diblokir (401); sitemap + RSS adalah sumber sah;
  situs sering timeout → retry wajib di semua fetch.
- Dashboard dari laptop lain: firewall rule port 8766
  (`buka_akses_dashboard_admin.bat`), atau Tailscale untuk lintas jaringan.
- Laporan HTML statis bisa dikirim tanpa server (render offline).
