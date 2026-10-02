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


def _isi_sel(sel):
    if sel is None:
        return ""
    return norm(str(sel)).replace(" ,", ",")


def _baris_spanduk(joined):
    return joined.startswith("roadmap") or "link dokumen roadmap" in joined


def _judul_caption(nomor, judul, header=None):
    """Judul tabel dari PDF tanpa duplikat (judul sumber bisa mengulang nomor).
    Judul dipakai untuk caption di dalam xlsx (bukan nama file), jadi tidak dipotong
    di sini — pemotongan untuk nama file dilakukan terpisah di generator."""
    j = judul
    if j.lower().startswith("tabel"):
        j = j[5:].lstrip()
    return f"Tabel {nomor} {j}".rstrip()


def _sel(rows, ri, ci):
    """Akses sel aman: baris hasil ekstraksi tidak selalu seragam panjangnya."""
    if ri >= len(rows) or ci >= len(rows[ri]):
        return ""
    return _isi_sel(rows[ri][ci])


def _serap_sel(rows, ri, ci):
    """Nilai sel untuk baris data contoh: serap runtunan kosong horizontal (sel yang
    teksnya melebar ke sel kanan) dan gabung vertikal (lanjutan baris di bawah,
    pola ekstrak: lanjutan berhenti tepat 1 kolom sebelum kolom isi berikutnya)."""
    n = len(rows[ri])
    parts, last_c = [], ci
    for c in range(ci, n):
        v = _sel(rows, ri, c)
        if v:
            parts.append(v)
            last_c = c
        else:
            break
    ri2 = ri + 1
    while ri2 < len(rows) and all(not _sel(rows, ri2, c) for c in range(0, last_c + 1)):
        lanjut = [_sel(rows, ri2, c) for c in range(last_c + 1, n)]
        if not any(lanjut):
            ri2 += 1
            continue
        # batas baris lanjutan: kolom isi pertama sel baris berikutnya - 1
        stop = n - 1
        if ri2 + 1 < len(rows):
            for c in range(ci, len(rows[ri2 + 1])):
                if _sel(rows, ri2 + 1, c):
                    stop = max(last_c, c - 1)
                    break
        for c in range(last_c + 1, stop + 1):
            v = _sel(rows, ri2, c)
            if v:
                parts.append(v)
        last_c = stop
        ri2 += 1
    if last_c == ci:
        return " ".join(parts)   # sel sempit: hanya serap vertikal, jangan melebar
    # sel lebar menutup kolom tetangganya -> kolom tetangga kosong; kembalikan None
    return None


def baris_dan_header(rows):
    """Baris header bertingkat (urutan untuk merge) + baris data contoh pertama."""
    idx = []
    for i, r in enumerate(rows[:10]):
        joined = " ".join(_isi_sel(c) for c in r if _isi_sel(c)).lower()
        if _baris_spanduk(joined):
            continue
        if _baris_header(r):
            idx.append(i)
        else:
            break
    if not idx:
        for i in range(min(6, len(rows))):
            if _baris_header(rows[i]) and sum(1 for c in rows[i] if _isi_sel(c)) >= 3:
                idx = [j for j in range(i, min(i + 3, len(rows))) if _baris_header(rows[j])]
                break
    if not idx:
        idx = [0]
    hdr_rows = [[_isi_sel(c) for c in rows[i]] for i in idx]
    # buang baris header yang benar-benar kosong (artefak ekstraksi)
    hdr_rows = [r for r in hdr_rows if any(v for v in r)]
    if not hdr_rows:
        hdr_rows = [["-"]]
    data_i = next((j for j in range(idx[-1] + 1, len(rows))
                   if any(_isi_sel(c) for c in rows[j])), None)
    if data_i is None:
        example = None
    else:
        example = []
        ci = 0
        while ci < len(rows[0]):
            v = _serap_sel(rows, data_i, ci)
            example.append(v or "")
            if v is None:            # sel lebar: tetangganya kosong, lompat
                ci += 2
            else:
                ci += 1
    return hdr_rows, example


