"""Fitur upload file pendukung akreditasi.

File fisik disimpan di folder lokal `akreditasi/data/uploads/<prodi_id>/`,
metadata (nama file, path, ukuran, status) di tabel MySQL
`akreditasi_upload_file` (lihat migrasi_tabel_upload_akreditasi.py). Sejak
Tahap 3, tombol "Ekstrak Data" di sini memicu ekstraksi_akreditasi.py --
hasilnya PREVIEW saja (akreditasi_upload_ekstraksi), user tetap harus
review & klik Simpan di tiap item (lihat dashboard_render.py
_render_item_form) sebelum masuk akreditasi_data_manual sbg data resmi.
"""

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st
from sqlalchemy import text

import db  # noqa: E402

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"
TIPE_PER_EKSTENSI = {".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx"}
STATUS_LABEL = {
    "belum_diekstrak": "⚪ Belum diekstrak",
    "sedang_diekstrak": "🔵 Sedang diekstrak",
    "diekstrak": "🟢 Sudah diekstrak",
    "gagal_ekstrak": "🔴 Gagal diekstrak",
}


def _nama_aman(nama: str) -> str:
    """Bersihkan nama file dari karakter yang bisa bermasalah di path lokal
    (tetap pertahankan nama asli file di kolom `nama_file` MySQL -- ini
    cuma dipakai untuk nama file FISIK di disk)."""
    nfkd = unicodedata.normalize("NFKD", nama)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_only).strip("_") or "file"


def simpan_upload(prodi_id: str, uploaded_file, diupload_oleh: str | None = None) -> int:
    """Simpan satu file upload (objek UploadedFile dari st.file_uploader) ke
    disk + insert 1 baris metadata ke akreditasi_upload_file. Return id baris
    yang baru disimpan."""
    ekstensi = Path(uploaded_file.name).suffix.lower()
    tipe = TIPE_PER_EKSTENSI.get(ekstensi, ekstensi.lstrip("."))

    prodi_dir = UPLOAD_DIR / prodi_id
    prodi_dir.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y%m%d%H%M%S%f")
    nama_disk = f"{stempel}_{_nama_aman(uploaded_file.name)}"
    path_lokal = prodi_dir / nama_disk

    data = uploaded_file.getvalue()
    path_lokal.write_bytes(data)

    engine = db.get_engine()
    now = datetime.now()

    def _insert():
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    f"INSERT INTO `{db.t('upload_file')}` "
                    "(prodi_id, nama_file, path_lokal, tipe_file, ukuran_bytes, status, "
                    "diupload_oleh, uploaded_at) "
                    "VALUES (:prodi_id, :nama_file, :path_lokal, :tipe_file, :ukuran_bytes, "
                    "'belum_diekstrak', :diupload_oleh, :uploaded_at)"
                ),
                {
                    "prodi_id": prodi_id,
                    "nama_file": uploaded_file.name,
                    "path_lokal": str(path_lokal),
                    "tipe_file": tipe,
                    "ukuran_bytes": len(data),
                    "diupload_oleh": diupload_oleh,
                    "uploaded_at": now,
                },
            )
            return result.lastrowid

    ok, new_id = db.with_retry(_insert, label=f"simpan upload {uploaded_file.name}")
    if not ok:
        # Bersihkan file fisik kalau insert metadata gagal -- jangan tinggalkan
        # file yatim yang tidak tercatat di MySQL.
        path_lokal.unlink(missing_ok=True)
        raise RuntimeError(f"Gagal menyimpan metadata upload untuk {uploaded_file.name}.")
    return new_id


@st.cache_data(ttl=15)
def load_upload_list(prodi_id: str) -> pd.DataFrame:
    engine = db.get_engine()
    if not db.table_exists(engine, db.t("upload_file")):
        return pd.DataFrame(columns=["id", "nama_file", "path_lokal", "tipe_file",
                                      "ukuran_bytes", "status", "uploaded_at"])
    return db.read_sql_retry(
        engine,
        f"SELECT id, nama_file, path_lokal, tipe_file, ukuran_bytes, status, uploaded_at "
        f"FROM `{db.t('upload_file')}` WHERE prodi_id = :prodi_id ORDER BY uploaded_at DESC",
        label="load daftar upload", params={"prodi_id": prodi_id},
    )


