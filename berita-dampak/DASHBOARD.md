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
| `berita_topik` | 471 pasangan url–tema (4 tema inti; 1 berita bisa multi-tema) |
| `ringkasan_topik_tahun` | jumlah berita per tema per tahun |
| `berita_kepmen_all` | 1.487 pasangan url–tema (14 tema Kepmen) + pilar + sdg — sumber utama dashboard |
| `berita_sdg_all` | pasangan url–SDG dedup (semua 14 tema) |
| `ringkasan_topik_all` | jumlah berita unik per 14 tema (topik, pilar, topik_kepmen, sdg) |
| `ringkasan_pilar` | jumlah berita unik per pilar (Lingkungan/Ekonomi/Sosial) |
| `ringkasan_pilar_tahun` | jumlah berita per pilar per tahun |
| `ringkasan_sdg_all` | jumlah berita unik per SDG (semua 14 tema) |
| `sitemap_sdg` | pasangan url–SDG mapping LANGSUNG seluruh 32.130 URL sitemap (mode "SDGs saja"; slug + judul/deskripsi) |
| `ringkasan_sdg_sitemap` | jumlah berita unik per SDG (17 SDG) dari sitemap_sdg |
| `ringkasan_sdg_sitemap_tahun` | jumlah berita per SDG per tahun (lastmod sitemap) |
| `berita_kepmen`, `berita_sdg`, `ringkasan_sdg` | legacy: 4 tema inti saja (masih ada, tidak dipakai dashboard) |
| `berita_kepmen_lengkap`, `ringkasan_kepmen_lengkap` | legacy: eksplorasi 9 tema (tidak dipakai dashboard) |

Data dimuat dengan cache Streamlit (`@st.cache_data`, TTL 300 detik).

## Sidebar: Filter Global

Semua chart dan tabel di bawah mengikuti filter; ringkasan dihitung ulang
sesuai filter.

- **Mode analisis** — radio 3 mode:
  - *Berdampak* — 3 pilar & 14 tema Kepmen, tanpa bagian SDG.
  - *Berdampak × SDGs* — tampilan penuh sekarang (tema + SDG dari berita bertema).
  - *SDGs saja* — mapping LANGSUNG seluruh 32.130 URL berita sitemap ke 17 SDG
    (tanpa tema dampak; teks = slug URL + judul/deskripsi yang sudah di-fetch).
