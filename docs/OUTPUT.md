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
- Topik dampak (13 topik, multi-select)
- Sumber (sitemap / RSS)
- Pilar Kepmen (Lingkungan / Ekonomi / Sosial)
- Tombol "🔄 Update Berita Terbaru" (jalankan pipeline di background)

**11 bagian:**
1. Ringkasan — 4 kartu: total berita, berita bertopik dampak, topik terpilih, rentang tahun
2. Distribusi per Topik Dampak — bar horizontal 13 topik, warna per pilar
3. Peta Topik Resmi Kepmen & Klaster SDGs — bar per Topik Kepmen (warna pilar),
   bar per SDG, heatmap topik×SDG, tren SDG per tahun, heatmap pilar×tahun,
   expander ringkasan per pilar, expander tabel pemetaan + indikator 13 topik
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

Isi: 11 chart + tabel indikator resmi 13 topik + tabel contoh berita per topik.

## 3. Database DuckDB

File: `berita-dampak/data/ugm_news.duckdb` (21 MB).

| Tabel | Isi | Baris (2026-08-20) |
|---|---|---|
| `sitemap` | URL berita ugm.ac.id + lastmod (baseline) | 32.130 |
| `berita` | Judul, tanggal, deskripsi, sumber | 4.787 |
| `berita_topik` | url–topik (4 topik inti) | 1.233 |
| `berita_kepmen_all` | url–topik–pilar–topik_kepmen–sdg (13 topik, sumber utama) | 2.481 |
| `berita_sdg_all` | url–sdg (dedup) | — |
| `ringkasan_topik_all` | jumlah berita per 13 topik | 12 |
| `ringkasan_pilar` | jumlah berita per pilar | 3 |
| `ringkasan_pilar_tahun` | jumlah berita per pilar per tahun | — |
| `ringkasan_sdg_all` | jumlah berita per SDG | 14 |
| `berita_kepmen`, `berita_sdg`, `ringkasan_sdg` | legacy (4 topik inti, tidak dipakai dashboard) | — |
| `berita_kepmen_lengkap`, `ringkasan_kepmen_lengkap` | legacy (eksplorasi 9 tema) | — |

Query manual: `duckdb -readonly data/ugm_news.duckdb` (jangan mode tulis saat
dashboard/update jalan).

## 4. Angka kunci (2026-08-20, lower-bound keyword match)

- Total berita: 4.787 | bertopik dampak: **1.969 (41%)**
- Per pilar: **Lingkungan 1.094**, **Sosial 631**, **Ekonomi 577**
- Topik terbesar: rehabilitasi lingkungan 653, limbah 379, kewirausahaan 374,
  pengabdian masyarakat 374, penelitian & inovasi 179, kolaborasi riset 138,
  instansi publik 124, energi 109, kunjungan akademik 70, belanja UMKM 31,
  pendidikan inklusif 20, transportasi 15
- SDG terbesar: SDG 13 (755), SDG 8 (703), SDG 9 (659), SDG 14 (651),
  SDG 15 (651), SDG 17 (608), SDG 1 (538)
- 2.818 berita tidak match — mayoritas berita umum (prestasi, wisuda,
  pengumuman); tersedia di expander cek manual.

## 5. Update otomatis

- **Cron mingguan**: Senin 06:00 (job Hermes `update_berita_dampak.sh`),
  log: `logs_update_mingguan.txt`.
- **Tombol dashboard**: sidebar → "🔄 Update Berita Terbaru" (background,
  log: `logs_update_dashboard.txt`).
- `update_mingguan.py` menjalankan 7 langkah pipeline; lock `data/.update_lock`
  mencegah tabrakan; fetch incremental (hanya URL baru).
