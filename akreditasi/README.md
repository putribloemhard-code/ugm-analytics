# Akreditasi — Kelengkapan Data LED & LKPS

Registry status kelengkapan data untuk penyusunan LED (Laporan Evaluasi Diri)
dan LKPS (Laporan Kinerja Program Studi), instrumen LAM-INFOKOM. Sumber
kebutuhan data: `docs/Data_Requirements_LED_LKPS_MEI.md`.

Subproyek ini **berdiri sendiri**, tidak menyentuh `berita-dampak/` atau
`matkul-sustainability/` (walau memakai database MySQL yang sama, lihat
"Penyimpanan data" di bawah).

**Cakupan data saat ini (2026-09-19, kueri MySQL):** 20 fakultas · 18 prodi
(seluruhnya FMIPA, termasuk Magister Elektronika dan Instrumentasi) · 198 baris
status item · 118 baris data manual terisi · 2 user · 1 file terupload.
Dokumen requirement awal hanya mencakup satu prodi (MEI), tetapi kode dan skema
sudah **multi-prodi** (`akreditasi_fakultas`, `akreditasi_prodi`) sehingga prodi
lain bisa ditambah tanpa mengubah struktur.

## Isi folder

| File / folder | Isi |
|---|---|
| `scripts/db.py` | Koneksi MySQL bersama (engine, retry) -- adaptasi `berita-dampak/scripts/db.py`, prefix tabel `akreditasi_` |
| `scripts/registry_kebutuhan_data.py` | **Satu sumber kebenaran (Fase 1)**: 49 item data yang dibutuhkan LED/LKPS (28 tabel LKPS + 3 tabel D1-D3 + 18 narasi LED), status ketersediaan, sumber data resmi per item |
| `data_source_map.json` | **Peta status sumber (Fase 1, 2026-09-11)**: 61 item — 5 `tersedia`, 41 `tidak_tersedia_akses_data`, 15 `tidak_tersedia_perlu_penyusunan_manusia`. PDF LED/LKPS lama HANYA dipakai untuk struktur item (kode/nama/kriteria/tabel), bukan isi |
| `scripts/pipeline_item_tersedia.py` | **Fase 2**: data live untuk 5 item "tersedia" (identitas PT/UPPS/PS, status akreditasi PS, VMTS, dst.) → `akreditasi_item_tersedia` (snapshot penuh tiap run) |
| `scripts/pipeline_sinta.py` | **Fase 2**: tarik daftar publikasi Scopus (10 terbaru/dosen) dari sinta.kemdiktisaintek.go.id → `akreditasi_publikasi_dosen` (akumulatif, upsert) |
| `scripts/pipeline_dcse_berita.py` | **Fase 2**: crawl arsip RSS dcse.fmipa.ugm.ac.id → `akreditasi_berita_dcse` (evidence pendukung lkps_2_d & lkps_4_c_2) |
| `scripts/ekstraksi_pattern.py` | **Fase 3**: tier ekstraksi TANPA AI (pattern-matching struktur dokumen) — dicoba lebih dulu untuk item berstruktur daftar berulang |
| `scripts/ekstraksi_akreditasi.py` | **Fase 3**: tier fallback LLM (per batch item registry); hasil = PREVIEW, user review dulu |
| `scripts/validasi_ekstraksi_pattern.py` | Validasi manual tier pattern untuk 2 bentuk tabel berbeda (vertikal LED vs horizontal LKPS) |
| `scripts/upload_akreditasi.py` | Upload file pendukung (fisik di `data/uploads/<prodi_id>/`, metadata di `akreditasi_upload_file`) + pemicu ekstraksi |
| `scripts/auth_akreditasi.py` | Login app akreditasi: email+password, **dibatasi domain UGM** (ugm.ac.id / mail.ugm.ac.id, dicocokkan persis), bcrypt, akun pertama otomatis admin |
| `scripts/akun_akreditasi.py` | Manajemen akun (riwayat generate, pekerjaan ongoing, aksi admin blokir/hapus/jadikan admin; admin tidak bisa mengunci dirinya sendiri) |
| `scripts/generate_template.py` | Generator dokumen `.docx` dari `akreditasi_data_manual` (section kosong tetap dibuat + placeholder) |
| `scripts/generate_laporan_live.py` | Generator dokumen `.docx` **Fase 3** — sumber murni live (hasil pipeline Fase 2), tidak menyentuh tabel data manual |
| `scripts/dashboard_render.py` | Modul render bersama — dipakai dashboard akreditasi mandiri DAN menu "Akreditasi" di dashboard berita-dampak |
| `scripts/migrasi_*.py` | Migrasi tabel (data_manual, prodi, fakultas, users, sessions, upload, ekstraksi, item_tersedia, publikasi_dosen, berita_dcse, arsip_pdf) — semua `CREATE TABLE IF NOT EXISTS`/idempoten |
| `dashboard_akreditasi.py` | Dashboard Streamlit — ringkasan kelengkapan, form input manual per item, tombol generate dokumen |
| `data/` | MySQL-only, tidak ada CSV/DuckDB. `data/uploads/<prodi_id>/` = file pendukung, `data/generated/` = riwayat laporan Word (keduanya di-gitignore) |
| `DASHBOARD.md` | Penjelasan isi dashboard + cara baca badge status |
| `PIPELINE.md` | Dokumentasi alur: registry → migrasi tabel → input manual → generate dokumen |