def header_dari_baris(hdr_rows, n_cols):
    """Header gabungan per kolom dari baris header bertingkat."""
    out = []
    for ci in range(n_cols):
        parts = []
        for r in hdr_rows:
            v = r[ci] if ci < len(r) else ""
            if v and v not in parts:
                parts.append(v)
        out.append(" ".join(parts) if parts else "-")
    return out


def gabung_sel_kosong(hdr_rows):
    """Serap kolom kosong di dalam runtunan kolom berisi yang identik antarbaris
    (pola pymupdf: sel lebar teksnya jatuh di kolom kiri runtunan kosong)."""
    if not hdr_rows:
        return hdr_rows
    n = max(len(r) for r in hdr_rows)
    rows = [r + [""] * (n - len(r)) for r in hdr_rows]
    ambil = [True] * n
    c = 0
    while c < n:
        if any(r[c] for r in rows):
            c += 1
            continue
        kiri = c - 1
        kanan = c + 1
        if kiri < 0 or kanan >= n or any(r[kanan] for r in rows):
            break  # ujung kiri/kanan atau runtunan kosong penuh: biarkan (dipangkas belakangan)
        vals_kiri = [r[kiri] for r in rows if r[kiri]]
        vals_kanan = [r[kanan] for r in rows if r[kanan]]
        if vals_kiri and vals_kiri == vals_kanan:
            ambil[c] = False
            c += 1
        else:
            break
    return [[r[c] for c in range(n) if ambil[c]] for r in rows]


def pangkas_kolom_kosong(hdr_rows, example):
    """Buang kolom yang kosong di header DAN baris contoh (artefak ekstraksi);
    bila baris contoh punya isi di sana, jadikan '-' supaya kolom tak salah buang."""
    if not hdr_rows:
        return hdr_rows, example
    n = max(len(r) for r in hdr_rows)
    hdr_rows = [r + [""] * (n - len(r)) for r in hdr_rows]
    if example is not None:
        example = example + [""] * (n - len(example))
    ambil = [True] * n
    for c in range(n):
        if any(r[c] for r in hdr_rows):
            continue
        if example is not None and example[c]:
            example[c] = "-"
        else:
            ambil[c] = False
    out_h = [[r[c] for c in range(n) if ambil[c]] for r in hdr_rows]
    out_e = [example[c] for c in range(n) if ambil[c]] if example is not None else None
    return out_h, out_e


def rapikan_struktur(hdr_rows, example):
    """Gabung kolom terpecah + pangkas kolom kosong artefak ekstraksi."""
    hdr_rows = gabung_sel_kosong(hdr_rows)
    return pangkas_kolom_kosong(hdr_rows, example)


def header_columns(table, rows, max_rows=10):
    """Gabung baris header bertingkat per kolom. Baris header = deretan sel pendek
    berhuruf di atas tabel; berhenti di baris pertama yang berisi data (sel panjang
    atau angka). Baris spanduk dilewati tanpa menghentikan pemindaian."""
    hdr_rows, example = baris_dan_header(rows)
    hdr_rows, _ = rapikan_struktur(hdr_rows, example)
    return header_dari_baris(hdr_rows, len(rows[0]))


def page_blocks(page):
    """Blok tabel satu halaman: (y0, nbaris, header, hdr_rows, example) — blok <2 baris
    dibuang. hdr_rows = baris header bertingkat (untuk merge di xlsx), example = baris
    data pertama yang selnya sudah diserap (contoh isi)."""
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
        hdr_rows, example = rapikan_struktur(*baris_dan_header(rows))
        header = header_dari_baris(hdr_rows, len(rows[0]))
        out.append((t.bbox[1], len(rows), header, hdr_rows, example))
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


def _serap_dari_rows(rows):
    """Serap baris data pertama dari rows mentah (untuk fallback blok pengganti yang
    hanya punya header gabungan)."""
    _, example = rapikan_struktur(*baris_dan_header(rows))
    return example


