"""Tier ekstraksi PATTERN-MATCHING (TANPA AI) -- dicoba SEBELUM fallback ke AI
Luna (ekstraksi_akreditasi.py), khusus utk item registry yang berstruktur
"daftar berulang" (list of records, mis. daftar dosen/tim penyusun/mahasiswa).
Banyak informasi begini bisa didapat murni dari STRUKTUR dokumen (tabel PDF/Word
asli, atau pola teks berulang spt gelar+nama) tanpa perlu panggil LLM sama
sekali -- lebih cepat, gratis, dan confidence-nya pasti (bukan tebakan model).

STATUS (2026-09-16): DIVALIDASI utk 3 kasus (lihat scripts/validasi_ekstraksi_pattern.py):
  A. tim_penyusun_led (LED PDF) -- tabel VERTIKAL (1 tabel kecil = 1 orang,
     tiap baris = 1 field "label : value"): 20/20 Nama + 20/20 Jabatan akurat;
     20/20 Nama juga akurat via pola_narasi (cek mutu jalur fallback).
  B. lkps_2_a_1 (LKPS, Tabel 2.A.1 Data Mahasiswa) -- tabel HORIZONTAL dgn
     header bertingkat & ter-merge: 4/4 baris, 16/16 sel akurat.
  C. lkps_2_a_4 (LKPS, Tabel 2.A.4 Sarana dan Prasarana) -- TABEL KEMBAR: ada
     4 tabel "Sarana dan Prasarana ..." di dokumen yang SAMA (2.A.4 h.18,
     3.A.1 h.37, 4.A.1 h.90, 5.2 h.100). 23/23 baris benar (hal. 18-20),
     0 salah comot dari 3 kembarannya.
BELUM digeneralisasi ke item "daftar berulang" lain & BELUM disambungkan ke
ekstrak_file() di ekstraksi_akreditasi.py -- JANGAN tambah entry baru ke
_TRIGGER_SECTION / _KOLOM_ALIAS / _KOLOM_HORIZONTAL di bawah TANPA validasi
manual serupa (bandingkan hasil ke isi dokumen asli satu per satu), sesuai
instruksi eksplisit user.

6 masalah nyata yang ketemu & sudah diperbaiki SAAT validasi (bukan teoretis --
semuanya awalnya lolos begitu saja & menghasilkan data salah):
  a. Record yang terpotong lintas HALAMAN bikin baris ganda + geser indeks
     (lihat _kumpulkan_kandidat -- fragmen tanpa "Nama" digabung ke record
     sebelumnya).
  b. Regex nama/gelar tanpa pembatasan halaman menangkap nama dari section
     LAIN yg tidak terkait (lihat ekstrak_via_pola_narasi -- window halaman
     dibatasi sama persis spt jalur tabel).
  c. Trigger longgar saja TIDAK cukup memisahkan section kembar antar-dokumen
     (LED vs LKPS sama-sama punya "IDENTITAS TIM PENYUSUN" berstruktur
     identik) -- diselesaikan oleh heuristik _jenis_dokumen, BUKAN dgn
     memperketat trigger.
  d. Parser VERTIKAL dipakai ke tabel HORIZONTAL menghasilkan data ngawur tanpa
     error (1 baris data digabung jadi satu string di kolom yg salah) -- makanya
     dibuat parser terpisah (_parse_tabel_horizontal) + guard signature kolom.
  e. HEADER tabel horizontal yang kebetulan punya sel persis "Nama" ikut
     ketangkap parser vertikal (tabel "Daftar Program Studi" di LED h.3 jadi
     baris palsu) -- diperbaiki dgn mewajibkan sel pemisah ":" setelah label.
  f. Tabel yang membentang banyak halaman hanya terbaca halaman PERTAMANYA,
     karena halaman lanjutan tidak mengulang header (Tabel 2.A.4 cuma dapat
     5 dari 23 baris) -- diperbaiki dgn mewariskan pemetaan kolom ke halaman
     lanjutan (_buat_parser_horizontal), dan mengambil SEMUA baris ber-anchor
     (bukan cuma blok kontigu) krn baris data sering diselingi sub-heading grup.

BATASAN yang DIKETAHUI (sengaja gagal-aman, bukan bug):
  - Sub-tabel dgn jumlah kolom BERBEDA di tengah tabel yang sama ditolak, bukan
    dipaksakan. Contoh: Tabel 2.A.4 hal. 21 (Indikator A1.5 Bandwidth & A1.6
    Lisensi Software) berlayout 8 kolom, bukan 9 -> 10 baris di sana TIDAK
    diekstrak. Lebih baik kosong (lanjut ke AI/manual) drpd salah kolom.
  - Struktur vertikal WAJIB punya sel pemisah ":" (lihat butir e). Dokumen yang
    memakai layout "label | value" tanpa ":" akan ditolak.

MEKANISME 3 LAPIS (revisi 2026-09-16) -- dirancang supaya GENERALISASI ke
dokumen bebas apa pun yang diupload user, bukan cuma 2 PDF referensi ini:

  Lapis 1 -- TRIGGER LONGGAR (ada_trigger_section): daftar SINONIM frasa
    (mis. ["tim penyusun", "identitas tim penyusun", "penyusun"]), TIDAK perlu
    judul persis & TIDAK perlu nomor tabel. Fungsinya cuma "apakah section
    semacam ini kelihatannya ada di dokumen", BUKAN alat presisi. Sengaja
    longgar krn judul tabel antar-prodi/antar-dokumen pasti bervariasi (di SATU
    dokumen LKPS referensi saja sudah ada 4 gaya penulisan + 2 typo:
    "Tabel 2.A..7" titik dobel, "Tabel 2.A.8." titik di akhir, dst).

  Lapis 2 -- STRUCTURE GUARD (_parse_tabel_vertikal/_parse_tabel_horizontal):
    PERTAHANAN UTAMA. Tabel yang signature kolomnya tidak cocok konfig item
    DITOLAK (return []), jadi trigger longgar tidak bikin data salah.

  Lapis 3 -- DISAMBIGUATOR KONTEKS (_deteksi_heading_bagian): untuk kasus di
    mana Lapis 2 TIDAK BISA membedakan karena strukturnya memang identik.
    Contoh nyata: 4 tabel "Sarana dan Prasarana ..." (2.A.4, 3.A.1, 4.A.1, 5.2)
    ada di SATU dokumen LKPS yang sama dengan signature kolom yang praktis
    identik (4.A.1 & 5.2 bahkan sama persis). Pembeda satu-satunya = konteks
    heading bagian TERDEKAT SEBELUM tabel ("3. Relevansi Penelitian" ->
    Bagian 3, "4. Relevansi PkM" -> Bagian 4, dst), dicocokkan ke nomor bagian
    item dari registry (_bagian_dari_tabel).

  Kalau setelah 3 lapis MASIH ada >=2 kandidat yang sama-sama lolos: JANGAN
  pilih otomatis. Kembalikan semuanya di "kandidat_ganda" lengkap dengan
  halaman sumbernya, biar UI menampilkan ke user utk dipilih manual -- reuse
  pola "konflik multi-file" yang sudah ada di tier AI (lihat deteksi_konflik
  di ekstraksi_akreditasi.py & tampilannya di dashboard_render._render_item_form).

  Cek jenis dokumen (_jenis_dokumen) SENGAJA cuma HEURISTIK TAMBAHAN utk kasus
  spesifik LED-vs-LKPS (2 dokumen yang kita tahu polanya & punya section tim
  penyusun kembar berstruktur identik). BUKAN mekanisme utama -- dokumen
  pendukung lain yang nanti diupload user (Excel data mahasiswa, scan SK, dst)
  tidak punya "sampul jenis dokumen" untuk dicek.

Urutan metode ekstraksi per item: tabel asli dulu (confidence tinggi), baru
pola narasi (confidence lebih rendah), baru menyerah ke AI Luna/manual.
"""