## Fase pengembangan

| Fase | Isi | Status |
|---|---|---|
| 1 | Registry 49 item + peta status sumber 61 item (`data_source_map.json`) | Selesai (2026-09-11) |
| 2 | Pipeline data live: item tersedia, publikasi SINTA, arsip RSS dcse | Selesai (2026-09-16) |
| 3 | Ekstraksi dokumen upload (pattern → LLM) + generator laporan live | Selesai (2026-09-16) |
| A+B | Login akreditasi (domain UGM, bcrypt, admin, sessions) | Selesai (2026-09-18) |
| berikutnya | RBAC per prodi, audit log aksi, cookie `Secure` (masih `False` untuk dev/HTTP), perluasan ke fakultas lain | Belum |

## Cara menjalankan (PowerShell, Windows)

```powershell
cd D:\ugm-analytics\akreditasi

# Sekali saja per tabel baru (semua idempoten, CREATE TABLE IF NOT EXISTS):
..\venv\Scripts\python.exe scripts\migrasi_tabel_akreditasi.py
..\venv\Scripts\python.exe scripts\migrasi_tabel_prodi.py
..\venv\Scripts\python.exe scripts\migrasi_tabel_users.py
# (lihat scripts/migrasi_*.py untuk tabel lainnya)

# Dashboard interaktif:
..\venv\Scripts\streamlit.exe run dashboard_akreditasi.py
```

Buka http://localhost:8501 (atau port yang ditampilkan terminal).

## Fase 2 — pipeline data live

Tiga pipeline mengisi item yang berstatus `tersedia` di `data_source_map.json`
(masing-masing bisa dijalankan lewat CLI; sebagian juga punya pemicu di dashboard):

```powershell
..\venv\Scripts\python.exe scripts\pipeline_item_tersedia.py   # 5 item resmi
..\venv\Scripts\python.exe scripts\pipeline_sinta.py           # publikasi Scopus 18 DTPR
..\venv\Scripts\python.exe scripts\pipeline_dcse_berita.py     # arsip RSS dcse.fmipa.ugm.ac.id
```

- `pipeline_item_tersedia.py` — snapshot penuh tiap run (replace).
- `pipeline_sinta.py` — akumulatif/upsert (~10 publikasi terbaru per dosen per run).
- `pipeline_dcse_berita.py` — arsip RSS sebagai evidence; item resminya TETAP
  `tidak_tersedia` (evidence perlu verifikasi manual).

## Fase 3 — ekstraksi dokumen upload

Upload file pendukung lewat dashboard → tersimpan fisik di `data/uploads/<prodi_id>/`
+ metadata di `akreditasi_upload_file`. Tombol "Ekstrak Data" menjalankan dua tier:

1. `scripts/ekstraksi_pattern.py` — pattern-matching TANPA AI (struktur tabel/pola
   teks berulang). Dicoba lebih dulu: lebih cepat, gratis, confidence pasti.
2. `scripts/ekstraksi_akreditasi.py` — fallback LLM per batch item registry (butuh
   `OPENAI_API_KEY` / `OPENAI_BASE_URL`).

Hasil keduanya masuk `akreditasi_upload_ekstraksi` sebagai **PREVIEW** — user wajib
review dan klik Simpan dulu; baru setelah itu masuk `akreditasi_data_manual`.

Catatan: model gateway `cx/gpt-5.6-luna` TIDAK menegakkan `response_format` JSON
Schema strict (dicoba 2026-09-16) → parsing respons harus defensif.

## Generate dokumen akreditasi

Dua generator:

- `scripts/generate_template.py` — dari `akreditasi_data_manual`; section/tabel yang
  datanya belum ada TETAP dibuat (header lengkap) dengan placeholder italic
  "⚠️ Data belum tersedia — sumber: {nama sistem}".
- `scripts/generate_laporan_live.py` — **Fase 3**, sumber murni live (hasil pipeline
  Fase 2), tidak menyentuh tabel data manual.

