"""Ekstraksi AI dari file upload akreditasi (Tahap 3).

Alur: 1 file -> extract teks (PyMuPDF/python-docx/openpyxl) -> panggilan
Luna PER BATCH kecil item registry yang relevan (LED atau LKPS, sesuai
mode dokumen) -> parse JSON -> simpan ke akreditasi_upload_ekstraksi
(BUKAN akreditasi_data_manual -- itu baru diisi setelah user review &
klik Simpan, lihat konfirmasi_ekstraksi() di bawah dan kebijakan
registry_kebutuhan_data.py poin 7).

CATATAN PENTING (2026-09-16) -- KENAPA PER BATCH, BUKAN 1 PANGGILAN UTK
SEMUA ITEM SEKALIGUS: awalnya dicoba 1 panggilan berisi semua 25 item LED
sekaligus (~455rb karakter dokumen + 96 kolom diminta) -- GAGAL dengan
"Error 524: Cloudflare Proxy Read Timeout" (origin/gateway Luna cuma
dikasih waktu 120 detik oleh Cloudflare, di luar kendali kode ini). Dites
ulang dengan batch lebih kecil: 5 item = 110.7 detik (nyaris limit, vs
57.7 detik di Tahap 2 pada jam yang beda -- waktu respons gateway ini
TERNYATA sangat fluktuatif, bukan cuma fungsi linear dari jumlah item),
8 item = timeout juga. Kesimpulan: batas 120 detik per panggilan itu
KERAS dan waktu respons tidak bisa diprediksi presisi, jadi kode ini
PAKAI BATCH KECIL (_BATCH_SIZE item per panggilan, retry kalau timeout)
-- teks dokumen TERPAKSA dikirim ulang tiap batch (sama seperti Tahap 2),
TAPI jumlah panggilan per dokumen jauh lebih sedikit & otomatis (bukan
lagi run manual per 5 item spt Tahap 2), dan ada retry otomatis kalau
satu batch timeout supaya user tidak perlu mengulang manual.

CATATAN response_format: gateway/model "cx/gpt-5.6-luna" TERNYATA TIDAK
menegakkan JSON Schema strict (dicoba 2026-09-16 -- model mengabaikan
skema yang diminta, balik struktur sendiri). Makanya di sini pakai
response_format json_object biasa (yang di Tahap 2 terbukti mengikuti
struktur yang diminta lewat prompt, cuma sesekali ada glitch sintaks
kecil) + _repair_json() sbg jaring pengaman, bukan JSON Schema strict.
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

import db  # noqa: E402
from registry_kebutuhan_data import KEBUTUHAN_DATA, led_items_by_kriteria, lkps_items_by_bagian  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL = "cx/gpt-5.6-luna"
_BATCH_SIZE = 4  # lihat catatan di docstring modul -- >=8 item/panggilan terbukti timeout
_TIMEOUT_DETIK = 115  # sedikit di bawah batas Cloudflare 120 detik, biar gagal cepat & rapi
_MAX_RETRY_PER_BATCH = 2

SYSTEM_PROMPT = """Kamu adalah asisten ekstraksi data untuk dokumen akreditasi program studi.
Tugasmu: baca TEKS DOKUMEN yang diberikan, lalu untuk SETIAP item data yang diminta, cari apakah
informasinya ADA secara eksplisit di teks tsb.

ATURAN KETAT (WAJIB DIPATUHI):
1. HANYA gunakan informasi yang benar-benar tertulis di TEKS DOKUMEN. JANGAN mengarang, JANGAN
   menebak, JANGAN mengisi dari pengetahuan umum di luar teks.
2. Kalau informasi untuk suatu kolom TIDAK ditemukan di teks, isi "nilai": null dan "kutipan": null
   untuk kolom itu -- JANGAN dikosongkan dengan string kosong, JANGAN diisi placeholder seperti
   "-" atau "tidak diketahui" sebagai pengganti null.
