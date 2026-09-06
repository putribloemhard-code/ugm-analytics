# PIPELINE — Akreditasi

Bukan pipeline scrape/tagging seperti `berita-dampak/` atau
`matkul-sustainability/` (tidak ada sumber data eksternal yang di-scrape) --
alurnya lebih ke **registry + input manual + generate dokumen**.

## Alur

```
scripts/registry_kebutuhan_data.py   # 1. Satu sumber kebenaran: 49 item data
                                      #    (dict KEBUTUHAN_DATA), status per item
        ↓
scripts/migrasi_tabel_akreditasi.py  # 2. Sekali jalan: bikin tabel MySQL
                                      #    akreditasi_data_manual (idempoten)
        ↓
dashboard_akreditasi.py              # 3. Isi data manual lewat form per item
        ↓ (tulis)
akreditasi_data_manual (MySQL)       # 4. Penyimpanan (skema "long"/EAV, lihat README.md)
        ↓ (baca)
scripts/generate_template.py         # 5. Generate .docx -- gabung registry + data manual
        ↓
template_akreditasi_YYYYMMDD.docx    # 6. Output -- diunduh lewat dashboard
```

## 1. Registry (`scripts/registry_kebutuhan_data.py`)

Dict Python `KEBUTUHAN_DATA`, 49 item, hasil transkripsi terstruktur dari
`docs/Data_Requirements_LED_LKPS_MEI.md`:

- 28 item `tipe="tabel"` = tabel-tabel LKPS Bagian 1-6.
- 3 item `tipe="tabel"` = D1-D3 (kekhasan kurikulum, bagian LED).
- 18 item `tipe="narasi"` = Identitas & Administrasi (3), Kriteria A (1),
  Kriteria B.1-B.8 (8), Kriteria C1-C6 (6).

Baca docstring modul untuk keputusan scoping (kenapa siklus PPEPP tidak
dipecah per tahap, kenapa `kriteria_led` untuk tabel LKPS adalah pemetaan
interpretatif — dokumen sumber tidak punya crosswalk eksplisit).

Tidak ada langkah "jalankan script ini" -- modul ini murni data statis
yang di-*import* oleh dashboard & generator.

## 2. Migrasi tabel (`scripts/migrasi_tabel_akreditasi.py`)

```powershell
..\venv\Scripts\python.exe scripts\migrasi_tabel_akreditasi.py
```

`CREATE TABLE IF NOT EXISTS` -- aman dijalankan berkali-kali, tidak
menghapus data yang sudah ada. Dashboard juga otomatis mendeteksi kalau
tabel belum ada dan menampilkan pesan cara migrasinya (tidak auto-run dari
dashboard, supaya operasi DDL selalu sengaja/manual).

## 3-4. Input manual + penyimpanan

Dashboard: tiap item `status_ketersediaan == "perlu_input_manual"` dapat
`st.data_editor` (kolom sesuai `kolom_dibutuhkan` item itu). Simpan =
DELETE seluruh baris `item_id` itu di `akreditasi_data_manual`, lalu INSERT
ulang dari isi editor saat itu (bukan upsert cell-per-cell) -- sederhana &
aman untuk skala data ini (form diisi manusia, bukan pipeline volume
tinggi), konsisten dengan cara `st.data_editor` mengembalikan seluruh
dataframe hasil edit sekaligus, bukan delta per sel.

Item `status_ketersediaan == "belum_tersedia"` TIDAK dapat form -- hanya
info box yang menyebut sumber data seharusnya (sistem yang mestinya
dipakai, dari `sumber_data`). Kalau proses pengisian datanya sudah bisa
dimulai, ubah `status_ketersediaan` jadi `"perlu_input_manual"` di registry
supaya form muncul.

## 5-6. Generate dokumen (`scripts/generate_template.py`)

Fungsi `generate(engine) -> bytes`. Baca SELURUH `akreditasi_data_manual`
sekali (bukan query per item -- lebih murah), lalu untuk tiap 49 item di
registry (urutan: Umum → A → B → C1-C6 → D):

- Ada data → render tabel Word (kolom = `kolom_dibutuhkan`) atau blok
  narasi (tergantung `tipe`).
- Tidak ada data (baik `belum_tersedia` maupun `perlu_input_manual` yang
  belum diisi) → placeholder italic abu-abu/merah "⚠️ Data belum tersedia
  — sumber: {sumber_data}". Section/tabel TETAP dibuat (header lengkap),
  TIDAK di-skip -- prinsip inti generator ini.

Section pertama dokumen ("Ringkasan & To-Do") adalah checklist semua item
yang masih placeholder -- untuk tim penyusun tahu persis apa yang harus
dikejar duluan.

Bisa dites/dijalankan lepas dari dashboard:

```powershell
..\venv\Scripts\python.exe scripts\generate_template.py
```

(hasil: `akreditasi/template_akreditasi.docx`, dari data yang SUDAH ada di
MySQL saat itu -- bukan data kosong, kecuali memang belum diisi sama sekali).

## Koneksi MySQL — aturan yang diikuti

Sama seperti `berita-dampak/PIPELINE.md` (`scripts/db.py` di sini adalah
adaptasi langsung, prefix `akreditasi_`): `pool_pre_ping=True` +
`pool_recycle=3600`, retry 3x di tiap baca/tulis (`with_retry()`). Volume
data subproyek ini kecil (input manusia, bukan scraping ribuan baris) --
tidak butuh `upsert()` batch/chunk seperti `berita-dampak` (simpan pakai
delete+reinsert per item, lihat di atas).
