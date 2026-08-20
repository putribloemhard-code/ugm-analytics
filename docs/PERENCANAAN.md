# PERENCANAAN — UGM Impact Analytics

## Tujuan

Mengidentifikasi, mengukur, dan memvisualisasikan **dampak UGM** terhadap
Sosial, Ekonomi, dan Lingkungan sesuai **Kepmendikti Saintek 361/M/KEP/2025**
(Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi), serta
memetakannya ke klaster **SDGs**. Data diambil dari sumber publik (ugm.ac.id)
atau data internal kampus — TANPA akses eLOK yang disetujui.

## Prinsip

- **Offline-first**: kerjakan dengan data lokal yang sudah ada; minta izin
  dulu sebelum scraping/network ke eLOK. ugm.ac.id (RSS + sitemap) sudah
  disetujui.
- **Satu sumber kebenaran**: mapping topik → Topik Resmi Kepmen → SDG diambil
  dari `UGM Analytics.xlsx` (sheet "Konten UGM Berdampak" + "#Ref") dan PDF
  Kepmen asli — jangan menebak.
- **Lower-bound & eksplorasi jelas**: angka hasil keyword-match adalah
  batas bawah (bukan angka resmi); label "eksplorasi — cek manual" dipakai
  di dashboard sampai divalidasi.
- **Terse & terdokumentasi**: tiap subproyek punya README + PIPELINE +
  DASHBOARD; semua file terkonsolidasi di folder proyek.

## Backlog ide (dari docs/listing-ide-analisis-dampak.md)

1. ~~Matkul Sustainability~~ — SELESAI (2026-08-12): keyword 9 topik Kepmen
   pada deskripsi matkul → bar per fakultas, drill-down per prodi, tren.
   `matkul-sustainability/`.
2. ~~Berita Dampak~~ — SELESAI (2026-08-18) + diperluas (2026-08-19/20):
   berita ugm.ac.id → 13 topik Kepmen → 3 pilar → SDG.
   `berita-dampak/`. + update otomatis mingguan (cron + tombol dashboard).
3. KKN Desa Binaan — BELUM: folder `kkn-desa-binaan/` kosong; butuh data
   eLOK (kkn.ugm.ac.id / pengabdian.ugm.ac.id/wilayah-binaan/). Perlu izin.
4. Mahasiswa Afirmasi — BELUM: folder `mahasiswa-afirmasi/` kosong; data
   sensitif (tracer study/SIMASTER), perlu akses resmi.

## Milestone berita-dampak

| Tanggal | Capaian |
|---|---|
| 2026-08-18 | Pipeline awal: sitemap (32.120 URL) + RSS + fetch detail (4.777 berita) + tagging 4 topik inti (462 unik) + dashboard + laporan HTML |
| 2026-08-19 | Tagging Kepmen/SDG resmi (berita_kepmen, berita_sdg, ringkasan_sdg); dashboard bagian Peta Kepmen & SDGs; filter pilar; laporan statis 8 chart |
| 2026-08-19 | Setup akses dashboard dari laptop lain: firewall rule 8766, Tailscale |
| 2026-08-20 | 13 topik lengkap (4 inti + 9 tema Kepmen lain) dengan SDG dari sheet #Ref → 1.181 berita unik; pilar Sosial terisi (sebelumnya 0) |
| 2026-08-20 | Perluasan keyword berbasis bukti (validasi sampel, tolak false positive) → 1.969 berita unik |
| 2026-08-20 | Update otomatis: `update_mingguan.py` (lock + incremental fetch), tombol dashboard, cron Senin 06:00 |
| 2026-08-20 | Dokumentasi lengkap + Git repo |

## Roadmap (ide berikutnya)

- Validasi manual sampel berita per topik untuk menaikkan status dari
  "eksplorasi" ke "terverifikasi" (turunkan false positive).
- Ekspor ringkasan per pilar/topik/SDG ke Excel (template Kepmen siap isi).
- Tambah filter fakultas/unit jika metadata berita tersedia.
- KKN Desa Binaan & Mahasiswa Afirmasi — menunggu data/izin.