def _blok_pengganti(lkps_pages, halaman, y_caption, pengganti):
    """Timpa struktur blok utama dengan blok pengganti bila header utama tidak
    informatif; baris contoh blok utama tetap dipakai bila pengganti tak punya."""
    kandidat = [(by0, h, hr, ex) for by0, _nr, h, hr, ex in lkps_pages[halaman - 1]
                if by0 >= y_caption - 3]
    if not kandidat:
        return
    def skor(h):
        return sum(1 for c in h if c.strip() not in ("", "-"))
    utama_h, utama_hr, utama_ex = kandidat[0][1], kandidat[0][2], kandidat[0][3]
    if skor(utama_h) >= max(1, len(utama_h) // 2):
        return
    for by0, h, hr, ex in kandidat[1:]:
        if skor(h) > skor(utama_h):
            pengganti["hdr_rows"] = hr
            if utama_ex is not None:
                pengganti["example"] = utama_ex
            elif ex is not None:
                pengganti["example"] = ex
            return


def _pilih_blok(hdrs):
    """Indeks blok paling informatif (paling sedikit sel '-'): blok pertama bisa
    lanjutan tabel dari halaman sebelumnya."""
    def skor(h):
        return sum(1 for c in h if c.strip() not in ("", "-"))
    return max(range(len(hdrs)), key=lambda i: skor(hdrs[i]))


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
        for y0, nrow, hdr, _hr, _ex in blks:
            toks = [t for t in (canon(c) for c in hdr) if t]
            if len(toks) < 3:                 # blok tanda tangan / pecahan tabel
                tanpa_header += 1
                continue
            sig.setdefault(tuple(toks), []).append(pno + 1)

    # --- LED: header tiap tabel resmi = blok di bawah caption badannya ---
    led_rows = []
    for nomor, judul, hal_cetak in led_toc:
        cap = led_caps.get(nomor)
        header, hdr_rows, example, hal_pdf = [], [], None, None
        if cap:
            hal_pdf, y0 = cap[0], cap[1]
            kandidat = [(h, hr, ex) for by0, _nr, h, hr, ex in led_pages[hal_pdf - 1]
                        if by0 >= y0 - 3]
            if not kandidat and hal_pdf < len(led_pages):
                # tabelnya nyambung ke halaman berikutnya (caption di akhir halaman)
                kandidat = [(h, hr, ex) for _y, _nr, h, hr, ex in led_pages[hal_pdf]]
            if kandidat:
                i = _pilih_blok([k[0] for k in kandidat])
                header, hdr_rows, example = kandidat[i]
        led_rows.append({"nomor": nomor, "judul": _judul_caption(nomor, judul),
                         "judul_raw": judul,
                         "hal_cetak": hal_cetak, "hal_pdf": hal_pdf, "header": header,
                         "hdr_rows": hdr_rows, "example": example})

    # --- LKPS: caption bernomor + tabel tanpa nomor di halaman daftar prodi ---
    lkps_rows = []
    for key in sorted(lkps_caps, key=urut_lkps):
        hal, title, y0 = lkps_caps[key]
        kandidat = [(by0, h, hr, ex) for by0, _nr, h, hr, ex in lkps_pages[hal - 1]
                    if by0 >= y0 - 3]
        r = {"nomor": key, "judul": _judul_caption(key, title), "judul_raw": title,
             "hal": hal, "header": [], "hdr_rows": [], "example": None}
        if kandidat:
            r["header"], r["hdr_rows"], r["example"] = (kandidat[0][1], kandidat[0][2],
                                                        kandidat[0][3])
            _blok_pengganti(lkps_pages, hal, y0, r)
        lkps_rows.append(r)

    lkps_tanpa = []
    for y0, nrow, hdr, hdr_rows, example in lkps_pages[LKPS_TANPA_NOMOR_PAGE]:
        lkps_tanpa.append({"nbaris": nrow, "header": hdr, "hdr_rows": hdr_rows,
                           "example": example})

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
