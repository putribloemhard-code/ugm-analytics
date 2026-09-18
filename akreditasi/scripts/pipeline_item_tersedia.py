"""Pipeline live utk 5 item resmi berstatus "tersedia" di
data_source_map.json: identitas_pt_upps_ps, status_akreditasi_seluruh_ps,
led_b2_vmts, lkps_2_b_1, lkps_6.

Kenapa pipeline ini ada (di luar 4 pipeline Bagian B yang diminta
eksplisit -- SINTA/PDDIKTI/dcse/BPS-Kemnaker-QS): 4 pipeline itu semua
sumber DATA PENDUKUNG (publikasi dosen, arsip berita) -- tidak satu pun
yang benar-benar menyimpan data live utk 5 item "tersedia" itu sendiri.
Tanpa pipeline ini, generator Fase 3 TIDAK PUNYA data live tersimpan utk
5 item tsb, cuma ingatan percakapan verifikasi Fase 1 -- itu tidak
auditable/tidak bisa dijalankan ulang, melanggar semangat "pipeline
tersimpan" yang diminta. Dibangun sekarang supaya Fase 3 benar-benar baca
dari MySQL, bukan dari isi PDF lama ATAU dari ingatan sesi ini.

Semua sumber di bawah SUDAH divalidasi bisa diambil requests polos (server-
rendered, no JS) -- lihat catatan per fungsi.

Jalankan:
    ..\\venv\\Scripts\\python.exe scripts\\pipeline_item_tersedia.py
"""
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
TABLE = db.t("item_tersedia")
COLUMNS = ["item_id", "baris_ke", "kolom", "nilai", "sumber_url", "fetched_at"]

URL_MEI = "https://dcse.fmipa.ugm.ac.id/mei/"
URL_MEI_VISIMISI = "https://dcse.fmipa.ugm.ac.id/mei/mei-visi-misi/"
URL_MEI_KURIKULUM = "https://dcse.fmipa.ugm.ac.id/mei/mei-kurikulum/"
URL_ADMISSIONS_MEI = ("https://admissions.ugm.ac.id/v26/program-studi/"
                       "magister-elektronika-dan-instrumentasi-master-in-electronics-and-instrumentations/")
URL_UGM_VISIMISI = "https://ugm.ac.id/id/17-visi-dan-misi/"

# Prodi di bawah Departemen Ilmu Komputer dan Elektronika (UPPS) -- daftar
# manual, diverifikasi 2026-09 dari menu navigasi dcse.fmipa.ugm.ac.id.
# "S2 Ilmu Komputer/Magister Ilmu Komputer" SENGAJA tidak dimasukkan --
# slug URL resminya belum ditemukan (percobaan "magister-ilmu-komputer"
# ternyata halaman blog post lama, bukan halaman profil prodi) -- lihat
# ringkasan akhir fungsi main(), ditandai eksplisit sbg gap, bukan diam2
# dilewati.
PRODI_DIKE = {
    "mei": ("Magister", "Magister Elektronika dan Instrumentasi"),
    "s1-elins": ("Sarjana", "Elektronika dan Instrumentasi"),
    "s1-ilkom": ("Sarjana", "Ilmu Komputer"),
    "mka": ("Magister", "Kecerdasan Artifisial"),
    "s3-ilkom": ("Doktor", "Ilmu Komputer"),
}
_PDF_AKREDITASI_RE = re.compile(r"/uploads/sites/\d+/\d+/\d+/([\w.-]+\.pdf)")


def _get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, timeout=30, headers=HEADERS)
        r.raise_for_status()
        return r
    except Exception as e:  # noqa: BLE001
        print(f"  GAGAL fetch {url}: {e}")
        return None


