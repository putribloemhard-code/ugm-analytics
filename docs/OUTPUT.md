# OUTPUT — Apa yang Dihasilkan (berita-dampak)

## 1. Dashboard Streamlit (interaktif)

File: `berita-dampak/dashboard_berita_dampak.py` — jalankan:

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\streamlit run dashboard_berita_dampak.py
```

Buka http://localhost:8766. Fitur:

**Sidebar filter global** (berlaku ke semua bagian):
- Rentang tahun (slider, 2005–2026)
- Topik dampak (14 tema, multi-select)
- Sumber (sitemap / RSS)
- Pilar Kepmen (Lingkungan / Ekonomi / Sosial)
- Tombol "🔄 Update Berita Terbaru" (jalankan pipeline di background)

**11 bagian:**
1. Ringkasan — 4 kartu: total berita, berita bertopik dampak, topik terpilih, rentang tahun
2. Distribusi per Topik Dampak — bar horizontal 14 tema, warna per pilar
3. Peta Topik Resmi Kepmen & Klaster SDGs — bar per Topik Kepmen (warna pilar),
   bar per SDG, heatmap topik×SDG, tren SDG per tahun, heatmap pilar×tahun,
   expander ringkasan per pilar, expander tabel pemetaan + indikator 14 tema
4. Heatmap Topik × Tahun
5. Tren Tahunan per Topik (line)
6. Tren Bulanan (musiman, bar stacked)
7. Cakupan vs Total Berita UGM per Tahun (baseline sitemap)
8. Keyword yang Memicu Match per Topik (bar)
9. Berita Multi-Topik (distribusi + daftar kombinasi)
10. Kata yang Paling Sering Muncul per Topik (word frequency)
11. Daftar Berita — tabel lengkap (tanggal, judul, topik, Topik Kepmen,
    indikator, SDG, sumber, tautan) + expander "berita tanpa match (cek manual)"

## 2. Laporan statis HTML (offline)

File: `berita-dampak/laporan_berita_dampak.html` (±5 MB, plotly JS inline —
buka langsung di browser tanpa server, tanpa internet). Regenerate:

```bash
..\venv\Scripts\python.exe scripts\laporan_static.py
```

Isi: 11 chart + tabel indikator resmi 14 tema + tabel contoh berita per topik.

## 3. Database DuckDB

File: `berita-dampak/data/ugm_news.duckdb` (21 MB).

| Tabel | Isi | Baris (2026-08-20) |
|---|---|---|
| `sitemap` | URL berita ugm.ac.id + lastmod (baseline) | 32.130 |
| `berita` | Judul, tanggal, deskripsi, sumber | 4.787 |
| `berita_topik` | url–topik (4 topik inti) | 1.392 |
| `berita_kepmen_all` | url–topik–dampak–topik_kepmen–sdg (14 tema resmi, sumber utama) | 3.084 baris / 2.369 url unik |
| `berita_sdg_all` | url–sdg (dedup) | 7.739 |
| `ringkasan_topik_all` | jumlah berita unik per tema (dari 14 tema resmi; pengajaran_pembelajaran 0 match) | 13 |
| `ringkasan_pilar` | jumlah berita per pilar | 3 |
| `ringkasan_pilar_tahun` | jumlah berita per pilar per tahun | 65 |
| `ringkasan_sdg_all` | jumlah berita per SDG | 14 |
| `berita_kepmen`, `berita_sdg`, `ringkasan_sdg` | legacy (4 topik inti, tidak dipakai dashboard) | — |
| `berita_kepmen_lengkap`, `ringkasan_kepmen_lengkap` | legacy (eksplorasi 9 tema) | — |

Query manual: `duckdb -readonly data/ugm_news.duckdb` (jangan mode tulis saat
dashboard/update jalan).

## 4. Angka kunci (2026-08-21, lower-bound keyword match)

- Total berita: 4.787 | bertopik dampak: **2.393 (50%)**
- Per pilar: **Lingkungan 1.165**, **Sosial 1.017**, **Ekonomi 692**
- Topik terbesar: rehabilitasi lingkungan 696, pengabdian masyarakat 616,
  kewirausahaan 410, limbah 403, instansi publik 271, penelitian & inovasi 264,
  kolaborasi riset 172, energi 135, kunjungan akademik 114, belanja UMKM 61,
  pendidikan inklusif 33, transportasi 21
- SDG terbesar: SDG 8 (1.009), SDG 17 (976), SDG 1 (844), SDG 13 (825),
  SDG 9 (794), SDG 11 (745)
- 2.394 berita tidak match — mayoritas berita umum (prestasi, wisuda,
  pengumuman); tersedia di expander cek manual.

## 5. Update otomatis

- **Cron mingguan**: Sabtu 06:00 (job Hermes `update_berita_dampak.sh`),
  log: `logs_update_mingguan.txt`.
- **Tombol dashboard**: sidebar → "🔄 Update Berita Terbaru" (background,
  log: `logs_update_dashboard.txt`).
- `update_mingguan.py` menjalankan 7 langkah pipeline; lock `data/.update_lock`
  mencegah tabrakan; fetch incremental (hanya URL baru).
