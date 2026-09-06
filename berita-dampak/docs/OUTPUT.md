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
- Tema dampak (14 tema, multi-select)
- Sumber (sitemap / RSS)
- Pilar Kepmen (Lingkungan / Ekonomi / Sosial)
- Tombol "🔄 Update Berita Terbaru" (jalankan pipeline di background)

**11 bagian:**
1. Ringkasan — 4 kartu: total berita, berita bertema dampak, tema terpilih, rentang tahun
2. Distribusi per Tema Dampak — bar horizontal 14 tema, warna per pilar
3. Peta Tema Resmi Kepmen & Klaster SDGs — bar per Tema Kepmen (warna pilar),
   bar per SDG, heatmap tema×SDG, tren SDG per tahun, heatmap pilar×tahun,
   expander ringkasan per pilar, expander tabel pemetaan + indikator 14 tema
4. Heatmap Tema × Tahun
5. Tren Tahunan per Tema (line)
6. Tren Bulanan (musiman, bar stacked)
7. Cakupan vs Total Berita UGM per Tahun (baseline sitemap)
8. Keyword yang Memicu Match per Tema (bar)
9. Berita Multi-Tema (distribusi + daftar kombinasi)
10. Kata yang Paling Sering Muncul per Tema (word frequency)
11. Daftar Berita — tabel lengkap (tanggal, judul, Tema Kepmen,
    indikator, SDG, sumber, tautan) + expander "berita tanpa match (cek manual)"

## 2. Laporan statis HTML (offline)

File: `berita-dampak/laporan_berita_dampak.html` (±5 MB, plotly JS inline —
buka langsung di browser tanpa server, tanpa internet). Regenerate:

```bash
..\venv\Scripts\python.exe scripts\laporan_static.py
```

Isi: 11 chart + tabel indikator resmi 14 tema + tabel contoh berita per tema.

## 3. Database DuckDB

File: `berita-dampak/data/ugm_news.duckdb` (21 MB).

| Tabel | Isi | Baris (2026-08-20) |
|---|---|---|
| `sitemap` | URL berita ugm.ac.id + lastmod (baseline) | 32.130 |
| `berita` | Judul, tanggal, deskripsi, sumber | 4.787 |
| `berita_topik` | url–tema (4 tema inti) | 1.392 |
| `berita_kepmen_all` | url–topik–dampak–topik_kepmen–sdg (14 tema resmi, sumber utama) | 3.084 baris / 2.369 url unik |
| `berita_sdg_all` | url–sdg (dedup) | 7.739 |
| `ringkasan_topik_all` | jumlah berita unik per tema (dari 14 tema resmi; pengajaran_pembelajaran 0 match) | 14 |
| `ringkasan_pilar` | jumlah berita per pilar | 3 |
| `ringkasan_pilar_tahun` | jumlah berita per pilar per tahun | 65 |
| `ringkasan_sdg_all` | jumlah berita per SDG | 14 |
| `sitemap_sdg` | url–sdg mapping langsung seluruh sitemap (mode SDGs saja) | 22.499 pasangan / 15.688 url unik (48,8%) |
| `ringkasan_sdg_sitemap` | jumlah berita unik per SDG (17 SDG) | 17 |
| `berita_kepmen`, `berita_sdg`, `ringkasan_sdg` | legacy (4 tema inti, tidak dipakai dashboard) | — |
| `berita_kepmen_lengkap`, `ringkasan_kepmen_lengkap` | legacy (eksplorasi 9 tema) | — |

Query manual: `duckdb -readonly data/ugm_news.duckdb` (jangan mode tulis saat
dashboard/update jalan).

## 4. Angka kunci (2026-08-21, lower-bound keyword match)

- Total berita: 4.787 | bertema dampak: **2.369 (49,5%)**
- Per pilar: **Lingkungan 1.105**, **Sosial 1.009**, **Ekonomi 700**
- Tema terbesar: rehabilitasi lingkungan 638, pengabdian masyarakat 635,
  limbah 392, kewirausahaan 303, instansi publik 271, penelitian & inovasi 237,
  kolaborasi riset 219, kunjungan akademik 159, energi 122, pengeluaran
  institusi 53, pendidikan inklusif 33, transportasi 14, pendidikan &
  penelitian 8, pengajaran & pembelajaran 0
- SDG terbesar: SDG 8 (1.050), SDG 17 (1.021), SDG 1 (838), SDG 11 (793),
  SDG 13 (759), SDG 9 (691), SDG 15 (646), SDG 14 (646), SDG 12 (444),
  SDG 6 (392)
- 2.418 berita tidak match — mayoritas berita umum (prestasi, wisuda,
  pengumuman); tersedia di expander cek manual.

## 5. Update otomatis

- **Cron mingguan**: Sabtu 06:00 (job Hermes `update_berita_dampak.sh`),
  log: `logs_update_mingguan.txt`.
- **Tombol dashboard**: sidebar → "🔄 Update Berita Terbaru" (background,
  log: `logs_update_dashboard.txt`).
- `update_mingguan.py` menjalankan 7 langkah pipeline; lock `data/.update_lock`
  mencegah tabrakan; fetch incremental (hanya URL baru).