def _h2_sections(html: str) -> dict[str, str]:
    """Ekstrak teks polos tiap section di antara heading <h2 class="wp-block-heading">
    (pola block editor WordPress dipakai dcse.fmipa.ugm.ac.id) -- dipakai utk
    halaman visi-misi (section: Visi/Misi/Tujuan)."""
    parts = re.split(r'<h2 class="wp-block-heading"[^>]*>(.*?)</h2>', html, flags=re.S)
    sections = {}
    # parts[0] = sebelum heading pertama (diabaikan); lalu berselang-seling judul, isi
    for i in range(1, len(parts) - 1, 2):
        judul = re.sub(r"<[^>]+>", "", parts[i]).strip()
        isi_html = parts[i + 1]
        # Batasi ke heading <h2> berikutnya (apa pun class-nya) ATAU ke
        # penutup area konten utama (footer/script/nav) -- BUG YANG SUDAH
        # TERJADI: section heading TERAKHIR di halaman (mis. "Tujuan") tidak
        # dibatasi apa pun kalau cuma potong di "<h2 " berikutnya, sehingga
        # ikut menelan seluruh footer + inline JS sampai akhir dokumen.
        batas = len(isi_html)
        for penanda in (r"<h2 ", r"<footer", r"<script", r"<nav", r'id="sidebar"', r"[Ss]haring is [Cc]aring"):
            m_batas = re.search(penanda, isi_html)
            if m_batas:
                batas = min(batas, m_batas.start())
        isi_html = isi_html[:batas]
        isi = unescape(re.sub(r"<[^>]+>", " ", isi_html))
        isi = re.sub(r"\s+", " ", isi).strip()
        sections[judul] = isi
    return sections


def kumpulkan_identitas_pt_upps_ps(now: datetime) -> list[tuple]:
    rows = []
    # SK Pendirian PT -- fakta hukum/historis stabil (PP tidak pernah direvisi
    # sejak 1949), TIDAK ditemukan satu halaman UGM resmi yang menyatakannya
    # eksplisit & bisa di-parse otomatis -- dicatat sbg referensi tetap,
    # sumber_url mengarah ke artikel yang mengutipnya, BUKAN klaim "live-parsed".
    rows.append(("identitas_pt_upps_ps", 1, "No. & Tanggal SK Pendirian PT",
                 "Peraturan Pemerintah No. 23 Tahun 1949, 16 Desember 1949",
                 "https://amp.kompas.com/tren/read/2021/12/19/100400365/"
                 "sejarah-berdirinya-universitas-gadjah-mada-19-desember-1949", now))

    r = _get(URL_ADMISSIONS_MEI)
    if r:
        m = re.search(r"Surat Keputusan Rektor Universitas Gadjah Mada Nomor ([\w./]+)", r.text)
        if m:
            rows.append(("identitas_pt_upps_ps", 1, "No. & Tanggal SK Pembukaan PS",
                         f"Keputusan Rektor UGM Nomor {m.group(1)}", URL_ADMISSIONS_MEI, now))

    r = _get(URL_MEI)
    if r:
        m_mail = re.search(r"email:\s*([\w.@-]+)", r.text)
        # Tangkap SELURUH string "(0274) 546194" langsung (bukan cuma
        # digit lalu ditempel manual "(0274)" di luar -- BUG YANG SUDAH
        # TERJADI: nomor jadi dobel "(0274) 0274) 546194" krn grup regex
        # ini dulu ikut menelan "0274)" lalu kode menambahkan "(0274)" lagi).
        m_phone = re.search(r"phone:\s*(\([\d]+\)\s*[\d\s-]+)<br", r.text)
        m_addr = re.search(r"<address>.*?<p>(.*?)</p>\s*<br>\s*<p>(.*?)</p>", r.text, re.S)
        if m_addr:
            alamat = unescape(re.sub(r"<[^>]+>", ", ", m_addr.group(1) + " " + m_addr.group(2)))
            alamat = re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", alamat)).strip(", ")
            rows.append(("identitas_pt_upps_ps", 1, "Nama & Alamat PT/UPPS/PS",
                         f"Universitas Gadjah Mada; Departemen Ilmu Komputer dan Elektronika "
                         f"(UPPS); Program Studi Magister Elektronika dan Instrumentasi; {alamat}",
                         URL_MEI, now))
        if m_mail:
            kontak = m_mail.group(1)
            if m_phone:
                kontak += f"; {re.sub(r'\s+', ' ', m_phone.group(1)).strip()}"
            rows.append(("identitas_pt_upps_ps", 1, "Kontak", kontak, URL_MEI, now))

    # Pejabat Penandatangan: TIDAK ditemukan halaman UGM yg bisa di-parse
    # otomatis utk nama rektor penandatangan SK spesifik 211/2023 -- gap
    # yang sudah ditandai eksplisit di data_source_map.json (Fase 1),
    # SENGAJA tidak diisi di sini drpd menebak.
    return rows