Di dashboard, tombol generate tersedia **dua** (satu per mode dokumen): `template_LED.docx`
dan `template_LKPS.docx` — bukan satu dokumen gabungan. Dokumen LED memuat sub-tabel
ringkas "Tabel LKPS Terkait" per Kriteria A/B/C1-C6 (nama, no. tabel, status saja);
isi lengkap tabel itu ada di dokumen LKPS.

```powershell
..\venv\Scripts\python.exe scripts\generate_template.py       # template_akreditasi.docx
..\venv\Scripts\python.exe scripts\generate_laporan_live.py   # laporan live
```

## Mengubah kebutuhan data (tambah/ubah item)

Edit `scripts/registry_kebutuhan_data.py` (dict `KEBUTUHAN_DATA`) — dashboard
dan generator dokumen otomatis ikut berubah, tidak perlu diedit terpisah.
Setiap item wajib punya: `kriteria_led`, `tabel_lkps` (atau `None`), `nama`,
`deskripsi_singkat`, `tipe` (`"tabel"` atau `"narasi"`), `kolom_dibutuhkan`,
`sumber_data`, `status_ketersediaan`, `mysql_table`.

Baca docstring di awal file itu untuk keputusan scoping v1 (kenapa siklus
PPEPP tidak dipecah per tahap, kenapa `kriteria_led` untuk tabel LKPS adalah
hasil pemetaan interpretatif, dst.) sebelum menambah item baru.

## Input data manual

Untuk item berstatus `perlu_input_manual`, isi lewat dashboard: buka
expander item terkait, isi tabel (`st.data_editor`, baris bisa ditambah
untuk data multi-baris seperti "per judul penelitian"), klik "💾 Simpan".
Data masuk ke tabel MySQL `akreditasi_data_manual`.

**Catatan skema**: kolom `baris_ke` di `akreditasi_data_manual` adalah
tambahan di luar spesifikasi awal (item_id, kolom, nilai, tahun, link_bukti,
diisi_oleh, updated_at) — dibutuhkan karena banyak tabel LKPS multi-baris
(mis. Tabel 3.A.2 "per judul penelitian", Tabel 3.C.1 "per kontrak kerja
sama"); tanpa kolom ini tidak mungkin merekonstruksi baris mana berpasangan
dengan baris mana saat baca balik.

## Generate dokumen akreditasi

Lihat bagian "Generate dokumen akreditasi" di atas — dua generator
(`generate_template.py` dari data manual, `generate_laporan_live.py` dari data live)
dan dua tombol terpisah di dashboard (LED / LKPS).

## Penyimpanan data

**MySQL** (database `ugm_analytics` — SAMA dengan `berita-dampak/`, kredensial
`.env` di root project: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `MYSQL_DB`), tabel berprefix `akreditasi_` (paralel `berita_`).
Tabel: `akreditasi_data_manual` (+ `_arsip_pdf`), `akreditasi_fakultas`,
`akreditasi_prodi`, `akreditasi_item_tersedia`, `akreditasi_users`,
`akreditasi_sessions`, `akreditasi_login_attempts`, `akreditasi_upload_file`,
`akreditasi_upload_ekstraksi`, `akreditasi_riwayat_generate`,
`akreditasi_berita_dcse`, `akreditasi_publikasi_dosen`.

Isi per 2026-09-19: 20 fakultas · 18 prodi · `akreditasi_data_manual` 118 baris
(14 item, diisi 2026-09-16 s/d 18) · `_arsip_pdf` 2.292 (isi lama dari PDF) ·
`publikasi_dosen` 151 · `berita_dcse` 200 · `upload_ekstraksi` 237 (preview) ·
`upload_file` 1 · 2 user.

## Sumber data

- `docs/Data_Requirements_LED_LKPS_MEI.md` — hasil review 2 dokumen asli:
  `docs/sumber/LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf` dan
  `docs/sumber/LKPS_Prodi_S2_Elektronika_dan_Instrumentasi.pdf`.
- `data_source_map.json` — peta status sumber 61 item (hasil verifikasi akses
  sumber live, bukan dari PDF).
- Sistem sumber per kategori data (SIMASTER, SIMASET, SINTA, dst.) — lihat
  "BAGIAN 3 — Sumber Data per Kategori" di dokumen requirement, dan field
  `sumber_data` per item di `scripts/registry_kebutuhan_data.py`.

Cakupan data saat ini: **18 prodi FMIPA** (termasuk MEI) dalam 20 fakultas.
Skema sudah multi-prodi (`akreditasi_fakultas` → `akreditasi_prodi`), jadi prodi
lain bisa ditambah tanpa perubahan struktur.

Detail alur lengkap: lihat `PIPELINE.md`. Detail isi dashboard: lihat `DASHBOARD.md`.
