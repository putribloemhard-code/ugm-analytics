# Akreditasi — Kelengkapan Data LED & LKPS

Registry status kelengkapan data untuk penyusunan LED (Laporan Evaluasi Diri)
dan LKPS (Laporan Kinerja Program Studi), instrumen LAM-INFOKOM — Prodi
Magister Elektronika dan Instrumentasi (MEI). Sumber kebutuhan data:
`docs/Data_Requirements_LED_LKPS_MEI.md`.

Subproyek ini **berdiri sendiri**, tidak menyentuh `berita-dampak/` atau
`matkul-sustainability/` (walau memakai database MySQL yang sama, lihat
"Penyimpanan data" di bawah).

## Isi folder

| File / folder | Isi |
|---|---|
| `scripts/db.py` | Koneksi MySQL bersama (engine, retry) -- adaptasi `berita-dampak/scripts/db.py`, prefix tabel `akreditasi_` |
| `scripts/registry_kebutuhan_data.py` | **Satu sumber kebenaran**: 49 item data yang dibutuhkan LED/LKPS (26+3 tabel LKPS/D1-D3, 18 item narasi LED), status ketersediaan, sumber data resmi per item |
| `scripts/migrasi_tabel_akreditasi.py` | Bikin tabel `akreditasi_data_manual` (jalankan sekali sebelum pakai dashboard) |
| `scripts/generate_template.py` | Generator dokumen `.docx` (python-docx) — satu dokumen gabungan LED+LKPS |
| `dashboard_akreditasi.py` | Dashboard Streamlit — ringkasan kelengkapan, form input manual per item, tombol generate dokumen |
| `data/` | Sengaja kosong — subproyek ini MySQL-only, tidak ada CSV/DuckDB lokal (folder tetap ada untuk konsistensi pola folder subproyek) |
| `DASHBOARD.md` | Penjelasan isi dashboard + cara baca badge status |
| `PIPELINE.md` | Dokumentasi alur: registry → migrasi tabel → input manual → generate dokumen |

## Cara menjalankan (PowerShell, Windows)

```powershell
cd D:\ugm-analytics\akreditasi

# Sekali saja (bikin tabel akreditasi_data_manual kalau belum ada):
..\venv\Scripts\python.exe scripts\migrasi_tabel_akreditasi.py

# Dashboard interaktif:
..\venv\Scripts\streamlit.exe run dashboard_akreditasi.py
```

Buka http://localhost:8501 (atau port yang ditampilkan terminal).

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

## Generate dokumen template akreditasi

Tombol "🔄 Generate Dokumen Template Akreditasi" di bagian bawah dashboard
menghasilkan SATU file `.docx`: cover + ringkasan kelengkapan + section
"Ringkasan & To-Do" (checklist item belum lengkap) + isi per Kriteria LED
(A–D), tabel LKPS disisipkan di sub-bagian terkait. Section/tabel yang
datanya belum ada TETAP dibuat (header lengkap), ditandai italic
"⚠️ Data belum tersedia — sumber: {nama sistem}" — dokumen selalu jadi
template lengkap, bukan dokumen bolong-bolong.

Bisa juga digenerate dari command line (hasil ke
`akreditasi/template_akreditasi.docx`):

```powershell
..\venv\Scripts\python.exe scripts\generate_template.py
```

## Penyimpanan data

**MySQL** (database `ugm_analytics` — SAMA dengan `berita-dampak/`, kredensial
`.env` di root project: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `MYSQL_DB`), tabel berprefix `akreditasi_` (paralel
`berita_`). Cuma satu tabel di v1: `akreditasi_data_manual`.

## Sumber data

- `docs/Data_Requirements_LED_LKPS_MEI.md` — hasil review 2 dokumen asli:
  `docs/sumber/LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf` dan
  `docs/sumber/LKPS_Prodi_S2_Elektronika_dan_Instrumentasi.pdf`.
- Sistem sumber per kategori data (SIMASTER, SIMASET, SINTA, dst.) — lihat
  "BAGIAN 3 — Sumber Data per Kategori" di dokumen requirement, dan field
  `sumber_data` per item di `scripts/registry_kebutuhan_data.py`.

Cakupan v1: **satu prodi (MEI)**, sesuai cakupan dokumen sumber — belum ada
dimensi multi-prodi di skema manapun.

Detail alur lengkap: lihat `PIPELINE.md`. Detail isi dashboard: lihat `DASHBOARD.md`.
