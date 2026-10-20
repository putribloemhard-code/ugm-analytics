"""Draf AI untuk item narasi LED (Kata Pengantar, Pendahuluan, Kriteria A-C, Penutup, dst.).

Bahan draf = data yang SUDAH ada di sistem untuk laporan itu: identitas prodi, isian item LED lain,
isian LKPS prodi yang sama di tahun yang sama, dan data live (Fase 2). LLM hanya merangkai bahan
itu menjadi narasi; fakta yang tidak ada di bahan ditulis sebagai penanda "[perlu dilengkapi: ...]"
supaya tim penyusun tahu apa yang harus diisi sendiri.

Hasil ditulis ke isian item (akreditasi_data_manual) dengan diisi_oleh = DIISI_AI. Begitu tim
mengedit lalu menyimpan, diisi_oleh berganti email penyimpan sehingga tanda "Draf AI" hilang
dengan sendirinya. Item final tidak pernah disentuh. Isian tim hanya diganti bila diminta
(`timpa=True`); isian itu dicadangkan dulu di akreditasi_draf_cadangan dan bisa dipulihkan
(`pulihkan`) selama draf AI penggantinya belum disunting.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import accreditation_sumber as sumber
from app.services.accreditation_workspace import (
    AccreditationWorkspaceService,
    NotFound,
    WorkspaceError,
    _registry,
)
from app.services.insight_ai import MODEL, _client, tersedia

DIISI_AI = "Draf AI"
# Item narasi yang isinya data identitas (nama PT, nomor SK, alamat), bukan narasi: tidak diserahkan ke AI.
ITEM_TANPA_AI = {"identitas_pt_upps_ps"}

_MAKS_BAHAN = 45_000
_MAKS_SEL = 400
_MAKS_NARASI = 2_500
_MAKS_BARIS = 15

SYSTEM_PROMPT = (
    "Kamu membantu tim penyusun Laporan Evaluasi Diri (LED) akreditasi program studi (instrumen "
    "LAM-INFOKOM) di Universitas Gadjah Mada. Tulis draf Bahasa Indonesia formal akademik untuk SATU "
    "item LED, per kolom yang diminta.\n"
    "ATURAN KETAT:\n"
    "1. Pakai HANYA fakta yang ada di BAHAN. Jangan mengarang angka, nama orang, tanggal, nomor SK, "
    "tautan, nama dokumen kebijakan, hasil survei, atau hasil evaluasi.\n"
    "2. Bila sebuah kalimat membutuhkan fakta yang tidak ada di BAHAN, tulis penanda persis "
    "\"[perlu dilengkapi: <fakta yang dibutuhkan>]\" di posisi itu, lalu lanjutkan kalimat lain.\n"
    "3. Kolom yang meminta tautan/dokumen: isi hanya bila tautan/dokumennya ada di BAHAN; bila tidak, "
    "isi dengan penanda saja.\n"
    "4. Untuk analisis (SWOT, evaluasi capaian, akar masalah, rencana peningkatan) yang tidak didukung "
    "BAHAN, tulis kerangka kalimat yang jelas bagian mana yang harus diisi tim dengan penanda.\n"
    "5. SETIAP kolom wajib berisi teks, tidak boleh kosong: bila bahannya tidak ada, tulis kerangka "
    "kalimat dengan penanda.\n"
    "6. Teks biasa tanpa markdown/heading/bullet; paragraf dipisah satu baris kosong.\n"
    "7. Bila ada NARASI SAAT INI (mis. salinan LED periode lalu): jadikan dasar. Pertahankan struktur, urutan "
    "pembahasan, dan gaya bahasanya; perbarui angka, tahun, dan klaim agar sesuai BAHAN terbaru. Kalimat yang "
    "faktanya tidak bisa dipastikan dari BAHAN tetap dipertahankan, diberi penanda \"[perlu dicek: <apa yang "
    "dicek>]\" di akhir kalimat itu.\n"
    "Balas HANYA satu objek JSON: kunci = nama kolom persis seperti yang diminta, nilai = teks draf."
)


def item_draf_ai() -> list[str]:
    """Item narasi LED yang bisa dibuatkan draf AI."""
    registry = _registry()
    return [item["id"] for items in registry.led_items_by_kriteria().values() for item in items
            if item["tipe"] == "narasi" and item["id"] not in ITEM_TANPA_AI]


def _potong(teks: str, maks: int) -> str:
    teks = " ".join(str(teks).split())
    return teks if len(teks) <= maks else teks[: maks - 1] + "…"


def _render_item(item: dict, sel: list[dict]) -> str:
    """Isian satu item jadi teks ringkas: narasi per kolom, tabel per baris (dibatasi)."""
    baris: dict[int, dict[str, str]] = {}
    for s in sel:
        if s["nilai"]:
            baris.setdefault(int(s["baris_ke"]), {})[s["kolom"]] = s["nilai"]
    if not baris:
        return ""
    judul = f"### {item['nama']}" + (f" (Tabel LKPS {item['tabel_lkps']})" if item.get("tabel_lkps") else "")
    if item["tipe"] == "narasi":
        isi = [f"{k}: {_potong(v, _MAKS_NARASI)}" for k, v in baris[min(baris)].items()]
    else:
        urut = sorted(baris)
        isi = [f"Baris {b}: " + "; ".join(f"{k}: {_potong(v, _MAKS_SEL)}" for k, v in baris[b].items())
               for b in urut[:_MAKS_BARIS]]
        if len(urut) > _MAKS_BARIS:
            isi.append(f"(… {len(urut) - _MAKS_BARIS} baris lain, total {len(urut)} baris)")
    return "\n".join([judul, *isi])


def _bahan(engine: Engine, laporan: dict[str, Any], item: dict) -> str:
    registry = _registry()
    lap_id, prodi_id = int(laporan["id"]), laporan["prodi_id"]
    with engine.connect() as conn:
        program = AccreditationWorkspaceService(engine)._program(conn, prodi_id)
        led = conn.execute(text("""
            SELECT item_id, baris_ke, kolom, nilai FROM akreditasi_data_manual
            WHERE laporan_id = :l ORDER BY item_id, baris_ke
        """), {"l": lap_id}).mappings().all()
        lkps = conn.execute(text("""
            SELECT d.item_id, d.baris_ke, d.kolom, d.nilai FROM akreditasi_data_manual d
            JOIN akreditasi_laporan l ON l.id = d.laporan_id
            WHERE l.prodi_id = :p AND l.dokumen = 'LKPS' AND l.tahun = :t ORDER BY d.item_id, d.baris_ke
        """), {"p": prodi_id, "t": laporan["tahun"]}).mappings().all()
        live = sumber.data_live(conn, prodi_id)

    def per_item(rows) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r["item_id"], []).append(dict(r))
        return out

    led_by, lkps_by = per_item(led), per_item(lkps)
    kriteria = item["kriteria_led"]
    relevan = lambda i: registry.KEBUTUHAN_DATA[i]["kriteria_led"] == kriteria  # noqa: E731

    bagian = [
        "## Identitas laporan",
        f"Program studi: {' '.join(filter(None, [program.get('jenjang'), program['nama']]))}",
        f"Fakultas: {program.get('fakultas') or '[tidak tercatat]'}",
        "Perguruan tinggi: Universitas Gadjah Mada",
        f"Dokumen: Laporan Evaluasi Diri (LED) tahun {laporan['tahun']}",
    ]
    # Urutan prioritas: bahan sekriteria dulu, lalu sisanya; berhenti saat batas karakter tercapai.
    kandidat: list[tuple[str, str, list[dict]]] = []
    for sumber_nama, data in (("Isian LED", led_by), ("Isian LKPS tahun yang sama", lkps_by)):
        for item_id, sel in data.items():
            if item_id != item["id"] and item_id in registry.KEBUTUHAN_DATA:
                kandidat.append((sumber_nama, item_id, sel))
    for item_id, it in live["items"].items():
        if item_id in registry.KEBUTUHAN_DATA and item_id not in led_by and item_id not in lkps_by:
            sel = [{"baris_ke": b, "kolom": k, "nilai": v} for b, row in enumerate(it["rows"], 1) for k, v in row.items()]
            kandidat.append(("Data live", item_id, sel))
    kandidat.sort(key=lambda k: (not relevan(k[1]), k[0] != "Isian LED"))

    terpakai = sum(len(b) for b in bagian)
    for sumber_nama, item_id, sel in kandidat:
        teks = _render_item({**registry.KEBUTUHAN_DATA[item_id], "id": item_id}, sel)
        if not teks or terpakai + len(teks) > _MAKS_BAHAN:
            continue
        bagian.append(f"[{sumber_nama}]\n{teks}")
        terpakai += len(teks)
    pendukung = sumber.pendukung(item["id"], live)
    if pendukung:
        bagian.append(f"## {pendukung['judul']} (total {pendukung['total']})")
        bagian += [" | ".join(r) for r in pendukung["rows"]]
    return "\n\n".join(bagian)


def _parse(teks: str, kolom: list[str]) -> dict[str, str]:
    teks = re.sub(r"^```(?:json)?\s*|\s*```$", "", teks.strip())
    try:
        data = json.loads(teks)
    except json.JSONDecodeError as exc:
        awal, akhir = teks.find("{"), teks.rfind("}")
        if awal < 0 or akhir <= awal:
            raise WorkspaceError("AI mengembalikan format yang tidak terbaca. Coba lagi.") from exc
        data = json.loads(teks[awal: akhir + 1])
    if not isinstance(data, dict):
        raise WorkspaceError("AI mengembalikan format yang tidak terbaca. Coba lagi.")
    return {k: str(data.get(k) or "").strip() for k in kolom}


def _pengisi_dan_final(engine: Engine, lap_id: int, item_id: str) -> tuple[set[str | None], bool]:
    with engine.connect() as conn:
        pengisi = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT diisi_oleh FROM akreditasi_data_manual WHERE laporan_id = :l AND item_id = :i"),
            {"l": lap_id, "i": item_id})}
        final = conn.execute(text("SELECT 1 FROM akreditasi_item_final WHERE laporan_id = :l AND item_id = :i"),
                             {"l": lap_id, "i": item_id}).first()
    return pengisi, bool(final)


def _narasi_saat_ini(engine: Engine, lap_id: int, item_id: str, kolom: list[str]) -> str:
    """Isian item ini sekarang (hasil ekstraksi LED lama atau isian tim), per kolom, untuk diperbarui AI.
    Draf AI sebelumnya tidak ikut: membuat ulang draf = mulai lagi dari bahan, bukan dari draf lama."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT kolom, nilai FROM akreditasi_data_manual
            WHERE laporan_id = :l AND item_id = :i AND baris_ke = 1 AND (diisi_oleh IS NULL OR diisi_oleh <> :ai)
        """), {"l": lap_id, "i": item_id, "ai": DIISI_AI}).all()
    isi = {k: v for k, v in rows if v and str(v).strip()}
    bagian = [f"### {k}\n{_potong(isi[k], _MAKS_NARASI * 4)}" for k in kolom if k in isi]
    teks = "\n\n".join(bagian)
    return teks[:_MAKS_BAHAN]


def _cadangkan(engine: Engine, lap_id: int, item_id: str) -> None:
    """Salin isian tim item ini ke tabel cadangan (menggantikan cadangan lama item yang sama)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM akreditasi_draf_cadangan WHERE laporan_id = :l AND item_id = :i"),
                     {"l": lap_id, "i": item_id})
        conn.execute(text("""
            INSERT INTO akreditasi_draf_cadangan (laporan_id, item_id, baris_ke, kolom, nilai, diisi_oleh, updated_at, dicadangkan_at)
            SELECT laporan_id, item_id, baris_ke, kolom, nilai, diisi_oleh, updated_at, :t
            FROM akreditasi_data_manual WHERE laporan_id = :l AND item_id = :i
        """), {"l": lap_id, "i": item_id, "t": datetime.now()})


