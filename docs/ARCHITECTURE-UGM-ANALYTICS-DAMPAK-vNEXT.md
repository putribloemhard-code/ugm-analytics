# Arsitektur UGM Analytics — Dampak vNEXT (4 Subproyek: Kurikulum, KKN, Mahasiswa, Berita)

Tipe dokumen: Arsitektur aplikasi eksisting (reverse engineering dari implementasi)
Sumber: repo `ugm-analytics` (main, 2026-08-21) — kode pipeline, dashboard, DuckDB, docs
Status: Lengkap utk layer Business/Data/Application/Technology; KKN & Mahasiswa = rencana (belum dibangun)

## 1. BUSINESS LAYER

### Visi Layanan

Mengukur dampak UGM terhadap masyarakat (sosial, ekonomi, lingkungan) berbasis
regulasi resmi: Kepmen 361/M/KEP/2025 (3 pilar + tema + indikator ber-formula) dan
17 SDGs. Empat sumber data: kurikulum matkul berkelanjutan (eLOK), berita publikasi
ugm.ac.id, KKN desa binaan (rencana), mahasiswa afirmasi (rencana).

### Proses Bisnis per Subproyek

| Proses | matkul-sustainability | kkn-desa-binaan | mahasiswa-afirmasi | berita-dampak |
|---|---|---|---|---|
| Pengumpulan data mentah | ✅ scrape_elok.py (eLOK) | ⏳ rencana | ⏳ rencana | ✅ backfill_sitemap, ingest, fetch_detail |
| Normalisasi & dedup | ✅ normalize_matkul.py | — | — | ✅ normalisasi.py |
| Tagging dampak (Kepmen/SDG) | ✅ tag_kepmen_matkul, tag_sdg_matkul | — | — | ✅ process_nlp, tag_kepmen_all.py |
| Agregasi per unit/tahun | ✅ ringkasan fakultas/prodi/tahun/topik | — | — | ✅ ringkasan pilar/topik/sdg/tahun |
| Dashboard interaktif | ✅ dashboard_matkul_kepmen.py, dashboard_matkul_sdg.py | — | — | ✅ dashboard_berita_dampak.py |
| Laporan statis offline | ✅ laporan_matkul_kepmen.html | — | — | ✅ laporan_berita_dampak.html |
| Update berkala otomatis | — | — | — | ✅ cron Sabtu 06:00 + tombol dashboard |

### Aktor

Analis dampak UGM (admin data) · Unit pengelola (fakultas/prodi/KKN) ·
Pemangku kepentingan eksternal (Kepmen Diktisaintek, DIKTI) · Publik (laporan statis)

## 2. DATA LAYER

| Domain | matkul-sustainability | berita-dampak | KKN & Mahasiswa |
|---|---|---|---|
| Kurikulum | elok_matkul_mentah/bersih/kepmen/sdg.csv, ringkasan_fakultas.csv (21), ringkasan_prodi.csv, ringkasan_tahun.csv, ringkasan_topik.csv | — | — |
| Berita | — | sitemap (32.130 URL), berita (4.787), berita_kepmen_all (2.393 unik), berita_sdg_all, ringkasan_pilar/topik/sdg/_tahun | — |

Referensi resmi (satu sumber kebenaran, folder `sumber/`): `sumber/UGM Analytics.xlsx`
(sheet "Konten UGM Berdampak" = 7 baris Dampak→Topik Resmi→Klaster SDGs→Indikator→Sumber Data;
sheet "#Ref" = pemetaan Dampak→Topik Kepmen→SDG sparse/merged),
`sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` (scan, OCR →
`docs/kepmen_361_ocr.txt`), `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf` (12 IKU — tema sama dgn Kepmen: 14).

Penyimpanan: DuckDB per subproyek (berita-dampak: `data/ugm_news.duckdb` 21 MB);
matkul-sustainability: CSV di `data/`. KKN & mahasiswa: `data/` + `scripts/` masih kosong.

## 3. APPLICATION LAYER

| Komponen | Teknologi | Bukti |
|---|---|---|
| Bahasa | Python 3.11 (venv `venv/` root) | pyproject/venv |
| Scraping | requests + bs4; retry wajib; fetch_detail parallel 8 thread + throttle | backfill_sitemap.py, fetch_detail.py |
| OCR | pymupdf (render dpi=200) + rapidocr-onnxruntime | ocr_kepmen.py → kepmen_361_ocr.txt |
| Normalisasi | pandas (strip teks, konversi tanggal, dedup URL mentah→bersih) | normalize_matkul.py, normalisasi.py |
| Tagging | keyword substring case-insensitive (judul+deskripsi, ID+EN); token pendek pakai `\b..\b`; multi-topik by design; SDG dedup per url | tag_kepmen_all.py, tag_kepmen_matkul.py |
| Mapping resmi | modul `scripts/kepmen_sdg.py` — satu sumber kebenaran: TOPIK_KEPMEN, TEMA_KEPMEN_LENGKAP, TOPIK_KEPMEN_ALL (14 tema), SDG_NAMA, WARNA_PILAR | dipakai dashboard + tagging + laporan |
| Dashboard | Streamlit (filter sidebar global, 11 bagian berita / drill-down fakultas-prodi matkul) | dashboard_berita_dampak.py |
| Laporan statis | plotly `write_html` (JS inline, offline) — BUKAN matplotlib/kaleido | laporan_static.py → *.html |
| Automasi update | update_mingguan.py + lock `data/.update_lock`; Popen detached dari tombol dashboard | update_mingguan.sh |

