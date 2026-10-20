"""Ekstraksi TANPA AI dari dokumen LED/LKPS lama prodi (PDF atau Word) berdasarkan STRUKTUR dokumen.

Pengganti ekstraksi AI (ekstraksi_akreditasi.py) untuk tombol "Ekstrak data": isi lama dipindahkan
APA ADANYA ke item laporan -- narasi disalin utuh (tidak diringkas), tabel dipecah per baris -- lalu
staf yang memutuskan per item apakah mau diperbarui dengan draf AI. Kontrak fungsi sama dengan modul
AI: `ekstrak_dokumen(path, tipe_file, mode, progress_callback)` -> (baris, ringkasan).

Alur:
1. Dokumen dibaca jadi urutan BLOK: judul, teks (paragraf), tabel. PDF: PyMuPDF (judul = baris tebal
   ukuran >= 11.5; tabel = find_tables). Word: gaya Heading / paragraf tebal pendek + tabel asli.
2. Judul dicocokkan ke kerangka LED (_KERANGKA_LED) dalam dua lapis: POLA judul persis (regex), lalu
   KATA KUNCI fallback (semua kata harus ada) bila judulnya tidak sama persis. Lapis kedua juga
   mencoba paragraf pendek, untuk dokumen yang judulnya tidak ditebalkan.
3. Narasi: isi bagian (semua blok sampai judul setingkat berikutnya, tanpa tabel) dibagi ke kolom
   item -- per sub-bagian (mis. tahap PPEPP untuk C1-C6), lalu per paragraf menurut kata kunci kolom.
   Paragraf yang tidak cocok ke kolom mana pun ikut kolom sebelumnya/pertama: TIDAK ADA TEKS YANG
   DIBUANG.
4. Tabel LED dicari tiga lapis: (a) DAFTAR TABEL dokumen (nomor -> halaman cetak -> halaman PDF),
   (b) kata kunci judul tabel di dalam bab kriterianya, (c) urutan tabel yang header-nya cocok di bab
   itu. Setiap kandidat WAJIB lolos pencocokan header ke kolom registry (_skor_header); tabel yang
   tidak cocok tidak dipakai (lebih baik kosong daripada salah kolom).
5. Kolom tabel PDF dibangun dari posisi sel HEADER (bukan grid mentah, yang sering terpecah jadi
   belasan kolom kosong pada sel gabungan); kata di baris data dimasukkan ke kolom menurut posisi
   horizontalnya. Tabel yang berlanjut ke halaman berikut (tanpa header / header berulang) digabung.

Divalidasi terhadap akreditasi/docs/sumber/LED_Prodi_S2_Elektronika_dan_Instrumentasi.pdf
(lihat scripts/validasi_ekstraksi_struktur.py).
"""

import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from registry_kebutuhan_data import KEBUTUHAN_DATA, led_items_by_kriteria, lkps_items_by_bagian  # noqa: E402

# Isi kolom "No" yang memulai baris data: angka ("1.", "12") atau kode butir ("A1", "B2", "C1.1").
_ANGKA_NO = re.compile(r"^(\d{1,3}|[A-H]\.?\d{1,2}(\.\d{1,2})?)[.)]?$")
_LABEL_HAL = re.compile(r"^(\d{1,3}|[ivxlc]{1,7})$", re.I)
_TITIK_DAFTAR = re.compile(r"\.{4,}|…{2,}")
_JUDUL_MIN_PT = 11.5


@dataclass
class Blok:
    jenis: str                      # "judul" | "teks" | "tabel"
    teks: str = ""
    hal: int | None = None          # halaman PDF (1-based); None untuk Word
    baris_mentah: list[str] = field(default_factory=list)   # baris asli (dipakai parser identitas)
    # khusus tabel
    kolom: list[str] | None = None  # label kolom (header bertingkat digabung " – "); None = tanpa header
    rentang: list[tuple[float, float]] | None = None
    record: list[dict[str, str]] = field(default_factory=list)
    awalan: dict[str, str] = field(default_factory=dict)    # teks sebelum nomor pertama (lanjutan record)
    x: tuple[float, float] = (0.0, 0.0)   # rentang horizontal tabel
    y: tuple[float, float] = (0.0, 0.0)   # rentang vertikal (baris teks / tabel)
    ukuran: float = 0.0
    hal_akhir: int | None = None          # halaman terakhir yang sudah disambung ke tabel ini
    grid: list[list[str]] = field(default_factory=list)   # sel mentah (tabel_mentah: tabel vertikal "Label : Nilai")


# ====================================================================================
# 1. Pembacaan dokumen -> blok
# ====================================================================================

def _rapat(teks: str) -> str:
    return re.sub(r"\s+", " ", teks or "").strip()


def _norm(teks: str) -> str:
    """Huruf kecil, tanda baca jadi spasi -- untuk pencocokan judul/kolom."""
    teks = (teks or "").lower().replace("–", "-").replace("—", "-")
    teks = re.sub(r"[^a-z0-9\-/ ]+", " ", teks)
    return re.sub(r"\s+", " ", teks).strip()


def _gabung_header(atas: str, bawah: str) -> str:
    atas, bawah = atas.strip(), bawah.strip()
    return atas + bawah if atas.endswith(("/", "-")) or bawah.startswith("/") else f"{atas} {bawah}"


def _header_tabel_pdf(tab) -> tuple[list[str], list[tuple[float, float]], float] | None:
    """Label + rentang x kolom DAUN header, dan batas bawah header. None = tabel tanpa header."""
    teks = tab.extract()
    baris_sel = [r.cells for r in tab.rows]
    mulai_data = None
    for i, r in enumerate(teks):
        isi = [c for c in r if c and c.strip()]
        # Baris data = nomor di sel pertama DAN ada isi lain; potongan header seperti "1" (dari "TS-" / "1")
        # berdiri sendiri, jadi bukan awal data. Sel panjang (> 60 huruf) juga tanda data, mis. lanjutan
        # baris dari halaman sebelumnya di bawah header berulang.
        if isi and ((_ANGKA_NO.match(isi[0].strip()) and len(isi) >= 2) or (i > 0 and any(len(_rapat(c)) > 60 for c in isi))):
            mulai_data = i
            break
    if mulai_data == 0:
        return None
    if mulai_data is None:
        # Tanpa nomor baris: tabel kecil yang semua selnya pendek = header saja (isinya dideteksi
        # sebagai tabel terpisah tepat di bawahnya); selain itu hanya baris pertama header.
        pendek = all(len(_rapat(c or "")) <= 40 for r in teks for c in r)
        mulai_data = len(teks) if len(teks) <= 3 and pendek else 1
    sel = []
    for i in range(mulai_data):
        for j, bbox in enumerate(baris_sel[i]):
            isi = _rapat(teks[i][j] if j < len(teks[i]) else "")
            if bbox and isi:
                sel.append({"x0": bbox[0], "x1": bbox[2], "y0": bbox[1], "y1": bbox[3], "t": isi})
    if not sel:
        return None
    # Satu sel header yang terpotong dua baris (mis. "IKU/" + "IKT") = sel dgn rentang x hampir sama.
    sel.sort(key=lambda s: (s["y0"], s["x0"]))
    gabung: list[dict] = []
    for s in sel:
        for g in gabung:
            lebar = min(g["x1"], s["x1"]) - max(g["x0"], s["x0"])
            if lebar > 0.8 * max(g["x1"] - g["x0"], s["x1"] - s["x0"]) and s["y0"] >= g["y1"] - 2:
                g["t"], g["y1"] = _gabung_header(g["t"], s["t"]), max(g["y1"], s["y1"])
                break
        else:
            gabung.append(dict(s))
    tengah = lambda s: (s["x0"] + s["x1"]) / 2  # noqa: E731
    daun = [s for s in gabung if not any(
        g is not s and g["y0"] >= s["y1"] - 2 and s["x0"] - 1 <= tengah(g) <= s["x1"] + 1 for g in gabung)]
    daun.sort(key=lambda s: s["x0"])
    label = []
    for d in daun:
        induk = sorted((g for g in gabung if g is not d and g["y1"] <= d["y0"] + 2
                        and g["x0"] - 1 <= tengah(d) <= g["x1"] + 1), key=lambda g: g["y0"])
        label.append(" – ".join([g["t"] for g in induk] + [d["t"]]))
    # Salah ketik umum di dokumen: tiga sub-kolom "TS-2, TS-1, TS-2" di bawah satu induk -> TS-2, TS-1, TS.
    for awal in range(len(label) - 2):
        trio = label[awal:awal + 3]
        induk_trio = {t.rsplit(" – ", 1)[0] if " – " in t else "" for t in trio}
        ujung = [_token(t)[1] for t in trio]
        if len(induk_trio) == 1 and all(len(u) == 1 for u in ujung) and len({u[0] for u in ujung}) < 3 \
                and ujung[0] == ("ts-2",) and ujung[1] == ("ts-1",):
            pre = trio[0].rsplit(" – ", 1)[0] + " – " if " – " in trio[0] else ""
            label[awal + 2] = pre + "TS"
    bawah = max(s["y1"] for s in gabung)
    return label, [(d["x0"], d["x1"]) for d in daun], bawah