3. Untuk tiap kolom yang nilainya ditemukan, sertakan "kutipan": potongan teks ASLI (verbatim,
   maksimal ~200 karakter) dari dokumen yang menjadi bukti/sumber nilai itu.
4. Item bertipe TABEL yang datanya berulang per tahun/judul/baris (mis. jumlah mahasiswa per
   TS-2/TS-1/TS, atau daftar judul penelitian) HARUS dipecah jadi BEBERAPA OBJEK "baris" terpisah
   di array "baris" -- SATU baris = satu tahun/judul/entitas, JANGAN digabung jadi satu string
   panjang dipisah titik koma. Item bertipe NARASI (satu kesatuan, bukan tabel berulang) cukup
   SATU objek di array "baris".
5. Kalau SATU ITEM sama sekali tidak ada informasinya di dokumen, tetap kembalikan itemnya dengan
   satu baris berisi semua kolom bernilai null -- jangan dihilangkan dari output.
6. Output HARUS JSON valid, tidak ada teks lain di luar JSON, tidak ada trailing comma/karakter
   liar (mis. titik koma) di dalam string atau setelah nilai.
"""


def _repair_json(raw: str) -> str:
    """Perbaikan ringan untuk glitch sintaks kecil yang pernah ditemukan di
    Tahap 2 (mis. titik koma nyasar tepat sebelum penutup objek/array) --
    BUKAN JSON Schema strict (lihat docstring modul), jadi ini jaring
    pengaman terakhir, dicoba HANYA kalau json.loads() gagal duluan."""
    fixed = re.sub(r';\s*(?=[}\]])', '', raw)
    fixed = re.sub(r',\s*(?=[}\]])', '', fixed)
    return fixed


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_repair_json(raw))


def _items_untuk_mode(mode: str) -> list[dict]:
    grouped = led_items_by_kriteria() if mode == "LED" else lkps_items_by_bagian()
    return [{**item, "id": item["id"]} for items in grouped.values() for item in items]


def _extract_text_pdf(path: str) -> str:
    import fitz
    doc = fitz.open(path)
    return "".join(page.get_text() for page in doc)


def _extract_text_docx(path: str) -> str:
    import docx
    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for tbl in d.tables:
        for row in tbl.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)


def _extract_text_xlsx(path: str) -> str:
    xls = pd.ExcelFile(path)
    parts = []
    for sheet in xls.sheet_names:
        df = xls.parse(sheet, header=None)
        parts.append(f"=== Sheet: {sheet} ===")
        parts.append(df.to_csv(index=False, header=False))
    return "\n".join(parts)


def extract_text(path: str, tipe_file: str) -> str:
    if tipe_file == "pdf":
        return _extract_text_pdf(path)
    if tipe_file == "docx":
        return _extract_text_docx(path)
    if tipe_file == "xlsx":
        return _extract_text_xlsx(path)
    raise ValueError(f"Tipe file tidak didukung: {tipe_file}")


def _build_user_prompt(document_text: str, items: list[dict]) -> str:
    items_desc = [
        {
            "item_id": item["id"],
            "nama": item["nama"],
            "deskripsi": item["deskripsi_singkat"],
            "tipe": item["tipe"],
            "kolom_dibutuhkan": item["kolom_dibutuhkan"],
        }
        for item in items
    ]
    schema_hint = {
        "hasil": [
            {
                "item_id": "string, sama persis dengan item_id yang diminta",
                "baris": [
                    {
                        "kolom": [
                            {"nama_kolom": "string", "nilai": "string atau null", "kutipan": "string atau null"}
                        ]
                    }
                ],
            }
        ]
    }
    return (
        f"ITEM DATA YANG DIMINTA (ekstrak masing-masing kalau ada di dokumen -- "
        f"{len(items)} item total):\n"
        f"{json.dumps(items_desc, ensure_ascii=False, indent=2)}\n\n"
        f"SKEMA OUTPUT (ikuti persis strukturnya):\n"
        f"{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        f"TEKS DOKUMEN (hasil ekstraksi file, boleh ada noise formatting):\n"
        f"---MULAI TEKS DOKUMEN---\n{document_text}\n---AKHIR TEKS DOKUMEN---"
    )


def _get_client():
    import os
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
        max_retries=0,  # retry level BATCH kita sendiri yang atur (lihat _call_llm_batch)
        timeout=_TIMEOUT_DETIK,
    )


def _call_llm_batch(client, document_text: str, items: list[dict]) -> tuple[dict, float]:
    """Satu panggilan Luna utk satu batch kecil item (lihat _BATCH_SIZE).
    Retry sendiri sampai _MAX_RETRY_PER_BATCH kali kalau timeout/gagal --
    limit 120 detik dari gateway (Cloudflare) itu KERAS & di luar kendali
    kita, jadi kegagalan pertama TIDAK otomatis berarti batch ini rusak,
    layak dicoba ulang sebelum menyerah."""
    user_prompt = _build_user_prompt(document_text, items)
    last_err: Exception | None = None
    for attempt in range(1, _MAX_RETRY_PER_BATCH + 1):
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            elapsed = time.time() - t0
            parsed = _parse_json_response(resp.choices[0].message.content)
            return parsed, elapsed
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < _MAX_RETRY_PER_BATCH:
                continue
    raise RuntimeError(f"Batch gagal setelah {_MAX_RETRY_PER_BATCH}x percobaan: {last_err}")


def _klaim_untuk_ekstraksi(engine, upload_file_id: int) -> bool:
    """Klaim atomik status "belum_diekstrak" -> "sedang_diekstrak" (UPDATE ...
    WHERE status='belum_diekstrak', cek rowcount) supaya 2 proses yang
    memicu ekstraksi bersamaan utk file yang SAMA (mis. dua tab/sesi browser,
    atau tombol UI diklik 2x sebelum rerun pertama update status) tidak
    dobel-insert baris ekstraksi identik yang nanti keliru terdeteksi
    deteksi_konflik() sbg "2 nilai beda dari file berbeda" (ditemukan
    2026-09-16 -- 2 proses sempat jalan bersamaan, hasil LLM sedikit beda
    krn non-determinisme, jadi lolos cek nunique(nilai) > 1 walau sumbernya
    cuma 1 file yang sama)."""
    def _try():
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    f"UPDATE `{db.t('upload_file')}` SET status = 'sedang_diekstrak' "
                    "WHERE id = :id AND status = 'belum_diekstrak'"
                ),
                {"id": upload_file_id},
            )
            return result.rowcount
    ok, rowcount = db.with_retry(_try, label=f"klaim ekstraksi upload {upload_file_id}")
    return bool(ok and rowcount == 1)


def ekstrak_file(upload_file_id: int, path_lokal: str, tipe_file: str, prodi_id: str,
                  mode: str, progress_callback=None) -> dict:
    """Jalankan ekstraksi utk 1 file yang sudah diupload, PER BATCH kecil
    item (lihat catatan gateway timeout di docstring modul) -- teks dokumen
    yang sama dikirim ulang tiap batch (tidak terhindarkan, API stateless),
    tapi jumlah panggilan otomatis & ada retry per-batch. Hasil (kolom yang
    nilainya ditemukan SAJA -- null tidak disimpan, lihat instruksi Tahap 3
    poin 4) disimpan ke akreditasi_upload_ekstraksi, update status file.

    `progress_callback(batch_ke, total_batch)` opsional, dipanggil sebelum
    tiap batch -- dipakai UI utk tampilkan progress bar (proses ini bisa
    makan beberapa menit utk dokumen dgn banyak item).

    Return dict ringkasan: {n_item_ditemukan, n_kolom_terisi, n_batch,
    n_batch_gagal, waktu_ekstraksi_teks, waktu_llm_total, error}."""
    engine = db.get_engine()
    ringkasan = {"n_item_ditemukan": 0, "n_kolom_terisi": 0, "n_batch": 0, "n_batch_gagal": 0,
                 "waktu_ekstraksi_teks": 0.0, "waktu_llm_total": 0.0, "error": None}

    if not _klaim_untuk_ekstraksi(engine, upload_file_id):
        ringkasan["error"] = (
            "File ini sedang/sudah diekstrak proses lain -- dilewati supaya tidak dobel."
        )
        return ringkasan

    t0 = time.time()
    try:
        text_doc = extract_text(path_lokal, tipe_file)
    except Exception as e:  # noqa: BLE001
        ringkasan["error"] = f"Gagal ekstrak teks file: {e}"
        _set_status(engine, upload_file_id, "gagal_ekstrak")
        return ringkasan
    ringkasan["waktu_ekstraksi_teks"] = time.time() - t0

    items = _items_untuk_mode(mode)
    batches = [items[i:i + _BATCH_SIZE] for i in range(0, len(items), _BATCH_SIZE)]
    ringkasan["n_batch"] = len(batches)
    client = _get_client()

    now = datetime.now()
    rows_to_insert = []
    item_ids_ditemukan: set[str] = set()
    batch_errors = []
    for i, batch_items in enumerate(batches, start=1):
        if progress_callback:
            progress_callback(i, len(batches))
        try:
            parsed, waktu_llm = _call_llm_batch(client, text_doc, batch_items)
        except Exception as e:  # noqa: BLE001
            ringkasan["n_batch_gagal"] += 1
            batch_errors.append(f"batch {i}/{len(batches)}: {e}")
            continue
        ringkasan["waktu_llm_total"] += waktu_llm

        for item_result in parsed.get("hasil", []):
            item_id = item_result.get("item_id")
            if item_id not in KEBUTUHAN_DATA:
                continue
            for baris_ke, baris in enumerate(item_result.get("baris", []), start=1):
                for kolom in baris.get("kolom", []):
                    nilai = kolom.get("nilai")
                    if nilai is None or str(nilai).strip() == "":
                        continue
                    item_ids_ditemukan.add(item_id)
                    ringkasan["n_kolom_terisi"] += 1
                    rows_to_insert.append({
                        "upload_file_id": upload_file_id,
                        "prodi_id": prodi_id,
                        "item_id": item_id,
                        "baris_ke": baris_ke,
                        "nama_kolom": kolom.get("nama_kolom", ""),
                        "nilai": str(nilai),
                        "kutipan": kolom.get("kutipan"),
                        "created_at": now,
                    })

    ringkasan["n_item_ditemukan"] = len(item_ids_ditemukan)
    if batch_errors:
        ringkasan["error"] = "; ".join(batch_errors)

    def _insert():
        with engine.begin() as conn:
            if rows_to_insert:
                conn.execute(
                    text(
                        f"INSERT INTO `{db.t('upload_ekstraksi')}` "
                        "(upload_file_id, prodi_id, item_id, baris_ke, nama_kolom, nilai, "
                        "kutipan, created_at) "
                        "VALUES (:upload_file_id, :prodi_id, :item_id, :baris_ke, :nama_kolom, "
                        ":nilai, :kutipan, :created_at)"
                    ),
                    rows_to_insert,
                )

    ok, _ = db.with_retry(_insert, label=f"simpan ekstraksi upload {upload_file_id}")
    if not ok:
        ringkasan["error"] = ((ringkasan["error"] + "; ") if ringkasan["error"] else "") + \
            "Gagal menyimpan hasil ekstraksi ke MySQL."
        _set_status(engine, upload_file_id, "gagal_ekstrak")
        return ringkasan

    # Status "gagal_ekstrak" cuma kalau SEMUA batch gagal (tidak ada satu pun
    # kolom berhasil diekstrak) -- kalau sebagian batch gagal tapi sebagian
    # berhasil, tetap "diekstrak" (parsial), error tercatat di ringkasan
    # supaya UI bisa kasih tau user bagian mana yang perlu diulang.
    status_akhir = "diekstrak" if rows_to_insert or ringkasan["n_batch_gagal"] < ringkasan["n_batch"] else "gagal_ekstrak"
    _set_status(engine, upload_file_id, status_akhir)
    return ringkasan


def _set_status(engine, upload_file_id: int, status: str) -> None:
    def _update():
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE `{db.t('upload_file')}` SET status = :status, diekstrak_at = :ts "
                    "WHERE id = :id"
                ),
                {"status": status, "ts": datetime.now(), "id": upload_file_id},
            )
    db.with_retry(_update, label=f"update status upload {upload_file_id}")


@st.cache_data(ttl=10)
def load_pending_ekstraksi(prodi_id: str) -> pd.DataFrame:
    """Semua baris ekstraksi yang BELUM dikonfirmasi user, join nama file
    sumbernya -- dipakai render_pending_ekstraksi_utk_item() di bawah."""
    engine = db.get_engine()
    if not db.table_exists(engine, db.t("upload_ekstraksi")):
        return pd.DataFrame(columns=["id", "upload_file_id", "item_id", "baris_ke", "nama_kolom",
                                      "nilai", "kutipan", "nama_file"])
    return db.read_sql_retry(
        engine,
        f"SELECT e.id, e.upload_file_id, e.item_id, e.baris_ke, e.nama_kolom, e.nilai, "
        f"e.kutipan, f.nama_file "
        f"FROM `{db.t('upload_ekstraksi')}` e "
        f"JOIN `{db.t('upload_file')}` f ON f.id = e.upload_file_id "
        f"WHERE e.prodi_id = :prodi_id AND e.dikonfirmasi_at IS NULL "
        f"ORDER BY e.item_id, e.baris_ke, e.nama_kolom",
        label="load pending ekstraksi", params={"prodi_id": prodi_id},
    )


def pending_untuk_item(prodi_id: str, item_id: str) -> pd.DataFrame:
    df = load_pending_ekstraksi(prodi_id)
    return df[df["item_id"] == item_id]


def deteksi_konflik(df: pd.DataFrame) -> pd.DataFrame:
    """Tandai (item_id, baris_ke, nama_kolom) yang punya >1 nilai BEDA dari
    file berbeda -- return df + kolom boolean 'konflik'. Boleh dipanggil ke
    seluruh pending (semua item sekaligus) atau ke slice satu item."""
    if not len(df):
        return df.assign(konflik=pd.Series(dtype=bool))
    n_unik = df.groupby(["item_id", "baris_ke", "nama_kolom"])["nilai"].transform("nunique")
    return df.assign(konflik=n_unik > 1)


def konfirmasi_ekstraksi(prodi_id: str, item_id: str, ekstraksi_ids: list[int]) -> None:
    """Tandai baris-baris ekstraksi (yang sudah diproses/dipilih user lewat
    form, entah dipakai atau tidak) sebagai selesai di-review supaya tidak
    muncul lagi sbg pending -- dipanggil SETELAH _render_item_form menyimpan
    ke akreditasi_data_manual (lihat wiring di page_akreditasi.py)."""
    if not ekstraksi_ids:
        return
    engine = db.get_engine()
    now = datetime.now()

    def _update():
        with engine.begin() as conn:
            placeholders = ", ".join(f":id{i}" for i in range(len(ekstraksi_ids)))
            params = {f"id{i}": v for i, v in enumerate(ekstraksi_ids)}
            params["ts"] = now
            conn.execute(
                text(
                    f"UPDATE `{db.t('upload_ekstraksi')}` SET dikonfirmasi_at = :ts "
                    f"WHERE id IN ({placeholders})"
                ),
                params,
            )

    db.with_retry(_update, label=f"konfirmasi ekstraksi item {item_id}")
    load_pending_ekstraksi.clear()
