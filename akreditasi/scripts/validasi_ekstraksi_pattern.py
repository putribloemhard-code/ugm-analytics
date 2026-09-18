"""Validasi manual tier ekstraksi pattern-matching (ekstraksi_pattern.py) untuk
DUA bentuk struktur tabel yang berbeda, masing-masing 1 item contoh:

  A. tim_penyusun_led (LED PDF) -- tabel VERTIKAL: 1 tabel kecil = 1 orang,
     tiap baris = 1 field "label : value".
  B. lkps_2_a_1 (LKPS PDF) -- tabel HORIZONTAL: 1 baris = 1 entitas (tahun TS),
     header bertingkat & ter-merge.

Ground truth KEDUANYA dihitung/diverifikasi manual langsung dari teks PDF asli,
BUKAN dari hasil ekstraksi AI sebelumnya, supaya validasi ini independen.

Catatan ground truth A: "Tanggung Jawab Bab/Kriteria" TIDAK ADA di teks PDF sama
sekali -- section lain (hal. 15, "B. TIM PENYUSUN DAN TANGGUNG JAWABNYA")
menyebut "Daftar nama tim penyusun lengkap dengan Tugas, dan Tanggung Jawab
terlampir di link" (lampiran eksternal, bukan isi dokumen).

Catatan ground truth B: baris "Jumlah" di Tabel 2.A.1 SENGAJA tidak dihitung sbg
entitas (itu baris TOTAL); baris TS-3 di dokumen ini memang kosong (cuma "-").

Jalankan: ..\\venv\\Scripts\\python.exe scripts\\validasi_ekstraksi_pattern.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ekstraksi_pattern import (  # noqa: E402
    ada_trigger_section,
    ekstrak_pattern_pdf,
    ekstrak_via_pola_narasi,
)

PDF_PATH = str(Path(__file__).resolve().parents[1] / "docs" / "sumber" /
               "LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf")
PDF_LKPS = str(Path(__file__).resolve().parents[1] / "docs" / "sumber" /
               "LKPS_Prodi_S2_Elektronika_dan_Instrumentasi.pdf")

# Ground truth B -- dihitung manual dari Tabel 2.A.1 (LKPS hal. 17).
# Kolom registry: Tahun | Daya Tampung | Jumlah Pendaftar | Jumlah Diterima | Aktif
GROUND_TRUTH_2A1 = [
    {"Tahun (TS-3/TS-2/TS-1/TS)": "TS-3"},  # baris kosong di dokumen (cuma "-")
    {"Tahun (TS-3/TS-2/TS-1/TS)": "TS-2", "Daya Tampung": "30",
     "Jumlah Pendaftar (Reguler/RPL/Afirmasi/Keb. Khusus)": "13 / 0 / 0",
     "Jumlah Diterima (Reguler/RPL/Afirmasi/Keb. Khusus)": "9 / 0 / 0 / 0 / 0 / 0",
     "Jumlah Mahasiswa Aktif": "9"},
    {"Tahun (TS-3/TS-2/TS-1/TS)": "TS-1", "Daya Tampung": "30",
     "Jumlah Pendaftar (Reguler/RPL/Afirmasi/Keb. Khusus)": "11 / 1 / 0",
     "Jumlah Diterima (Reguler/RPL/Afirmasi/Keb. Khusus)": "10 / 1 / 0 / 0 / 0 / 0",
     "Jumlah Mahasiswa Aktif": "20"},
    {"Tahun (TS-3/TS-2/TS-1/TS)": "TS", "Daya Tampung": "30",
     "Jumlah Pendaftar (Reguler/RPL/Afirmasi/Keb. Khusus)": "12 / 2 / 0",
     "Jumlah Diterima (Reguler/RPL/Afirmasi/Keb. Khusus)": "8 / 2 / 0 / 0 / 0 / 0",
     "Jumlah Mahasiswa Aktif": "30"},
]

# Ground truth diverifikasi manual dari teks PDF hal. 4-8 (nomor urut 1-20).
GROUND_TRUTH = [
    ("Aina Musdholifah, S.Kom., M.Kom., Ph.D.", "Ketua Departemen IKE"),
    ("Oskar Natan, S.ST., M.Tr.T., Ph.D.", "Sekretaris Departemen IKE"),
    ("Prof. Drs. Agus Harjoko, M.Sc., Ph.D.", "Pengarah"),
    ("Prof. Dra. Sri Hartati, M.Sc., Ph.D.", "Pengarah"),
    ("Dr. Andi Dharmawan, S.Si., M.Cs.", "Ketua Tim"),
    ("Dr. techn. Aufaclav Zatu Kusuma Frisky, S.Si., M.Sc.", "Sekretaris Tim"),
    ("Prof. Dr. Techn. Ahmad Ashari, M.I.Kom.", "Penyusun"),
    ("Dr. Mardhani Riasetiawan, S.E., Ak., M.T.", "Penyusun"),
    ("Nia Gella Augoestien, S.Si., M.Cs.", "Penyusun"),
    ("Muhammad Auzan, S.Si., M.Cs.", "Penyusun"),
    ("Ika Candradewi, S.Si., M.Cs.", "Penyusun"),
    ("Zandy Yudha Perwira, S.Si., M.Cs.", "Penyusun"),
    ("Muhammad Husni Santriaji, S.Si., M.T., M.S., Ph.D.", "Penyusun"),
    ("Lukman Awaludin, S.Si., M.Cs.", "Penyusun"),
    ("Dr. Dyah Aruming Tyas, S.Si.", "Penyusun"),
    ("Bakhtiar Alldino Ardi Sumbodo, S.Si., M.Cs.", "Penyusun"),
    ("Dr. Muhammad Idham Ananta Timur, M.Kom.", "Penyusun"),
    ("Triyogatama Wahyu Widodo, M.Kom.", "Penyusun"),
    ("Nur Achmad Sulistyo Putro, S.Si., M.Cs., Ph.D.", "Penyusun"),
    ("Catur Atmaji, S.Si., M.Cs.", "Penyusun"),
]


def main() -> None:
    print(f"Ground truth: {len(GROUND_TRUTH)} orang (Nama + Jabatan), 0 dari 20 punya")
    print('"Tanggung Jawab Bab/Kriteria" di teks PDF (lihat docstring modul).\n')

    # ---------- Jalur produksi: trigger -> tabel -> (fallback pola narasi) ----------
    import fitz
    doc = fitz.open(PDF_PATH)
    teks_dokumen = "".join(page.get_text() for page in doc)

    hasil = ekstrak_pattern_pdf(PDF_PATH, "tim_penyusun_led", teks_dokumen)
    print(f"=== Jalur produksi (trigger -> tabel -> pola narasi) ===")
    print(f"Metode terpakai: {hasil['metode']}")
    print(f"Jumlah baris ditemukan: {len(hasil['baris'])}\n")

    truth_nama = [g[0] for g in GROUND_TRUTH]
    truth_jabatan = [g[1] for g in GROUND_TRUTH]

    n_nama_cocok = 0
    n_jabatan_cocok = 0
    n_tj_cocok = 0
    salah = []
    for i, baris in enumerate(hasil["baris"]):
        nama = baris.get("Nama", "")
        jabatan = baris.get("Jabatan dalam Tim", "")
        tj = baris.get("Tanggung Jawab Bab/Kriteria", "")
        nama_expected = truth_nama[i] if i < len(truth_nama) else None
        jabatan_expected = truth_jabatan[i] if i < len(truth_jabatan) else None
        ok_nama = nama.strip() == (nama_expected or "").strip()
        ok_jabatan = jabatan.strip() == (jabatan_expected or "").strip()
        if ok_nama:
            n_nama_cocok += 1
        else:
            salah.append(f"  baris {i+1}: dapat Nama={nama!r}, seharusnya={nama_expected!r}")
        if jabatan:
            if ok_jabatan:
                n_jabatan_cocok += 1
            else:
                salah.append(f"  baris {i+1}: dapat Jabatan={jabatan!r}, seharusnya={jabatan_expected!r}")
        if tj:
            n_tj_cocok += 1  # seharusnya SELALU 0 -- data ini tidak ada di PDF

    print(f"Nama akurat: {n_nama_cocok}/{len(GROUND_TRUTH)}")
    print(f"Jabatan akurat: {n_jabatan_cocok}/{len(GROUND_TRUTH)}")
    print(f"Tanggung Jawab Bab/Kriteria terisi (SEHARUSNYA 0, data tdk ada di PDF): {n_tj_cocok}")
    if len(hasil["baris"]) != len(GROUND_TRUTH):
        print(f"⚠️ JUMLAH BARIS BEDA: dapat {len(hasil['baris'])}, seharusnya {len(GROUND_TRUTH)}")
    if salah:
        print("\nKetidakcocokan:")
        for s in salah:
            print(s)
    else:
        print("\nTIDAK ADA kesalahan/kelewat pada jalur produksi.")

    # ---------- Cek tambahan (bukan jalur produksi): kualitas fallback pola_narasi ----------
    # Disimulasikan thd teks yg sama, SEOLAH tabel gagal terdeteksi -- utk
    # membuktikan tier fallback juga berfungsi, bukan cuma teoretis.
    print("\n=== Cek tambahan: kualitas fallback pola_narasi (simulasi tabel gagal) ===")
    baris_narasi = ekstrak_via_pola_narasi(PDF_PATH, "tim_penyusun_led")
    nama_narasi = [b["Nama"] for b in baris_narasi]
    n_cocok_narasi = sum(1 for i, n in enumerate(nama_narasi) if i < len(truth_nama) and n.strip() == truth_nama[i].strip())
    print(f"Jumlah nama ditemukan via pola_narasi: {len(nama_narasi)} / {len(GROUND_TRUTH)}")
    print(f"Akurat (urutan & isi persis sama dgn ground truth): {n_cocok_narasi}/{len(GROUND_TRUTH)}")
    salah_narasi = [f"  - dapat: {n!r}" for i, n in enumerate(nama_narasi)
                    if i >= len(truth_nama) or n.strip() != truth_nama[i].strip()]
    if salah_narasi:
        print("Ketidakcocokan pola_narasi:")
        for s in salah_narasi:
            print(s)
    else:
        print("TIDAK ADA kesalahan/kelewat pada fallback pola_narasi juga.")

    validasi_horizontal()
    validasi_tabel_kembar()
    uji_lapis_3()
    uji_kandidat_ganda()
    uji_negatif()


def validasi_horizontal() -> None:
    """Validasi B -- struktur tabel HORIZONTAL (lkps_2_a_1, Tabel 2.A.1 LKPS)."""
    print("\n\n########## VALIDASI B: TABEL HORIZONTAL (lkps_2_a_1) ##########")
    print(f"Ground truth: {len(GROUND_TRUTH_2A1)} baris entitas (TS-3/TS-2/TS-1/TS); "
          "baris \"Jumlah\" = total, sengaja tidak dihitung.\n")

    import fitz
    teks_lkps = "".join(p.get_text() for p in fitz.open(PDF_LKPS))
    hasil = ekstrak_pattern_pdf(PDF_LKPS, "lkps_2_a_1", teks_lkps)
    print(f"Metode terpakai: {hasil['metode']}")
    print(f"Jumlah baris ditemukan: {len(hasil['baris'])}\n")

    n_sel_benar = n_sel_truth = 0
    salah = []
    for i, truth in enumerate(GROUND_TRUTH_2A1):
        dapat = hasil["baris"][i] if i < len(hasil["baris"]) else {}
        for kolom, nilai_truth in truth.items():
            n_sel_truth += 1
            nilai_dapat = dapat.get(kolom, "")
            if nilai_dapat.strip() == nilai_truth.strip():
                n_sel_benar += 1
            else:
                salah.append(f"  baris {i+1} [{kolom}]: dapat={nilai_dapat!r}, "
                             f"seharusnya={nilai_truth!r}")
        # kolom yang TIDAK ada di ground truth tapi terisi = salah tangkap
        for kolom, nilai_dapat in dapat.items():
            if kolom not in truth and nilai_dapat.strip():
                salah.append(f"  baris {i+1} [{kolom}]: SALAH TANGKAP {nilai_dapat!r} "
                             "(di PDF kolom ini kosong utk baris tsb)")

    print(f"Sel akurat: {n_sel_benar}/{n_sel_truth}")
    if len(hasil["baris"]) != len(GROUND_TRUTH_2A1):
        print(f"⚠️ JUMLAH BARIS BEDA: dapat {len(hasil['baris'])}, "
              f"seharusnya {len(GROUND_TRUTH_2A1)}")
    if salah:
        print("\nKetidakcocokan:")
        for s in salah:
            print(s)
    else:
        print("TIDAK ADA kesalahan/kelewat/salah tangkap pada tabel horizontal.")


# Ground truth C: Tabel 2.A.4 (LKPS hal. 18-20, Indikator A1.1-A1.4) = 23 baris.
# Hal. 21 (Indikator A1.5 Bandwidth & A1.6 Lisensi Software) punya layout BEDA
# (8 kolom, bukan 9) -- 10 baris di sana SENGAJA ditolak guard, bukan dipaksakan.
GT_2A4_JUMLAH = 23
GT_2A4_SPOTCHECK = {   # baris_ke (1-based) -> (Nama Ruang/Fasilitas, Daya Tampung, Luas)
    1: ("Co working Space Lantai 5 Gedung s1", "30", "600"),
    6: ("Ruang 419", "30", "49"),
    14: ("Ruang pertemuan ADA", "11", "32"),
    23: ("Ruang Dosen", "17 ruang", "@ 8"),
}


def validasi_tabel_kembar() -> None:
    """Validasi C -- lkps_2_a_4, SATU dari EMPAT tabel "Sarana dan Prasarana ..."
    yang ada di dokumen LKPS yang SAMA (2.A.4 h.18, 3.A.1 h.37, 4.A.1 h.90,
    5.2 h.100). Membuktikan tidak salah comot dari 3 kembarannya."""
    print("\n\n########## VALIDASI C: TABEL KEMBAR SATU DOKUMEN (lkps_2_a_4) ##########")
    print(f"Ground truth: {GT_2A4_JUMLAH} baris (hal. 18-20, Indikator A1.1-A1.4).")
    print("3 tabel kembar di dokumen yang sama: 3.A.1 (h.37), 4.A.1 (h.90), 5.2 (h.100).\n")

    import fitz
    teks = "".join(p.get_text() for p in fitz.open(PDF_LKPS))
    hasil = ekstrak_pattern_pdf(PDF_LKPS, "lkps_2_a_4", teks)
    baris = hasil["baris"]
    print(f"Metode terpakai: {hasil['metode']}")
    print(f"Jumlah baris ditemukan: {len(baris)} (harapan {GT_2A4_JUMLAH})")

    salah = []
    for ke, (nama, tampung, luas) in GT_2A4_SPOTCHECK.items():
        b = baris[ke - 1] if ke - 1 < len(baris) else {}
        got = (b.get("Nama Ruang/Fasilitas", ""), b.get("Daya Tampung", ""), b.get("Luas (m2)", ""))
        if got != (nama, tampung, luas):
            salah.append(f"  baris {ke}: dapat {got}, seharusnya {(nama, tampung, luas)}")
    # bukti tidak nyomot kembaran: nama khas 3 tabel kembar tidak boleh muncul
    khas_kembar = ["Ruang Laboratorium 1 Elektronika", "Lab Komputer SIC"]
    for k in khas_kembar:
        if any(k.lower() in b.get("Nama Lab/Fasilitas", b.get("Nama Ruang/Fasilitas", "")).lower()
               for b in baris):
            salah.append(f"  SALAH COMOT dari tabel kembar: '{k}' ikut terekstrak")

    print(f"Spot-check sel: {len(GT_2A4_SPOTCHECK) - len([s for s in salah if 'baris' in s])}"
          f"/{len(GT_2A4_SPOTCHECK)} cocok")
    if len(baris) != GT_2A4_JUMLAH:
        print(f"⚠️ JUMLAH BARIS BEDA: dapat {len(baris)}, seharusnya {GT_2A4_JUMLAH}")
    if salah:
        print("\nKetidakcocokan:")
        for s in salah:
            print(s)
    else:
        print("TIDAK ADA salah comot dari 3 tabel kembar, semua spot-check cocok.")


def uji_lapis_3() -> None:
    """Bukti LAPIS 3 (konteks bagian) benar-benar bekerja: dipakai konfigurasi
    yang SENGAJA hanya memakai kolom yang dimiliki SEMUA tabel kembar, supaya
    Lapis 2 (structure guard) tidak bisa membedakan sama sekali."""
    print("\n\n########## UJI LAPIS 3: DISAMBIGUASI KONTEKS BAGIAN ##########")
    import pdfplumber
    import ekstraksi_pattern as ep

    konfig = {
        "anchor_baris": r"^(?!nama prasarana$).{3,}$",
        "kolom": [{"sig": s, "registry": r, "hanya_satu_kolom": True} for s, r in [
            ("nama prasarana", "Nama Lab/Fasilitas"), ("daya tampung", "Daya Tampung"),
            ("luas ruang", "Luas (m2)"), ("milik sendiri", "Status Kepemilikan"),
            ("berlisensi", "Status Lisensi"), ("perangkat", "Daftar Perangkat"),
            ("link bukti", "Link Bukti")]],
    }
    asli_k = ep._KOLOM_HORIZONTAL.get("lkps_4_a_1")
    asli_t = ep._TRIGGER_SECTION.get("lkps_4_a_1")
    ep._KOLOM_HORIZONTAL["lkps_4_a_1"] = konfig
    ep._TRIGGER_SECTION["lkps_4_a_1"] = ["sarana dan prasarana", "prasarana"]
    try:
        with pdfplumber.open(PDF_LKPS) as pdf:
            parse, reset = ep._buat_parser_horizontal(konfig)
            kandidat = ep._kumpulkan_kandidat(pdf, parse, False, reset)
            heading = ep._deteksi_heading_bagian(pdf)
            print(f"Lapis 2 saja -> {len(kandidat)} kandidat (tabel kembar TIDAK terbedakan):")
            for k in kandidat:
                print(f"   hal {k['halaman_mulai']+1:3d}-{k['halaman_akhir']+1:3d} | "
                      f"{len(k['baris']):2d} baris | Bagian "
                      f"{ep._bagian_di_halaman(heading, k['halaman_mulai'])}")
            sisa = ep._saring_kandidat(kandidat, "lkps_4_a_1", pdf)
            harap = ep._bagian_diharapkan("lkps_4_a_1")
            print(f"\nHarapan bagian dari registry ('4.A.1') = {harap}")
            ok = (len(sisa) == 1 and
                  ep._bagian_di_halaman(heading, sisa[0]["halaman_mulai"]) == harap)
            for k in sisa:
                print(f"Setelah Lapis 1+3 -> hal {k['halaman_mulai']+1}-{k['halaman_akhir']+1} "
                      f"| Bagian {ep._bagian_di_halaman(heading, k['halaman_mulai'])} "
                      f"| {len(k['baris'])} baris")
            print("LAPIS 3 BERHASIL memilih yang benar." if ok else "⚠️ LAPIS 3 GAGAL.")
    finally:
        if asli_k is None:
            ep._KOLOM_HORIZONTAL.pop("lkps_4_a_1", None)
        else:
            ep._KOLOM_HORIZONTAL["lkps_4_a_1"] = asli_k
        if asli_t is None:
            ep._TRIGGER_SECTION.pop("lkps_4_a_1", None)
        else:
            ep._TRIGGER_SECTION["lkps_4_a_1"] = asli_t


def uji_kandidat_ganda() -> None:
    """Kalau 3 lapis TIDAK berhasil menyisakan 1 kandidat (mis. dokumen bebas
    user yang tidak punya struktur heading bagian LKPS), hasilnya HARUS
    kandidat_ganda -- semua ditawarkan ke user, BUKAN dipilih otomatis."""
    print("\n\n########## UJI KANDIDAT GANDA (tanpa heading bagian) ##########")
    import fitz
    import ekstraksi_pattern as ep

    konfig = {
        "anchor_baris": r"^(?!nama prasarana$).{3,}$",
        "kolom": [{"sig": s, "registry": r, "hanya_satu_kolom": True} for s, r in [
            ("nama prasarana", "Nama Lab/Fasilitas"), ("daya tampung", "Daya Tampung"),
            ("luas ruang", "Luas (m2)"), ("milik sendiri", "Status Kepemilikan"),
            ("berlisensi", "Status Lisensi"), ("perangkat", "Daftar Perangkat"),
            ("link bukti", "Link Bukti")]],
    }
    asli_k = ep._KOLOM_HORIZONTAL.get("lkps_4_a_1")
    asli_t = ep._TRIGGER_SECTION.get("lkps_4_a_1")
    asli_h = ep._deteksi_heading_bagian
    ep._KOLOM_HORIZONTAL["lkps_4_a_1"] = konfig
    ep._TRIGGER_SECTION["lkps_4_a_1"] = ["sarana dan prasarana", "prasarana"]
    ep._deteksi_heading_bagian = lambda pdf: []   # simulasi dokumen tanpa heading bagian
    try:
        teks = "".join(p.get_text() for p in fitz.open(PDF_LKPS))
        h = ep.ekstrak_pattern_pdf(PDF_LKPS, "lkps_4_a_1", teks)
        print(f"metode = {h['metode']}")
        print(f"baris auto-pick = {len(h['baris'])} (HARUS 0 -- tidak boleh dipilihkan otomatis)")
        print(f"kandidat ditawarkan ke user = {len(h['kandidat_ganda'])}:")
        for k in h["kandidat_ganda"]:
            contoh = k["baris"][0].get("Nama Lab/Fasilitas", "")[:34] if k["baris"] else "-"
            print(f"   hal {k['halaman_mulai']}-{k['halaman_akhir']} | {len(k['baris'])} baris "
                  f"| {contoh}")
        ok = h["metode"] == "kandidat_ganda" and not h["baris"] and len(h["kandidat_ganda"]) >= 2
        print("BENAR: tidak dipilih otomatis, semua kandidat diserahkan ke user."
              if ok else "⚠️ GAGAL: seharusnya kandidat_ganda tanpa auto-pick.")
    finally:
        ep._deteksi_heading_bagian = asli_h
        if asli_k is None:
            ep._KOLOM_HORIZONTAL.pop("lkps_4_a_1", None)
        else:
            ep._KOLOM_HORIZONTAL["lkps_4_a_1"] = asli_k
        if asli_t is None:
            ep._TRIGGER_SECTION.pop("lkps_4_a_1", None)
        else:
            ep._TRIGGER_SECTION["lkps_4_a_1"] = asli_t


def uji_negatif() -> None:
    """Pastikan tier ini TIDAK menangkap yang bukan haknya (false positive)."""
    print("\n\n########## UJI NEGATIF ##########")
    import fitz
    teks_led = "".join(p.get_text() for p in fitz.open(PDF_PATH))
    teks_lkps = "".join(p.get_text() for p in fitz.open(PDF_LKPS))

    kasus = [
        ("tim_penyusun_led di dokumen LKPS (ada section KEMBAR utk tim LKPS)",
         PDF_LKPS, "tim_penyusun_led", teks_lkps),
        ("lkps_2_a_1 di dokumen LED (tabel ini tidak ada di LED)",
         PDF_PATH, "lkps_2_a_1", teks_led),
        ("item yang belum terdaftar di kamus (led_b4_mahasiswa_lulusan)",
         PDF_PATH, "led_b4_mahasiswa_lulusan", teks_led),
    ]
    for judul, pdf, item_id, teks in kasus:
        hasil = ekstrak_pattern_pdf(pdf, item_id, teks)
        trigger = ada_trigger_section(item_id, teks)
        status = "OK (tidak menangkap)" if hasil["metode"] == "tidak_ditemukan" else "⚠️ MENANGKAP!"
        print(f"  {judul}")
        print(f"    trigger={trigger} | metode={hasil['metode']} | "
              f"baris={len(hasil['baris'])} -> {status}")


if __name__ == "__main__":
    main()
