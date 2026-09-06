# DASHBOARD — Akreditasi

`dashboard_akreditasi.py` — jalankan:

```powershell
cd D:\ugm-analytics\akreditasi
..\venv\Scripts\streamlit.exe run dashboard_akreditasi.py
```

## Isi

LED (Laporan Evaluasi Diri) dan LKPS (Laporan Kinerja Program Studi) adalah
**dua dokumen terpisah** dengan navigasi berbeda (LED per Kriteria A-D,
LKPS per Bagian 1-6) -- seluruh dashboard di bawah ini menyesuaikan
sepenuhnya dengan mode yang dipilih, bukan tampilan gabungan dengan filter
tambahan. Lihat aturan pemisahan dokumen di docstring
`scripts/registry_kebutuhan_data.py` poin 6.

**1. Selector "Pilih dokumen"** — radio LED / LKPS tepat di bawah judul.
Mengubah mode ini mengganti kartu ringkasan, tab, dan tombol generate di
bawahnya sekaligus.

**2. Ringkasan atas** — 4 kartu metrik, dihitung ULANG per mode:
- Total item data (21 untuk LED, 28 untuk LKPS)
- 🟢 Tersedia otomatis (0 di v1 — belum ada pipeline yang mengisi otomatis,
  lihat catatan di `README.md`)
- 🟡🟠 Perlu input manual (x/y terisi)
- 🔴 Belum tersedia (butuh sumber data yang belum ada, mis. tracer study,
  dokumen kebijakan belum disusun)

Plus progress bar kelengkapan keseluruhan mode aktif.

**3a. Mode LED — tab per Kriteria** (Umum, A, B, C1–C6, D) — tiap tab berisi:
- Item narasi/D1-D3 kriteria itu, masing-masing sebagai expander berjudul
  `{badge} {nama item}` (deskripsi, sumber data, status, form/info box --
  sama seperti poin 4 di bawah).
- Untuk tab A/B/C1-C6 (bukan Umum/D): subsection read-only **"📎 Tabel LKPS
  terkait"** — daftar item LKPS ber-`kriteria_led` sama (evidence PPEPP),
  masing-masing cuma badge + nama + no. tabel + tombol "🔗 Buka di LKPS"
  yang memindahkan mode ke LKPS. TIDAK ada form isian di sini -- satu item
  = satu tempat isi data (LKPS), lihat poin 3b.

**3b. Mode LKPS — tab per Bagian** (Bagian 1 Tata Kelola, 2 Pendidikan,
3 Penelitian, 4 PkM, 5 Sistem Tata Kelola & Sarpras, 6 Diferensiasi Misi) --
tiap tab berisi seluruh tabel LKPS Bagian itu, masing-masing expander berisi
form isian ASLI (lihat poin 4).

**4. Isi expander per item** (LED maupun LKPS):
- Deskripsi singkat item
- Tabel LKPS terkait (kalau ada)
- Sumber data (sistem/dokumen yang seharusnya jadi sumber, mis. "FINANCE
  SIMASTER", "Tracer study mandiri UPPS/Fakultas")
- Status
- **Kalau `perlu_input_manual`**: tabel isian (`st.data_editor`) sesuai
  kolom yang dibutuhkan tabel/narasi itu — bisa tambah baris untuk data
  multi-baris (mis. daftar judul penelitian). Tombol "💾 Simpan" menulis ke
  MySQL, badge status ikut berubah setelah reload.
- **Kalau `belum_tersedia`**: info box (read-only) menyebut sumber data
  seharusnya — tidak ada form isian (belum ada jalur pengumpulan data untuk
  item ini).

### Badge status

| Badge | Arti |
|---|---|
| 🟢 | `tersedia_otomatis` — ada pipeline/tabel MySQL yang mengisi otomatis |
| 🟡 | `perlu_input_manual`, sudah ada data tersimpan |
| 🟠 | `perlu_input_manual`, form masih kosong |
| 🔴 | `belum_tersedia` — belum ada jalur sumber data sama sekali |

**5. Tombol "🔄 Generate Dokumen Template {LED/LKPS}"** — DUA tombol
terpisah (satu per mode, generate dokumen mode yang sedang aktif, bukan
satu tombol gabungan): `generate_led_docx()` menghasilkan `template_LED.docx`
(cover + ringkasan kelengkapan LED + checklist to-do + isi per Kriteria,
tiap Kriteria A/B/C1-C6 ditutup sub-tabel ringkas "Tabel LKPS Terkait");
`generate_lkps_docx()` menghasilkan `template_LKPS.docx` (cover + ringkasan
kelengkapan LKPS + checklist to-do + isi per Bagian). Tersedia lewat tombol
unduh begitu selesai digenerate. Lihat detail struktur dokumen di
`PIPELINE.md`.

## Cara baca dokumen hasil generate

- Tabel/section dengan data terisi → tampil normal (tabel Word/paragraf).
- Tabel/section TANPA data → tetap ada (header lengkap), isinya SATU baris/
  paragraf italic abu-abu-kemerahan "⚠️ Data belum tersedia — sumber:
  {nama sistem}" — bukan section yang hilang.
- Halaman kedua tiap dokumen ("Ringkasan & To-Do") adalah rekap SEMUA
  section (dalam dokumen itu saja -- LED atau LKPS, tidak gabungan) yang
  masih placeholder — dipakai tim penyusun sebagai daftar kerja, supaya
  tidak perlu scroll seluruh dokumen untuk tahu apa yang kurang.
- Dokumen LED memuat sub-tabel ringkas "Tabel LKPS Terkait" di tiap Kriteria
  A/B/C1-C6 (nama, no. tabel, status saja) -- isi lengkap tabel itu ada di
  dokumen LKPS, TIDAK diduplikasi ke LED.

## Entry point lain: menu "Akreditasi" di dashboard berita-dampak

UI di atas (selector mode, ringkasan, tabs, form, tombol generate) dipakai
BARENG oleh menu "Akreditasi" di `dashboard_berita_dampak.py`
(`berita-dampak/page_akreditasi.py`) lewat `scripts/dashboard_render.py` --
data yang diisi lewat salah satu entry point otomatis muncul di entry point
lainnya (satu tabel MySQL yang sama). Entry point itu menambahkan satu
bagian ekstra di bawah dashboard LED/LKPS: "📎 Lampiran: Data Dampak & SDG"
(dari analisis berita-dampak sendiri), ikut disisipkan ke dokumen Word yang
digenerate dari sana.