import re

from registry_kebutuhan_data import KEBUTUHAN_DATA, _bagian_dari_tabel

# ---------- LAPIS 1: trigger LONGGAR (daftar sinonim) per item ----------
# Cukup SATU sinonim match (substring case-insensitive, whitespace dirapatkan).
# SENGAJA tidak memuat nomor tabel & tidak harus judul persis -- presisi
# diserahkan ke Lapis 2 (structure guard) & Lapis 3 (konteks bagian).
# Sinonim WAJIB diverifikasi ada di dokumen nyata, jangan dikarang: saat
# validasi, "anggota penyusun" ternyata 0 kemunculan di kedua PDF referensi.
_TRIGGER_SECTION: dict[str, list[str]] = {
    "tim_penyusun_led": ["identitas tim penyusun", "tim penyusun", "penyusun"],
    "lkps_2_a_1": ["data mahasiswa", "daya tampung"],
    "lkps_2_a_4": ["sarana dan prasarana", "sarana prasarana", "prasarana"],
}

# ---------- LAPIS 3: konteks Bagian LKPS (disambiguator tabel kembar) ----------
# Heading bagian di dokumen LKPS dikenali dari "<nomor>. <judul>" DI MANA nomor
# DAN salah satu sinonim judul harus sama-sama cocok -- syarat ganda ini yang
# menyaring noise (dokumen referensi punya ratusan baris "2. Sertifikasi ...",
# "3. Pelatihan ..." yang bukan heading bagian). Terbukti menghasilkan tepat 6
# heading, satu per bagian, tanpa false positive.
# Judul di PDF TIDAK selalu sama dgn LABEL_BAGIAN_LKPS di registry (mis. Bagian
# 1 di registry "Tata Kelola" tapi di PDF "Budaya Mutu"), makanya dipakai daftar
# sinonim, bukan label registry.
_KONTEKS_BAGIAN: dict[str, list[str]] = {
    "1": ["budaya mutu", "tata kelola"],
    "2": ["relevansi pendidikan", "pendidikan"],
    "3": ["relevansi penelitian", "penelitian"],
    "4": ["relevansi pkm", "pkm", "pengabdian kepada masyarakat"],
    "5": ["akuntabilitas"],
    "6": ["diferensiasi misi"],
}
_HEADING_BAGIAN_RE = re.compile(r"^([1-6])\.\s+(.{4,50})$")