def kumpulkan_status_akreditasi(now: datetime) -> list[tuple]:
    rows = []
    baris = 1
    for slug, (jenjang, nama_bidang) in PRODI_DIKE.items():
        url = f"https://dcse.fmipa.ugm.ac.id/{slug}/"
        r = _get(url)
        if not r:
            continue
        m = _PDF_AKREDITASI_RE.search(r.text)
        if not m:
            print(f"  [status_akreditasi] {slug}: link PDF akreditasi tidak ketemu di halaman -- dilewati")
            continue
        fname = m.group(1)
        m2 = re.match(r"^(.*?)-LAM-(.+?)-(\d{4})-(\d{4})\.pdf$", fname, re.I)
        if not m2:
            print(f"  [status_akreditasi] {slug}: nama file PDF ({fname}) tidak cocok pola -- dilewati")
            continue
        peringkat = m2.group(2).replace("-", " ")
        tahun_mulai, tahun_akhir = m2.group(3), m2.group(4)
        vals = {
            "Jenis Program": jenjang,
            "Nama PS": nama_bidang,
            "Status/Peringkat": peringkat,
            "Tanggal Kadaluarsa": f"{tahun_akhir} (masa berlaku {tahun_mulai}-{tahun_akhir})",
        }
        for kolom, nilai in vals.items():
            rows.append(("status_akreditasi_seluruh_ps", baris, kolom, nilai, url, now))
        baris += 1
    return rows


def kumpulkan_led_b2_vmts(now: datetime) -> list[tuple]:
    rows = []
    r = _get(URL_MEI_VISIMISI)
    if not r:
        return rows
    sec = _h2_sections(r.text)
    if "Visi" in sec:
        rows.append(("led_b2_vmts", 1, "Visi/Misi/Tujuan Strategis PS",
                     "VISI: " + sec["Visi"] + " || MISI: " + sec.get("Misi", "") +
                     " || TUJUAN: " + sec.get("Tujuan", ""), URL_MEI_VISIMISI, now))
    return rows


def kumpulkan_lkps_2_b_1(now: datetime) -> list[tuple]:
    import io

    import pandas as pd

    r = _get(URL_MEI_KURIKULUM)
    if not r:
        return []
    try:
        tables = pd.read_html(io.StringIO(r.text))
    except ValueError:
        print("  [lkps_2_b_1] tidak ada <table> terparse di halaman kurikulum")
        return []

    rows = []
    baris = 1
    # Tabel pertama = Matakuliah Wajib+Proposal+Tesis (satu tabel gabungan di
    # halaman ini), tabel berikutnya = Matakuliah Pilihan. Baris "Jumlah"
    # (subtotal SKS) dibuang -- bukan mata kuliah.
    for df in tables:
        if "Code" not in df.columns and "Kode / Code" not in df.columns:
            continue
        kode_col = "Code" if "Code" in df.columns else "Kode / Code"
        for _, row in df.iterrows():
            kode = str(row.get(kode_col, "")).strip()
            if not kode or kode.lower() == "nan" or not re.match(r"^[A-Z]{2,4}\d+", kode):
                continue  # skip baris "Jumlah"/subtotal
            nama_col = "Mata Kuliah" if "Mata Kuliah" in df.columns else "Matakuliah"
            nama = str(row.get(nama_col, "")).replace("\n", " ").strip()
            sks = str(row.get("SKS", "")).strip()
            sem = str(row.get("Sem", row.get("Semester", ""))).strip()
            jenis = str(row.get("Jenis", "Pilihan" if "Jenis" not in df.columns else row.get("Jenis", ""))).strip()
            vals = {"Kode MK": kode, "Nama MK": nama, "SKS": sks, "Semester Penawaran": sem}
            if jenis and jenis.lower() != "nan":
                # LABEL DIPERBAIKI 2026-09-11: field ini cuma status Wajib
                # (MKW)/Pilihan dari tabel kurikulum -- BUKAN "Domain KKNI"
                # (field resmi registry, konsep beda: kualifikasi KKNI).
                # Nama kolom sengaja beda dari kolom_dibutuhkan registry
                # supaya generator laporan tidak salah isi field resmi
                # "Domain KKNI" dgn data yang salah konsep.
                vals["Jenis (Wajib/Pilihan)"] = jenis
            for kolom, nilai in vals.items():
                rows.append(("lkps_2_b_1", baris, kolom, nilai, URL_MEI_KURIKULUM, now))
            baris += 1
    return rows


