# PIPELINE — Analisis Dampak Berita UGM (berita-dampak)

## Tujuan

Mengidentifikasi dan memetakan berita dampak UGM pada 4 topik:
rehabilitasi lingkungan, kewirausahaan, kunjungan akademik, kolaborasi riset.
Sumber data: situs publik ugm.ac.id (RSS + sitemap). Bukan eLOK.

## Alur processing

1. **Backfill sitemap** — `scripts/backfill_sitemap.py`
   Ambil seluruh `post-sitemapN.xml` dari `https://ugm.ac.id/wp-sitemap.xml`.
   Simpan (url, lastmod) ke tabel `sitemap` di `data/ugm_news.duckdb`.
   Idempoten (INSERT OR IGNORE), ada retry otomatis per sitemap.
   Hasil: ~32.000 URL berita (2007–2026).

2. **Ingest RSS** — `scripts/ingest.py`
   Ambil feed `https://ugm.ac.id/id/feed/` dan `/en/feed/` (10 item masing-masing)
   dengan judul, tanggal, kategori, deskripsi. Simpan ke tabel `berita` (sumber='rss').

3. **Fetch detail** — `scripts/fetch_detail.py`
   Filter URL sitemap yang slug-nya cocok kata kunci topik (ID+EN),
   lalu fetch halaman untuk mengambil judul (h1), deskripsi (meta description),
   tanggal (datePublished). Simpan ke tabel `berita` (sumber='sitemap').
   ~4.700 URL relevan; throttle 0,3 detik + retry.

4. **Normalisasi** — `scripts/normalisasi.py`
   Bersihkan teks, konversi tanggal (RFC 822 / ISO 8601 → YYYY-MM-DD),
   buang duplikat URL dan baris tanpa judul.

5. **Tagging topik** — `scripts/process_nlp.py`
   Substring match (case-insensitive) kamus `scripts/keywords.py`
   terhadap judul + deskripsi. Satu berita bisa multi-topik.
   Output: tabel `berita_topik` (url, topik) dan `ringkasan_topik_tahun`.

6. **Tagging Kepmen & SDG — SEMUA tema (14 tema)** — `scripts/tag_kepmen_all.py`
   Map tiap berita ke 14 tema resmi Kepmen 361/M/KEP/2025: 4 topik inti
   (rehabilitasi_lingkungan, kewirausahaan, kunjungan_akademik, kolaborasi_riset
   — keyword dari `scripts/keywords.py`) + 9 tema lain (pendidikan inklusif,
   penelitian & inovasi, pengabdian masyarakat, instansi publik, pengajaran &
   pembelajaran, belanja UMKM, energi, limbah, transportasi — keyword dari
   `TEMA_KEPMEN_LENGKAP` di `scripts/kepmen_sdg.py`). Tiap topik membawa pilar
   (Lingkungan/Ekonomi/Sosial) + klaster SDGs resmi dari `UGM Analytics.xlsx`
   (sheet "Konten UGM Berdampak" & "#Ref").
   Output tabel baru (menggantikan berita_kepmen/berita_sdg sebagai sumber
   dashboard):
   - `berita_kepmen_all` (url, topik, dampak, topik_kepmen, sdg '13|14|15')
   - `berita_sdg_all` (url, sdg — dedup per url)
   - `ringkasan_topik_all` (topik, dampak, topik_kepmen, sdg, jumlah_berita)
   - `ringkasan_pilar` (dampak, jumlah_berita)
   - `ringkasan_pilar_tahun` (dampak, tahun, jumlah_berita)
   - `ringkasan_sdg_all` (sdg, nama_sdg, jumlah_berita)
   Tabel lama (berita_kepmen, berita_sdg, berita_kepmen_lengkap,
   ringkasan_kepmen_lengkap) tetap ada di DB tapi tidak dipakai dashboard.

7. **Output**
   - `dashboard_berita_dampak.py` — Streamlit interaktif dengan filter global
     (tahun, topik, sumber). Bagian: ringkasan, distribusi per topik,
     peta Topik Resmi Kepmen & klaster SDGs (bar + heatmap topik×SDG),
     heatmap topik×tahun, tren tahunan, tren bulanan (musiman),
     cakupan vs total berita UGM (baseline sitemap), breakdown keyword match,
     multi-topik, word frequency per topik, daftar berita (dengan kolom
     Topik Kepmen & SDG), cek manual.
   - `scripts/laporan_static.py` → `laporan_berita_dampak.html`
     (plotly write_html, JS inline — render tanpa internet)

## Run commands (dari folder berita-dampak)