# ---------- Heuristik TAMBAHAN (bukan mekanisme utama): jenis dokumen ----------
# HANYA utk kasus LED-vs-LKPS yang polanya sudah kita tahu: dua dokumen ini
# punya section "IDENTITAS TIM PENYUSUN" kembar dengan struktur tabel IDENTIK,
# jadi Lapis 2 tidak bisa membedakan. Item di _DOKUMEN_WAJIB cuma dicoba kalau
# jenis dokumennya cocok ATAU tidak terdeteksi (dokumen lain -- Excel, scan SK,
# dst -- tidak punya sampul begini, jadi TIDAK boleh diblokir gara-gara ini).
_JENIS_DOKUMEN = {
    "LED": "laporan evaluasi diri",
    "LKPS": "laporan kinerja program studi",
}
_DOKUMEN_WAJIB: dict[str, str] = {"tim_penyusun_led": "LED"}

# ---------- Alias label kolom (huruf kecil, tanpa titik dua) -> kolom_dibutuhkan registry ----------
# Dipakai TAHAP 2.1 (parse tabel vertikal: 1 tabel = 1 record, tiap baris = 1
# field "label : value") -- lihat _parse_tabel_vertikal(). Item baru WAJIB
# divalidasi manual dulu (cek 1 dokumen nyata) sebelum ditambah ke sini.
_KOLOM_ALIAS: dict[str, dict[str, str]] = {
    "tim_penyusun_led": {
        "nama": "Nama",
        "jabatan": "Jabatan dalam Tim",
        "tugas": "Tanggung Jawab Bab/Kriteria",
        "tanggung jawab": "Tanggung Jawab Bab/Kriteria",
    },
}

# ---------- Konfigurasi tabel HORIZONTAL (1 baris = 1 entitas, kolom = field) ----------
# Struktur KEDUA yang divalidasi (setelah tabel vertikal spt tim_penyusun_led).
# Tabel LKPS pakai header BERTINGKAT & ter-merge (mis. Tabel 2.A.1: grup "Jumlah
# Calon Mahasiswa"/"Jumlah Mahasiswa Baru"/"Jumlah Mahasiswa Aktif" masing-masing
# membawahi sub-kolom Reguler/RPL x Diterima/Afirmasi/Kebutuhan Khusus), sementara
# kolom_dibutuhkan di registry sudah DIRINGKAS jadi beberapa kolom gabungan saja
# (lihat nama kolomnya: "(Reguler/RPL/Afirmasi/Keb. Khusus)"). Jadi pemetaannya
# BUKAN 1 kolom PDF : 1 kolom registry, tapi SATU RENTANG kolom PDF -> 1 kolom
# registry (nilainya digabung pakai " / " sesuai urutan di dokumen).
#
# Tiap entry "kolom" dicocokkan lewat SIGNATURE kolom = gabungan semua sel header
# di kolom itu (lihat _signature_kolom). Rentangnya otomatis: dari kolom awal
# sampai SEBELUM kolom awal entry berikutnya. Entry dgn registry=None sengaja
# "membuang" rentang kolom yg tidak dipakai registry, sekaligus jadi penanda
# BATAS akhir rentang entry sebelumnya (tanpa ini, rentang "Jumlah Mahasiswa
# Baru" akan bocor menelan kolom-kolom "Jumlah Mahasiswa Aktif").
# `hanya_satu_kolom`: ambil kolom awalnya saja, jangan serentang.
_KOLOM_HORIZONTAL: dict[str, dict] = {
    "lkps_2_a_1": {
        # Baris data dikenali dari sel kolom pertama. Baris "Jumlah" SENGAJA tidak
        # diikutkan -- itu baris TOTAL, bukan entitas (kolom registry-nya sendiri
        # cuma menyebut TS-3/TS-2/TS-1/TS).
        "anchor_baris": r"^TS(-\d)?$",
        "kolom": [
            {"sig": "ts", "registry": "Tahun (TS-3/TS-2/TS-1/TS)", "hanya_satu_kolom": True},
            {"sig": "daya tampung", "registry": "Daya Tampung", "hanya_satu_kolom": True},
            {"sig": "jumlah calon mahasiswa",
             "registry": "Jumlah Pendaftar (Reguler/RPL/Afirmasi/Keb. Khusus)"},
            {"sig": "jumlah mahasiswa baru",
             "registry": "Jumlah Diterima (Reguler/RPL/Afirmasi/Keb. Khusus)"},
            # Rincian Reguler/RPL mahasiswa aktif TIDAK dipakai registry (registry
            # cuma minta totalnya) -- diklaim lalu dibuang, sekaligus jadi batas
            # akhir rentang "jumlah mahasiswa baru" di atas.
            {"sig": "jumlah mahasiswa aktif", "registry": None},
            {"sig": "total mahasiswa aktif", "registry": "Jumlah Mahasiswa Aktif",
             "hanya_satu_kolom": True},
        ],
    },
    # Tabel 2.A.4 Sarana dan Prasarana Pendidikan -- salah satu dari EMPAT tabel
    # "Sarana dan Prasarana ..." di dokumen LKPS yang sama (2.A.4, 3.A.1, 4.A.1,
    # 5.2) yang signature kolomnya praktis identik. Sengaja dikonfigurasi utk
    # menguji Lapis 3 (konteks bagian) -- tanpa itu, keempatnya tidak
    # terbedakan sama sekali oleh structure guard.
    "lkps_2_a_4": {
        "anchor_baris": r"^\d{1,3}$",  # kolom "no" urut 1,2,3,...
        "kolom": [
            {"sig": "no", "registry": None, "hanya_satu_kolom": True},
            {"sig": "nama prasarana", "registry": "Nama Ruang/Fasilitas", "hanya_satu_kolom": True},
            {"sig": "daya tampung", "registry": "Daya Tampung", "hanya_satu_kolom": True},
            {"sig": "luas ruang", "registry": "Luas (m2)", "hanya_satu_kolom": True},
            {"sig": "milik sendiri", "registry": "Status Kepemilikan", "hanya_satu_kolom": True},
            {"sig": "berlisensi", "registry": "Status Lisensi Perangkat Lunak",
             "hanya_satu_kolom": True},
            {"sig": "perangkat", "registry": "Daftar Perangkat", "hanya_satu_kolom": True},
            {"sig": "link bukti", "registry": "Link Bukti", "hanya_satu_kolom": True},
        ],
    },
}