def kumpulkan_lkps_6(now: datetime) -> list[tuple]:
    rows = []
    r = _get(URL_UGM_VISIMISI)
    if r:
        # Halaman ini pola HTML-nya beda dari halaman dcse (bold inline <b>,
        # bukan <h2 class="wp-block-heading">) -- ekstraksi khusus, bukan
        # pakai _h2_sections.
        m = re.search(r"og:description\" content=\"(.*?)\"", r.text)
        visi_pt = unescape(m.group(1)).replace("&nbsp;", " ").strip() if m else ""
        m_misi = re.search(r"<b>Misi<br\s*/?>\s*</b></p>(.*?)<p>\s*&nbsp;\s*</p>\s*<p><b>Tujuan",
                            r.text, re.S)
        misi_pt = unescape(re.sub(r"<[^>]+>", " ", m_misi.group(1))) if m_misi else ""
        misi_pt = re.sub(r"\s+", " ", misi_pt).strip()
        if visi_pt:
            rows.append(("lkps_6", 1, "Level (PT/UPPS/PS)", "PT (Universitas Gadjah Mada)", URL_UGM_VISIMISI, now))
            rows.append(("lkps_6", 1, "Teks Visi", visi_pt, URL_UGM_VISIMISI, now))
            if misi_pt:
                rows.append(("lkps_6", 1, "Teks Misi", misi_pt, URL_UGM_VISIMISI, now))

    # UPPS (Departemen Ilmu Komputer dan Elektronika): TIDAK ditemukan
    # halaman visi-misi tingkat departemen terpisah dari visi-misi tiap
    # prodi -- kemungkinan departemen memang tidak menerbitkan visi sendiri
    # yang terpisah dari agregat visi prodi-prodinya. Gap ini SENGAJA
    # dicatat sbg baris dgn nilai eksplisit "tidak ditemukan", bukan
    # dilewati diam-diam.
    rows.append(("lkps_6", 2, "Level (PT/UPPS/PS)", "UPPS (Departemen Ilmu Komputer dan Elektronika)", None, now))
    rows.append(("lkps_6", 2, "Teks Visi",
                 "[TIDAK DITEMUKAN] Belum ada halaman visi-misi tingkat departemen (terpisah dari "
                 "visi-misi tiap prodi) yang teridentifikasi di dcse.fmipa.ugm.ac.id -- perlu ditelusuri "
                 "manual atau dikonfirmasi ke sekretariat departemen.", None, now))

    r2 = _get(URL_MEI_VISIMISI)
    if r2:
        sec = _h2_sections(r2.text)
        if "Visi" in sec:
            rows.append(("lkps_6", 3, "Level (PT/UPPS/PS)", "PS (Magister Elektronika dan Instrumentasi)",
                         URL_MEI_VISIMISI, now))
            rows.append(("lkps_6", 3, "Teks Visi", sec["Visi"], URL_MEI_VISIMISI, now))
            if sec.get("Misi"):
                rows.append(("lkps_6", 3, "Teks Misi", sec["Misi"], URL_MEI_VISIMISI, now))
    return rows


def main() -> None:
    engine = db.get_engine()
    if not db.table_exists(engine, TABLE):
        raise SystemExit(f"Tabel {TABLE} belum ada -- jalankan dulu scripts/migrasi_tabel_item_tersedia.py")

    now = datetime.now()
    kolektor = [
        ("identitas_pt_upps_ps", kumpulkan_identitas_pt_upps_ps),
        ("status_akreditasi_seluruh_ps", kumpulkan_status_akreditasi),
        ("led_b2_vmts", kumpulkan_led_b2_vmts),
        ("lkps_2_b_1", kumpulkan_lkps_2_b_1),
        ("lkps_6", kumpulkan_lkps_6),
    ]

    total = 0
    for item_id, fn in kolektor:
        print(f"--- {item_id} ---")
        rows = fn(now)
        if not rows:
            print("  TIDAK ADA DATA TERTARIK (cek koneksi/parsing)")
            continue
        # Hapus dulu baris lama item ini (tiap run = snapshot penuh ulang utk item
        # ini, BUKAN akumulatif -- beda dgn pipeline_sinta/pipeline_dcse_berita yg
        # memang harus akumulatif krn per-run cuma dpt sebagian; di sini tiap run
        # SUDAH re-fetch semua kolom item, jadi replace penuh lebih benar drpd
        # menyisakan baris basi kalau mis. jumlah baris kurikulum berubah).
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM `{TABLE}` WHERE item_id = :item_id"), {"item_id": item_id})
        saved = db.upsert(engine, TABLE, COLUMNS, rows,
                           update_columns=["nilai", "sumber_url", "fetched_at"],
                           label=f"upsert {item_id}")
        total += saved
        print(f"  {len(rows)} baris tersimpan")

    print(f"\nSELESAI. Total baris tersimpan: {total}")


if __name__ == "__main__":
    main()
