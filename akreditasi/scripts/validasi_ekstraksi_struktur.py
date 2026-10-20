"""Validasi ekstraksi tanpa AI (ekstraksi_struktur.py) terhadap LED asli Prodi MEI di docs/sumber.

Setiap harapan di bawah dicek manual terhadap halaman PDF (render gambar) saat modul dibuat, 2026-10-20.
Jalankan setelah mengubah ekstraksi_struktur.py:

    venv\\Scripts\\python.exe akreditasi\\scripts\\validasi_ekstraksi_struktur.py

Tabel yang SENGAJA kosong (lebih baik kosong daripada salah kolom):
  - C2.2 & C5.5: kolom di PDF per TS, registry meminta per semester (Ganjil/Genap).
  - C6.4: sel header PDF tergabung (No/Referensi/Indikator/IKU jadi satu sel) -> header ditolak.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ekstraksi_struktur as es  # noqa: E402

PDF = Path(__file__).resolve().parents[1] / "docs" / "sumber" / "LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf"


def main() -> int:
    rows, ring = es.ekstrak_dokumen(str(PDF), "pdf", "LED")
    per: dict[str, dict[int, dict[str, str]]] = {}
    for r in rows:
        per.setdefault(r["item_id"], {}).setdefault(r["baris_ke"], {})[r["nama_kolom"]] = r["nilai"]
    gagal: list[str] = []

    def cek(syarat: bool, pesan: str) -> None:
        print(("OK   " if syarat else "GAGAL ") + pesan)
        if not syarat:
            gagal.append(pesan)

    tabel_led = [i for i in es.KEBUTUHAN_DATA if i.startswith("led_tabel_")]
    kosong = {i for i in tabel_led if i not in per}
    cek(kosong == {"led_tabel_c2_2", "led_tabel_c5_5", "led_tabel_c6_4"}, f"36/39 tabel LED terisi (kosong: {sorted(kosong)})")
    for i in tabel_led:
        if i in per:
            kolom = set(es.KEBUTUHAN_DATA[i]["kolom_dibutuhkan"])
            terisi = set().union(*per[i].values())
            cek(terisi == kolom, f"{i}: semua kolom terisi")

    jumlah = {"led_tabel_c1_1": 4, "led_tabel_c3_2": 8, "led_tabel_c4_2": 5, "led_tabel_c4_3": 6,
              "led_tabel_c4_4": 7, "led_tabel_c5_1": 9}
    for i, n in jumlah.items():
        cek(len(per.get(i, {})) == n, f"{i}: {n} baris (dapat {len(per.get(i, {}))})")

    c11 = per["led_tabel_c1_1"]
    cek(c11[3]["Indikator"].startswith("Jumlah program studi pascasarjana") and c11[4]["Sasaran/Target – TS"] == "4",
        "C1.1 baris 3-4 dari halaman lanjutan (hal. 23)")
    c32 = per["led_tabel_c3_2"]
    cek([c32[b]["Indikator"] for b in (2, 3, 4)] == ["Jumlah laboratorium Pendukung Penelitian",
                                                     "Jumlah Peralatan Pendukung Penelitian", "Jumlah Software Legal"],
        "C3.2: indikator A1.2-A1.4 tidak tergeser (nomor di tengah sel)")
    cek(c32[1]["Referensi/Kebijakan/Standar"] == c32[4]["Referensi/Kebijakan/Standar"],
        "C3.2: Referensi sel gabungan A1.1-A1.4 tersalin ke tiap baris")
    cek(per["led_tabel_c4_4"][6]["Indikator"] == "Jumlah dana pkm (juta)"
        and per["led_tabel_c4_4"][6]["Capaian Kinerja – TS"] == "65", "C4.4: nomor terpotong 'A3.' + '3' = satu baris")
    cek(per["led_tabel_c4_2"][1]["Indikator"].startswith("Proses pelaksanaan PkM"),
        "C4.2 tidak tertukar dengan C4.3 (header kolom identik)")
    cek(per["led_tabel_c6_5"][1]["Kinerja – TS"] == "100", "C6.5: salah ketik header 'TS-2' ganda dikoreksi jadi TS")

    tim = per["tim_penyusun_led"]
    cek(len(tim) == 20 and all(r.get("Jabatan dalam Tim") for r in tim.values()), "Tim penyusun: 20 orang + jabatan")
    cek(tim[5] == {"Nama": "Dr. Andi Dharmawan, S.Si., M.Cs.", "Jabatan dalam Tim": "Ketua Tim"},
        "Tim penyusun: kartu terpotong hal. 4/5 digabung")
    idn = per["identitas_pt_upps_ps"][1]
    cek(len(idn) == 16 and idn["Nomor SK Pembukaan PS"] == "Keputusan Rektor UGM No. 211/UN1.P/KPT/HUKOR/2023",
        "Identitas: 16 butir")

    narasi = {i: v[1] for i, v in per.items() if es.KEBUTUHAN_DATA[i]["tipe"] == "narasi"}
    cek(narasi["kata_pengantar"]["Kata Pengantar"].endswith("Tim Penyusun"), "Kata Pengantar utuh sampai penutupnya")
    penutup = narasi["bab3_penutup"]["Bab III Penutup"]
    cek("SOEKARNO" not in penutup and "Sertifikat Akreditasi" not in penutup, "Penutup tanpa lampiran scan")
    cek(len(narasi["led_kriteria_a"]) == 7, "Kriteria A: 5 aspek makro + mikro + sintesis")
    for n in range(1, 7):
        item = next(i for i in narasi if i.startswith(f"led_c{n}_"))
        cek(len(narasi[item]) == 5, f"{item}: 5 tahap PPEPP terisi")
    c1 = narasi["led_c1_budaya_mutu"]["Dokumen Penetapan / Kebijakan (link)"]
    cek("Peraturan Rektor UGM no 7 tahun 2022 pasal 55 Renstra" not in c1, "Narasi C1 tidak memuat isi tabel")

    print(f"\n{len(gagal)} gagal; {ring['n_item_ditemukan']} item, {ring['n_kolom_terisi']} nilai, "
          f"{ring['waktu_ekstraksi_teks']:.0f} detik")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