def _garis_horizontal(page) -> list[tuple[float, float, float]]:
    """Ruas garis horizontal yang tergambar di halaman (y, x0, x1): garis biasa dan tepi atas/bawah kotak."""
    ruas = []
    for d in page.get_drawings():
        for it in d.get("items", []):
            if it[0] == "l" and abs(it[1].y - it[2].y) < 1.5:
                ruas.append(((it[1].y + it[2].y) / 2, min(it[1].x, it[2].x), max(it[1].x, it[2].x)))
            elif it[0] == "re":
                r = it[1]
                ruas += [(r.y0, r.x0, r.x1)] if r.height < 2.5 else [(r.y0, r.x0, r.x1), (r.y1, r.x0, r.x1)]
    return ruas


def _batas_kolom(ruas: list[tuple[float, float, float]], bbox, y_mulai: float, rentang: tuple[float, float]) -> list[float]:
    """Posisi y garis horizontal yang melintasi tengah satu kolom, di area data tabel (urut, tanpa duplikat)."""
    _, _, _, y1 = bbox
    xc = (rentang[0] + rentang[1]) / 2
    ys: list[float] = []
    for y, a, b in sorted(ruas):
        if y_mulai - 2 <= y <= y1 + 2 and a - 1 <= xc <= b + 1 and not any(abs(y - v) <= 1.5 for v in ys):
            ys.append(y)
    return sorted(ys)


def _isi_tabel_pdf(blok: Blok, words: list, y_mulai: float, bbox, ruas=None) -> None:
    """Kata di area data tabel -> record per kolom.

    Batas baris diambil dari garis horizontal tabel (bila ada), karena nomor di sel yang tinggi diletakkan
    di tengah sel dan teks di atasnya akan terbawa ke baris sebelumnya kalau nomor dipakai sebagai patokan.
    Tanpa garis: record baru dimulai oleh nomor di kolom "No". Teks sebelum record pertama = `awalan`
    (lanjutan record terakhir halaman sebelumnya)."""
    x0, y0, x1, y1 = bbox
    kata = [w for w in words if x0 - 2 <= (w[0] + w[2]) / 2 <= x1 + 2 and y_mulai - 1 <= (w[1] + w[3]) / 2 <= y1 + 2]
    if not kata or not blok.rentang:
        return
    kata.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))

    def kolom_untuk(w) -> int:
        xc = (w[0] + w[2]) / 2
        for i, (a, b) in enumerate(blok.rentang):
            if a - 1 <= xc <= b + 1:
                return i
        return min(range(len(blok.rentang)), key=lambda i: min(abs(xc - blok.rentang[i][0]), abs(xc - blok.rentang[i][1])))

    def per_kolom(ws) -> dict[int, list[str]]:
        per: dict[int, list[str]] = {}
        for w in sorted(ws, key=lambda w: (round((w[1] + w[3]) / 2 / 3), w[0])):
            per.setdefault(kolom_untuk(w), []).append(w[4])
        return per

    i_no = next((i for i, k in enumerate(blok.kolom) if _norm(k) in ("no", "no.", "nomor")), None)

    def kelompok_baris(ws) -> list[list]:
        hasil: list[list] = []
        for w in ws:
            yc = (w[1] + w[3]) / 2
            if hasil and abs(hasil[-1][0] - yc) <= 3:
                hasil[-1][1].append(w)
            else:
                hasil.append([yc, [w]])
        return hasil

    def teks_no(ws) -> str:
        return "".join(w[4] for w in sorted(ws, key=lambda w: w[0]) if i_no is not None and kolom_untuk(w) == i_no)

    def awal_record(baris_pita: list[list]) -> list[int]:
        """Indeks baris yang memulai record: ada nomor di kolom No. Nomor yang terpotong ("A1." lalu "1"
        di baris berikutnya) dihitung satu."""
        awal, sebelum = [], ""
        for i, (_, b) in enumerate(baris_pita):
            no = teks_no(b)
            lanjutan_kode = bool(re.fullmatch(r"\d{1,2}", no)) and bool(re.fullmatch(r"[A-H]\.?\d{1,2}\.", sebelum))
            if no and not lanjutan_kode and (_ANGKA_NO.match(no) or re.fullmatch(r"[A-H]\.?\d{1,2}\.", no)):
                awal.append(i)
            sebelum = no or sebelum
        return awal

    yc_ = lambda w: (w[1] + w[3]) / 2  # noqa: E731
    batas_no = _batas_kolom(ruas or [], bbox, y_mulai, blok.rentang[i_no]) if i_no is not None else []
    if len(batas_no) >= 2:
        # 1) Pita baris = di antara garis yang melintasi kolom No. Di dalam satu pita, tiap nomor memulai
        #    sub-baris (tabel yang barisnya tidak bergaris); teks di atas nomor pertama milik sub-baris pertama
        #    (nomor diletakkan di tengah sel yang tinggi).
        tepi = sorted({y_mulai, *[b for b in batas_no if b > y_mulai + 1], y1})
        pita: list[tuple[float, float]] = list(zip(tepi, tepi[1:]))
        sub: list[dict] = []   # {pita, ya, yb, bernomor}
        for p, (ya, yb) in enumerate(pita):
            ws = sorted((w for w in kata if ya <= yc_(w) < yb), key=lambda w: (yc_(w), w[0]))
            if not ws:
                continue
            baris_pita = kelompok_baris(ws)
            awal = awal_record(baris_pita)
            if not awal:
                sub.append({"pita": p, "ya": ya, "yb": yb, "bernomor": False})
                continue
            potong = [ya] + [(baris_pita[a - 1][0] + baris_pita[a][0]) / 2 for a in awal[1:]] + [yb]
            sub += [{"pita": p, "ya": a, "yb": z, "bernomor": True} for a, z in zip(potong, potong[1:])]
        isi: list[dict[int, list[str]]] = [{} for _ in sub]
        # 2) Tiap kolom dipotong menurut garisnya sendiri. Sel yang menaungi beberapa pita (sel gabungan,
        #    mis. satu Referensi untuk A1.1-A1.4) disalin ke sub-baris pertama tiap pita yang dinaunginya;
        #    sel di dalam satu pita dibagi ke sub-barisnya menurut posisi vertikal kata.
        for j in range(len(blok.rentang)):
            kata_j = [w for w in kata if kolom_untuk(w) == j]
            if not kata_j:
                continue
            gj = _batas_kolom(ruas or [], bbox, y_mulai, blok.rentang[j])
            tepi_j = sorted({y_mulai, *[b for b in gj if b > y_mulai + 1], y1}) if len(gj) >= 2 else tepi
            for ca, cb in zip(tepi_j, tepi_j[1:]):
                ws = sorted((w for w in kata_j if ca <= yc_(w) < cb), key=lambda w: (round(yc_(w) / 3), w[0]))
                if not ws:
                    continue
                kena = sorted({s["pita"] for s in sub if min(cb, s["yb"]) - max(ca, s["ya"]) > 1})
                if len(kena) > 1:
                    for p in kena:
                        k = next(i for i, s in enumerate(sub) if s["pita"] == p)
                        isi[k].setdefault(j, []).extend(w[4] for w in ws)
                    continue
                for w in ws:
                    k = next((i for i, s in enumerate(sub) if s["ya"] <= yc_(w) < s["yb"]), None)
                    if k is not None:
                        isi[k].setdefault(j, []).append(w[4])
        # 3) Sub-baris tanpa nomor = lanjutan record sebelumnya (atau record terakhir halaman sebelumnya).
        record: list[dict[int, list[str]]] = []
        awalan: dict[int, list[str]] = {}
        for s, per in zip(sub, isi):
            if s["bernomor"]:
                record.append(per)
                continue
            target = record[-1] if record else awalan
            for i, t in per.items():
                if t != target.get(i, [])[-len(t):]:   # sel gabungan yang sudah tersalin jangan digandakan
                    target.setdefault(i, []).extend(t)
        blok.record += [_rekam(blok, r) for r in record if r]
        if awalan:
            blok.awalan = _rekam(blok, awalan)
        return

    baris = kelompok_baris(kata)
    awal = set(awal_record(baris)) if i_no is not None else set()
    sekarang: dict[int, list[str]] | None = None
    awalan: dict[int, list[str]] = {}
    for n, (_, ws) in enumerate(baris):
        per = per_kolom(ws)
        baru = n in awal if i_no is not None else sekarang is None or 0 in per
        if baru:
            if sekarang is not None:
                blok.record.append(_rekam(blok, sekarang))
            sekarang = {}
        target = sekarang if sekarang is not None else awalan
        for i, t in per.items():
            target.setdefault(i, []).extend(t)
    if sekarang is not None:
        blok.record.append(_rekam(blok, sekarang))
    if awalan:
        blok.awalan = _rekam(blok, awalan)


def _rekam(blok: Blok, isi: dict[int, list[str]]) -> dict[str, str]:
    return {blok.kolom[i]: _rapat(" ".join(t)) for i, t in isi.items() if i < len(blok.kolom) and _rapat(" ".join(t))}


