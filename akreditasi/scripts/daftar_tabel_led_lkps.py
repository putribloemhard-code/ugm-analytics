# -*- coding: utf-8 -*-
"""Ekstraksi daftar tabel LED + LKPS Prodi S2 Elektronika dan Instrumentasi (MEI).

Sumber: akreditasi/docs/sumber/{LED,LKPS}_Prodi_S2_Elektronika_dan_Instrumentasi.pdf

Dipakai dua pemakai:
  - generate_daftar_tabel_led_lkps.py  -> menulis akreditasi/docs/Daftar_Tabel_LED_dan_LKPS_MEI.md
  - generate_xlsx_tabel_led_lkps.py    -> menulis satu .xlsx per tabel (LED 42, LKPS 38)

Semua nama kolom di sini = satu sumber kebenaran, jangan disalin ulang ke pemakai.
"""
import difflib
import re

import pymupdf

BASE = "D:/ugm-analytics/akreditasi/docs/sumber/"
LED = BASE + "LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf"
LKPS = BASE + "LKPS_Prodi_S2_Elektronika_dan_Instrumentasi.pdf"
MD = "D:/ugm-analytics/akreditasi/docs/Daftar_Tabel_LED_dan_LKPS_MEI.md"
DIR_XLSX = "D:/ugm-analytics/akreditasi/docs/tabel_xlsx"

HEADER_MAXLEN = 40
SEP = " ǀ "

# Halaman DAFTAR TABEL LED (indeks 0 = halaman PDF 1).
LED_TOC_PAGES = [11, 12]
# Halaman LKPS berisi tabel tanpa nomor (daftar program studi) — indeks 0-based.
LKPS_TANPA_NOMOR_PAGE = 1

# Kosakata nama kolom yang dikenal -> dipakai untuk mengenali baris header & merapikan
# tanda tangan header LED (sel di luar kosakata = data yang bocor ke baris header).
VOCAB = [
    "no", "no.", "referensi", "referensi/kebijakan/standar", "referensi penetapan",
    "indikator", "iku", "ikt", "iku/ikt", "iku /ikt", "iku/i kt", "iku/ ikt",
    "sasaran/target", "target", "standar/target", "capaian", "capaian kinerja",
    "capaian/kinerja", "kinerja", "ts-2", "ts-1", "ts", "ts- 2", "ts- 1", "jumlah",
    "nama prasarana", "daya", "daya tampung", "luas", "luas ruang", "milik",
    "milik sendiri", "berlisensi", "berlisensi (l)/", "perangkat", "link bukti",
    "kode mk", "kode", "nama mata kuliah", "mata kuliah", "status", "sks",
    "semester", "cpl", "keterangan kekhasan", "domain penerapan", "metode analisis",
    "nama", "judul", "tahun", "sumber", "durasi", "pendanaan", "unit kerja",
    "nama unit", "dokumen spmi", "laporan audit", "spesifikasi kkni",
    "capaian pembelajaran lulusan (cpl)", "temuan", "parameter",
    "pilar strategis", "fokus riset bidang elektronika dan instrumentasi",
    "target teknologi utama", "jenis program", "nama program studi", "program studi",
    "jumlah mahasiswa saat ts 4)", "tgl. kadaluarsa", "no. dan tgl. sk",
]
VOCAB_SET = set(VOCAB)


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def canon(cell):
    """Kembalikan token kosakata (huruf kecil) atau None bila sel tampak seperti data."""
    c = norm(cell)
    if not c:
        return None
    # "TS- 1"/"TS-1"/"ts-1" -> satu bentuk supaya tidak terpecah jadi ragam header berbeda
    key = re.sub(r"\s+", " ", c.lower().rstrip(".:"))
    key = re.sub(r"(ts|iku|ikt)\s*-\s*(\d)", r"\1-\2", key)
    key = re.sub(r"\s*/\s*", "/", key)
    # "iku/i kt", "iku /ikt", "iku/ ikt" -> satu bentuk "iku/ikt"
    key = re.sub(r"iku\s*/\s*i\s*kt\b", "iku/ikt", key)
    if key in VOCAB_SET:
        return key
    # header bisa tercampur data dalam satu sel ("TS-2 9 3") -> ambil token kosakata di depan
    for v in VOCAB:
        if key.startswith(v + " ") and len(v) >= 3:
            return v
    return None


def _baris_header(r):
    """True bila baris layak dihitung header: kosong, atau semua sel pendek, ada yang
    berhuruf, dan tidak ada sel angka-murni (angka = data, walau pendek)."""
    cells = [norm(c) for c in r]
    nonempty = [c for c in cells if c]
    if not nonempty:
        return True
    if any(len(c) > HEADER_MAXLEN for c in nonempty):
        return False
    if not any(re.search(r"[A-Za-z]", c) for c in nonempty):
        return False
    # sel angka-murni (boleh berisi tanda baca/centang) -> baris data
    if any(re.fullmatch(r"[\d.,\s%\-+/()√vV×xX]*", c) for c in nonempty):
        return False
    return True