def render_upload_section(prodi_id: str, mode: str, diupload_oleh: str | None = None) -> None:
    """UI upload file pendukung + daftar file + tombol ekstraksi AI. Dipanggil
    dari page_akreditasi.py SETELAH Lingkup/Fakultas/Prodi/Pilihan laporan
    terisi semua. `mode` ("LED"/"LKPS") menentukan set item registry yang
    dipakai utk ekstraksi (lihat ekstraksi_akreditasi._items_untuk_mode) --
    SESUAI mode dokumen yang lagi aktif di dropdown "Pilihan laporan"."""
    st.subheader("📤 Upload File Pendukung")
    st.caption(
        "Unggah dokumen pendukung akreditasi (PDF/Word/Excel, maks. 25 MB per file). Setelah "
        "diupload, klik \"Ekstrak Data\" untuk mencoba mengambil nilai-nilai relevan secara "
        "otomatis (AI) -- hasilnya PREVIEW yang perlu Anda cek & konfirmasi di tabel item "
        "kelengkapan data di bawah, BUKAN langsung jadi data resmi."
    )
    uploaded_files = st.file_uploader(
        "Pilih file (bisa lebih dari satu)",
        type=["pdf", "docx", "xlsx"],
        accept_multiple_files=True,
        key=f"akreditasi_upload_{prodi_id}",
    )
    if uploaded_files:
        if st.button("💾 Simpan file yang diunggah", key=f"akreditasi_upload_simpan_{prodi_id}"):
            berhasil, gagal = 0, []
            for f in uploaded_files:
                try:
                    simpan_upload(prodi_id, f, diupload_oleh=diupload_oleh)
                    berhasil += 1
                except Exception as e:  # noqa: BLE001
                    gagal.append(f"{f.name}: {e}")
            load_upload_list.clear()
            if berhasil:
                st.success(f"{berhasil} file tersimpan.")
            for pesan in gagal:
                st.error(f"Gagal menyimpan {pesan}")
            if berhasil:
                st.rerun()

    daftar = load_upload_list(prodi_id)
    if len(daftar):
        st.markdown("**File yang sudah diupload untuk prodi ini:**")
        tampil = daftar.copy()
        tampil["status"] = tampil["status"].map(lambda s: STATUS_LABEL.get(s, s))
        tampil["ukuran_bytes"] = (tampil["ukuran_bytes"] / 1024).round(1).astype(str) + " KB"
        tampil_show = tampil.rename(columns={
            "nama_file": "Nama File", "tipe_file": "Tipe", "ukuran_bytes": "Ukuran",
            "status": "Status", "uploaded_at": "Waktu Upload",
        })[["Nama File", "Tipe", "Ukuran", "Status", "Waktu Upload"]]
        st.dataframe(tampil_show, width="stretch", hide_index=True)

        belum = daftar[daftar["status"] == "belum_diekstrak"]
        if len(belum):
            st.caption(
                f"{len(belum)} file belum diekstrak -- proses ini bisa makan beberapa menit "
                "per file (dipecah jadi beberapa panggilan AI kecil, lihat catatan di "
                "ekstraksi_akreditasi.py soal batas waktu gateway)."
            )
            if st.button(f"🔍 Ekstrak Data dari {len(belum)} File Baru (mode {mode})",
                         key=f"akreditasi_ekstrak_{prodi_id}"):
                from ekstraksi_akreditasi import ekstrak_file

                for _, row in belum.iterrows():
                    progress = st.progress(0.0, text=f"Mengekstrak {row['nama_file']}...")

                    def _cb(i, total, _nama=row["nama_file"], _bar=progress):
                        _bar.progress(i / total, text=f"Mengekstrak {_nama} -- batch {i}/{total}")

                    ringkasan = ekstrak_file(
                        int(row["id"]), row["path_lokal"], row["tipe_file"], prodi_id, mode,
                        progress_callback=_cb,
                    )
                    progress.progress(1.0, text=f"Selesai: {row['nama_file']}")
                    if ringkasan.get("error"):
                        st.warning(
                            f"{row['nama_file']}: {ringkasan['n_item_ditemukan']} item ditemukan "
                            f"({ringkasan['n_kolom_terisi']} kolom), tapi ada kendala -- "
                            f"{ringkasan['error']}"
                        )
                    else:
                        st.success(
                            f"{row['nama_file']}: {ringkasan['n_item_ditemukan']} item ditemukan, "
                            f"{ringkasan['n_kolom_terisi']} kolom terisi "
                            f"({ringkasan['n_batch']} batch, {ringkasan['waktu_llm_total']:.0f} "
                            "detik total panggilan AI)."
                        )
                load_upload_list.clear()
                from ekstraksi_akreditasi import load_pending_ekstraksi
                load_pending_ekstraksi.clear()
                st.rerun()
    else:
        st.caption("Belum ada file yang diupload untuk prodi ini.")
