# Dashboard: Analisis Dampak Berita UGM (berita-dampak)

File: `dashboard_berita_dampak.py` — dijalankan dengan Streamlit:

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\streamlit run dashboard_berita_dampak.py
```

Lalu buka http://localhost:8766 (atau http://10.73.1.179:8766 dari laptop
lain di jaringan yang sama; port 8766 harus dibuka di firewall — lihat
`D:\ugm-analytics\buka_akses_dashboard_admin.bat`).

## Sumber data

`data/ugm_news.duckdb` (database DuckDB lokal, tanpa internet):

| Tabel | Isi |
|---|---|
| `sitemap` | 32.120 URL berita ugm.ac.id (2005–2026) — baseline volume |
| `berita` | 4.777 berita: judul, tanggal, deskripsi, sumber (RSS/sitemap) |
| `berita_topik` | 471 pasangan url–topik (4 topik inti; 1 berita bisa multi-topik) |
| `ringkasan_topik_tahun` | jumlah berita per topik per tahun |
| `berita_kepmen_all` | 1.487 pasangan url–tema (14 tema Kepmen) + pilar + sdg — sumber utama dashboard |
| `berita_sdg_all` | pasangan url–SDG dedup (semua 14 tema) |
| `ringkasan_topik_all` | jumlah berita unik per 14 tema (topik, pilar, topik_kepmen, sdg) |
| `ringkasan_pilar` | jumlah berita unik per pilar (Lingkungan/Ekonomi/Sosial) |
| `ringkasan_pilar_tahun` | jumlah berita per pilar per tahun |
| `ringkasan_sdg_all` | jumlah berita unik per SDG (semua 14 tema) |
| `berita_kepmen`, `berita_sdg`, `ringkasan_sdg` | legacy: 4 topik inti saja (masih ada, tidak dipakai dashboard) |
| `berita_kepmen_lengkap`, `ringkasan_kepmen_lengkap` | legacy: eksplorasi 9 tema (tidak dipakai dashboard) |

Data dimuat dengan cache Streamlit (`@st.cache_data`, TTL 300 detik).

## Sidebar: Filter Global

Semua chart dan tabel di bawah mengikuti filter; ringkasan dihitung ulang
sesuai filter.

- **Rentang tahun** — select slider, default seluruh data (2005–2026).
- **Topik dampak** — multi-select 14 tema Kepmen (4 inti + 9 tema lain),
  default semua.
- **Sumber** — sitemap dan/atau RSS.
- **Pilar dampak (Kepmen)** — Lingkungan/Ekonomi/Sosial, default semua;
  memfilter SELURUH bagian (ringkasan, distribusi, peta Kepmen & SDG,
  heatmap, tren, daftar berita) — bukan hanya bagian Peta.

## Isi Dashboard

### Ringkasan (4 kartu)
1. Total berita (sesuai filter).
2. Berita bertopik dampak — jumlah berita unik yang match ≥ 1 dari 14 tema.
3. Topik terpilih — berapa topik yang aktif di filter.
4. Rentang tahun — rentang yang sedang difilter.

### 1 — Distribusi per Topik Dampak
Bar horizontal jumlah berita unik per 14 tema, warna per pilar.
Saat ini: limbah (376), pengabdian masyarakat (294), kewirausahaan (276),
penelitian & inovasi (172), rehabilitasi_lingkungan (95), energi (88),
kunjungan akademik (65), kolaborasi riset (35), instansi publik (33),
belanja UMKM (21), pendidikan inklusif (18), transportasi (14).

### 2 — Peta Topik Resmi Kepmen & Klaster SDGs
Menjawab "berita ini masuk indikator Kepmen yang mana dan SDGs berapa".
Pemetaan Kepmendikti Saintek 361/M/KEP/2025 (dari `UGM Analytics.xlsx`
sheet "Konten UGM Berdampak" & "#Ref", divalidasi dengan PDF Kepmen asli).
14 tema:

| Topik berita | Pilar | Topik Resmi Kepmen | Klaster SDGs |
|---|---|---|---|
| Rehabilitasi Lingkungan | Lingkungan | Keanekaragaman Hayati (Rehabilitasi dan Restorasi Lingkungan) | SDG 13, 14, 15 |
| Kewirausahaan | Ekonomi | Ekosistem Kewirausahaan | SDG 8, 9 |
| Kunjungan Akademik | Ekonomi | Kunjungan Akademik dan Pengeluaran Pengunjung | SDG 8, 11 |
| Kolaborasi Riset | Ekonomi | Penelitian dan Pertukaran Pengetahuan | SDG 9, 17 |
| Pendidikan Inklusif | Sosial | Pendidikan Inklusif | SDG 1, 4, 10 |
| Penelitian & Inovasi Sosial | Sosial | Penelitian dan Inovasi | SDG 1, 9 |
| Pengabdian Masyarakat | Sosial | Pengabdian dan Pengembangan Masyarakat | SDG 1, 8, 11, 17 |
| Kontribusi Instansi Publik | Sosial | Kontribusi terhadap Instansi Publik | SDG 16, 17 |
| Pengajaran & Pembelajaran | Ekonomi | Pengajaran dan Pembelajaran | SDG 8 |
| Belanja UMKM Lokal | Ekonomi | Pengeluaran Institusi | SDG 8, 12 |
| Energi & Infrastruktur | Lingkungan | Energi dan Infrastruktur Ramah Lingkungan | SDG 7, 13 |
| Limbah & Daur Ulang | Lingkungan | Pengelolaan Limbah dan Daur Ulang | SDG 6, 12 |
| Mobilitas Ramah Lingkungan | Lingkungan | Mobilitas Ramah Lingkungan (Transportasi) | SDG 11, 13 |

Sub-bagian di dalamnya:
- **Bar Topik Resmi Kepmen** — jumlah berita per topik Kepmen, warna per pilar
  (hijau = Lingkungan, biru = Ekonomi, oranye = Sosial).
- **Bar per SDG** — berapa berita unik masuk tiap SDG. Saat ini: SDG 8 (522),
  SDG 9 (455), SDG 1 (449), SDG 12 (397), SDG 6 (376), SDG 11 (371),
  SDG 17 (355), SDG 13 (195).
- **Heatmap Topik Dampak × SDG** — kombinasi topik dan SDG; sel kosong =
  topik itu tidak memetakan ke SDG tersebut.
- **Tren SDG per Tahun** — line chart jumlah berita per SDG per tahun.
- **Heatmap Pilar Dampak × Tahun** — jumlah berita per pilar per tahun.
- **Expander: Ringkasan per pilar dampak** — kartu metrik + bar 3 pilar
  (Lingkungan 547, Ekonomi 373, Sosial 473 saat ini).
- **Expander: tabel pemetaan resmi + indikator Kepmen (14 tema)** — mapping
  lengkap + nama indikator resmi, formula, satuan (sesuai PDF Kepmen).

Indikator resmi Kepmen per topik (dari
`Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf`, hasil OCR di
`D:\\ugm-analytics\\docs\\kepmen_361_ocr.txt`):

| Topik berita | Indikator Kepmen | Formula | Satuan |
|---|---|---|---|
| Rehabilitasi Lingkungan | Jumlah program rehabilitasi dan restorasi lingkungan PT | Jumlah program rehabilitasi/restorasi pada periode berjalan | Program |
| Kewirausahaan | Jumlah entitas spin-off/start-up dari PT yang masih aktif | Jumlah entitas dari hasil riset/inkubasi yang aktif beroperasi | Entitas |
| Kunjungan Akademik | Jumlah pengeluaran pengunjung kegiatan akademik | Rata-rata pengeluaran per pengunjung (Rp) × jumlah pengunjung | Rupiah |
| Kolaborasi Riset | Pendapatan PT dari hilirisasi riset/spin-off dengan industri & pemerintah | Jumlah pendapatan hilirisasi riset/paten/prototipe/spin-off | Rupiah |

### 3 — Heatmap Topik × Tahun
Matriks jumlah berita per kombinasi topik × tahun (skala hijau, angka di sel).
Cara baca: peningkatan aktivitas tiap topik antar tahun sekilas terlihat
(mis. 2024–2026 hampir semua topik naik).

### 4 — Tren Tahunan per Topik
Line chart jumlah berita per tahun, warna per topik. Melihat
pertumbuhan/penurunan aktivitas dampak UGM per bidang.

### 5 — Tren Bulanan (musiman)
Bar stacked jumlah berita per bulan kalender (Jan–Des), semua tahun digabung.
Menunjukkan musim aktivitas: mis. kunjungan akademik cenderung ramai di
bulan-bulan tertentu.

### 6 — Cakupan vs Total Berita UGM per Tahun
Dua seri:
- Bar abu-abu = seluruh URL di sitemap ugm.ac.id per tahun (baseline volume
  konten UGM).
- Garis hijau = berita yang match topik dampak.

Cara baca: proporsi garis hijau terhadap bar menunjukkan seberapa besar
konten UGM yang tercatat sebagai aktivitas dampak per tahun. Nilai ini
**lower-bound** karena hanya 4 topik yang dicari dan keyword terbatas.

### 7 — Keyword yang Memicu Match per Topik
Bar horizontal per keyword (dari `scripts/keywords.py`), warna per topik.
Menjawab "berita itu masuk topik karena kata apa?" — mis. kewirausahaan
dominan karena "kewirausahaan"/"wirausaha", bukan "umkm"/"startup".

### 8 — Berita Multi-Topik
Bar distribusi jumlah topik per berita (1, 2, 3). Mayoritas 1 topik; ada
beberapa berita yang masuk 2–3 topik sekaligus (tabel kombinasi di bawahnya).

### 9 — Kata yang Paling Sering Muncul per Topik
Selectbox topik → bar 15 kata teratas dari judul + deskripsi (stopword ID/EN
dibuang). Gambaran isi berita per topik tanpa perlu baca semua.

### 10 — Daftar Berita
Tabel lengkap sesuai filter dengan kolom:
- **Tanggal**, **Judul**, **Sumber**, **Tautan** (klik untuk buka berita asli)
- **Topik** — 1–4 topik dampak berita (bisa lebih dari satu)
- **Topik Kepmen** — topik resmi Kepmen yang dipetakan
- **Indikator Kepmen** — nama indikator resmi
- **SDG** — klaster SDGs (mis. "SDG 8, SDG 9")

### Expander: Berita Tanpa Match Topik (cek manual)
Daftar berita dalam filter yang tidak masuk topik mana pun. Dipakai untuk
cek manual — false positive/negative bisa terjadi karena data sumber
(deskripsi terpotong, keyword tidak lengkap, dll).

## Laporan Statis (tanpa server)

`scripts/laporan_static.py` → `laporan_berita_dampak.html` di root subproject.
Isi: 9 chart (distribusi topik, heatmap topik×tahun, tren tahunan, cakupan vs
total, keyword match, multi-topik, bar topik Kepmen, bar SDG, tren SDG per
tahun) + 4 chart word frequency + tabel indikator resmi Kepmen + tabel 5
contoh berita per topik. Plotly.js di-embed inline → render **tanpa internet**.

Regenerasi setelah ada data baru:

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\python.exe scripts\laporan_static.py
```