- **Rentang tahun** — select slider, default seluruh data (2005–2026).
- **Filter mengikuti mode**: mode *Berdampak* / *Berdampak × SDGs* menampilkan
  filter **Tema dampak**, **Sumber**, **Pilar dampak (Kepmen)**; mode *SDGs saja*
  menampilkan filter **SDG (17)** (multi-select, contoh "SDG 4 — Pendidikan
  Berkualitas") — bukan filter tema.

## Isi Dashboard

### Ringkasan (4 kartu)
1. Total berita (sesuai filter).
2. Berita bertema dampak — jumlah berita unik yang match ≥ 1 dari 14 tema.
3. Tema terpilih — berapa tema yang aktif di filter.
4. Rentang tahun — rentang yang sedang difilter.

### 1 — Distribusi per Tema Dampak
Bar horizontal jumlah berita unik per 14 tema, warna per pilar. Semua 14
tema selalu tampil — tema tanpa match (pengajaran & pembelajaran) muncul
dengan jumlah 0, bukan hilang dari chart.
Saat ini: rehabilitasi lingkungan (638), pengabdian masyarakat (635), limbah
(392), kewirausahaan (303), instansi publik (271), penelitian & inovasi (237),
kolaborasi riset (219), kunjungan akademik (159), energi (122), pengeluaran
institusi (53), pendidikan inklusif (33), transportasi (14), pendidikan &
penelitian (8), pengajaran & pembelajaran (0).

### 2 — Peta Tema Resmi Kepmen & Klaster SDGs
Menjawab "berita ini masuk indikator Kepmen yang mana dan SDGs berapa".
Pemetaan Kepmendikti Saintek 361/M/KEP/2025 (dari `UGM Analytics.xlsx`
sheet "Konten UGM Berdampak" & "#Ref", divalidasi dengan PDF Kepmen asli).
14 tema:

| Tema berita | Pilar | Tema Resmi Kepmen | Klaster SDGs |
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
| Pengeluaran Institusi | Ekonomi | Pengeluaran Institusi | SDG 8, 12 |
| Energi & Infrastruktur | Lingkungan | Energi dan Infrastruktur Ramah Lingkungan | SDG 7, 13 |
| Limbah & Daur Ulang | Lingkungan | Pengelolaan Limbah dan Daur Ulang | SDG 6, 12 |
| Mobilitas Ramah Lingkungan | Lingkungan | Mobilitas Ramah Lingkungan (Transportasi) | SDG 11, 13 |
| Pendidikan dan Penelitian | Lingkungan | Pendidikan dan Penelitian | SDG 14, 15 |

Sub-bagian di dalamnya:
- **Bar Tema Resmi Kepmen** — jumlah berita per tema Kepmen, warna per pilar
  (hijau = Lingkungan, biru = Ekonomi, oranye = Sosial).
- **Bar per SDG** — berapa berita unik masuk tiap SDG. Saat ini: SDG 8 (1.050),
  SDG 17 (1.021), SDG 1 (838), SDG 11 (793), SDG 13 (759), SDG 9 (691),
  SDG 15 (646), SDG 14 (646), SDG 12 (444), SDG 6 (392).
- **Heatmap Tema Dampak × SDG** — kombinasi tema dan SDG; sel kosong =
  tema itu tidak memetakan ke SDG tersebut.
- **Tren SDG per Tahun** — line chart jumlah berita per SDG per tahun.
- **Heatmap Pilar Dampak × Tahun** — jumlah berita per pilar per tahun.
- **Expander: Ringkasan per pilar dampak** — kartu metrik + bar 3 pilar
  (Lingkungan 1.105, Ekonomi 700, Sosial 1.009 saat ini).
- **Expander: tabel pemetaan resmi + indikator Kepmen (14 tema)** — mapping
  lengkap + nama indikator resmi, formula, satuan (sesuai PDF Kepmen).

Indikator resmi Kepmen per tema (dari
`Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf`, hasil OCR di
`D:\\ugm-analytics\\docs\\kepmen_361_ocr.txt`):

| Tema berita | Indikator Kepmen | Formula | Satuan |
|---|---|---|---|
| Rehabilitasi Lingkungan | Jumlah program rehabilitasi dan restorasi lingkungan PT | Jumlah program rehabilitasi/restorasi pada periode berjalan | Program |
| Kewirausahaan | Jumlah entitas spin-off/start-up dari PT yang masih aktif | Jumlah entitas dari hasil riset/inkubasi yang aktif beroperasi | Entitas |
| Kunjungan Akademik | Jumlah pengeluaran pengunjung kegiatan akademik | Rata-rata pengeluaran per pengunjung (Rp) × jumlah pengunjung | Rupiah |
| Kolaborasi Riset | Pendapatan PT dari hilirisasi riset/spin-off dengan industri & pemerintah | Jumlah pendapatan hilirisasi riset/paten/prototipe/spin-off | Rupiah |

### 3 — Heatmap Tema × Tahun
Matriks jumlah berita per kombinasi tema × tahun (skala hijau, angka di sel).
Cara baca: peningkatan aktivitas tiap tema antar tahun sekilas terlihat
(mis. 2024–2026 hampir semua tema naik).

### 4 — Tren Tahunan per Tema
Line chart jumlah berita per tahun, warna per tema. Melihat
pertumbuhan/penurunan aktivitas dampak UGM per bidang.

### 5 — Tren Bulanan (musiman)
Bar stacked jumlah berita per bulan kalender (Jan–Des), semua tahun digabung.
Menunjukkan musim aktivitas: mis. kunjungan akademik cenderung ramai di
bulan-bulan tertentu.

### 6 — Cakupan vs Total Berita UGM per Tahun
Dua seri:
- Bar abu-abu = seluruh URL di sitemap ugm.ac.id per tahun (baseline volume
  konten UGM).
- Garis hijau = berita yang match tema dampak.

Cara baca: proporsi garis hijau terhadap bar menunjukkan seberapa besar
konten UGM yang tercatat sebagai aktivitas dampak per tahun. Nilai ini
**lower-bound** karena pencarian keyword terbatas (14 tema) dan deskripsi
yang tersedia.

### 7 — Keyword yang Memicu Match per Tema
Bar horizontal per keyword (dari `scripts/keywords.py`), warna per tema.
Menjawab "berita itu masuk tema karena kata apa?" — mis. kewirausahaan
dominan karena "kewirausahaan"/"wirausaha", bukan "umkm"/"startup".

### 8 — Berita Multi-Tema
Bar distribusi jumlah tema per berita (1, 2, 3). Mayoritas 1 tema; ada
beberapa berita yang masuk 2–3 tema sekaligus (tabel kombinasi di bawahnya).

### 9 — Kata yang Paling Sering Muncul per Tema
Selectbox tema → bar 15 kata teratas dari judul + deskripsi (stopword ID/EN
dibuang). Gambaran isi berita per tema tanpa perlu baca semua.

### 10 — Daftar Berita
Tabel lengkap sesuai filter dengan kolom:
- **Tanggal**, **Judul**, **Sumber**, **Tautan** (klik untuk buka berita asli)
- **Tema Kepmen** — tema resmi Kepmen yang dipetakan
- **Indikator Kepmen** — nama indikator resmi
- **SDG** — klaster SDGs (mis. "SDG 8, SDG 9")

### Expander: Berita Tanpa Match Tema (cek manual)
Daftar berita dalam filter yang tidak masuk tema mana pun. Dipakai untuk
cek manual — false positive/negative bisa terjadi karena data sumber
(deskripsi terpotong, keyword tidak lengkap, dll).

## Mode "SDGs saja" (seluruh 32.130 URL)

Menu Mode analisis → *SDGs saja*. Mapping langsung url berita sitemap ke
17 SDG TANPA tema dampak Kepmen — jangkauan jauh lebih luas (15.688 / 32.130
= 48,8% URL bertanda ≥1 SDG, vs 2.369 berita bertema). Teks yang dicocokkan:
kata-kata slug URL (untuk 27.343 yang belum di-fetch) + judul & deskripsi
(untuk 4.787 yang sudah). Satu berita bisa masuk beberapa SDG. Kamus:
`scripts/sdg_keywords.py` (17 SDG, ID+EN, dari nama resmi & target SDG).
Bagian: metrik cakupan, bar distribusi per SDG (17), tren SDG per tahun,
heatmap SDG × tahun, tabel ringkasan per SDG, expander "Lihat keyword per
SDG", cek manual berita tanpa tanda SDG. Filter sidebar mode ini = **SDG (17)**
multi-select (bukan tema dampak) — metrik & grafik mengikuti SDG terpilih.

## Laporan Statis (tanpa server)

`scripts/laporan_static.py` → `laporan_berita_dampak.html` di root subproject.
Isi: 9 chart (distribusi tema, heatmap tema×tahun, tren tahunan, cakupan vs
total, keyword match, multi-tema, bar tema Kepmen, bar SDG, tren SDG per
tahun) + 4 chart word frequency + tabel indikator resmi Kepmen + tabel 5
contoh berita per tema. Plotly.js di-embed inline → render **tanpa internet**.

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

- Angka bertema (2.369 unik / 4.787 berita) adalah **lower-bound**:
  pencarian keyword terbatas pada 14 tema dan deskripsi yang tersedia.
- Berita EN dan ID bisa duplikat konten (terjemahan) — dedup berdasarkan URL,
  bukan konten, sehingga terjemahan dihitung sebagai 2 berita.
- Baseline sitemap = SEMUA berita situs (32.130 URL: 19.223 /id/berita/ +
  12.907 /en/news/; ID & EN adalah terjemahan konten sama). `berita` di tabel
  hanya subset yang slug-nya cocok keyword tema (fetch_detail) — proporsi di
  bagian 6 adalah indikasi kasar, bukan statistik resmi.
- Pemetaan Kepmen & SDG mengikuti template `UGM Analytics.xlsx` — bukan
  hitungan mandiri; klaster SDG adalah atribut resmi tema, jadi semua berita
  dalam satu tema otomatis membawa SDG yang sama (bukan hasil keyword
  matching per berita). Berita di luar 4 tema tidak punya kolom Kepmen/SDG.
- Eksplorasi tema Kepmen lain (bagian 2, expander) adalah keyword-match kasar —
  bukan angka resmi; cek manual sebelum dipakai.
- Periksa daftar "tanpa match" di bagian 10/expander sebelum menarik kesimpulan.