def header_columns(table, rows, max_rows=10):
    """Gabung baris header bertingkat per kolom. Baris header = deretan sel pendek
    berhuruf di atas tabel; berhenti di baris pertama yang berisi data (sel panjang
    atau angka). Baris spanduk dilewati tanpa menghentikan pemindaian."""
    idx = []
    for i, r in enumerate(rows[:max_rows]):
        joined = " ".join(norm(c) for c in r if norm(c)).lower()
        # baris spanduk "Roadmap / Link dokumen roadmap ..." menjorok ke area header:
        # dilewati (tidak ikut digabung), pemindaian lanjut ke baris berikutnya.
        if joined.startswith("roadmap") or "link dokumen roadmap" in joined:
            continue
        if _baris_header(r):
            idx.append(i)
        else:
            break
    if not idx:
        # baris pertama bukan header (mis. berisi URL panjang dari spanduk Roadmap):
        # cari deret baris header pertama di beberapa baris teratas.
        for i in range(min(6, len(rows))):
            if _baris_header(rows[i]) and sum(1 for c in rows[i] if norm(c)) >= 3:
                idx = [j for j in range(i, min(i + 3, len(rows))) if _baris_header(rows[j])]
                break
    if not idx:
        idx = [0]
    out = []
    for ci in range(len(rows[0])):
        parts = []
        for ri in idx:
            v = norm(rows[ri][ci]) if ci < len(rows[ri]) else ""
            if v and v not in parts:
                parts.append(v)
        out.append(" ".join(parts) if parts else "-")
    return out


def page_blocks(page):
    """Blok tabel satu halaman: (y0, nbaris, header) — blok <2 baris dibuang."""
    out = []
    try:
        tabs = page.find_tables()
    except Exception:
        return out
    for t in tabs.tables:
        try:
            rows = t.extract()
        except Exception:
            continue
        if len(rows) < 2:
            continue
        out.append((t.bbox[1], len(rows), header_columns(t, rows)))
    return sorted(out)


def _cari_y(page, key):
    """y0 caption. PDF menulis titik ganda ("2.A..7") sehingga search_for literal bisa
    gagal (kalau gagal, y jatuh ke 0 dan header terambil dari tabel halaman sebelumnya):
    coba bentuk bertitik ganda lalu potongan nomor di depannya."""
    hits = page.search_for(key)
    if not hits:
        bagian = key.split(".")
        for alt in ("..".join(bagian), ".".join(bagian[:-1]) + "." if len(bagian) > 1 else key):
            hits = page.search_for(alt)
            if hits:
                break
    return hits[0].y0 if hits else 0.0


def caption_map(doc):
    """nomor tabel LKPS -> (halaman PDF, judul, y0 caption).

    Pendekatan span: cari semua posisi "Tabel <nomor>" di teks halaman, judul = teks antara
    caption ini dan caption berikutnya. Pola bertitel (`Tabel 2.A.3 ... [^.]*`) tidak dipakai
    karena `[^.]*` menelan caption berikutnya bila teks di antaranya belum ada titik —
    akibatnya caption berikutnya hilang. Judul yang diawali huruf kecil = rujukan silang.
    """
    caps = {}
    pat = re.compile(r"(?<![\w.])Tabel\s+(\d+(?:\.\w+)*)")
    for pno in range(doc.page_count):
        page = doc[pno]
        flat = re.sub(r"\.{2,}", ".", norm(page.get_text()))
        ms = list(pat.finditer(flat))
        for i, m in enumerate(ms):
            key = m.group(1)
            if key in caps:
                continue
            end = ms[i + 1].start() if i + 1 < len(ms) else len(flat)
            title = flat[m.end():end].strip(" .")
            if not title[:1].isupper():
                continue
            caps[key] = (pno + 1, title[:110], _cari_y(page, key))
    return caps


def caption_map_led(doc, toc):
    """nomor tabel LED -> (halaman PDF, y0 caption) | None bila tak ketemu.

    LED sering menulis rujukan silang "Tabel C2.1" di prosa dan label navigasi
    "[Link]" di tepi halaman, jadi kemunculan dipilih yang teks SESUDAHNYA paling
    mirip judul tabel di DAFTAR TABEL (difflib), bukan sekadir kemunculan pertama."""
    caps = {}
    for nomor, judul, _hal in toc:
        kandidat = []
        for pno in range(doc.page_count):
            if pno in LED_TOC_PAGES:
                continue
            page = doc[pno]
            flat = re.sub(r"\.{2,}", ".", norm(page.get_text()))
            for m in re.finditer(rf"(?<![\w.])Tabel\s+{re.escape(nomor)}\b", flat):
                follow = flat[m.end():m.end() + 80].strip(" .:")
                kandidat.append((pno + 1, page, follow))
        if not kandidat:
            caps[nomor] = None
            continue
        def mirip(k):
            _, _, follow = k
            return difflib.SequenceMatcher(None, follow[:60].lower(), judul[:60].lower()).ratio()
        hal, page, _ = max(kandidat, key=mirip)
        caps[nomor] = (hal, _cari_y(page, nomor))
    return caps