Cara paling praktis membagikan ke laptop lain: kirim file
`laporan_berita_dampak.html` (≈4,9 MB) — buka langsung di browser, tidak
perlu server, tidak perlu firewall.

## Alur Data

```
sitemap ugm.ac.id (32.120 URL) ── backfill_sitemap.py ──┐
RSS id/en (10+10 item) ──────── ingest.py ──────────────┤
                                                        ▼
                                    data/ugm_news.duckdb
    fetch_detail.py (filter slug + fetch 4.761 halaman) → berita
    normalisasi.py (bersihkan, dedup)                    → berita
    process_nlp.py (keyword 4 topik)                     → berita_topik
    tag_kepmen_berita.py (peta Kepmen + SDG dari xlsx)   → berita_kepmen, berita_sdg
    tag_kepmen_lengkap.py (eksplorasi 9 tema lain)       → berita_kepmen_lengkap
    laporan_static.py                                    → laporan_berita_dampak.html
```

## Cara Membaca Hasil (caveat)

- Angka bertopik (462 unik / 4.777 berita) adalah **lower-bound**:
  pencarian keyword terbatas pada 4 topik dan deskripsi yang tersedia.
- Berita EN dan ID bisa duplikat konten (terjemahan) — dedup berdasarkan URL,
  bukan konten, sehingga terjemahan dihitung sebagai 2 berita.
- Baseline sitemap mencakup seluruh post UGM, bukan hanya berita — proporsi
  di bagian 6 adalah indikasi kasar, bukan statistik resmi.
- Pemetaan Kepmen & SDG mengikuti template `UGM Analytics.xlsx` — bukan
  hitungan mandiri; klaster SDG adalah atribut resmi topik, jadi semua berita
  dalam satu topik otomatis membawa SDG yang sama (bukan hasil keyword
  matching per berita). Berita di luar 4 topik tidak punya kolom Kepmen/SDG.
- Eksplorasi tema Kepmen lain (bagian 2, expander) adalah keyword-match kasar —
  bukan angka resmi; cek manual sebelum dipakai.
- Periksa daftar "tanpa match" di bagian 10/expander sebelum menarik kesimpulan.