# ---------- TAHAP 2.2: pola narasi (gelar akademik Indonesia + nama) ----------
# Dipakai HANYA kalau tabel gagal/kosong. Sengaja cuma menangkap NAMA (+gelar) --
# TIDAK mencoba pasangkan Jabatan/Tanggung Jawab dari teks bebas (itu alasan
# confidence-nya lebih rendah drpd tabel, sesuai instruksi user).
_GELAR_DEPAN = r"(?:Prof|Dr|Drs|Dra|Ir|drg|H|Hj|techn|Techn)\.?"
_DEPAN = rf"(?:{_GELAR_DEPAN}\s+){{0,3}}"
_NAMA_INTI = r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,5}"
_GELAR_TOKEN = r"[A-Z][A-Za-z]{0,4}\.(?:[A-Z][A-Za-z]{0,4}\.)*"
_GELAR_BELAKANG = rf"{_GELAR_TOKEN}(?:\s*,\s*{_GELAR_TOKEN})*"
_NAMA_GELAR_RE = re.compile(rf"(?P<nama>{_DEPAN}{_NAMA_INTI}\s*,\s*{_GELAR_BELAKANG})")


def _normalisasi(teks: str) -> str:
    """Rapatkan semua whitespace jadi 1 spasi + lowercase, supaya frasa trigger
    tetap ketemu walau di PDF aslinya terpotong antar-baris/antar-kolom (mis.
    heading "IDENTITAS TIM PENYUSUN\\nLAPORAN EVALUASI DIRI")."""
    return re.sub(r"\s+", " ", teks).lower()


def ada_trigger_section(item_id: str, teks_dokumen: str) -> bool:
    """TAHAP 1 -- True kalau >=1 frasa trigger utk item ini ditemukan (substring
    case-insensitive, whitespace dirapatkan dulu) di teks dokumen. Item tanpa
    entry di _TRIGGER_SECTION SELALU False (belum divalidasi -- lihat docstring
    modul)."""
    triggers = _TRIGGER_SECTION.get(item_id)
    if not triggers:
        return False
    teks_rapat = _normalisasi(teks_dokumen)
    return any(trig in teks_rapat for trig in triggers)


def _label_dari_sel(sel: str) -> str:
    return re.sub(r"[:\s]+$", "", (sel or "").strip()).lower()


def _parse_tabel_vertikal(tabel: list, alias: dict[str, str]) -> dict[str, str]:
    """Parse SATU tabel "vertikal" (pola yang ditemukan di PDF LED asli: tiap
    tabel kecil = 1 record/orang, tiap baris = 1 field "[no_urut?, label, ':',
    value]"). Return {kolom_registry: value} -- KOSONG kalau tabel ini tidak
    match label manapun di `alias` (bukan tabel person, dilewati)."""
    hasil: dict[str, str] = {}
    for row in tabel:
        sel = [c for c in row if c is not None and c != ""]
        if len(sel) < 2:
            continue
        for idx, cell in enumerate(sel):
            label = _label_dari_sel(cell)
            if label in alias:
                # WAJIB ada sel pemisah ":" tepat setelah label -- itulah ciri
                # struktur "label : value". Tanpa syarat ini, HEADER tabel
                # HORIZONTAL yang kebetulan punya sel persis "Nama" ikut
                # ketangkap (kasus nyata: tabel "Daftar Program Studi" di LED
                # hal. 3 menghasilkan baris palsu 'Akreditasi Program Studi
                # Jumlah' sbg Nama).
                if idx + 1 >= len(sel) or sel[idx + 1].strip() != ":":
                    break
                sisa = [v.strip() for v in sel[idx + 1:] if v and v.strip() and v.strip() != ":"]
                if sisa:
                    # Rapikan newline di DALAM sel -- pdfplumber mempertahankan
                    # line-wrap asli PDF (mis. gelar panjang yang dipotong ke baris
                    # berikutnya jadi "S.Si.,\nM.Sc."), padahal itu satu nilai utuh.
                    hasil[alias[label]] = re.sub(r"\s+", " ", " ".join(sisa)).strip()
                break
    return hasil


