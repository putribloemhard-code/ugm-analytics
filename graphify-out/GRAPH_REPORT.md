# Graph Report - ugm-analytics  (2026-09-18)

## Corpus Check
- 128 files · ~465,741 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1092 nodes · 1831 edges · 84 communities (64 shown, 20 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 49 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7570bc3f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- v1/analytics.py
- t
- auth_akreditasi.py
- ekstraksi_pattern.py
- PRD — Frontend Analytics Non-Streamlit
- App.tsx
- ekstraksi_akreditasi.py
- generate_akreditasi_docx.py
- dashboard_render.py
- common.py
- package.json
- BAGIAN 3 — Sumber Data per Kategori
- sdg_label
- datetime
- generate_template.py
- compilerOptions
- Isi Dashboard
- generate_laporan_live.py
- pencarian.py
- test_api_contracts.py
- compilerOptions
- registry_kebutuhan_data.py
- Isi Dashboard
- akreditasi/scripts/db.py
- AccreditationService
- PIPELINE — Analisis Dampak Berita UGM (berita-dampak)
- Arsitektur UGM Analytics — Dampak vNEXT (4 Subproyek: Kurikulum, KKN, Mahasiswa, Berita)
- FRAMEWORK — Arsitektur & Konvensi UGM Impact Analytics
- data_loader.py
- Listing Ide: Analisis Dampak UGM (Kepmen 361/M/KEP/2025 & SDGs)
- Cara Processing
- Akreditasi — Kelengkapan Data LED & LKPS
- Berita Dampak — Analisis Dampak Berita UGM
- PIPELINE — Akreditasi
- BeautifulSoup
- Paket Deploy Terisolasi — UGM Analytics
- inject_css
- OUTPUT — Apa yang Dihasilkan (berita-dampak)
- PERENCANAAN — UGM Impact Analytics
- style.py
- tag_kepmen_matkul.py
- UGM Impact Analytics
- UGM Analytics Web Design
- DASHBOARD — Akreditasi
- data_uri_ikon
- matkul-sustainability
- migrasi_prodi_id.py
- gabungkan_duplikat_matkul
- migrasi_ke_mysql.py
- siapkan_logo.py
- engine_url
- migrasi_arsip_pdf.py
- migrasi_tabel_akreditasi.py
- migrasi_tabel_berita_dcse.py
- migrasi_tabel_ekstraksi_akreditasi.py
- migrasi_tabel_item_tersedia.py
- migrasi_tabel_prodi.py
- migrasi_tabel_publikasi_dosen.py
- migrasi_tabel_upload_akreditasi.py
- migrasi_tabel_users.py
- update_mingguan.py
- migrate_mysql_to_postgres.py
- matkul-sustainability/scripts/laporan_static.py
- map_matkul_ke_sdg
- tsconfig.json
- ocr_kepmen.py
- sdg_keywords.py
- update_mingguan.sh script
- akun_akreditasi.py
- md_aman
- _render_kartu
- save_upload
- schemas.py
- build_report
- logo_data_uri
- _user_login

## God Nodes (most connected - your core abstractions)
1. `AnalyticsService` - 31 edges
2. `t()` - 28 edges
3. `get_engine()` - 27 edges
4. `with_retry()` - 24 edges
5. `compilerOptions` - 17 edges
6. `PRD — Frontend Analytics Non-Streamlit` - 15 edges
7. `led_items_by_kriteria()` - 14 edges
8. `read_sql_retry()` - 14 edges
9. `ekstrak_pattern_pdf()` - 13 edges
10. `lkps_items_by_bagian()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `_render_riwayat()` --calls--> `riwayat_generate_user()`  [INFERRED]
  berita-dampak/page_profil.py → akreditasi/scripts/akun_akreditasi.py
- `_render_ongoing()` --calls--> `pekerjaan_ongoing()`  [INFERRED]
  berita-dampak/page_profil.py → akreditasi/scripts/akun_akreditasi.py
- `render()` --calls--> `daftar_user()`  [INFERRED]
  berita-dampak/page_admin.py → akreditasi/scripts/akun_akreditasi.py
- `_render_kartu()` --indirect_call--> `set_blokir()`  [INFERRED]
  berita-dampak/page_admin.py → akreditasi/scripts/akun_akreditasi.py
- `_render_kartu()` --indirect_call--> `set_admin()`  [INFERRED]
  berita-dampak/page_admin.py → akreditasi/scripts/akun_akreditasi.py

## Import Cycles
- None detected.

## Communities (84 total, 20 thin omitted)

### Community 0 - "v1/analytics.py"
Cohesion: 0.18
Nodes (23): accreditation(), accreditation_login(), accreditation_logout(), accreditation_me(), accreditation_register(), accreditation_upload(), _auth_user(), filters() (+15 more)

### Community 1 - "t"
Cohesion: 0.06
Nodes (76): main(), Backfill deskripsi berita sitemap yang kosong (fallback og:description).  Sekali, get(), main(), parse_entries(), Backfill berita UGM dari sitemap ke MySQL.  Mengambil seluruh post-sitemapN.xml, Daftar post-sitemapN.xml dari sitemap index., Ekstrak (url, lastmod) dari satu sitemap. (+68 more)

### Community 2 - "auth_akreditasi.py"
Cohesion: 0.14
Nodes (25): ambil_user_aktif(), _baris_ke_user(), _catat_percobaan(), _hash_token(), keluar(), login(), normalisasi_email(), pulihkan_user() (+17 more)

### Community 3 - "ekstraksi_pattern.py"
Cohesion: 0.06
Nodes (51): ada_trigger_section(), _bagian_di_halaman(), _bagian_diharapkan(), _blok_baris_data(), _buat_parser_horizontal(), _cari_halaman_trigger_pdf(), _deteksi_heading_bagian(), ekstrak_pattern_pdf() (+43 more)

### Community 4 - "PRD — Frontend Analytics Non-Streamlit"
Cohesion: 0.05
Nodes (43): Constraints and assumptions, Deferred: accreditation phase, Dependencies and related documents, Existing system evidence, FR-001 — Public application routes, FR-002 — Search interpretation, FR-003 — Impact analytics parity, FR-004 — Direct-SDG analytics parity (+35 more)

### Community 5 - "App.tsx"
Cohesion: 0.08
Nodes (31): AccreditationLogin(), AccreditationPage(), AnalyticsContent(), AnalyticsPage(), AppShell(), assetUrl(), emptyFilters, FilterState (+23 more)

### Community 6 - "ekstraksi_akreditasi.py"
Cohesion: 0.09
Nodes (32): _build_user_prompt(), _call_llm_batch(), deteksi_konflik(), ekstrak_file(), extract_text(), _extract_text_docx(), _extract_text_pdf(), _extract_text_xlsx() (+24 more)

### Community 7 - "generate_akreditasi_docx.py"
Cohesion: 0.19
Nodes (16): build_laporan(), _format_sel(), nama_file(), DataFrame, Document, Generator laporan Word (.docx) ringkasan analisis Dampak/Dampak x SDGs/SDGs.  RE, Rangkai satu laporan .docx: cover + filter aktif + ringkasan eksekutif +     N s, UI lengkap "Unduh Laporan (Word)": caption + tombol generate + tombol     unduh. (+8 more)

### Community 8 - "dashboard_render.py"
Cohesion: 0.06
Nodes (70): Dashboard Streamlit -- kelengkapan data akreditasi (LED & LKPS), berdiri sendiri, pekerjaan_ongoing(), Kombinasi (prodi, LED/LKPS) di mana user ini punya >=1 item yang sudah     ia ko, consume_pending_switch(), ensure_ready(), get_engine(), load_data_manual(), load_fakultas() (+62 more)

### Community 9 - "common.py"
Cohesion: 0.13
Nodes (21): hover_keterangan(), insight_heatmap(), insight_top2(), load_data_or_stop(), penjelasan(), Counter, DataFrame, Kalimat insight top-1 vs top-2 dari dataframe chart peringkat/distribusi -- (+13 more)

### Community 10 - "package.json"
Cohesion: 0.07
Nodes (28): react, react-dom, react-router-dom, @types/node, @types/react, @types/react-dom, typescript, vite (+20 more)

### Community 11 - "BAGIAN 3 — Sumber Data per Kategori"
Cohesion: 0.07
Nodes (27): 10. Data mutu (SPMI, Audit Mutu Internal), 11. Bukti pendukung (link dokumen) — sumber arsip lintas kategori, 1. Data legal/administratif (SK pendirian, SK akreditasi, SOTK), 2. Data SDM (dosen/DTPR & tenaga kependidikan), 3. Data keuangan, 4. Data sarana & prasarana, 5. Data kurikulum (mata kuliah, RPS, pemetaan CPL), 6. Data mahasiswa (asal, keragaman, afirmasi) (+19 more)

### Community 12 - "sdg_label"
Cohesion: 0.17
Nodes (23): main(), rangkai_narasi(), Generate narasi ringkasan/insight pakai OpenAI API (LLM), simpan ke cache MySQL, Minta OpenAI merangkai `data_ringkas` jadi narasi; kalau gagal apa pun,     bali, Label ringkas: 'SDG 13 — Penanganan Perubahan Iklim'., sdg_label(), generate_executive_summary(), generate_impact_insight() (+15 more)

### Community 13 - "datetime"
Cohesion: 0.15
Nodes (22): fetch_page(), is_relevan_mei(), main(), parse_feed(), Pipeline live: crawl arsip berita/pengumuman dcse.fmipa.ugm.ac.id (RSS feed resm, _get(), _h2_sections(), kumpulkan_identitas_pt_upps_ps() (+14 more)

### Community 15 - "compilerOptions"
Cohesion: 0.09
Nodes (22): DOM, DOM.Iterable, ES2021, src, compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop (+14 more)

### Community 16 - "Isi Dashboard"
Cohesion: 0.10
Nodes (20): 10 — Daftar Berita, 1 — Distribusi per Tema Dampak, 2 — Peta Tema Resmi Kepmen & Klaster SDGs, 3 — Heatmap Tema × Tahun, 4 — Tren Tahunan per Tema, 5 — Tren Bulanan (musiman), 6 — Cakupan vs Total Berita UGM per Tahun, 7 — Keyword yang Memicu Match per Tema (+12 more)

### Community 17 - "generate_laporan_live.py"
Cohesion: 0.12
Nodes (35): _add_cover(), _add_item_section(), _add_placeholder(), _add_sumber_tambahan(), _add_tersedia(), generate_led_docx(), generate_lkps_docx(), load_berita_dcse_relevan() (+27 more)

### Community 18 - "pencarian.py"
Cohesion: 0.15
Nodes (17): Halaman Beranda -- landing page dashboard analisis dampak UGM., _ada_kata(), banner(), _batasi_tahun(), Hasil, parse(), Pencarian kata kunci untuk kotak "Mau analisis apa?" di Beranda.  BUKAN AI: quer, Kalimat penjelas: kenapa user mendarat di halaman ini dengan filter ini. (+9 more)

### Community 20 - "compilerOptions"
Cohesion: 0.12
Nodes (15): ES2023, vite.config.ts, compilerOptions, allowImportingTsExtensions, lib, module, moduleDetection, moduleResolution (+7 more)

### Community 21 - "registry_kebutuhan_data.py"
Cohesion: 0.20
Nodes (6): Settings, build_database_url(), get_engine(), Engine, URL, test_postgres_engine_url_uses_environment()

### Community 22 - "Isi Dashboard"
Cohesion: 0.13
Nodes (14): 9 Topik Resmi (keyword matching), Alur Data, Bagian 1 — Bar Chart Semua Fakultas, Bagian 2 — Treemap: Fakultas → Prodi → Mata Kuliah, Bagian 3 — Heatmap: Topik Kepmen × Fakultas, Bagian 4 — Donut Sebaran per Topik, Bagian 5 — Tren per Tahun (Stacked per Fakultas), Bagian 6 — Drill-down Mata Kuliah per Prodi (+6 more)

### Community 23 - "akreditasi/scripts/db.py"
Cohesion: 0.23
Nodes (12): get_engine(), Engine, Koneksi MySQL bersama untuk subproyek akreditasi.  Semua tabel memakai prefix "a, pandas.read_sql dibungkus retry., INSERT ... ON DUPLICATE KEY UPDATE, dikirim per-batch kecil -- pola     identik, Nama tabel MySQL dengan prefix 'akreditasi_' (mis. t('data_manual') -> 'akredita, Jalankan `func()`; retry sampai `attempts` kali kalau melempar exception.     Re, read_sql_retry() (+4 more)

### Community 24 - "AccreditationService"
Cohesion: 0.17
Nodes (15): search(), parse_search(), SearchResult, whole_word(), kepmen(), keywords(), load_accreditation_module(), load_module() (+7 more)

### Community 25 - "PIPELINE — Analisis Dampak Berita UGM (berita-dampak)"
Cohesion: 0.17
Nodes (11): Alur processing, Caveat, Hasil (terakhir dijalankan: 2026-08-20), Migrasi penuh DuckDB -> MySQL (2026-08-29), Pengembangan dashboard (2026-08-19), Pengembangan dashboard (2026-08-20 — 14 tema / 3 pilar lengkap), Penyimpanan data, PIPELINE — Analisis Dampak Berita UGM (berita-dampak) (+3 more)

### Community 26 - "Arsitektur UGM Analytics — Dampak vNEXT (4 Subproyek: Kurikulum, KKN, Mahasiswa, Berita)"
Cohesion: 0.17
Nodes (11): 1. BUSINESS LAYER, 2. DATA LAYER, 3. APPLICATION LAYER, 4. TECHNOLOGY LAYER, 5. TEMUAN KONSOLIDASI (operasional/arsitektur), 6. KARAKTER ARSITEKTUR, 7. DOKUMEN TERKAIT, Aktor (+3 more)

### Community 27 - "FRAMEWORK — Arsitektur & Konvensi UGM Impact Analytics"
Cohesion: 0.18
Nodes (10): DuckDB di Windows — aturan penting, FRAMEWORK — Arsitektur & Konvensi UGM Impact Analytics, Jaringan & akses, Koneksi MySQL — aturan penting (berita-dampak), Konvensi tagging, Mapping resmi (satu sumber kebenaran), Pipeline berita-dampak (detail), Pipeline umum (pola matkul-sustainability → dipakai berita-dampak) (+2 more)

### Community 28 - "data_loader.py"
Cohesion: 0.27
Nodes (9): _get_engine(), load(), load_narasi_cache(), load_ringkasan_beranda(), DataFrame, Loading data (MySQL) untuk dashboard analisis dampak berita UGM.  Dipakai bareng, Engine SQLAlchemy ke MySQL, di-cache lintas rerun (cache_resource: koneksi     t, Narasi hasil rangkaian LLM (Gemini), digenerate mingguan lewat     scripts/gener (+1 more)

### Community 29 - "Listing Ide: Analisis Dampak UGM (Kepmen 361/M/KEP/2025 & SDGs)"
Cohesion: 0.20
Nodes (9): 1. Mata Kuliah → Integrasi Kurikulum Sustainability, 2. Sebaran KKN → Desa Binaan, 3. Berita UGM → Program Rehabilitasi Lingkungan (dan dampak lain), 4. Asal Mahasiswa → Keterserapan Kelompok Afirmasi, 5. Berita → Ekosistem Kewirausahaan (Startup/Spin-off UGM), 6. Berita (Entitas EVT) → Kunjungan Akademik, 7. Berita (Topik "Kerjasama") → Kolaborasi Riset-Industri, Listing Ide: Analisis Dampak UGM (Kepmen 361/M/KEP/2025 & SDGs) (+1 more)

### Community 30 - "Cara Processing"
Cohesion: 0.20
Nodes (9): 1. Scrape/kumpulkan deskripsi tiap mata kuliah, 2. Normalisasi, 3. Keyword matching ke topik resmi Kepmen, 4. Output, Cara Processing, Caveat, Hasil (sampel eLOK, 382 matkul bersih), Menjalankan ulang (offline, tanpa scrape) (+1 more)

### Community 31 - "Akreditasi — Kelengkapan Data LED & LKPS"
Cohesion: 0.22
Nodes (8): Akreditasi — Kelengkapan Data LED & LKPS, Cara menjalankan (PowerShell, Windows), Generate dokumen template akreditasi, Input data manual, Isi folder, Mengubah kebutuhan data (tambah/ubah item), Penyimpanan data, Sumber data

### Community 32 - "Berita Dampak — Analisis Dampak Berita UGM"
Cohesion: 0.22
Nodes (8): Berita Dampak — Analisis Dampak Berita UGM, Isi folder, Mengubah tampilan dashboard, Menjalankan dashboard, Menjalankan laporan statis, Penyimpanan data, Sumber data, Update data berkala

### Community 33 - "PIPELINE — Akreditasi"
Cohesion: 0.25
Nodes (7): 1. Registry (`scripts/registry_kebutuhan_data.py`), 2. Migrasi tabel (`scripts/migrasi_tabel_akreditasi.py`), 3-4. Input manual + penyimpanan, 5-6. Generate dokumen (`scripts/generate_template.py`), Alur, Koneksi MySQL — aturan yang diikuti, PIPELINE — Akreditasi

### Community 34 - "BeautifulSoup"
Cohesion: 0.43
Nodes (7): BeautifulSoup, ambil_course_dari_kategori(), ambil_daftar_kategori_fakultas(), ambil_subkategori(), Ambil semua link kategori tingkat atas (Fakultas + Sekolah Pascasarjana + Sekola, Ambil semua link subkategori di dalam 1 halaman Fakultas/Sekolah.      eLOK tida, scrape_semua()

### Community 35 - "Paket Deploy Terisolasi — UGM Analytics"
Cohesion: 0.25
Nodes (7): Batas dan asumsi, Catatan data, Gate pra-deploy, Isi paket, Kontrak environment, Paket Deploy Terisolasi — UGM Analytics, Setelah lifecycle diizinkan

### Community 36 - "inject_css"
Cohesion: 0.24
Nodes (8): Simpan file hasil generate ke disk + catat di akreditasi_riwayat_generate.     D, simpan_riwayat_generate(), User di sesi berjalan (setelah wajib_login/pulihkan_user dipanggil di     run ya, user_aktif(), Logika + UI halaman "Akreditasi" (berita-dampak).  Dashboard kelengkapan data LE, render(), _terapkan_lanjutkan(), Halaman Akreditasi.  Dashboard kelengkapan data LED & LKPS (registry 49 item, fo

### Community 37 - "OUTPUT — Apa yang Dihasilkan (berita-dampak)"
Cohesion: 0.29
Nodes (6): 1. Dashboard Streamlit (interaktif), 2. Laporan statis HTML (offline), 3. Database DuckDB, 4. Angka kunci (2026-08-21, lower-bound keyword match), 5. Update otomatis, OUTPUT — Apa yang Dihasilkan (berita-dampak)

### Community 38 - "PERENCANAAN — UGM Impact Analytics"
Cohesion: 0.29
Nodes (6): Backlog ide (dari docs/listing-ide-analisis-dampak.md), Milestone berita-dampak, PERENCANAAN — UGM Impact Analytics, Prinsip, Roadmap (ide berikutnya), Tujuan

### Community 39 - "style.py"
Cohesion: 0.13
Nodes (15): css_ikon_sidebar(), data_uri_ikon(), inject_css(), judul_halaman(), Konstanta, styling, dan helper yang dipakai bareng oleh semua halaman dashboard, Logo di shared/assets/logo/ sbg data URI (dipakai sidebar, kartu Beranda,     ju, Judul halaman (pengganti st.title) dgn logo gambar, bukan emoji -- logo     yang, <style> logo menu sidebar (base64, total <25 KB, di-cache per proses).     Logo (+7 more)

### Community 40 - "tag_kepmen_matkul.py"
Cohesion: 0.38
Nodes (6): ekstrak_tahun(), main(), match_topik(), Tagging mata kuliah ke topik resmi Kepmen 361/M/KEP/2025 — Dampak Lingkungan, Te, Kembalikan daftar id topik yang match ke judul/deskripsi., Tahun dari judul (mis. '... 2024'). None kalau tidak ada.

### Community 41 - "UGM Impact Analytics"
Cohesion: 0.29
Nodes (6): Dokumentasi, Lingkungan, Mulai cepat (berita-dampak), Referensi resmi (folder `sumber/`), Subproyek, UGM Impact Analytics

### Community 42 - "UGM Analytics Web Design"
Cohesion: 0.29
Nodes (6): Accessibility, Direction, Layout, Tokens, Typography and motion, UGM Analytics Web Design

### Community 43 - "DASHBOARD — Akreditasi"
Cohesion: 0.33
Nodes (5): Badge status, Cara baca dokumen hasil generate, DASHBOARD — Akreditasi, Entry point lain: menu "Akreditasi" di dashboard berita-dampak, Isi

### Community 44 - "data_uri_ikon"
Cohesion: 0.44
Nodes (9): login(), logout(), normalize_email(), Any, Engine, register(), token_hash(), user_from_token() (+1 more)

### Community 45 - "matkul-sustainability"
Cohesion: 0.33
Nodes (5): Cara menjalankan (dari folder ini, pakai venv proyek), Catatan, Hasil (sampel eLOK), Isi folder, matkul-sustainability

### Community 46 - "migrasi_prodi_id.py"
Cohesion: 0.60
Nodes (4): _column_exists(), _key_exists(), main(), Migrasi akreditasi_data_manual: tambah kolom prodi_id -- WAJIB dijalankan sebelu

### Community 47 - "gabungkan_duplikat_matkul"
Cohesion: 0.50
Nodes (4): gabungkan_duplikat_matkul(), normalisasi_nama_matkul(), Group course yang namanya sama (dalam fakultas+program yang sama) setelah normal, Hapus penanda kelas/dosen dari judul course eLOK, biar course yang sama tidak te

### Community 48 - "migrasi_ke_mysql.py"
Cohesion: 0.60
Nodes (4): main(), migrasi_csv(), migrasi_duckdb(), Migrasi data UGM Impact Analytics dari DuckDB (dan CSV) ke MySQL.  Jalankan dari

### Community 49 - "siapkan_logo.py"
Cohesion: 0.50
Nodes (4): main(), Path, Siapkan file logo untuk dashboard: rapikan gambar mentah lalu simpan ke shared/a, siapkan()

### Community 50 - "engine_url"
Cohesion: 0.67
Nodes (3): engine_url(), main(), URL

### Community 66 - "sdg_keywords.py"
Cohesion: 0.28
Nodes (4): NewsService, Any, Engine, ValueError

### Community 76 - "akun_akreditasi.py"
Cohesion: 0.21
Nodes (14): AksiDitolak, _cek_pelaku(), daftar_user(), hapus_user(), DataFrame, Data akun app akreditasi: riwayat generate laporan, pekerjaan "ongoing" per user, Semua user + jumlah dokumen yang pernah mereka generate., Hapus akun + sesi + riwayat generate-nya (termasuk file). Data yang ia     konfi (+6 more)

### Community 77 - "md_aman"
Cohesion: 0.27
Nodes (10): baca_file_riwayat(), Isi file riwayat, atau None kalau file sudah tidak ada. Path WAJIB     berada di, md_aman(), Escape karakter markdown -- nama user tampil di st.caption/markdown., Halaman "Profil Saya" (menu Akreditasi): identitas akun, pekerjaan yang sedang b, render(), _render_ongoing(), _render_riwayat() (+2 more)

### Community 78 - "_render_kartu"
Cohesion: 0.43
Nodes (6): _jalankan(), Halaman "Admin" (menu Akreditasi): kelola akun pengguna.  Pengamanan berlapis: 1, render(), _render_kartu(), _tgl(), Halaman Admin (menu Akreditasi). Logika & penolakan non-admin di page_admin.rend

### Community 79 - "save_upload"
Cohesion: 0.38
Nodes (6): safe_filename(), Any, Engine, Path, save_upload(), UploadError

### Community 80 - "schemas.py"
Cohesion: 0.53
Nodes (5): AnalyticsResponse, ErrorResponse, ReportRequest, SearchResponse, BaseModel

### Community 81 - "build_report"
Cohesion: 0.70
Nodes (4): build_report(), Any, Document, _table()

## Knowledge Gaps
- **238 isolated node(s):** `update_mingguan.sh script`, `name`, `private`, `version`, `type` (+233 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `sdg_label()` connect `sdg_label` to `common.py`, `t`, `generate_laporan_live.py`, `style.py`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `get_engine()` connect `t` to `sdg_label`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **What connects `update_mingguan.sh script`, `name`, `private` to the rest of the system?**
  _238 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `t` be split into smaller, more focused modules?**
  _Cohesion score 0.05567765567765568 - nodes in this community are weakly interconnected._
- **Should `auth_akreditasi.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13846153846153847 - nodes in this community are weakly interconnected._
- **Should `ekstraksi_pattern.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06458635703918723 - nodes in this community are weakly interconnected._
- **Should `PRD — Frontend Analytics Non-Streamlit` be split into smaller, more focused modules?**
  _Cohesion score 0.045454545454545456 - nodes in this community are weakly interconnected._