def item_bercadangan(engine: Engine, lap_id: int) -> set[str]:
    try:
        with engine.connect() as conn:
            return {r[0] for r in conn.execute(text(
                "SELECT DISTINCT item_id FROM akreditasi_draf_cadangan WHERE laporan_id = :l"), {"l": lap_id})}
    except Exception:  # noqa: BLE001 -- tabel belum dibuat (API belum menjalankan ensure_schema)
        return set()


def pulihkan(engine: Engine, laporan: dict[str, Any], item_id: str) -> dict[str, Any]:
    """Kembalikan isian tim yang diganti draf AI. Ditolak bila draf itu sudah disunting tim."""
    lap_id = int(laporan["id"])
    if item_id not in item_bercadangan(engine, lap_id):
        raise WorkspaceError("Tidak ada isian sebelumnya yang bisa dipulihkan untuk item ini.")
    pengisi, _ = _pengisi_dan_final(engine, lap_id, item_id)
    if pengisi - {DIISI_AI}:
        raise WorkspaceError("Draf AI item ini sudah disunting tim; pemulihan dibatalkan supaya suntingan tidak hilang.")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM akreditasi_data_manual WHERE laporan_id = :l AND item_id = :i"),
                     {"l": lap_id, "i": item_id})
        conn.execute(text("DELETE FROM akreditasi_item_final WHERE laporan_id = :l AND item_id = :i"),
                     {"l": lap_id, "i": item_id})
        conn.execute(text("""
            INSERT INTO akreditasi_data_manual
              (prodi_id, laporan_id, item_id, baris_ke, kolom, tahun, nilai, link_bukti, diisi_oleh, updated_at)
            SELECT :p, laporan_id, item_id, baris_ke, kolom, NULL, nilai, NULL, diisi_oleh, updated_at
            FROM akreditasi_draf_cadangan WHERE laporan_id = :l AND item_id = :i
        """), {"p": laporan["prodi_id"], "l": lap_id, "i": item_id})
        conn.execute(text("DELETE FROM akreditasi_draf_cadangan WHERE laporan_id = :l AND item_id = :i"),
                     {"l": lap_id, "i": item_id})
    return {"message": "Isian sebelumnya dipulihkan."}