## 4. TECHNOLOGY LAYER

| Komponen | Detail |
|---|---|
| Sumber data kurikulum | elok.ugm.ac.id (Moodle, akses guest) — offline-first: butuh izin sebelum re-scrape |
| Sumber data berita | ugm.ac.id: sitemap `wp-sitemap.xml` (33 file), RSS `/id/feed/` + `/en/feed/` (10 item each); wp-json DIBLOKIR (401) |
| Database | DuckDB file per subproyek; Windows: satu koneksi tulis mengunci TOTAl file → dashboard wajib `read_only=True` + retry 10×1s; query manual `duckdb -readonly` |
| Serving dashboard | Streamlit port 8766, headless; LAN via firewall rule (`buka_akses_dashboard_admin.bat`); lintas jaringan via Tailscale |
| Scheduling | Hermes cron `update_berita_dampak.sh` Sabtu 06:00 |
| Versioning | Git repo PRIVATE `putribloemhard-code/ugm-analytics` (auth `~/.git-credentials`; collaborator baca: dedieko-priyadi) |
| Referensi resmi | `sumber/UGM Analytics.xlsx`, `sumber/Salinan_Kepmen_361...pdf`, `sumber/Buku_IKU...pdf` |

## 5. TEMUAN KONSOLIDASI (operasional/arsitektur)

- ugm.ac.id wp-json diblokir 401 → reverse engineering: sitemap + RSS adalah sumber sah; situs sering timeout → retry wajib di semua fetch
- eLOK: user menolak probing jaringan live — semua kerja berbasis data lokal; re-scrape harus konfirmasi dulu
- DuckDB di Windows: koneksi tulis (DuckDB CLI / DBeaver wizard) mengunci file total — dashboard IOException; fix: `duckdb -readonly`, disconnect DBeaver, atau retry loop
- Keyword false-positive DITOLAK berbasis validasi sampel: delegation (prestasi lomba), desa/village, kebijakan/policy, nuclear (terlalu luas)
- Keyword WAJIB bersumber dari detailing tabel Kepmen (definisi/kriteria/ketentuan per tema, OCR docs/kepmen_361_ocr.txt) — istilah di luar detailing dibuang; kata luas lintas-tema ditolak; token ≤5 huruf otomatis word boundary di tag_kepmen_all.py (proven 2026-08-21: "paten" substring-match "kabupaten" 190 FP → \bpaten\b 2 match relevan)
- Klaster SDG adalah atribut TOPIK (semua berita satu topik membawa SDG sama), bukan matching per berita; SDG di-dedup per url
- Angka dampak = lower-bound keyword match (2.369/4.787, 49,5%) — sediakan expander "tidak match" untuk cek manual
- Update mingguan menulis DB 10–15 mnt → dashboard tak bisa dibuka; lock file cegah update ganda
- PyMuPDF Windows menolak path MSYS `/d/...` — pakai `D:/...`
- Buku IKU (12 IKU) dan Kepmen 361 (3 pilar/14 tema) BERBAGI taksonomi tema yang sama (Sosial 4, Ekonomi 5, Lingkungan 5) — rangkuman Kepmen menjabarkan tiap tema ke indikator+formula; jangan campur hitungan: 12 IKU kinerja PT ≠ 14 tema indikator dampak

## 6. KARAKTER ARSITEKTUR

- Multi-sumber, satu makna: 2 sumber eksternal (eLOK, ugm.ac.id) + 3 referensi resmi dipetakan ke satu taksonomi (Kepmen 361 + SDG) lewat `kepmen_sdg.py`
- Pola pipeline seragam per subproyek: scrape → normalisasi → tagging → agregasi → output (dashboard + laporan), didokumentasikan README/PIPELINE/DASHBOARD
- Output ganda: Streamlit interaktif (analisis) + HTML plotly inline (berbagi offline tanpa server)
- Data lokal-first: DuckDB/CSV lokal, render offline, tanpa layanan eksternal runtime
- Bottom-up: data mentah → tag → agregasi → pilar/SDG → laporan; setiap lapisan bisa diverifikasi manual

## 7. DOKUMEN TERKAIT

- `docs/PERENCANAAN.md` (tujuan/backlog/milestone) · `docs/FRAMEWORK.md` (arsitektur/konvensi/stack) · `docs/OUTPUT.md` (hasil) · `docs/listing-ide-analisis-dampak.md` (ide backlog) · `docs/kepmen_361_ocr.txt` (OCR Kepmen)
- Per subproyek: `README.md` (peta file) + `PIPELINE.md` (alur) + `DASHBOARD.md` (isi dashboard) — matkul-sustainability & berita-dampak lengkap
- Referensi resmi: `sumber/UGM Analytics.xlsx` · `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` · `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf`
- Angka kunci live (2026-08-21, DuckDB): berita 4.787 total; 2.369 unik bertopik (49,5%); pilar Lingkungan 1.105 / Sosial 1.009 / Ekonomi 700; topik terbesar rehabilitasi_lingkungan 638, pengabdian_masyarakat 635, limbah 392, kewirausahaan 303; SDG terbesar SDG 8 (1.050), 17 (1.021), 1 (838), 13 (759). Matkul: 460 matkul, 21 fakultas, 5 topik sustainability (26 matkul tagged; Kehutanan 58.8%).