```bash
../venv/Scripts/python.exe scripts/backfill_sitemap.py
../venv/Scripts/python.exe scripts/ingest.py
../venv/Scripts/python.exe scripts/fetch_detail.py   # lama: ~4.700 halaman
../venv/Scripts/python.exe scripts/normalisasi.py
../venv/Scripts/python.exe scripts/process_nlp.py
../venv/Scripts/python.exe scripts/tag_kepmen_all.py   # 14 tema + SDG (utama)
../venv/Scripts/python.exe scripts/tag_kepmen_berita.py   # legacy: 4 topik inti saja
../venv/Scripts/python.exe scripts/tag_kepmen_lengkap.py  # legacy: 9 tema eksplorasi
../venv/Scripts/python.exe scripts/laporan_static.py
streamlit run dashboard_berita_dampak.py
```

## Hasil (terakhir dijalankan: 2026-08-20)

- sitemap: 32.130 URL berita (2005–2026)
- berita di tabel: 4.787 (20 dari RSS, sisanya fetch detail sitemap)
- tagging 14 tema Kepmen (tag_kepmen_all.py):
  - 2.481 baris url–tema; 1.969 berita unik match ≥1 tema (41% dari 4.787)
  - per pilar: Lingkungan 1.094, Sosial 631, Ekonomi 577
  - per topik: rehabilitasi lingkungan 653, limbah 379, kewirausahaan 374,
    pengabdian masyarakat 374, penelitian & inovasi 179, kolaborasi riset 138,
    instansi publik 124, energi 109, kunjungan akademik 70, belanja UMKM 31,
    pendidikan inklusif 20, transportasi 15
  - SDG terbanyak: SDG 13 (755), SDG 8 (703), SDG 9 (659), SDG 14 (651),
    SDG 15 (651), SDG 17 (608), SDG 1 (538), SDG 11 (457), SDG 12 (408)
- 2026-08-20 (perluasan keyword): keywords.py + TEMA_KEPMEN_LENGKAP diperluas
  (hutan/forest/kehutanan/mangrove → rehabilitasi; entrepreneur/research
  collaboration/joint research → ekonomi; community service/kementerian/solar/
  plastic/plastik → tema terkait). Hasil: 1.181 → 1.969 berita unik.
  Kandidat yang DITOLAK karena false positive: delegation (prestasi lomba),
  desa/village (generik), kebijakan/policy (generik), nuclear.
- 2026-08-20 (update otomatis): `scripts/update_mingguan.py` menjalankan
  pipeline lengkap (lock file data/.update_lock mencegah tumpang tindih);
  dashboard punya tombol "🔄 Update Berita Terbaru" (sidebar, jalankan
  background); cron Hermes Sabtu 06:00 (update_berita_dampak.sh).
  fetch_detail incremental: hanya URL yang belum ada (dibandingkan dalam
  bentuk bersih — rtrim '/' + split '?' — karena sitemap menyimpan URL mentah
  sedangkan normalisasi menyimpan versi bersih; kalau dibandingkan mentah,
  semua URL dianggap baru → duplikat). normalisasi dedup URL bersih.
  Terverifikasi: run penuh exit 0 (13 menit), 4.787 berita, AppTest OK.
- indikator resmi per topik (nama + formula + satuan) dari hasil OCR PDF
  Kepmen (`docs/kepmen_361_ocr.txt`); tampil di expander dashboard + tabel
  laporan statis (14 tema)

## Caveat

- REST API wp-json diblokir (401) — tidak bisa dipakai; fetch halaman manual.
- Situs ugm.ac.id sering timeout; script sudah punya retry.
- Keyword slug bisa memunculkan false positive (mis. "usaha" di nama lembaga);
  daftar "tidak match" tersedia di dashboard untuk cek manual.
- Berita EN (ugm.ac.id/en) dan ID (ugm.ac.id/id) bisa duplikat konten
  (terjemahan). Dedup berdasarkan URL, bukan konten.
- Baseline sitemap mencakup semua post UGM (bukan hanya berita) — proporsi
  di chart "Cakupan vs Total" adalah indikasi kasar.
- Angka bertopik adalah lower-bound: keyword terbatas pada 14 tema + deskripsi
  yang tersedia di halaman.

## Re-tagging keyword berbasis detailing tabel Kepmen (2026-08-21)

Semua keyword mapping (dampak/pilar, topik Kepmen, SDG) dirombak agar
bersumber dari detailing indikator tiap tema di TABEL Kepmen 361
(bagian "DEFINISI, KRITERIA, KETENTUAN, DAN FORMULA", OCR:
`docs/kepmen_361_ocr.txt`) — bukan dugaan/istilah umum. Prinsip:

1. Keyword = istilah yang benar-benar muncul di detailing tema itu
   (nama tema, definisi, kriteria, ketentuan). Istilah di luar detailing
   DIBUANG, mis.: ekosistem/habitat/wildlife/deforestasi (kehati),
   umkm/smes (kewirausahaan — itu tema Pengabdian/Pengeluaran Institusi),
   polusi/pencemaran/microplastic/biodegradable (limbah),
   regulasi (kebijakan publik), bangunan hijau/net zero/karbon/biodiesel/
   transisi energi (energi), bus kampus/shuttle/trans jogja/transportasi
   publik/kampus hijau (transportasi), studi banding/delegasi/guest lecture
   (kunjungan akademik), bazar/pasar/pemberdayaan umkm (belanja UMKM),
   riset untuk masyarakat/penelitian terapan/applied research/science for
   society (penelitian & inovasi sosial).
2. Keyword baru dari detailing yang masuk: reboisasi, lahan kritis, ruang
   terbuka hijau, erosi, banjir (kehati); hilirisasi, paten, lisensi, royalti,
   komersialisasi, HKI, prototipe (kolaborasi riset); wisuda, seminar,
   konferensi, simposium, lomba, festival, gathering alumni (kunjungan
   akademik); PLTS, mikrohidro, emisi, kendaraan listrik (energi); pupuk
   organik, ekonomi sirkular, IPAL, komposting (limbah); BUMDes, ketahanan
   pangan, digitalisasi desa (pengabdian); puskesmas, pemerintah desa,
   kelurahan (kebijakan publik).
3. Kata luas yang = materi lintas-tema TIDAK dipakai (93/160 match tema
   "Pendidikan & Penelitian" ternyata noise berita umum lewat kata
   pembangunan berkelanjutan/perubahan iklim/sustainability — dibuang;
   tersisa 8 berita matkul/modul/ESD).
4. Token pendek (≤5 huruf) otomatis word boundary di `tag_kepmen_all.py`
   (proven: "paten" substring-match "kabupaten" 190x → \bpaten\b 2x relevan).

Hasil re-tag (DuckDB, 2026-08-21): 3.084 baris url–tema / 2.369 berita unik
bertopik (49,5%); pilar Lingkungan 1.105, Sosial 1.009, Ekonomi 700; topik
terbesar rehabilitasi_lingkungan 638, pengabdian_masyarakat 635, limbah 392,
kewirausahaan 303; SDG terbesar SDG 8 (1.050), 17 (1.021), 1 (838), 13 (759).

## Pengembangan dashboard (2026-08-20 — 14 tema / 3 pilar lengkap)

Sosial pilar sebelumnya kosong (3 topik inti = Ekonomi, 1 = Lingkungan).
Sekarang: tagging SEMUA berita ke 14 tema Kepmen (4 inti + 9 tema lain)
via `tag_kepmen_all.py`; klaster SDG 9 tema lain diisi dari sheet "#Ref"
(sebelumnya kosong). Dashboard: filter topik & pilar berlaku ke 14 tema;
bagian baru "Ringkasan per pilar"; peta Kepmen + SDG mencakup semua tema;
expander eksplorasi lama diganti tabel 14 tema. Hasil: 1.181 berita unik
(Lingkungan 547, Sosial 473, Ekonomi 373). Laporan statis disinkronkan
(11 chart + tabel 14 tema). Verifikasi: AppTest default + filter pilar
Sosial tanpa exception; Streamlit HTTP 200.

## Pengembangan dashboard (2026-08-19)

Dashboard diperluas dari 5 bagian menjadi 12 (lihat DASHBOARD.md):
peta Topik Resmi Kepmen & klaster SDGs (bar per topik Kepmen + bar per SDG +
heatmap topik×SDG + tabel pemetaan resmi), heatmap topik×tahun, tren bulanan,
cakupan vs total berita UGM, breakdown keyword, multi-topik, word frequency,
filter global di sidebar; daftar berita kini menampilkan kolom Topik Kepmen &
SDG. Laporan statis disinkronkan (8 chart + word frequency).
Verifikasi: AppTest 3 skenario (default, 1 topik, rentang tahun) tanpa
exception; Streamlit HTTP 200.

Referensi resmi di folder `sumber/`:
- `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` — Kepmen asli
  (scan; hasil OCR: `docs/kepmen_361_ocr.txt`, via `scripts/ocr_kepmen.py`)
- `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf` — buku IKU (12 IKU, detail)
- `sumber/UGM Analytics.xlsx` — template pengumpulan data + sheet `#Ref` (pemetaan
  Dampak → Topik Kepmen → SDGs), sumber mapping `scripts/kepmen_sdg.py`
