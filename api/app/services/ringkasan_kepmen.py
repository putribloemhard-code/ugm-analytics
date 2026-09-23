"""Angka & catatan resmi dari Ringkasan Indikator Kepmen (sumber kebenaran indikator MK).

Rujukan: `matkul-sustainability/data/Ringkasan Indikator Kepmen.md` / `.json`
(konversi manual dari `Ringkasan Indikator Kepmen.pdf` — PDF asli tetap disimpan).
Angka di sini DI-CHECK-SILANG otomatis terhadap CSV kurasi lewat
`cek_silang_csv()` — dipanggil test + `load_matkul()` supaya kode tidak bisa
lari dari angka resmi tanpa kegagalan yang terlihat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

RINGKASAN_MD = (
    Path(__file__).resolve().parents[3] / "matkul-sustainability" / "data"
    / "Ringkasan Indikator Kepmen.md"
)

# Tabel status (per baris data) — ringkasan PDF/MD.
STATUS_RESMI: dict[str, int] = {
    "Substansial - dihitung": 511,
    "Parsial/bergantung topik - verifikasi RPS": 142,
    "Perlu cek manual (keyword terdeteksi)": 0,
    "Tidak terkait (nama mirip keyword)": 258,
    "Tidak terkait / bergantung topik": 1574,
    "Belum dinilai - deskripsi otomatis": 0,
    "Tidak terkait (dinilai dari deskripsi)": 5959,
    "Belum dapat dinilai - cek kurikulum": 19,
    # "Total baris" 8463 = penjumlahan 8 status di atas; CSV asli punya 8.465
    # baris fisik: selisih +2 = baris dengan status kosong (nama_mk kosong,
    # lihat catatan 7 di Ringkasan) yang tidak masuk tabel status.
    "Total baris (tabel status)": 8463,
    "Baris fisik CSV (termasuk status kosong)": 8465,
    "Angka indikator (MK unik berstatus Substansial)": 453,
}

# Kriteria a-j -> jumlah MK unik substansial yang memuat topik tsb (Ringkasan).
KRITERIA_RESMI: dict[str, int] = {
    "a": 165, "b": 116, "c": 42, "d": 59, "e": 33,
    "f": 142, "g": 127, "h": 35, "i": 117, "j": 130,
}

# Keyword resmi per kriteria (sheet "Keyword Kepmen") — rujukan dokumentasi,
# tidak dipakai matching (matching sudah terkurasi di CSV).
KRITERIA_KEYWORD: dict[str, str] = {
    "a": "pembangunan berkelanjutan, sustainable development, sdgs, berkelanjutan, "
         "keberlanjutan, sustainability, lestari, esg",
    "b": "perubahan iklim, climate change, gas rumah kaca, emisi, stok karbon, "
         "penyimpanan karbon, perdagangan karbon, pajak karbon, karbon hutan, "
         "jejak karbon, paleoklimat",
    "c": "energi terbarukan, renewable energy, bioenergi, panas bumi, geotermal, "
         "energi surya, biogas, bioetanol, biodiesel, transisi energi, efisiensi energi, "
         "konservasi energi, hemat energi",
    "d": "pengelolaan limbah, limbah, air limbah, daur ulang, recycling, ipal",
    "e": "ekonomi sirkular, circular economy, zero waste, simbiosis industri, "
         "hasil samping, siklus hidup, life cycle assessment",
    "f": "konservasi lingkungan, konservasi tanah dan air, konservasi air, "
         "kawasan konservasi, konservasi",
    "g": "keanekaragaman hayati, biodiversitas, biodiversity, taksonomi, sistematika, "
         "satwa liar, sumber daya genetik, musuh alami",
    "h": "rehabilitasi dan restorasi lingkungan, rehabilitasi lahan, rehabilitasi hutan, "
         "restorasi, reklamasi, reboisasi, revegetasi, bioremediasi, rehabilitasi habitat",
    "i": "pengelolaan sumber daya alam, sumber daya alam, sumber daya air, "
         "sumber daya hutan, sumber daya lahan, sumber daya perikanan, pengelolaan das",
    "j": "pencemaran lingkungan, pencemaran, polutan, kesehatan lingkungan, "
         "sanitasi lingkungan, air bersih dan sanitasi, pengurangan risiko bencana, "
         "mitigasi bencana, jasa ekosistem, jasa lingkungan, ekosistem, ketahanan pangan, "
         "pertanian organik, pengendalian hayati",
}

# Catatan metode inti (butir 1-7 Ringkasan) — ringkasan baris demi baris,
# dipakai CATATAN_MATKUL di story.py supaya teks UI selaras sumber resmi.
CATATAN_METODE_RESMI: tuple[str, ...] = (
    "Deskripsi disusun dari NAMA mata kuliah (file tidak memuat silabus/RPS): "
    "rumusan kerja untuk tagging, BUKAN bukti; pelaporan resmi butuh kurikulum/RPS/silabus.",
    "Baris praktikum mengambil deskripsi MK induk dengan awalan 'Praktikum pendamping'; "
    "MK berkode/tak lengkap berstatus 'Belum dapat dinilai - cek kurikulum'.",
    "Keyword a-j sengaja hanya di deskripsi MK Substansial — MK mirip keyword tapi beda "
    "makna (Konservasi Gigi, Data Mining, dst.) ditulis tanpa keyword agar tidak false positive.",
    "Parsial = topik bergantung kelas/proyek (KKN, dst.) atau menyinggung sepintas; "
    "sesuai ketentuan Kepmen no. 2 tidak dihitung kecuali RPS menunjukkan topik substansial.",
    "Kriteria j (topik lain relevan) mencakup pencemaran, kesehatan lingkungan, risiko "
    "bencana, ekosistem, ketahanan pangan, pengendalian hayati — interpretasi 'topik lain "
    "yang relevan', perlu disepakati tim sebelum pelaporan.",
    "Matching: substring case-insensitive di awal kata ('lestari' tidak cocok 'pelestarian'); "
    "keyword yang tercakup keyword lebih panjang tidak dihitung ganda.",
    "Dua baris sumber memiliki nama_mk kosong dan dibiarkan kosong.",
)


@dataclass
class HasilCekSilang:
    """Hasil cek silang CSV kurasi vs angka resmi Ringkasan."""

    ok: bool = True
    perbedaan: list[str] = field(default_factory=list)

    def banding(self, nama: str, aktual: int, resmi: int) -> None:
        if aktual != resmi:
            self.ok = False
            self.perbedaan.append(f"{nama}: CSV={aktual} vs Ringkasan={resmi}")


def cek_silang_csv(total_penawaran: int, n_substansial: int, n_mk_unik: int,
                   parsial: int, hitung_kriteria: dict[str, int]) -> HasilCekSilang:
    """Bandingkan angka CSV kurasi dengan angka resmi Ringkasan (lengkap, bukan sampel)."""
    hasil = HasilCekSilang()
    hasil.banding("baris Substansial", n_substansial, STATUS_RESMI["Substansial - dihitung"])
    hasil.banding("baris Parsial", parsial, STATUS_RESMI["Parsial/bergantung topik - verifikasi RPS"])
    hasil.banding("MK unik (angka indikator)", n_mk_unik,
                  STATUS_RESMI["Angka indikator (MK unik berstatus Substansial)"])
    hasil.banding("baris fisik CSV", total_penawaran,
                  STATUS_RESMI["Baris fisik CSV (termasuk status kosong)"])
    for huruf, resmi in KRITERIA_RESMI.items():
        hasil.banding(f"kriteria {huruf}", hitung_kriteria.get(huruf, 0), resmi)
    return hasil