def _baca_pdf(path: str, progress=None) -> list[Blok]:
    import pymupdf

    blok: list[Blok] = []
    tabel_akhir: Blok | None = None
    with pymupdf.open(path) as doc:
        n = doc.page_count
        for pno, page in enumerate(doc, start=1):
            if progress:
                progress(pno, n)
            words = page.get_text("words")
            ruas = _garis_horizontal(page)
            semua = [t for t in page.find_tables().tables if t.bbox[2] - t.bbox[0] > 120]
            tabs = [t for t in semua if t.row_count >= 2]
            # Tabel satu baris (potongan kartu "Nama : ..." di ujung halaman) hanya disimpan mentah.
            satu = [t for t in semua if t.row_count == 1]
            # Tabel kecil di dalam tabel lain (artefak deteksi) dibuang.
            tabs = [t for t in tabs if not any(o is not t and o.bbox[0] <= t.bbox[0] + 1 and o.bbox[1] <= t.bbox[1] + 1
                                               and o.bbox[2] >= t.bbox[2] - 1 and o.bbox[3] >= t.bbox[3] - 1 for o in tabs)]
            elemen: list[tuple[float, object]] = [(t.bbox[1], t) for t in tabs]
            elemen += [(t.bbox[1], Blok("tabel_mentah", hal=pno, grid=[[_rapat(c or "") for c in r] for r in t.extract()]))
                       for t in satu]
            kotak = [t.bbox for t in tabs + satu]
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    spans = [s for s in ln["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    teks = _rapat("".join(s["text"] for s in ln["spans"]))
                    x0, y0, x1, y1 = ln["bbox"]
                    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
                    if any(k[0] - 2 <= xc <= k[2] + 2 and k[1] - 2 <= yc <= k[3] + 2 for k in kotak):
                        continue
                    if _LABEL_HAL.match(teks) and (y0 < 90 or y1 > page.rect.height - 60):
                        elemen.append((y0, Blok("label_hal", teks=teks.lower(), hal=pno)))
                        continue
                    tebal = all((s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)
                    ukuran = max(s["size"] for s in spans)
                    jenis = "judul" if tebal and ukuran >= _JUDUL_MIN_PT and len(teks) <= 220 else "teks"
                    elemen.append((y0, Blok(jenis, teks=teks, hal=pno, baris_mentah=[teks], y=(y0, y1), ukuran=ukuran)))
            elemen.sort(key=lambda e: e[0])
            for _, e in elemen:
                if isinstance(e, Blok) and e.jenis == "tabel_mentah":
                    blok.append(e)
                    continue
                if isinstance(e, Blok):
                    # Judul, caption "Tabel ...", atau paragraf panjang di antara = tabel sebelumnya selesai.
                    if e.jenis == "judul" or re.match(r"^tabel\s", e.teks, re.I) or len(e.teks) > 150:
                        tabel_akhir = None
                    _tambah_baris(blok, e)
                    continue
                grid = [[_rapat(c or "") for c in r] for r in e.extract()]
                tb = None if _grid_vertikal(grid) else _blok_tabel(e, pno, words, ruas, tabel_akhir)
                if tb is None:
                    # Tabel vertikal atau tanpa header yang bukan lanjutan (mis. kartu "Nama : ..." per anggota tim).
                    blok.append(Blok("tabel_mentah", hal=pno, grid=grid))
                    continue
                blok.append(tb)
                if tb.kolom:
                    tabel_akhir = tb
    return blok


def _blok_tabel(t, pno: int, words: list, ruas: list, tabel_akhir: Blok | None) -> Blok | None:
    """Tabel PyMuPDF -> Blok. Tabel tanpa header (atau header berulang) di ATAS halaman, sejajar dengan
    tabel ber-header terakhir, dibaca sebagai lanjutan tabel itu (kolom pinjaman, `kolom` = None)."""
    tb = Blok("tabel", hal=pno, x=(t.bbox[0], t.bbox[2]), y=(t.bbox[1], t.bbox[3]))
    head = _header_tabel_pdf(t)
    induk = None
    if tabel_akhir is not None and _sejajar(tabel_akhir, tb):
        akhir = tabel_akhir.hal_akhir or tabel_akhir.hal
        # Halaman berikut, di bagian atas; atau tepat di bawah tabel header-saja di halaman yang sama.
        if (akhir == pno - 1 and t.bbox[1] < 160) or (akhir == pno and not tabel_akhir.record
                                                       and 0 <= t.bbox[1] - tabel_akhir.y[1] < 30):
            induk = tabel_akhir
    if head and not (induk is not None and head[0] == induk.kolom):
        tb.kolom, tb.rentang, y_mulai = head
        _isi_tabel_pdf(tb, words, y_mulai, t.bbox, ruas)
        return tb
    if induk is None:
        return None
    y_mulai = head[2] if head else t.bbox[1]
    tb.kolom, tb.rentang = induk.kolom, induk.rentang
    _isi_tabel_pdf(tb, words, y_mulai, t.bbox, ruas)
    tb.kolom, tb.teks = None, "lanjutan"
    induk.hal_akhir = pno
    return tb


def _sejajar(a: Blok, b: Blok) -> bool:
    return abs(a.x[0] - b.x[0]) < 25 and abs(a.x[1] - b.x[1]) < 25


def _tambah_baris(blok: list[Blok], e: Blok) -> None:
    """Gabungkan baris PDF jadi paragraf/judul. Paragraf baru di jeda vertikal besar atau awal butir."""
    akhir = blok[-1] if blok else None
    if e.jenis == "label_hal":
        blok.append(e)
        return
    sambung = (akhir is not None and akhir.jenis == e.jenis and akhir.hal == e.hal and akhir.y[1] and
               0 <= e.y[0] - akhir.y[1] <= (8 if e.jenis == "teks" else 10))
    if e.jenis == "teks" and re.match(r"^([●•▪\-–]|\d{1,2}[.)]\s|[a-z][.)]\s)", e.teks):
        sambung = False
    # Judul berikutnya yang bernomor sendiri ("B.1.", "C1.2", "A.") atau beda ukuran = judul baru.
    if e.jenis == "judul" and akhir is not None and (abs(akhir.ukuran - e.ukuran) > 0.6 or re.match(
            r"^(bab\s|kriteria\s|[a-d]\s?\.?\s?\d|[a-d]\.\s|\d+(\.\d+)+|\[)", e.teks, re.I)):
        sambung = False
    if sambung:
        akhir.teks = f"{akhir.teks} {e.teks}" if not akhir.teks.endswith("-") else akhir.teks[:-1] + e.teks
        akhir.baris_mentah.append(e.teks)
        akhir.y = (akhir.y[0], e.y[1])
    else:
        blok.append(e)


def _baca_docx(path: str, progress=None) -> list[Blok]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(path)
    blok: list[Blok] = []
    anak = list(doc.element.body.iterchildren())
    for i, el in enumerate(anak, start=1):
        if progress and i % 50 == 0:
            progress(i, len(anak))
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, doc)
            teks = _rapat(p.text)
            if not teks:
                continue
            gaya = (p.style.name or "").lower() if p.style is not None else ""
            runs = [r for r in p.runs if r.text.strip()]
            tebal = bool(runs) and all(r.bold for r in runs)
            judul = gaya.startswith(("heading", "judul", "title")) or (tebal and len(teks) <= 220)
            blok.append(Blok("judul" if judul else "teks", teks=teks, baris_mentah=[teks]))
        elif tag == "tbl":
            blok.extend(_tabel_docx(Table(el, doc), blok))
    return blok


def _grid_vertikal(grid: list[list[str]]) -> bool:
    """Tabel "Label | : | Nilai" (kartu anggota tim, spesifikasi program): separuh baris punya sel ":"."""
    titik_dua = sum(1 for r in grid if ":" in [(c or "").strip() for c in r]
                    or any((c or "").strip().startswith(":") for c in r[1:]))
    return titik_dua >= max(2, len(grid) // 2)


def _tabel_docx(tabel, blok_sebelum: list[Blok]) -> list[Blok]:
    sel = []
    for r in tabel.rows:
        lihat, baris = set(), []
        for c in r.cells:
            # Sel gabungan horizontal muncul berulang (objek _tc sama): cukup sekali.
            baris.append("" if id(c._tc) in lihat else _rapat(c.text))
            lihat.add(id(c._tc))
        sel.append(baris)
    if not sel:
        return []
    if _grid_vertikal(sel):
        return [Blok("tabel_mentah", grid=sel)]
    mulai = next((i for i, r in enumerate(sel) if _ANGKA_NO.match(next((c for c in r if c), ""))), None)
    if mulai == 0:
        sebelum = next((b for b in reversed(blok_sebelum) if b.jenis in ("tabel", "judul")), None)
        if sebelum is None or sebelum.jenis != "tabel" or not (sebelum.kolom or sebelum.baris_mentah):
            return []
        kolom = sebelum.kolom or sebelum.baris_mentah
        tb = Blok("tabel", teks="lanjutan", baris_mentah=list(kolom))
        tb.record = _record_docx(sel, kolom)
        return [tb]
    mulai = 1 if mulai is None else mulai
    n = max(len(r) for r in sel)
    label = []
    for j in range(n):
        bagian = []
        for i in range(mulai):
            t = sel[i][j] if j < len(sel[i]) else ""
            if not t:
                # sel gabungan vertikal/horizontal: ambil teks terdekat di kiri pada baris header yang sama
                k = j - 1
                while k >= 0 and i < mulai and not (sel[i][k] if k < len(sel[i]) else ""):
                    k -= 1
                t = sel[i][k] if k >= 0 and i < mulai - 1 else ""
            if t and (not bagian or bagian[-1] != t):
                bagian.append(t)
        label.append(" – ".join(bagian))
    tb = Blok("tabel", kolom=label)
    tb.record = _record_docx(sel[mulai:], label)
    return [tb]


def _record_docx(baris: list[list[str]], kolom: list[str]) -> list[dict[str, str]]:
    i_no = next((i for i, k in enumerate(kolom) if _norm(k) in ("no", "no.", "nomor")), None)
    hasil: list[dict[str, str]] = []
    for r in baris:
        isi = {kolom[j]: t for j, t in enumerate(r) if j < len(kolom) and t}
        if not isi:
            continue
        lanjut = i_no is not None and hasil and not (r[i_no] if i_no < len(r) else "")
        if lanjut:
            for k, v in isi.items():
                hasil[-1][k] = _rapat(f"{hasil[-1].get(k, '')} {v}")
        else:
            hasil.append(isi)
    return hasil


def _nilai_sel(v) -> str:
    """Nilai sel Excel -> teks seperti yang terlihat (12.0 -> "12", tanggal -> ISO)."""
    from datetime import date, datetime

    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat(sep=" ", timespec="minutes")
    if isinstance(v, date):
        return v.isoformat()
    return _rapat(str(v))


def _baca_xlsx(path: str, progress=None) -> list[Blok]:
    """Workbook -> blok. Tiap sheet: nama sheet sebagai judul, lalu wilayah yang dipisah baris kosong.
    Wilayah = caption/judul (baris dengan satu sel teks) diikuti tabel. Sel gabungan horizontal diperluas ke
    semua kolomnya supaya header bertingkat ("Sasaran/Target" di atas TS-2/TS-1/TS) terbaca sebagai induk."""
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True, read_only=False)
    blok: list[Blok] = []
    for n, ws in enumerate(wb.worksheets, start=1):
        if progress:
            progress(n, len(wb.worksheets))
        if ws.max_row > 5000:
            continue
        grid = [[_nilai_sel(c) for c in r] for r in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)]
        induk_v: set[tuple[int, int]] = set()   # sel bawah dari gabungan vertikal (bukan isi baru)
        for rng in ws.merged_cells.ranges:
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    if r == rng.min_row and c != rng.min_col and r - 1 < len(grid) and c - 1 < len(grid[r - 1]):
                        grid[r - 1][c - 1] = grid[rng.min_row - 1][rng.min_col - 1]
                    elif r > rng.min_row:
                        induk_v.add((r - 1, c - 1))
        judul = ws.title.strip()
        if judul and not re.fullmatch(r"(sheet|lembar|tabel)\s*\d*", judul, re.I):
            # Sheet bernama kode tabel ("C1.1", "2.A.1") dibaca seperti caption "Tabel C1.1".
            kode = re.match(r"^(tabel\s+)?([a-d]\d+\.\d+|\d\.[a-z](\.\d+)*)\b", judul, re.I)
            blok.append(Blok("judul", teks=f"Tabel {judul}" if kode and not kode.group(1) else judul))
        wilayah: list[list[int]] = []
        for i, r in enumerate(grid):
            if any(r):
                if wilayah and wilayah[-1][-1] == i - 1:
                    wilayah[-1].append(i)
                else:
                    wilayah.append([i])
        for baris in wilayah:
            # Baris pembuka dengan satu nilai = caption/judul. Hanya baris pertama wilayah atau yang diawali
            # "Tabel": baris berikutnya yang satu nilai (sel gabungan "Jumlah Mahasiswa Baru") = header bertingkat.
            pertama = True
            while baris and len({v for v in grid[baris[0]] if v}) == 1:
                teks = next(v for v in grid[baris[0]] if v)
                if not pertama and not re.match(r"^tabel\s", teks, re.I):
                    break
                blok.append(Blok("teks", teks=teks, baris_mentah=[teks]))
                baris, pertama = baris[1:], False
            if not baris:
                continue
            sel = [grid[i] for i in baris]
            if _grid_vertikal(sel):
                blok.append(Blok("tabel_mentah", grid=sel))
                continue
            blok.extend(_tabel_grid(sel, [{(j) for (r, j) in induk_v if r == i} for i in baris], blok))
    return blok


def _tabel_grid(sel: list[list[str]], bawah_gabung: list[set[int]], blok_sebelum: list[Blok]) -> list[Blok]:
    """Grid sel (Excel) -> Blok tabel ber-header. Header = baris sebelum baris bernomor pertama; tanpa nomor,
    header = baris yang masih tertutup sel gabungan dari baris pertama (minimal satu baris)."""
    mulai = next((i for i, r in enumerate(sel) if _ANGKA_NO.match(next((c for c in r if c), ""))
                  and sum(1 for c in r if c) >= 2), None)
    if mulai == 0:
        return _tabel_docx_dari_grid(sel, blok_sebelum)
    if mulai is None:
        mulai = 1
        while mulai < len(sel) and bawah_gabung[mulai]:
            mulai += 1
    n = max(len(r) for r in sel)
    label = []
    for j in range(n):
        bagian: list[str] = []
        for i in range(mulai):
            t = sel[i][j] if j < len(sel[i]) else ""
            if not t or j in bawah_gabung[i]:
                continue
            if bagian and bagian[-1].endswith(("/", "-")):
                bagian[-1] = _gabung_header(bagian[-1], t)
            elif not bagian or bagian[-1] != t:
                bagian.append(t)
        label.append(" – ".join(bagian))
    # Kolom kosong di ujung kanan (lebar sheet) dibuang.
    while label and not label[-1] and all(len(r) < len(label) or not r[len(label) - 1] for r in sel[mulai:]):
        label.pop()
    if not any(label):
        return []
    tb = Blok("tabel", kolom=label)
    data = [r for r in sel[mulai:] if any(c and c != "-" for c in r)]
    tb.record = _record_docx(data, label)
    return [tb]


def _tabel_docx_dari_grid(sel: list[list[str]], blok_sebelum: list[Blok]) -> list[Blok]:
    """Grid tanpa header (baris pertama sudah bernomor) = lanjutan tabel ber-header sebelumnya."""
    sebelum = next((b for b in reversed(blok_sebelum) if b.jenis in ("tabel", "judul")), None)
    if sebelum is None or sebelum.jenis != "tabel" or not (sebelum.kolom or sebelum.baris_mentah):
        return []
    kolom = sebelum.kolom or sebelum.baris_mentah
    tb = Blok("tabel", teks="lanjutan", baris_mentah=list(kolom))
    tb.record = _record_docx(sel, kolom)
    return [tb]


def baca_dokumen(path: str, tipe_file: str, progress=None) -> list[Blok]:
    tipe = (tipe_file or Path(path).suffix.lstrip(".")).lower()
    if tipe == "pdf":
        return _baca_pdf(path, progress)
    if tipe in ("docx", "doc"):
        return _baca_docx(path, progress)
    if tipe in ("xlsx", "xlsm"):
        return _baca_xlsx(path, progress)
    raise ValueError(f"Tipe file {tipe} belum didukung ekstraksi tanpa AI (gunakan PDF, Word, atau Excel).")


# ====================================================================================
# 2. Kerangka LED: penanda judul (pola persis + kata kunci fallback)
# ====================================================================================

@dataclass
class Penanda:
    kunci: str
    tingkat: int
    pola: list[str]                          # regex pada judul yang sudah di-_norm
    kata: list[list[str]] = field(default_factory=list)   # fallback: SEMUA kata di satu daftar harus ada
    induk: str | None = None


_TAHAP = {"penetapan": "penetapan", "pelaksanaan": "pelaksanaan", "evaluasi": "evaluasi",
          "pengendalian": "pengendalian", "peningkatan": "peningkatan"}


def _kerangka_led() -> list[Penanda]:
    k = [
        Penanda("identitas", 0, [r"^identitas pengusul"], [["identitas", "pengusul"]]),
        Penanda("spesifikasi", 1, [r"spesifikasi program"], [["spesifikasi"]], "identitas"),
        Penanda("daftar_ps", 1, [r"daftar program studi pada"], [["daftar", "program", "studi"]], "identitas"),
        Penanda("tim", 0, [r"^identitas tim penyusun"], [["tim", "penyusun", "identitas"]]),
        Penanda("kata_pengantar", 0, [r"^kata pengantar$"], [["kata", "pengantar"]]),
        Penanda("ringkasan", 0, [r"^ringkasan eksekutif$"], [["ringkasan", "eksekutif"]]),
        Penanda("daftar_isi", 0, [r"^daftar isi$"], [["daftar", "isi"]]),
        Penanda("daftar_tabel", 0, [r"^daftar tabel$"], [["daftar", "tabel"]]),
        Penanda("daftar_gambar", 0, [r"^daftar gambar$"], [["daftar", "gambar"]]),
        Penanda("bab1", 0, [r"^bab (i|1)\b.*pendahuluan", r"^pendahuluan$"], [["pendahuluan"]]),
        Penanda("bab1_dasar", 1, [r"^(a\.? )?dasar penyusunan"], [["dasar", "penyusunan"]], "bab1"),
        Penanda("bab1_tim", 1, [r"^(b\.? )?tim penyusun dan tanggung jawab"], [["tim", "penyusun", "tanggung"]], "bab1"),
        Penanda("bab1_mekanisme", 1, [r"^(c\.? )?mekanisme kerja"], [["mekanisme", "kerja"]], "bab1"),
        Penanda("krit_a", 0, [r"^kriteria a\b"], [["kondisi", "eksternal"], ["lingkungan", "eksternal"]]),
        Penanda("a_makro", 1, [r"^a ?\.? ?1\b.*lingkungan makro", r"^lingkungan makro"], [["lingkungan", "makro"]], "krit_a"),
        Penanda("a_mikro", 1, [r"^a ?\.? ?2\b.*lingkungan mikro", r"^lingkungan mikro"], [["lingkungan", "mikro"]], "krit_a"),
        Penanda("a_analisis", 1, [r"^a ?\.? ?3\b"], [["analisis", "aspek"], ["swot"], ["sintesis"]], "krit_a"),
        Penanda("krit_b", 0, [r"^kriteria b\b"], [["profil", "unit", "pengelola"]]),
    ]
    sub_b = [("b1", ["sejarah"]), ("b2", ["visi", "misi"]), ("b3", ["organisasi", "tata", "kerja"]),
             ("b4", ["mahasiswa", "lulusan"]), ("b5", ["dosen", "kependidikan"]), ("b6", ["keuangan", "sarana"]),
             ("b7", ["penjaminan", "mutu"]), ("b8", ["kinerja"])]
    for kode, kata in sub_b:
        n = kode[1]
        k.append(Penanda(kode, 1, [rf"^b ?\.? ?{n}\b"], [kata], "krit_b"))
    k.append(Penanda("krit_c", 0, [r"^kriteria c$", r"^kriteria c\b"], [["kriteria", "c"]]))
    judul_c = {1: [["budaya", "mutu"]], 2: [["relevansi", "pendidikan"]], 3: [["penelitian"]],
               4: [["pengabdian"], ["pkm"]], 5: [["akuntabilitas"]], 6: [["diferensiasi", "misi"]]}
    for n, kata in judul_c.items():
        kode = f"c{n}"
        k.append(Penanda(kode, 1, [rf"^c ?{n} ?\.? [a-z]"], kata, "krit_c"))
        for tahap in _TAHAP:
            # "C1.1 [PENETAPAN] ...", "C2.1. [PENETAPAN]", "C3.3. EVALUASI", "4.1 [PENETAPAN]"
            k.append(Penanda(f"{kode}_{tahap}", 2,
                             [rf"^(c ?)?{n} ?\.? ?\d ?\.? ?{tahap}\b", rf"^(c ?)?{n} ?\.? ?\d\b.*\[ ?{tahap} ?\]"],
                             [[tahap]], kode))
    k += [
        Penanda("krit_d", 0, [r"^kriteria d\b"], [["suplemen", "program", "studi"]]),
        Penanda("d1", 1, [r"^d ?1\b"], [["inti", "kekhasan"]], "krit_d"),
        Penanda("d2", 1, [r"^d ?2\b"], [["domain"], ["sektor", "spesifik"]], "krit_d"),
        Penanda("d3", 1, [r"^d ?3\b"], [["metode", "analisis"]], "krit_d"),
        Penanda("bab3", 0, [r"^bab (iii|3)\b", r"^penutup$"], [["penutup"]]),
        Penanda("lampiran", 0, [r"^lampiran\b", r"^daftar pustaka"], [["lampiran"]]),
    ]
    return k


@dataclass
class Bagian:
    kunci: str
    tingkat: int
    mulai: int      # indeks blok judul
    akhir: int      # indeks blok setelah bagian (eksklusif)
    metode: str     # "pola" | "kata_kunci"


def _cocok_kata(teks: str, daftar: list[list[str]]) -> bool:
    kata_teks = set(teks.split())
    return any(all(any(k == w or (len(k) > 4 and w.startswith(k)) for w in kata_teks) for k in kata) for kata in daftar)


def petakan_bagian(blok: list[Blok], kerangka: list[Penanda]) -> dict[str, Bagian]:
    """Cari judul tiap penanda: pola persis dulu, lalu kata kunci; induk membatasi rentang pencarian."""
    # Halaman lampiran yang ditempel di akhir PDF (scan SK, sertifikat) tidak bernomor halaman cetak:
    # badan dokumen berakhir di halaman bernomor terakhir, supaya Penutup tidak ikut menyalin lampiran.
    hal_bernomor = [b.hal for b in blok if b.jenis == "label_hal" and b.hal]
    akhir_badan = next((i for i, b in enumerate(blok) if hal_bernomor and b.hal and b.hal > max(hal_bernomor)), len(blok))
    blok = blok[:akhir_badan]
    judul = [(i, _norm(b.teks)) for i, b in enumerate(blok) if b.jenis == "judul" and not _TITIK_DAFTAR.search(b.teks)]
    lemah = [(i, _norm(b.teks)) for i, b in enumerate(blok)
             if b.jenis == "teks" and len(b.teks) <= 120 and not b.teks.rstrip().endswith((".", ",", ";"))
             and not _TITIK_DAFTAR.search(b.teks)]
    ketemu: dict[str, tuple[int, str]] = {}
    batas: dict[str, tuple[int, int]] = {}

    def rentang(p: Penanda) -> tuple[int, int]:
        if p.induk and p.induk in batas:
            return batas[p.induk]
        return (0, len(blok))

    # Urut tingkat supaya induk sudah punya rentang sebelum anaknya dicari.
    for tingkat in sorted({p.tingkat for p in kerangka}):
        lapis = [p for p in kerangka if p.tingkat == tingkat]
        for p in lapis:
            a, z = rentang(p)
            if p.induk and p.induk not in batas:
                continue
            hasil = None
            for i, t in judul:
                if a <= i < z and i not in {v[0] for v in ketemu.values()} and any(re.search(r, t) for r in p.pola):
                    hasil = (i, "pola")
                    break
            if hasil is None and p.kata:
                for sumber in (judul, lemah):
                    for i, t in sumber:
                        if a <= i < z and i not in {v[0] for v in ketemu.values()} and len(t.split()) <= 18 \
                                and _cocok_kata(t, p.kata):
                            hasil = (i, "kata_kunci")
                            break
                    if hasil:
                        break
            if hasil:
                ketemu[p.kunci] = hasil
        # batas bagian tingkat ini = sampai penanda berikutnya dgn tingkat <= tingkat ini
        urut = sorted((v[0], p.tingkat, p.kunci) for p in kerangka if p.kunci in ketemu and p.tingkat <= tingkat
                      for v in [ketemu[p.kunci]])
        for idx, (i, t, kunci) in enumerate(urut):
            if t != tingkat:
                continue
            akhir = next((j for j, tt, _ in urut[idx + 1:] if tt <= tingkat), len(blok))
            induk = next((p.induk for p in kerangka if p.kunci == kunci), None)
            if induk and induk in batas:
                akhir = min(akhir, batas[induk][1])
            batas[kunci] = (i, akhir)
    return {k: Bagian(k, next(p.tingkat for p in kerangka if p.kunci == k), batas[k][0], batas[k][1], ketemu[k][1])
            for k in ketemu if k in batas}


# ====================================================================================
# 3. Narasi: isi bagian -> kolom item
# ====================================================================================

# Per item narasi: kolom -> (sub-bagian, kata kunci paragraf). Sub-bagian None = seluruh bagian item.
_NARASI_LED: dict[str, dict] = {
    "kata_pengantar": {"bagian": "kata_pengantar"},
    "ringkasan_eksekutif": {"bagian": "ringkasan"},
    "bab3_penutup": {"bagian": "bab3"},
    "bab1_pendahuluan": {"bagian": "bab1", "kolom": [
        ("A. Dasar Penyusunan", "bab1_dasar", []),
        ("B. Mekanisme Kerja Penyusunan Evaluasi Diri", "bab1_mekanisme", []),
    ], "lewati": ["bab1_tim"]},
    "led_kriteria_a": {"bagian": "krit_a", "kolom": [
        ("Lingkungan Makro – Kebijakan", "a_makro", ["kebijakan", "politik", "regulasi"]),
        ("Lingkungan Makro – Ekonomi", "a_makro", ["ekonomi"]),
        ("Lingkungan Makro – Sosial", "a_makro", ["sosial"]),
        ("Lingkungan Makro – Budaya", "a_makro", ["budaya"]),
        ("Lingkungan Makro – IPTEK", "a_makro", ["iptek", "teknologi"]),
        ("Lingkungan Mikro (9 aspek: pesaing, pengguna lulusan, dst.)", "a_mikro", []),
        ("Sintesis SWOT / Peluang Strategis", "a_analisis", []),
    ]},
    "led_b1_sejarah": {"bagian": "b1", "kolom": [
        ("Tanggal & SK Pendirian UPPS", None, ["upps", "departemen", "fakultas"]),
        ("Tanggal Pendirian PS", None, ["program studi", "prodi"]),
        ("Capaian Akreditasi Terkini", None, ["akreditasi", "terakreditasi"]),
    ]},
    "led_b2_vmts": {"bagian": "b2", "kolom": [
        ("Visi/Misi/Tujuan Strategis UPPS", None, ["departemen", "upps", "fakultas"]),
        ("Visi/Misi/Tujuan Strategis PS", None, ["program studi", "prodi"]),
        ("Renstra Multi-Tahun (link)", None, ["renstra", "rencana strategis"]),
        ("Target Capaian Kinerja (TCK) Tahunan", None, ["tck", "target capaian", "kontrak kinerja"]),
    ]},
    "led_b3_organisasi": {"bagian": "b3", "kolom": [
        ("SK SOTK (link)", None, ["sotk", "struktur organisasi", "tata kerja"]),
        ("Daftar Unit/Lab di bawah UPPS", None, ["laboratorium", "lab ", "unit"]),
        ("Struktur Gugus Jaminan Mutu", None, ["gugus", "jaminan mutu", "gjm", "gkm"]),
        ("Struktur Komite Kurikulum", None, ["kurikulum", "komite"]),
    ]},
    "led_b4_mahasiswa_lulusan": {"bagian": "b4", "kolom": [
        ("Jumlah Mahasiswa Aktif", None, ["mahasiswa aktif", "jumlah mahasiswa"]),
        ("Rata-rata Penerimaan/Tahun", None, ["penerimaan", "pendaftar", "diterima", "daya tampung"]),
        ("Jumlah Lulusan", None, ["lulusan", "wisuda", "meluluskan"]),
        ("Profil Karier Lulusan", None, ["karier", "karir", "bekerja", "tracer"]),
        ("Skema Dukungan (Beasiswa/Dana Publikasi)", None, ["beasiswa", "dana publikasi", "bantuan"]),
    ]},
    "led_b5_dosen_tendik": {"bagian": "b5", "kolom": [
        ("Jumlah Dosen (per Des. TS)", None, ["dosen"]),
        ("Dokumen Proyeksi Kenaikan Pangkat", None, ["kenaikan pangkat", "jabatan fungsional", "proyeksi"]),
        ("Jumlah Tenaga Kependidikan", None, ["tenaga kependidikan", "tendik"]),
    ]},
    "led_b6_keuangan_sarpras": {"bagian": "b6", "kolom": [
        ("Sumber Pendanaan (Pemerintah/UKT/Eksternal)", None, ["dana", "pendanaan", "ukt", "anggaran", "keuangan"]),
        ("Luas & Jumlah Ruang Kelas", None, ["ruang kelas", "ruang kuliah", "luas"]),
        ("Fasilitas Khusus (Lab, Alat Riset Besar)", None, ["laboratorium", "alat", "fasilitas"]),
    ]},
    "led_b7_spmi": {"bagian": "b7", "kolom": [
        ("Struktur SPMI (Pengawal per Tahap PPEPP)", None, ["spmi", "ppepp", "penjaminan"]),
        ("Jumlah IKU/IKT yang Dimandatkan TCK", None, ["iku", "ikt", "tck"]),
    ]},
    "led_b8_kinerja_ringkas": {"bagian": "b8", "kolom": [
        ("Highlight Capaian Pendidikan", None, ["pendidikan", "pembelajaran", "lulusan", "mahasiswa"]),
        ("Highlight Capaian Penelitian", None, ["penelitian", "publikasi", "riset"]),
        ("Highlight Capaian PkM", None, ["pengabdian", "pkm", "masyarakat"]),
    ]},
}
for _n, _item in {1: "led_c1_budaya_mutu", 2: "led_c2_relevansi_pendidikan", 3: "led_c3_penelitian",
                  4: "led_c4_pkm", 5: "led_c5_akuntabilitas", 6: "led_c6_diferensiasi_misi"}.items():
    _NARASI_LED[_item] = {"bagian": f"c{_n}", "kolom": [
        ("Dokumen Penetapan / Kebijakan (link)", f"c{_n}_penetapan", []),
        ("Bukti Pelaksanaan", f"c{_n}_pelaksanaan", []),
        ("Evaluasi Capaian (TS-2/TS-1/TS)", f"c{_n}_evaluasi", []),
        ("Rencana Tindak Lanjut (RTL)", f"c{_n}_pengendalian", []),
        ("Hasil Peningkatan setelah RTL", f"c{_n}_peningkatan", []),
    ]}


def _sub_di(bagian: dict[str, Bagian], i: int, kandidat: set[str]) -> str | None:
    """Sub-bagian terdalam (di antara `kandidat`) yang memuat blok ke-i."""
    isi = [b for k, b in bagian.items() if k in kandidat and b.mulai <= i < b.akhir]
    return max(isi, key=lambda b: b.tingkat).kunci if isi else None


def _kolom_paragraf(teks: str, calon: list[tuple[str, str | None, list[str]]], sebelum: str | None) -> str:
    """Kolom untuk satu paragraf: kata kunci di awal paragraf ("A.1.2. Aspek Ekonomi: ...") menang;
    lalu kolom pertama (urutan registry) yang kata kuncinya muncul; lalu kolom paragraf sebelumnya."""
    teks_n = f" {_norm(teks)} "
    kepala = teks_n[:90]
    posisi = [(kepala.find(f" {k}"), idx) for idx, (_, _, kata) in enumerate(calon) for k in kata if f" {k}" in kepala]
    if posisi:
        return calon[min(posisi)[1]][0]
    for nama, _, kata in calon:
        if any(f" {k}" in teks_n for k in kata):
            return nama
    if sebelum in [c[0] for c in calon]:
        return sebelum
    return calon[0][0]


def _narasi(blok: list[Blok], bagian: dict[str, Bagian], item_id: str) -> tuple[dict[str, str], str] | None:
    konf = _NARASI_LED.get(item_id)
    if not konf or konf["bagian"] not in bagian:
        return None
    b = bagian[konf["bagian"]]
    kolom_reg = list(KEBUTUHAN_DATA[item_id]["kolom_dibutuhkan"])
    spes = konf.get("kolom") or [(kolom_reg[0], None, [])]
    # Nama kolom di konfigurasi disamakan ke registry lewat _norm (tanda pisah registry bisa "–" atau "—").
    per_norm = {_norm(k): k for k in kolom_reg}
    spes = [(per_norm[_norm(k)], sub, kata) for k, sub, kata in spes if _norm(k) in per_norm]
    subs = {sub for _, sub, _ in spes if sub} | set(konf.get("lewati", []))
    isi: dict[str, list[str]] = {}
    sebelum: str | None = None
    for i in range(b.mulai + 1, b.akhir):
        bl = blok[i]
        if bl.jenis not in ("judul", "teks") or not bl.teks.strip():
            continue
        sub = _sub_di(bagian, i, subs)
        if sub in konf.get("lewati", []):
            continue
        if sub and bagian[sub].mulai == i:
            continue   # judul sub-bagian itu sendiri (mis. "C1.1 [PENETAPAN]") tidak ikut disalin
        calon = [s for s in spes if s[1] == sub] or ([s for s in spes if s[1] is None] if sub is None else [])
        if not calon:
            calon = spes[:1] if sebelum is None else [s for s in spes if s[0] == sebelum]
        pilih = _kolom_paragraf(bl.teks, calon, sebelum)
        isi.setdefault(pilih, []).append(bl.teks.strip())
        sebelum = pilih
    hasil = {k: "\n\n".join(v) for k, v in isi.items() if v}
    return (hasil, f"hal. {blok[b.mulai].hal}" if blok[b.mulai].hal else "Word") if hasil else None


# ====================================================================================
# 4. Tabel: header -> kolom registry, lokasi tabel
# ====================================================================================

_SINONIM = {"capaian": "kinerja", "realisasi": "kinerja", "sasaran": "target", "standar": "target",
            "ganjil": "gasal", "kadaluarsa": "kedaluwarsa", "tgl": "tanggal", "iku": "ikuikt", "ikt": "ikuikt",
            "ik": "ikuikt"}


def _token(label: str) -> tuple[set[str], tuple[str, ...]]:
    t = _norm(label).replace("ts - ", "ts-").replace("ts -", "ts-").replace("ts- ", "ts-")
    ts = tuple(re.findall(r"\bts(?:-\d)?\b", t))
    kata = {_SINONIM.get(w, w) for w in re.findall(r"[a-z]{2,}", t) if w not in ("ts", "dan", "atau", "di", "per")}
    return kata, ts


def petakan_kolom(header: list[str], kolom_reg: list[str]) -> dict[str, str]:
    """Label header dokumen -> kolom registry. TS-2/TS-1/TS wajib sama persis; kata dicocokkan longgar."""
    calon = []
    for h in header:
        if _norm(h) in ("no", "no.", "nomor", ""):
            continue
        kh, tsh = _token(h)
        for k in kolom_reg:
            kk, tsk = _token(k)
            if tsh != tsk:
                continue
            if not kk or not kh:
                # "TS-2" polos hanya cocok dengan kolom yang juga polos, bukan "TS-2 – Genap".
                s = 1.0 if not kk and not kh else 0.0
            else:
                s = len(kh & kk) / len(kk | kh) if kh else 0.0
                if kk <= kh or kh <= kk:
                    s = max(s, 0.6)
            if s >= 0.3:
                calon.append((s, h, k))
    peta: dict[str, str] = {}
    for s, h, k in sorted(calon, reverse=True):
        if h not in peta and k not in peta.values():
            peta[h] = k
    isi = [h for h in header if _norm(h) not in ("no", "no.", "nomor", "")]
    if len(peta) < len(kolom_reg) / 2 and len(isi) == len(kolom_reg):
        peta = dict(zip(isi, kolom_reg))   # posisional: jumlah kolom persis sama
    return peta


def _skor(header: list[str] | None, kolom_reg: list[str]) -> float:
    """Porsi kolom registry yang ketemu di header. 0 bila header rusak: label ganda, atau ada kolom
    deskriptif (tanpa TS, mis. Indikator/Referensi) yang tidak ketemu -- tanda sel header tergabung."""
    if not header or len(set(header)) < len(header):
        return 0.0
    peta = petakan_kolom(header, kolom_reg)
    deskriptif = [k for k in kolom_reg if not _token(k)[1]]
    if len(deskriptif) < len(kolom_reg) and any(k not in peta.values() for k in deskriptif):
        return 0.0
    return len(peta) / len(kolom_reg)


def _record_tabel(blok: list[Blok], i: int) -> list[dict[str, str]]:
    """Record tabel ke-i + lanjutannya di halaman berikut (sampai ada judul/tabel ber-header lain)."""
    rec = [dict(r) for r in blok[i].record]
    j = i + 1
    while j < len(blok):
        b = blok[j]
        if b.jenis in ("judul", "tabel_mentah") or (b.jenis == "tabel" and b.kolom):
            break
        if b.jenis == "tabel":
            if b.awalan and rec:
                for k, v in b.awalan.items():
                    rec[-1][k] = _rapat(f"{rec[-1].get(k, '')} {v}")
            rec += [dict(r) for r in b.record]
        elif b.jenis == "teks" and len(b.teks) > 200:
            break   # paragraf panjang di antara = tabel sudah selesai
        j += 1
    # Baris judul sub-kelompok ("B1 Implementasi peta jalan" diikuti B1.1, B1.2, ...) bukan data.
    k_no = next((k for k in (blok[i].kolom or []) if _norm(k) in ("no", "no.", "nomor")), None)
    if k_no:
        no = [r.get(k_no, "").strip().rstrip(".") for r in rec]
        rec = [r for n, r in zip(range(len(rec)), rec)
               if not (no[n] and any(x.startswith(no[n] + ".") for x in no[n + 1:n + 2]))]
    return rec


def _daftar_tabel(blok: list[Blok], bagian: dict[str, Bagian]) -> dict[str, str]:
    """{"c1.1": label halaman cetak} dari halaman DAFTAR TABEL."""
    if "daftar_tabel" not in bagian:
        return {}
    b = bagian["daftar_tabel"]
    teks = " ".join(blok[i].teks for i in range(b.mulai + 1, b.akhir) if blok[i].jenis in ("teks", "judul"))
    hasil = {}
    for m in re.finditer(r"tabel\s+([a-d]\s?\d+\s?\.\s?\d+)\s+(.+?)\s*(?:\.{3,}|…+)\s*([0-9ivxlc]+)\b", teks, re.I):
        hasil[re.sub(r"\s", "", m.group(1)).lower()] = m.group(3).lower()
    return hasil


def _halaman_pdf(blok: list[Blok]) -> dict[str, int]:
    """Label halaman cetak -> nomor halaman PDF (dari angka di kepala/kaki halaman)."""
    peta = {}
    for b in blok:
        if b.jenis == "label_hal" and b.teks not in peta:
            peta[b.teks] = b.hal
    return peta


_KATA_UMUM = {"dan", "atau", "yang", "terkait", "dengan", "di", "ke", "dari", "pada", "untuk", "serta", "baik",
              "tabel", "upps", "ps", "prodi", "mei", "indikator", "kebijakan", "standar", "lingkup"}


def _kata_judul(judul: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", _norm(judul)) if w not in _KATA_UMUM}


def _tabel_led(blok: list[Blok], bagian: dict[str, Bagian], items: list[dict]) -> dict[str, tuple[list[dict], str]]:
    daftar = _daftar_tabel(blok, bagian)
    hal_pdf = _halaman_pdf(blok)
    tabel_idx = [i for i, b in enumerate(blok) if b.jenis == "tabel" and b.kolom]
    terpakai: set[int] = set()
    hasil: dict[str, tuple[list[dict], str]] = {}

    def kode_item(item) -> str | None:
        m = re.match(r"tabel\s+([a-d]\d+\.\d+)", item["nama"].strip().lower())
        return m.group(1) if m else None

    def pakai(item_id, i, metode):
        terpakai.add(i)
        hasil[item_id] = (_record_tabel(blok, i), f"hal. {blok[i].hal} · {metode}" if blok[i].hal else metode)

    tabel_items = [it for it in items if it["tipe"] == "tabel" and kode_item(it)]
    # (a) caption "Tabel C1.1 ..." tepat di atas tabel (bukti terkuat). Blok yang muncul di antara
    # caption dan tabel hanya boleh label halaman / teks pendek (lanjutan caption dua baris).
    tolak: set[str] = set()   # caption ketemu tapi tabel di bawahnya tidak cocok -> jangan tebak lewat halaman
    for it in tabel_items:
        kode, kolom = kode_item(it), it["kolom_dibutuhkan"]
        pola = re.compile(rf"^tabel\s+{re.escape(kode)}(?!\d)", re.I)
        for c, b in enumerate(blok):
            if b.jenis not in ("teks", "judul") or len(b.teks) > 300 or not pola.match(b.teks.strip()):
                continue
            nxt = next((i for i in range(c + 1, min(c + 5, len(blok))) if blok[i].jenis == "tabel"), None)
            if nxt is None or any(blok[j].jenis == "judul" or len(blok[j].teks) > 300 for j in range(c + 1, nxt)):
                continue
            if blok[nxt].kolom and nxt not in terpakai and _skor(blok[nxt].kolom, kolom) >= 0.6:
                pakai(it["id"], nxt, "caption tabel")
            else:
                tolak.add(it["id"])
            break
    # (b) DAFTAR TABEL -> halaman PDF -> tabel ber-header ke-k di halaman itu
    per_hal: dict[str, list[str]] = {}
    for kode, lbl in daftar.items():
        per_hal.setdefault(lbl, []).append(kode)
    for it in tabel_items:
        if it["id"] in hasil or it["id"] in tolak:
            continue
        kode, kolom = kode_item(it), it["kolom_dibutuhkan"]
        lbl = daftar.get(kode)
        if not lbl or lbl not in hal_pdf:
            continue
        di_hal = [i for i in tabel_idx if blok[i].hal == hal_pdf[lbl]]
        urutan = per_hal[lbl].index(kode)
        if urutan < len(di_hal) and di_hal[urutan] not in terpakai and _skor(blok[di_hal[urutan]].kolom, kolom) >= 0.6:
            pakai(it["id"], di_hal[urutan], "Daftar Tabel")
    # (c) kata kunci judul tabel di bab kriterianya, (d) urutan tabel ber-header cocok di bab itu
    for it in tabel_items:
        if it["id"] in hasil or it["id"] in tolak:
            continue
        kode, kolom = kode_item(it), it["kolom_dibutuhkan"]
        bab = bagian.get(re.match(r"([a-d]\d+)", kode).group(1))
        a, z = (bab.mulai, bab.akhir) if bab else (0, len(blok))
        kata = _kata_judul(re.sub(r"^tabel\s+\S+\s*", "", it["nama"].lower()))
        terbaik = None
        for i, b in enumerate(blok[a:z], start=a):
            # Judul, atau caption pendek "Tabel ..." yang nomornya beda/salah ketik (umum di Excel rekap).
            caption = b.jenis == "teks" and len(b.teks) <= 250 and re.match(r"^tabel\s", b.teks, re.I)
            if (b.jenis != "judul" and not caption) or not kata:
                continue
            nomor = re.match(r"^tabel\s+([a-d]\d+\.\d+)", b.teks.strip().lower())
            if nomor and nomor.group(1) != kode:
                continue   # caption milik tabel lain (judulnya mirip, mis. C1.1 vs C1.3)
            cocok = len(kata & _kata_judul(b.teks)) / len(kata)
            if cocok >= 0.6 and (terbaik is None or cocok > terbaik[0]):
                terbaik = (cocok, i)
        if terbaik:
            nxt = next((i for i in tabel_idx if i > terbaik[1] and i not in terpakai), None)
            if nxt is not None and nxt < z and _skor(blok[nxt].kolom, kolom) >= 0.6:
                pakai(it["id"], nxt, "kata kunci judul")
                continue
        if bab is None:
            continue   # tanpa bab (mis. Excel bebas) urutan tabel bukan bukti: banyak tabel berkolom identik
        for i in tabel_idx:
            if a <= i < z and i not in terpakai and _skor(blok[i].kolom, kolom) >= 0.8:
                pakai(it["id"], i, "urutan tabel di bab")
                break
    return hasil


def _tabel_setelah(blok: list[Blok], bag: Bagian | None, kolom: list[str]) -> int | None:
    if bag is None:
        return None
    for i in range(bag.mulai + 1, bag.akhir):
        if blok[i].jenis == "tabel" and blok[i].kolom and _skor(blok[i].kolom, kolom) >= 0.5:
            return i
    return None


def _label_ke_kolom(label: str, kolom: list[str], alias: dict[str, str]) -> str | None:
    t = _norm(re.sub(r"\s*\d\)\s*$", "", label))
    if t in alias:
        return alias[t]
    kt, _ = _token(t)
    terbaik = max(((len(kt & _token(k)[0]) / max(len(_token(k)[0] | kt), 1), k) for k in kolom), default=(0, None))
    return terbaik[1] if terbaik[0] >= 0.6 else None


def _vertikal(grid: list[list[str]], kolom: list[str], alias: dict[str, str]) -> dict[str, str]:
    """Satu tabel "Label : Nilai" -> {kolom registry: nilai}. Sel ":" dan nomor urut dilewati."""
    hasil: dict[str, str] = {}
    for r in grid:
        sel = [c for c in r if c and not _ANGKA_NO.match(c)]
        if not sel:
            continue
        if ":" in sel:
            i = sel.index(":")
            label, nilai = " ".join(sel[:i]), " ".join(sel[i + 1:])
        elif len(sel) >= 2 and sel[1].startswith(":"):
            label, nilai = sel[0], " ".join([sel[1][1:]] + sel[2:])
        else:
            continue
        k = _label_ke_kolom(label, kolom, alias)
        if k and nilai.strip():
            hasil[k] = _rapat(nilai)
    return hasil


def _tim_penyusun(blok: list[Blok], bagian: dict[str, Bagian], kolom: list[str]) -> tuple[list[dict], str] | None:
    """Kartu anggota tim (satu tabel vertikal per orang) di bagian IDENTITAS TIM PENYUSUN."""
    bag = bagian.get("tim")
    if bag is None:
        return None
    alias = {"jabatan": next((k for k in kolom if k.lower().startswith("jabatan")), "Jabatan"),
             "tugas": next((k for k in kolom if "tanggung" in k.lower()), ""),
             "tanggung jawab": next((k for k in kolom if "tanggung" in k.lower()), "")}
    alias = {a: k for a, k in alias.items() if k}
    rec: list[dict[str, str]] = []
    for b in blok[bag.mulai + 1:bag.akhir]:
        if b.jenis != "tabel_mentah":
            continue
        r = _vertikal(b.grid, kolom, alias)
        if r.get("Nama"):
            rec.append(r)
        elif r and rec:
            # Kartu terpotong pergantian halaman: sisa kartu (tanpa Nama) milik kartu sebelumnya.
            rec[-1] = {**r, **rec[-1]}
    return (rec, f"hal. {blok[bag.mulai].hal}" if blok[bag.mulai].hal else "Word") if rec else None


def _identitas(blok: list[Blok], bagian: dict[str, Bagian], kolom: list[str]) -> tuple[dict[str, str], str] | None:
    """Spesifikasi program "Label : Nilai" (baris teks PDF atau tabel 2-3 kolom di Word)."""
    bag = bagian.get("spesifikasi") or bagian.get("identitas")
    if bag is None:
        return None
    baris: list[str] = []
    dari_tabel: dict[str, str] = {}
    for i in range(bag.mulai + 1, bag.akhir):
        b = blok[i]
        if b.jenis == "tabel_mentah":
            dari_tabel.update(_vertikal(b.grid, kolom, {}))
        elif b.jenis in ("teks", "judul"):
            baris += b.baris_mentah or [b.teks]
    if len(dari_tabel) >= 3:
        return dari_tabel, f"hal. {blok[bag.mulai].hal}" if blok[bag.mulai].hal else "Word"

    def label_cocok(t: str) -> str | None:
        t = re.sub(r"\s*\d\)\s*$", "", t)
        kt, _ = _token(t)
        terbaik = max(((len(kt & _token(k)[0]) / max(len(_token(k)[0] | kt), 1), k) for k in kolom), default=(0, None))
        return terbaik[1] if terbaik[0] >= 0.6 else None

    hasil: dict[str, str] = {}
    sekarang, label_buf = None, []
    for t in baris:
        t = t.strip()
        if ":" in t and t != ":" and not sekarang:
            kiri, _, kanan = t.partition(":")
            k = label_cocok(kiri)
            if k:
                hasil[k] = kanan.strip()
                continue
        if t == ":":
            k = label_cocok(" ".join(label_buf[-3:])) or label_cocok(" ".join(label_buf[-2:])) or label_cocok(" ".join(label_buf[-1:]))
            if k:
                sekarang = k
                hasil[k] = ""
            label_buf = []
            continue
        if sekarang:
            # baris berikut milik nilai, kecuali ia awal label baru (diikuti ":" -> ditangani di atas)
            kandidat = label_cocok(t)
            if kandidat and kandidat not in hasil and hasil[sekarang]:
                sekarang, label_buf = None, [t]
                continue
            hasil[sekarang] = _rapat(f"{hasil[sekarang]} {t}")
        else:
            label_buf.append(t)
    # label yang terpotong dua baris ("Pejabat ... Pembukaan" + "PS") bisa masuk ke nilai sebelumnya:
    # buang ekor yang persis awal label lain.
    hasil = {k: v for k, v in hasil.items() if v}
    return (hasil, f"hal. {blok[bag.mulai].hal}" if blok[bag.mulai].hal else "Word") if hasil else None


# ====================================================================================
# 5. Entry point
# ====================================================================================

def _items(mode: str) -> list[dict]:
    grouped = led_items_by_kriteria() if mode == "LED" else lkps_items_by_bagian()
    return [{**item, "id": item["id"]} for items in grouped.values() for item in items]


def _tabel_lkps(blok: list[Blok], items: list[dict]) -> dict[str, tuple[list[dict], str]]:
    """LKPS: judul "Tabel 2.A.1 ..." di badan dokumen -> tabel ber-header cocok berikutnya; fallback kata kunci nama."""
    tabel_idx = [i for i, b in enumerate(blok) if b.jenis == "tabel" and b.kolom]
    hasil, terpakai = {}, set()
    for it in items:
        if it["tipe"] != "tabel" or not it.get("tabel_lkps"):
            continue
        kode = re.escape(_norm(it["tabel_lkps"])).replace(r"\.", r"\s?\.+\s?")
        kata = _kata_judul(it["nama"])
        kandidat = [i for i, b in enumerate(blok) if b.jenis in ("judul", "teks") and len(b.teks) < 250
                    and re.search(rf"\btabel\s+{kode}\b", _norm(b.teks))]
        if not kandidat and kata:
            kandidat = [i for i, b in enumerate(blok) if b.jenis == "judul"
                        and len(kata & _kata_judul(b.teks)) / len(kata) >= 0.6]
        for awal in kandidat:
            nxt = next((i for i in tabel_idx if i > awal and i not in terpakai), None)
            if nxt is not None and _skor(blok[nxt].kolom, it["kolom_dibutuhkan"]) >= 0.5:
                terpakai.add(nxt)
                hasil[it["id"]] = (_record_tabel(blok, nxt), f"hal. {blok[nxt].hal}" if blok[nxt].hal else "Word")
                break
    return hasil


def ekstrak_dokumen(path_lokal: str, tipe_file: str, mode: str,
                    progress_callback=None, client=None) -> tuple[list[dict], dict]:
    """Sama kontraknya dengan ekstraksi_akreditasi.ekstrak_dokumen (argumen `client` diabaikan)."""
    ringkasan = {"n_item_ditemukan": 0, "n_kolom_terisi": 0, "n_batch": 1, "n_batch_gagal": 0,
                 "waktu_ekstraksi_teks": 0.0, "waktu_llm_total": 0.0, "error": None, "metode": "tanpa_ai"}
    t0 = time.time()
    try:
        blok = baca_dokumen(path_lokal, tipe_file, progress_callback)
    except Exception as e:  # noqa: BLE001
        ringkasan.update(error=f"Gagal membaca file: {e}", n_batch_gagal=1)
        return [], ringkasan
    items = _items(mode)
    temuan: dict[str, tuple[list[dict], str]] = {}
    if mode == "LED":
        bagian = petakan_bagian(blok, _kerangka_led())
        for it in items:
            if it["id"] in _NARASI_LED:
                n = _narasi(blok, bagian, it["id"])
                if n:
                    temuan[it["id"]] = ([n[0]], n[1])
        idn = _identitas(blok, bagian, list(KEBUTUHAN_DATA["identitas_pt_upps_ps"]["kolom_dibutuhkan"]))
        if idn:
            temuan["identitas_pt_upps_ps"] = ([idn[0]], idn[1])
        temuan.update(_tabel_led(blok, bagian, items))
        for item_id, kunci in (("status_akreditasi_seluruh_ps", "daftar_ps"),
                               ("lkps_d1", "d1"), ("lkps_d2", "d2"), ("lkps_d3", "d3")):
            if item_id in KEBUTUHAN_DATA and item_id not in temuan:
                i = _tabel_setelah(blok, bagian.get(kunci), KEBUTUHAN_DATA[item_id]["kolom_dibutuhkan"])
                if i is not None:
                    temuan[item_id] = (_record_tabel(blok, i), f"hal. {blok[i].hal}" if blok[i].hal else "Word")
        if "tim_penyusun_led" in KEBUTUHAN_DATA:
            tim = _tim_penyusun(blok, bagian, list(KEBUTUHAN_DATA["tim_penyusun_led"]["kolom_dibutuhkan"]))
            if tim:
                temuan["tim_penyusun_led"] = tim
    else:
        temuan.update(_tabel_lkps(blok, items))
    ringkasan["waktu_ekstraksi_teks"] = time.time() - t0

    baris_hasil: list[dict] = []
    for item_id, (records, sumber) in temuan.items():
        item = KEBUTUHAN_DATA[item_id]
        kolom_reg = list(item["kolom_dibutuhkan"])
        for baris_ke, rec in enumerate(records, start=1):
            if item["tipe"] == "tabel" and rec and not set(rec) <= set(kolom_reg):
                peta = petakan_kolom(list(rec), kolom_reg)
                rec = {peta[k]: v for k, v in rec.items() if k in peta}
            for kolom, nilai in rec.items():
                if kolom in kolom_reg and str(nilai).strip():
                    baris_hasil.append({"item_id": item_id, "baris_ke": baris_ke, "nama_kolom": kolom,
                                        "nilai": str(nilai).strip(), "kutipan": sumber})
    ringkasan["n_item_ditemukan"] = len({r["item_id"] for r in baris_hasil})
    ringkasan["n_kolom_terisi"] = len(baris_hasil)
    return baris_hasil, ringkasan