def _cari_halaman_trigger_pdf(pdf, item_id: str) -> "int | None":
    triggers = _TRIGGER_SECTION.get(item_id)
    if not triggers:
        return None
    for i, page in enumerate(pdf.pages):
        teks = _normalisasi(page.extract_text() or "")
        if any(trig in teks for trig in triggers):
            return i
    return None


def _buat_parser_horizontal(konfig: dict):
    """Parser horizontal BER-STATE: mengingat pemetaan kolom dari halaman
    terakhir yang punya header, supaya halaman LANJUTAN (yang tabelnya langsung
    mulai dari baris data) tetap bisa diekstrak. State di-reset tiap blok
    kandidat berakhir, supaya pemetaan tidak bocor ke tabel kembar di bagian
    dokumen lain. Return (parse, reset)."""
    state: dict = {"rentang": None}

    def _parse(tabel):
        hasil = _parse_tabel_horizontal(tabel, konfig, state["rentang"])
        if hasil and state["rentang"] is None:
            # simpan pemetaan dari tabel BER-HEADER pertama di blok ini
            n_kol = max(len(r) for r in tabel)
            rows = [list(r) + [""] * (n_kol - len(r)) for r in tabel]
            blok = _blok_baris_data(rows, re.compile(konfig["anchor_baris"], re.I))
            if blok and blok[0] > 0:
                state["rentang"] = _petakan_kolom_horizontal(rows, konfig, blok[0], n_kol)
        return hasil

    def _reset():
        state["rentang"] = None

    return _parse, _reset


def _kumpulkan_kandidat(pdf, parse_tabel, gabung_lanjutan: bool, reset_state=None) -> list[dict]:
    """LAPIS 2 -- scan SELURUH dokumen, kumpulkan semua BLOK kandidat yang lolos
    structure guard. Blok = deretan halaman BERURUTAN yang punya tabel lolos
    guard (tabel panjang yang membentang banyak halaman tetap jadi 1 blok;
    tabel kembar di bagian dokumen lain jadi blok TERPISAH supaya bisa
    dibedakan/ditawarkan ke user, bukan diam-diam digabung jadi satu).

    `gabung_lanjutan` utk pola VERTIKAL: record yang terpotong lintas halaman
    (baris "Nama" di halaman N, sisa field di N+1 -- kasus nyata orang ke-5 di
    PDF LED) digabung ke record sebelumnya, bukan jadi record baru."""
    kandidat: list[dict] = []
    aktif: "dict | None" = None
    for i, page in enumerate(pdf.pages):
        baris_halaman = []
        for tbl in page.extract_tables():
            hasil = parse_tabel(tbl)
            if hasil:
                baris_halaman.extend(hasil)
        if baris_halaman:
            if aktif is None:
                aktif = {"halaman_mulai": i, "halaman_akhir": i, "baris": []}
            aktif["halaman_akhir"] = i
            for rec in baris_halaman:
                if gabung_lanjutan and aktif["baris"] and "Nama" not in rec:
                    aktif["baris"][-1].update(rec)
                else:
                    aktif["baris"].append(rec)
        elif aktif is not None:
            kandidat.append(aktif)
            aktif = None
            if reset_state:
                reset_state()
    if aktif is not None:
        kandidat.append(aktif)
    return kandidat


def _saring_kandidat(kandidat: list[dict], item_id: str, pdf) -> list[dict]:
    """LAPIS 1 + LAPIS 3 -- saring blok kandidat dgn trigger longgar lalu
    konteks bagian. Penyaringan bersifat "kalau tidak yakin, JANGAN buang":
    lapis yang tidak bisa diterapkan (mis. item tanpa nomor tabel -> tidak
    punya bagian harapan) dilewati, bukan menggugurkan kandidat."""
    if len(kandidat) <= 1:
        return kandidat

    # --- Lapis 1: frasa trigger harus muncul di halaman blok atau tepat sebelumnya
    triggers = _TRIGGER_SECTION.get(item_id) or []
    if triggers:
        teks_hal = {}

        def _teks(i):
            if i not in teks_hal:
                teks_hal[i] = _normalisasi(pdf.pages[i].extract_text() or "")
            return teks_hal[i]

        lolos = [k for k in kandidat
                 if any(t in _teks(i)
                        for i in range(max(0, k["halaman_mulai"] - 1), k["halaman_akhir"] + 1)
                        for t in triggers)]
        if lolos:
            kandidat = lolos
    if len(kandidat) <= 1:
        return kandidat

    # --- Lapis 3: konteks bagian terdekat sebelum tabel harus cocok registry
    harapan = _bagian_diharapkan(item_id)
    if harapan:
        heading = _deteksi_heading_bagian(pdf)
        if heading:
            lolos = [k for k in kandidat
                     if _bagian_di_halaman(heading, k["halaman_mulai"]) == harapan]
            if lolos:
                kandidat = lolos
    return kandidat


