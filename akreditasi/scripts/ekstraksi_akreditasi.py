"""Ekstraksi AI dari file upload akreditasi (Tahap 3).

Alur: 1 file -> extract teks (PyMuPDF/python-docx/openpyxl) -> panggilan
Luna PER BATCH kecil item registry yang relevan (LED atau LKPS, sesuai
mode dokumen) -> parse JSON -> daftar baris (item_id, baris_ke, nama_kolom,
nilai, kutipan). Modul ini MURNI (tanpa DB/UI): penyimpanan ke
akreditasi_upload_ekstraksi, klaim status file, deteksi konflik, dan
konfirmasi setelah review ada di API
(api/app/services/accreditation_workspace.py). Hasil ekstraksi tetap
PREVIEW -- baru masuk akreditasi_data_manual setelah user review & klik
Simpan (kebijakan registry_kebutuhan_data.py poin 7).

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from dotenv import load_dotenv

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
    import pymupdf as fitz  # nama modul "fitz" sudah deprecated
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


def ekstrak_dokumen(path_lokal: str, tipe_file: str, mode: str,
                    progress_callback=None, client=None) -> tuple[list[dict], dict]:
    """Ekstraksi 1 file PER BATCH kecil item (lihat catatan gateway timeout di
    docstring modul) -- teks dokumen yang sama dikirim ulang tiap batch (tidak
    terhindarkan, API stateless), tapi jumlah panggilan otomatis & ada retry
    per-batch. Hanya kolom yang nilainya DITEMUKAN yang dikembalikan (null
    dibuang, lihat instruksi Tahap 3 poin 4).

    `progress_callback(batch_ke, total_batch)` opsional, dipanggil sebelum
    tiap batch. `client` opsional (default klien OpenAI dari .env) --
    disuntikkan oleh uji.

    Return (baris, ringkasan). baris = list dict {item_id, baris_ke,
    nama_kolom, nilai, kutipan}; ringkasan = {n_item_ditemukan,
    n_kolom_terisi, n_batch, n_batch_gagal, waktu_ekstraksi_teks,
    waktu_llm_total, error}. Gagal baca teks -> baris kosong + error, TIDAK
    melempar exception."""
    ringkasan = {"n_item_ditemukan": 0, "n_kolom_terisi": 0, "n_batch": 0, "n_batch_gagal": 0,
                 "waktu_ekstraksi_teks": 0.0, "waktu_llm_total": 0.0, "error": None}
    t0 = time.time()
    try:
        text_doc = extract_text(path_lokal, tipe_file)
    except Exception as e:  # noqa: BLE001
        ringkasan["error"] = f"Gagal ekstrak teks file: {e}"
        return [], ringkasan
    ringkasan["waktu_ekstraksi_teks"] = time.time() - t0

    items = _items_untuk_mode(mode)
    batches = [items[i:i + _BATCH_SIZE] for i in range(0, len(items), _BATCH_SIZE)]
    ringkasan["n_batch"] = len(batches)
    client = client or _get_client()

    baris_hasil: list[dict] = []
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
                    baris_hasil.append({
                        "item_id": item_id,
                        "baris_ke": baris_ke,
                        "nama_kolom": kolom.get("nama_kolom", ""),
                        "nilai": str(nilai),
                        "kutipan": kolom.get("kutipan"),
                    })

    ringkasan["n_item_ditemukan"] = len(item_ids_ditemukan)
    if batch_errors:
        ringkasan["error"] = "; ".join(batch_errors)
    return baris_hasil, ringkasan