def parse_daftar_tabel(doc, pages):
    """Parse blok DAFTAR TABEL LED: 'Tabel X judul ..... hal' (judul bisa lanjut baris)."""
    raw = "\n".join(doc[p].get_text() for p in pages)
    raw = raw.replace("\u2026", ".").replace("\u00a0", " ")
    items, buf = [], ""
    for line in raw.splitlines():
        s = line.strip()
        if s.lower().startswith("tabel "):
            buf = s
        elif buf:
            buf += " " + s
        if not buf:
            continue
        m = re.match(r"Tabel\s+([A-Z]?\d[\w.]*)\s+(.*?)\.{3,}\s*(\d+)\s*$", buf)
        if m:
            # backslash nyasar di PDF sumber ("... keberlanjutan penelitian.\ ") dibuang
            judul = norm(m.group(2)).replace("\\", "").strip(" .")
            items.append((m.group(1), judul, int(m.group(3))))
            buf = ""
    return items


def header_untuk(lkps_pages, halaman, y_caption):
    """Header blok tabel LKPS di bawah caption. Kalau blok pertama headernya tidak
    informatif (banyak sel kosong — biasanya lanjutan tabel halaman sebelumnya), pakai
    blok berikutnya yang headernya lebih lengkap. Kembalikan list sel."""
    kandidat = [(by0, hdr) for by0, nrow, hdr in lkps_pages[halaman - 1]
                if by0 >= y_caption - 3]
    if not kandidat:
        return []
    def skor(h):
        return sum(1 for c in h if c.strip() not in ("", "-"))
    utama = kandidat[0][1]
    if skor(utama) >= max(1, len(utama) // 2):
        return utama
    for _, h in kandidat[1:]:
        if skor(h) > skor(utama):
            return h
    return utama


def urut_lkps(key):
    return [int(x) if x.isdigit() else x for x in key.split(".")]


def ekstrak():
    """Kembalikan dict berisi semua yang dibutuhkan kedua pemakai."""
    led = pymupdf.open(LED)
    lkps = pymupdf.open(LKPS)
    try:
        led_toc = parse_daftar_tabel(led, LED_TOC_PAGES)
        led_caps = caption_map_led(led, led_toc)
        led_pages = [page_blocks(led[p]) for p in range(led.page_count)]
        lkps_caps = caption_map(lkps)
        lkps_pages = [page_blocks(lkps[p]) for p in range(lkps.page_count)]
    finally:
        led.close()
        lkps.close()

    # --- LED: kelompokkan blok per tanda tangan kolom KANONIK ---
    sig, tanpa_header = {}, 0
    for pno, blks in enumerate(led_pages):
        for y0, nrow, hdr in blks:
            toks = [t for t in (canon(c) for c in hdr) if t]
            if len(toks) < 3:                 # blok tanda tangan / pecahan tabel
                tanpa_header += 1
                continue
            sig.setdefault(tuple(toks), []).append(pno + 1)

    # --- LED: header tiap tabel resmi = blok di bawah caption badannya ---
    led_rows = []
    for nomor, judul, hal_cetak in led_toc:
        cap = led_caps.get(nomor)
        header, hal_pdf = [], None
        if cap:
            hal_pdf, y0 = cap[0], cap[1]
            kandidat = [h for by0, _, h in led_pages[hal_pdf - 1] if by0 >= y0 - 3]
            if not kandidat and hal_pdf < len(led_pages):
                # tabelnya nyambung ke halaman berikutnya (caption di akhir halaman)
                kandidat = [h for _, _, h in led_pages[hal_pdf]]
            header = pilih_blok_informatif(kandidat)
        led_rows.append({"nomor": nomor, "judul": judul, "hal_cetak": hal_cetak,
                         "hal_pdf": hal_pdf, "header": header})

    # --- LKPS: caption bernomor + tabel tanpa nomor di halaman daftar prodi ---
    lkps_rows = []
    for key in sorted(lkps_caps, key=urut_lkps):
        hal, title, y0 = lkps_caps[key]
        lkps_rows.append({"nomor": key, "judul": title, "hal": hal,
                          "header": header_untuk(lkps_pages, hal, y0)})

    lkps_tanpa = []
    for y0, nrow, hdr in lkps_pages[LKPS_TANPA_NOMOR_PAGE]:
        lkps_tanpa.append({"nbaris": nrow, "header": hdr})

    return {
        "led_toc": led_toc,
        "led_rows": led_rows,
        "led_pages": led_pages,
        "led_sig": sig,
        "led_tanpa_header": tanpa_header,
        "lkps_rows": lkps_rows,
        "lkps_tanpa_nomor": lkps_tanpa,
    }


def pilih_blok_informatif(hdrs):
    """Dari kandidat blok di bawah caption, pilih yang paling informatif (paling sedikit
    sel '-'): blok pertama bisa lanjutan tabel dari halaman sebelumnya."""
    def skor(h):
        return sum(1 for c in h if c.strip() not in ("", "-"))
    return max(hdrs, key=skor) if hdrs else []