def buat_draf(engine: Engine, laporan: dict[str, Any], item_id: str, client: Any = None,
              timpa: bool = False) -> dict[str, Any]:
    """Buat draf AI satu item narasi LED dan simpan ke isian laporan (diisi_oleh = DIISI_AI).

    `timpa=True` mengizinkan mengganti isian tim; isian itu dicadangkan dulu (lihat `pulihkan`)."""
    registry = _registry()
    item = registry.KEBUTUHAN_DATA.get(item_id)
    if not item:
        raise NotFound("Item kebutuhan data tidak dikenal.")
    item = {**item, "id": item_id}
    if laporan["dokumen"] != "LED" or item_id not in item_draf_ai():
        raise WorkspaceError("Draf AI hanya tersedia untuk item narasi LED.")
    if client is None and not tersedia():
        raise WorkspaceError("Draf AI belum dikonfigurasi (OPENAI_API_KEY kosong di .env).")

    lap_id = int(laporan["id"])
    pengisi, final = _pengisi_dan_final(engine, lap_id, item_id)
    if final:
        raise WorkspaceError("Item ini sudah ditandai final; kembalikan ke draft dulu bila ingin dibuatkan draf AI.")
    isian_tim = bool(pengisi - {DIISI_AI})
    if isian_tim and not timpa:
        raise WorkspaceError("Item ini sudah diisi tim; pilih \"Perbarui dengan draf AI\" untuk memperbaruinya.")

    kolom = list(item["kolom_dibutuhkan"])
    pesan = (f"ITEM: {item['nama']}\nKriteria: {registry.LABEL_KRITERIA.get(item['kriteria_led'], item['kriteria_led'])}\n"
             f"Deskripsi: {item['deskripsi_singkat']}\nKOLOM YANG DIMINTA (JSON key): {json.dumps(kolom, ensure_ascii=False)}\n\n"
             f"BAHAN:\n{_bahan(engine, laporan, item)}")
    saat_ini = _narasi_saat_ini(engine, lap_id, item_id, kolom)
    if saat_ini:
        pesan += f"\n\nNARASI SAAT INI (perbarui, jangan tulis dari nol):\n{saat_ini}"
    try:
        resp = (client or _client()).chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": pesan}],
        )
        jawaban = resp.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001 -- galat jaringan/kuota apa pun = pesan ramah
        logging.getLogger(__name__).exception("draf AI %s gagal", item_id)
        raise WorkspaceError("Layanan AI sedang tidak bisa dihubungi. Coba lagi beberapa saat lagi.") from exc
    isi = _parse(jawaban, kolom)
    if not any(isi.values()):
        raise WorkspaceError("AI tidak mengembalikan isi draf. Coba lagi.")
    # Kolom yang tetap dikosongkan AI diberi penanda supaya tidak terlewat saat review.
    isi = {k: v or f"[perlu dilengkapi: {k}]" for k, v in isi.items()}
    if isian_tim:  # cadangan hanya dari isian tim; draf AI yang dibuat ulang tidak menggeser cadangan itu
        _cadangkan(engine, lap_id, item_id)
    AccreditationWorkspaceService(engine).save_item(laporan, item_id, [isi], DIISI_AI)
    return {"message": f"Draf AI {item['nama']} tersimpan. Periksa dan sunting sebelum dipakai.",
            "penanda": sum(v.count("[perlu dilengkapi") for v in isi.values())}