def ekstrak_via_tabel_pdf(pdf_path: str, item_id: str) -> list[dict[str, str]]:
    """Ekstraksi tabel VERTIKAL (1 tabel kecil = 1 record). Dipertahankan sbg
    API lama (return list baris saja); pemakaian penuh 3 lapis + kandidat ganda
    ada di ekstrak_pattern_pdf()."""
    import pdfplumber

    alias = _KOLOM_ALIAS.get(item_id)
    if not alias:
        return []
    with pdfplumber.open(pdf_path) as pdf:
        kandidat = _kumpulkan_kandidat(
            pdf, lambda t: ([r] if (r := _parse_tabel_vertikal(t, alias)) else []), True)
        kandidat = _saring_kandidat(kandidat, item_id, pdf)
        return kandidat[0]["baris"] if len(kandidat) == 1 else []


def _jenis_dokumen(teks_awal: str) -> "str | None":
    """Heuristik TAMBAHAN (bukan mekanisme utama -- lihat docstring modul):
    tebak jenis dokumen dari sampul. None kalau tidak yakin / dokumen jenis
    lain (Excel, scan SK, dst) -- dan None TIDAK boleh memblokir ekstraksi."""
    t = _normalisasi(teks_awal)
    cocok = [nama for nama, frasa in _JENIS_DOKUMEN.items() if frasa in t]
    return cocok[0] if len(cocok) == 1 else None


def _deteksi_heading_bagian(pdf) -> list[tuple[int, str]]:
    """LAPIS 3 -- daftar (indeks_halaman, nomor_bagian) tiap heading bagian LKPS
    yang ditemukan, urut halaman. Syarat GANDA (nomor cocok DAN judul memuat
    salah satu sinonim bagian itu) -- lihat catatan di _KONTEKS_BAGIAN."""
    hasil = []
    for i, page in enumerate(pdf.pages):
        for baris in (page.extract_text() or "").split("\n"):
            m = _HEADING_BAGIAN_RE.match(re.sub(r"\s+", " ", baris.strip()))
            if not m:
                continue
            nomor, judul = m.group(1), m.group(2).lower()
            if any(k in judul for k in _KONTEKS_BAGIAN[nomor]):
                hasil.append((i, nomor))
    return hasil


def _bagian_di_halaman(heading: list[tuple[int, str]], halaman: int) -> "str | None":
    """Nomor bagian yang berlaku di suatu halaman = heading bagian TERAKHIR
    yang muncul pada/atau sebelum halaman itu."""
    sebelum = [nomor for hal, nomor in heading if hal <= halaman]
    return sebelum[-1] if sebelum else None


def _bagian_diharapkan(item_id: str) -> "str | None":
    """Nomor bagian yang SEHARUSNYA memuat item ini, diambil dari nomor tabel
    di registry (mis. "2.A.4" -> "2"). None kalau item tidak punya nomor tabel
    (mis. tim_penyusun_led) -- berarti Lapis 3 tidak dipakai utk item itu."""
    item = KEBUTUHAN_DATA.get(item_id)
    return _bagian_dari_tabel(item["tabel_lkps"]) if item else None


def _signature_kolom(tabel: list, batas_header: int, n_kol: int) -> list[str]:
    """Signature tiap kolom = gabungan semua sel header (baris 0..batas_header-1)
    di kolom itu. SENGAJA TIDAK pakai forward-fill sel merge: forward-fill
    terbukti membocorkan label satu kolom ke semua kolom di kanannya (mis.
    "Daya" nempel ke 17 kolom lain di Tabel 2.A.1)."""
    sig = []
    for j in range(n_kol):
        bagian = [re.sub(r"\s+", " ", (tabel[i][j] or "").strip()) for i in range(batas_header)]
        sig.append(" ".join(b for b in bagian if b).lower())
    return sig


def _blok_baris_data(tabel: list, anchor_re) -> list[int]:
    """Indeks baris data = blok KONTIGU TERPANJANG dari baris yang sel pertamanya
    match anchor. Pakai blok kontigu (bukan semua baris yg match) karena HEADER
    tabel pun sering punya sel yg match anchor (mis. label kolom "TS" di Tabel
    2.A.1 berdiri sendiri di baris header) -- baris header spt itu terisolasi,
    sedangkan baris data selalu berderet."""
    cocok = [i for i, r in enumerate(tabel)
             if anchor_re.match(re.sub(r"\s+", " ", (r[0] or "").strip()))]
    if not cocok:
        return []
    blok, cur = [], [cocok[0]]
    for a, b in zip(cocok, cocok[1:]):
        if b == a + 1:
            cur.append(b)
        else:
            blok.append(cur)
            cur = [b]
    blok.append(cur)
    return max(blok, key=len)


def _petakan_kolom_horizontal(tabel: list, konfig: dict, batas_header: int,
                               n_kol: int) -> "list[tuple[list[int], dict]] | None":
    """Hitung pemetaan rentang kolom PDF -> kolom registry dari baris HEADER.
    None kalau ada entry konfig yang signature-nya tidak ketemu (= tabel ini
    bukan yang dicari; lebih baik gagal drpd memetakan kolom yang salah)."""
    sig = _signature_kolom(tabel, batas_header, n_kol)
    awal = []
    for entry in konfig["kolom"]:
        ketemu = next((j for j, s in enumerate(sig) if entry["sig"] in s), None)
        if ketemu is None:
            return None
        awal.append((ketemu, entry))
    awal.sort(key=lambda x: x[0])

    rentang: list[tuple[list[int], dict]] = []
    for pos, (mulai, entry) in enumerate(awal):
        if entry.get("hanya_satu_kolom"):
            kolom = [mulai]
        else:
            akhir = awal[pos + 1][0] if pos + 1 < len(awal) else n_kol
            kolom = list(range(mulai, akhir))
        rentang.append((kolom, entry))
    return rentang


def _parse_tabel_horizontal(tabel: list, konfig: dict,
                             rentang_warisan: "list | None" = None) -> list[dict[str, str]]:
    """Parse SATU tabel horizontal (1 baris = 1 entitas) jadi list record.
    Return [] kalau tabel ini tidak cocok konfig (bukan tabel yang dicari).

    `rentang_warisan` = pemetaan kolom dari halaman SEBELUMNYA, dipakai kalau
    tabel ini adalah LANJUTAN yang langsung mulai dari baris data tanpa
    mengulang header (kasus nyata: Tabel 2.A.4 membentang hal. 18-21, hanya
    hal. 18 yang punya baris header)."""
    if not tabel:
        return []
    n_kol = max(len(r) for r in tabel)
    tabel = [list(r) + [""] * (n_kol - len(r)) for r in tabel]

    anchor = re.compile(konfig["anchor_baris"], re.I)
    blok = _blok_baris_data(tabel, anchor)
    if not blok:
        return []

    if blok[0] > 0:
        rentang = _petakan_kolom_horizontal(tabel, konfig, blok[0], n_kol)
        if rentang is None:
            return []
        batas = blok[0]
    else:
        # Halaman lanjutan (tanpa header): hanya boleh pakai pemetaan warisan,
        # dan cuma kalau jumlah kolomnya sama persis.
        if not rentang_warisan or max(k for kol, _ in rentang_warisan for k in kol) >= n_kol:
            return []
        rentang = rentang_warisan
        batas = 0

    # Ambil SEMUA baris ber-anchor sejak batas header -- bukan cuma blok kontigu
    # terpanjang, karena baris data sering diselingi sub-heading grup di
    # tengah tabel (mis. "Indikator A1.1", "Indikator A1.2" di Tabel 2.A.4).
    idx_data = [i for i in range(batas, len(tabel))
                if anchor.match(re.sub(r"\s+", " ", (tabel[i][0] or "").strip()))]

    records = []
    for i in idx_data:
        rec: dict[str, str] = {}
        for kolom, entry in rentang:
            if entry["registry"] is None:
                continue
            nilai = [re.sub(r"\s+", " ", (tabel[i][j] or "").strip()) for j in kolom]
            # Buang sel kosong & placeholder "-" (lihat kebijakan: jangan isi
            # placeholder, biarkan kosong supaya jelas datanya memang tidak ada).
            nilai = [v for v in nilai if v and v != "-"]
            if nilai:
                rec[entry["registry"]] = " / ".join(nilai)
        if rec:
            records.append(rec)
    return records


def ekstrak_via_tabel_horizontal_pdf(pdf_path: str, item_id: str) -> list[dict[str, str]]:
    """Ekstraksi tabel HORIZONTAL (1 baris = 1 entitas). API lama (return list
    baris saja); pemakaian penuh 3 lapis ada di ekstrak_pattern_pdf()."""
    import pdfplumber

    konfig = _KOLOM_HORIZONTAL.get(item_id)
    if not konfig:
        return []
    with pdfplumber.open(pdf_path) as pdf:
        parse, reset = _buat_parser_horizontal(konfig)
        kandidat = _kumpulkan_kandidat(pdf, parse, False, reset)
        kandidat = _saring_kandidat(kandidat, item_id, pdf)
        return kandidat[0]["baris"] if len(kandidat) == 1 else []


def ekstrak_via_pola_narasi(pdf_path: str, item_id: str) -> list[dict[str, str]]:
    """TAHAP 2.2 -- Fallback kalau tabel gagal: regex gelar akademik Indonesia +
    nama, HALAMAN PER HALAMAN dgn pembatasan window YANG SAMA persis dgn tabel
    (berhenti 1 halaman setelah halaman terakhir yg masih ada match).

    PENTING (ditemukan saat validasi): membiarkan regex ini jalan ke SELURUH
    teks dokumen (tanpa pembatasan halaman) menghasilkan FALSE POSITIVE dari
    bagian dokumen lain yg tidak terkait (mis. nama pejabat lain yg disebut
    sbg referensi di section lain) -- makanya WAJIB dibatasi ke window trigger
    section yg sama spt tabel, BUKAN teks dokumen penuh.

    HANYA dipakai utk item yang punya kolom "Nama" di alias (lihat
    _KOLOM_ALIAS) -- utk item lain, return []. Confidence LEBIH RENDAH drpd
    tabel: cuma menangkap nama, kolom lain (Jabatan dst) dibiarkan kosong."""
    import pdfplumber

    alias = _KOLOM_ALIAS.get(item_id)
    if not alias or "Nama" not in alias.values():
        return []

    records: list[dict[str, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        mulai = _cari_halaman_trigger_pdf(pdf, item_id)
        if mulai is None:
            return []
        halaman_kosong_berturut = 0
        for i in range(mulai, len(pdf.pages)):
            teks_rapat = re.sub(r"\s+", " ", pdf.pages[i].extract_text() or "")
            matches = [m.group("nama").strip() for m in _NAMA_GELAR_RE.finditer(teks_rapat)]
            if matches:
                records.extend({"Nama": n} for n in matches)
                halaman_kosong_berturut = 0
            elif records:
                halaman_kosong_berturut += 1
                if halaman_kosong_berturut >= 1:
                    break
    return records


def ekstrak_pattern_pdf(pdf_path: str, item_id: str, teks_dokumen: str) -> dict:
    """Entry point tier pattern-matching utk 1 item dari 1 file PDF, memakai
    mekanisme 3 lapis penuh (lihat docstring modul).

    Return {"metode": "tabel_terdeteksi" | "pola_narasi" | "kandidat_ganda" |
                      "tidak_ditemukan",
            "baris": [{kolom_registry: value}, ...],   # kosong kalau kandidat_ganda
            "kandidat_ganda": [{"halaman_mulai", "halaman_akhir", "baris"}, ...]}

    "kandidat_ganda" = ada >=2 section yang sama-sama lolos 3 lapis. SENGAJA
    tidak dipilihkan otomatis -- caller (UI) menampilkan semuanya + halaman
    sumbernya ke user, sama seperti penanganan konflik multi-file di tier AI."""
    import pdfplumber

    kosong = {"metode": "tidak_ditemukan", "baris": [], "kandidat_ganda": []}
    if not ada_trigger_section(item_id, teks_dokumen):
        return kosong

    # Heuristik TAMBAHAN: kalau item ini khusus satu jenis dokumen DAN jenis
    # dokumen terdeteksi jelas TAPI tidak cocok -> lewati. Dokumen yang jenisnya
    # tidak terdeteksi (Excel, scan SK, dll) TIDAK diblokir.
    wajib = _DOKUMEN_WAJIB.get(item_id)
    if wajib:
        jenis = _jenis_dokumen(teks_dokumen[:4000])
        if jenis is not None and jenis != wajib:
            return kosong

    alias = _KOLOM_ALIAS.get(item_id)
    konfig = _KOLOM_HORIZONTAL.get(item_id)

    # Item hanya terdaftar di SALAH SATU konfig: vertikal (1 tabel = 1 record)
    # atau horizontal (1 baris = 1 entitas).
    if alias:
        def _parse(t):
            rec = _parse_tabel_vertikal(t, alias)
            return [rec] if rec else []
        _reset = None
        gabung_lanjutan = True
    elif konfig:
        _parse, _reset = _buat_parser_horizontal(konfig)
        gabung_lanjutan = False
    else:
        return kosong

    with pdfplumber.open(pdf_path) as pdf:
        kandidat = _kumpulkan_kandidat(pdf, _parse, gabung_lanjutan, _reset)
        kandidat = _saring_kandidat(kandidat, item_id, pdf)

        if len(kandidat) == 1:
            return {"metode": "tabel_terdeteksi", "baris": kandidat[0]["baris"],
                    "kandidat_ganda": []}
        if len(kandidat) > 1:
            return {"metode": "kandidat_ganda", "baris": [],
                    "kandidat_ganda": [
                        {"halaman_mulai": k["halaman_mulai"] + 1,   # 1-based utk user
                         "halaman_akhir": k["halaman_akhir"] + 1,
                         "baris": k["baris"]}
                        for k in kandidat]}

    baris_narasi = ekstrak_via_pola_narasi(pdf_path, item_id)
    if baris_narasi:
        return {"metode": "pola_narasi", "baris": baris_narasi, "kandidat_ganda": []}
    return kosong
