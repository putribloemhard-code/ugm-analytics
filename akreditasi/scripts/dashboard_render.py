"""Komponen UI Streamlit yang dipakai BARENG oleh dua entry point:
- akreditasi/dashboard_akreditasi.py (app berdiri sendiri)
- berita-dampak/page_akreditasi.py (menu "Akreditasi" di dashboard berita-dampak)

Diekstrak ke sini supaya form input manual, badge status, dan generator
dokumen SATU sumber kebenaran -- data yang diisi lewat salah satu entry
point otomatis muncul di entry point lainnya (sama-sama baca/tulis tabel
MySQL akreditasi_data_manual).
"""

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

import db  # noqa: E402
from registry_kebutuhan_data import (  # noqa: E402
    LABEL_BAGIAN_LKPS,
    LABEL_KRITERIA,
    STATUS_LABEL,
    URUTAN_BAGIAN_LKPS,
    URUTAN_KRITERIA,
    badge_status,
    is_narasi_penilaian,
    led_items_by_kriteria,
    lkps_cuplikan_untuk_kriteria,
    lkps_items_by_bagian,
    ringkasan_status,
)


# Default prodi_id kalau selector (render_prodi_selector, lihat di bawah)
# belum sempat dipanggil oleh caller -- juga dipakai sbg nilai fallback
# instansiasi widget selectbox pertama kali (index MIPA/MEI). JANGAN ubah
# jadi None/kosong (kolom prodi_id di akreditasi_data_manual NOT NULL).
PRODI_AKTIF_DEFAULT = "mei"
_TAMBAH_PRODI_SENTINEL = "+ Tambah prodi baru"


def _slugify(nama: str) -> str:
    """"Magister Kecerdasan Artifisial" -> "magister-kecerdasan-artifisial"."""
    nfkd = unicodedata.normalize("NFKD", nama)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug or "prodi"


@st.cache_data(ttl=600)
def load_fakultas() -> pd.DataFrame:
    engine = get_engine()
    if not db.table_exists(engine, db.t("fakultas")):
        return pd.DataFrame(columns=["id", "nama", "slug", "url"])
    return db.read_sql_retry(
        engine, f"SELECT id, nama, slug, url FROM `{db.t('fakultas')}` ORDER BY nama",
        label="load fakultas",
    )


@st.cache_data(ttl=600)
def load_prodi(fakultas_id: int | None = None) -> pd.DataFrame:
    engine = get_engine()
    if not db.table_exists(engine, db.t("prodi")):
        return pd.DataFrame(columns=["id", "fakultas_id", "nama", "jenjang", "slug", "url"])
    sql = f"SELECT id, fakultas_id, nama, jenjang, slug, url FROM `{db.t('prodi')}`"
    params = {}
    if fakultas_id is not None:
        sql += " WHERE fakultas_id = :fakultas_id"
        params["fakultas_id"] = fakultas_id
    sql += " ORDER BY nama"
    return db.read_sql_retry(engine, sql, label="load prodi", params=params)


def tambah_prodi(fakultas_id: int, nama: str, jenjang: str) -> str:
    """Insert 1 prodi baru ke akreditasi_prodi lewat form "+ Tambah prodi
    baru" di render_prodi_selector(). Slug di-generate dari nama, dibikin
    unik kalau ada tabrakan (mis. dua fakultas beda punya prodi bernama
    sama). Return slug yang tersimpan (dipakai sbg prodi_id)."""
    engine = get_engine()
    base_slug = _slugify(nama)
    slug = base_slug
    with engine.connect() as conn:
        i = 2
        while conn.exec_driver_sql(
            f"SELECT COUNT(*) FROM `{db.t('prodi')}` WHERE slug = %s", (slug,)
        ).scalar():
            slug = f"{base_slug}-{i}"
            i += 1

    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO `{db.t('prodi')}` (fakultas_id, nama, jenjang, slug) "
                 "VALUES (:fakultas_id, :nama, :jenjang, :slug)"),
            {"fakultas_id": fakultas_id, "nama": nama, "jenjang": jenjang, "slug": slug},
        )
    load_prodi.clear()
    return slug


_PILIH_FAKULTAS_SENTINEL = "-- Pilih Fakultas --"
_PILIH_PRODI_SENTINEL = "-- Pilih Program Studi --"


def render_prodi_selector() -> str | None:
    """2 dropdown (Fakultas -> Program Studi) + form "+ Tambah prodi baru"
    kalau prodi yang dicari belum ada di akreditasi_prodi. Return slug prodi
    terpilih (dipakai sbg prodi_id ke load_data_manual/render_tabs_*), atau
    None kalau Fakultas dan/atau Program Studi belum dipilih -- caller WAJIB
    cek None dan st.stop() dengan pesan sebelum lanjut ke bagian yang butuh
    prodi_id (data_manual, tabs LED/LKPS, dst)."""
    df_fakultas = load_fakultas()
    if not len(df_fakultas):
        st.warning("Tabel akreditasi_fakultas kosong -- jalankan scripts/migrasi_tabel_prodi.py.")
        return None

    fakultas_nama = df_fakultas["nama"].tolist()
    col1, col2 = st.columns(2)
    with col1:
        fakultas_pilih = st.selectbox(
            "Fakultas (wajib)", options=[_PILIH_FAKULTAS_SENTINEL] + fakultas_nama, index=0,
            key="akreditasi_fakultas_pilih",
        )
    if fakultas_pilih == _PILIH_FAKULTAS_SENTINEL:
        with col2:
            st.selectbox("Program Studi (wajib)", options=[_PILIH_PRODI_SENTINEL], index=0,
                          key="akreditasi_prodi_pilih_disabled", disabled=True)
        return None
    fakultas_row = df_fakultas[df_fakultas["nama"] == fakultas_pilih].iloc[0]

    df_prodi = load_prodi(int(fakultas_row["id"]))
    with col2:
        if len(df_prodi):
            opsi = [_PILIH_PRODI_SENTINEL] + df_prodi["nama"].tolist() + [_TAMBAH_PRODI_SENTINEL]
            prodi_pilih = st.selectbox("Program Studi (wajib)", options=opsi, index=0,
                                        key="akreditasi_prodi_pilih")
        else:
            st.selectbox("Program Studi (wajib)", options=[_TAMBAH_PRODI_SENTINEL], index=0,
                          key="akreditasi_prodi_pilih", disabled=True)
            prodi_pilih = _TAMBAH_PRODI_SENTINEL
            st.caption(f"Belum ada prodi tersimpan utk {fakultas_pilih}.")

    if prodi_pilih == _PILIH_PRODI_SENTINEL:
        return None
    if prodi_pilih != _TAMBAH_PRODI_SENTINEL:
        return df_prodi[df_prodi["nama"] == prodi_pilih].iloc[0]["slug"]

    with st.form(key="form_tambah_prodi"):
        st.caption(f"Tambah prodi baru di bawah **{fakultas_pilih}**:")
        nama_baru = st.text_input("Nama Program Studi", key="tambah_prodi_nama")
        jenjang_baru = st.selectbox("Jenjang", options=["Sarjana", "Magister", "Doktor", "Profesi", "Spesialis"],
                                     key="tambah_prodi_jenjang")
        if st.form_submit_button("➕ Tambah Prodi"):
            if not nama_baru.strip():
                st.error("Nama Program Studi tidak boleh kosong.")
                st.stop()
            slug_baru = tambah_prodi(int(fakultas_row["id"]), nama_baru.strip(), jenjang_baru)
            st.success(f"Prodi \"{nama_baru}\" ditambahkan (prodi_id: {slug_baru}).")
            st.session_state["akreditasi_prodi_pilih"] = nama_baru.strip()
            st.rerun()
    st.stop()


@st.cache_resource
def get_engine():
    return db.get_engine()


@st.cache_data(ttl=60)
def load_data_manual(prodi_id: str = PRODI_AKTIF_DEFAULT) -> pd.DataFrame:
    engine = get_engine()
    if not db.table_exists(engine, db.t("data_manual")):
        return pd.DataFrame(columns=["prodi_id", "item_id", "baris_ke", "kolom", "tahun", "nilai",
                                      "link_bukti", "diisi_oleh", "updated_at"])
    return db.read_sql_retry(
        engine, f"SELECT * FROM `{db.t('data_manual')}` WHERE prodi_id = :prodi_id",
        label="load data_manual", params={"prodi_id": prodi_id},
    )


_SWITCH_KEY = "_akreditasi_switch_dokumen_to"


def consume_pending_switch() -> None:
    """Panggil SEBELUM merender widget st.radio(key="akreditasi_dokumen") di
    tiap entry point (dashboard_akreditasi.py / page_akreditasi.py) --
    Streamlit melarang mengubah session_state milik sebuah widget key SETELAH
    widget itu diinstansiasi di run yang sama, jadi tombol "Buka di LKPS" (lihat
    _render_cuplikan_lkps) menitip nilai di key sementara ini lalu rerun; nilai
    itu baru dipindah ke key asli "akreditasi_dokumen" di run berikutnya,
    sebelum widget-nya sendiri dibuat."""
    if _SWITCH_KEY in st.session_state:
        st.session_state["akreditasi_dokumen"] = st.session_state.pop(_SWITCH_KEY)


def ensure_ready() -> bool:
    """True kalau koneksi MySQL + tabel akreditasi_data_manual siap dipakai;
    kalau tidak, tampilkan pesan error/panduan migrasi lewat Streamlit dan
    return False (caller sebaiknya st.stop() setelah ini)."""
    try:
        engine = get_engine()
    except Exception as e:  # noqa: BLE001
        st.error(f"Gagal terhubung ke MySQL: {e}")
        st.info("Cek .env di root project (MYSQL_HOST/PORT/USER/PASSWORD/DB).")
        return False
    if not db.table_exists(engine, db.t("data_manual")):
        st.warning(
            "Tabel `akreditasi_data_manual` belum ada. Jalankan sekali dari terminal:\n\n"
            "```\ncd akreditasi\n..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_akreditasi.py\n```"
        )
        return False
    return True


def render_ringkasan_atas(df_manual: pd.DataFrame, item_ids: "set[str] | list[str] | None" = None) -> tuple[dict, set]:
    """`item_ids` membatasi item yang dihitung (default semua 49) -- dipakai
    untuk ringkasan per mode LED/LKPS, lihat render_tabs_led/render_tabs_lkps."""
    filled_ids = set(df_manual["item_id"].unique()) if len(df_manual) else set()
    ringkasan = ringkasan_status(item_ids=item_ids, terisi_ids=filled_ids)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total item", ringkasan["total"])
    c2.metric("🟢 Tersedia otomatis", ringkasan["tersedia_otomatis"])
    c3.metric("🟡🟠 Perlu input manual", f"{ringkasan['perlu_manual_terisi']}/{ringkasan['perlu_manual_total']} terisi")
    c4.metric("🔴 Belum tersedia", ringkasan["belum_tersedia"])
    st.progress(*teks_kelengkapan(ringkasan, "Kelengkapan keseluruhan"))
    return ringkasan, filled_ids


def teks_kelengkapan(ringkasan: dict, awalan: str) -> tuple[float, str]:
    """(persen, teks) progress kelengkapan -- dipakai halaman Akreditasi DAN
    kartu Profil supaya angkanya selalu sama persis."""
    pct = ringkasan["lengkap"] / ringkasan["total"] if ringkasan["total"] else 0
    teks = f"{awalan}: {ringkasan['lengkap']}/{ringkasan['total']} item ({pct * 100:.0f}%)"
    if ringkasan["narasi_total"]:
        teks += (f" · termasuk {ringkasan['narasi_terisi']}/{ringkasan['narasi_total']} "
                 "item narasi 📝")
    return pct, teks


def _render_item_form(engine, item: dict, df_manual: pd.DataFrame, filled_ids: set,
                       prodi_id: str = PRODI_AKTIF_DEFAULT,
                       pending_ekstraksi: "pd.DataFrame | None" = None,
                       diisi_oleh_terverifikasi: str | None = None) -> None:
    """Satu item = satu expander dengan form input manual (data_editor + simpan).
    Dipakai APA ADANYA oleh render_tabs_led (item narasi/D1-D3) dan
    render_tabs_lkps (item tabel Bagian 1-6) -- satu-satunya tempat form
    disimpan ke MySQL, lihat docstring modul poin 6 di registry_kebutuhan_data.

    `df_manual` diasumsikan SUDAH difilter ke satu prodi_id (lihat
    load_data_manual) -- `prodi_id` di sini dipakai eksplisit di
    DELETE/INSERT & key widget, supaya baris prodi lain tidak tertimpa &
    state data_editor tidak nyampur kalau nanti selector prodi (Bagian B)
    diaktifkan.

    `pending_ekstraksi` (Tahap 3, opsional -- default None = perilaku SAMA
    PERSIS spt sebelumnya, dipakai app akreditasi/ standalone) adalah hasil
    ekstraksi AI utk item ini yang BELUM dikonfirmasi user (kolom: baris_ke,
    nama_kolom, nilai, kutipan, nama_file, id, konflik) -- lihat
    ekstraksi_akreditasi.py. Kalau ada, ditampilkan sbg preview kuning
    "perlu diverifikasi" DI ATAS data_editor, pre-fill sel yang masih kosong
    di data_manual (TIDAK menimpa data yang sudah dikonfirmasi manual), dan
    kolom yang ada KONFLIK (beda nilai antar file) dibiarkan kosong di
    editor + ditampilkan semua opsinya supaya user pilih/edit sendiri --
    JANGAN pernah auto-pilih salah satu (lihat kebijakan Tahap 3 poin 3).
    `diisi_oleh_terverifikasi` = nama/email reviewer, ditulis ke kolom
    diisi_oleh SAAT user klik Simpan (bukan sebelumnya -- sebelum Simpan,
    data AI belum masuk akreditasi_data_manual sama sekali, lihat kebijakan
    registry_kebutuhan_data.py poin 7)."""
    item_id = item["id"]
    ada_data = item_id in filled_ids
    badge = badge_status(item_id, ada_data)
    is_narasi = is_narasi_penilaian(item)
    label = f"{badge} {item['nama']}"
    if item["tabel_lkps"]:
        label += f"  ·  Tabel LKPS {item['tabel_lkps']}"
    pending_item = (
        pending_ekstraksi[pending_ekstraksi["item_id"] == item_id]
        if pending_ekstraksi is not None and len(pending_ekstraksi) else None
    )
    ada_pending = pending_item is not None and len(pending_item)
    if ada_pending:
        label += "  ·  📝 Ada draft AI" if is_narasi else "  ·  🟡 Ada hasil ekstraksi AI"
    with st.expander(label):
        st.caption(item["deskripsi_singkat"])
        mcol1, mcol2 = st.columns(2)
        mcol1.markdown(f"**Sumber data:** {item['sumber_data']}")
        mcol2.markdown(f"**Status:** {STATUS_LABEL[item['status_ketersediaan']]}")

        # "belum_tersedia" = TIDAK ada form sama sekali, utk item jenis apa pun.
        # Item yang form-nya ditampilkan WAJIB berstatus perlu_input_manual,
        # supaya item yang sudah diisi selalu ikut dihitung di ringkasan_status.
        if item["status_ketersediaan"] == "belum_tersedia":
            st.info(
                "Belum ada pipeline/form untuk item ini. Sumber data seharusnya: "
                f"**{item['sumber_data']}**. Ubah status_ketersediaan di registry "
                "kalau sudah bisa diisi manual."
            )
            return

        if is_narasi:
            # Item narasi/penilaian (jenis_kendala == perlu_penyusunan_manusia) -- catatan
            # ini SELALU tampil, baik AI berhasil bikin draft dari dokumen yang diupload
            # ATAUPUN tidak ada draft sama sekali (beda dari item data: bukan soal akurasi
            # kutipan, tapi soal kesegaran/relevansi narasi dgn kondisi & evaluasi terkini).
            st.info(
                "📝 **Draft dari data yang diupload — perlu disesuaikan tim penyusun dengan "
                "kondisi & evaluasi TERKINI sebelum digunakan.** Ini bukan soal akurasi kutipan "
                "(beda dari item data), tapi soal kesegaran & relevansi narasinya."
            )

        sub = df_manual[df_manual["item_id"] == item_id]
        kolom = item["kolom_dibutuhkan"]
        if item["tipe"] == "narasi":
            existing = {r["kolom"]: r["nilai"] for _, r in sub[sub["baris_ke"] == 1].iterrows()}
            wide = pd.DataFrame([{k: existing.get(k, "") for k in kolom}])
        else:
            wide_rows: dict[int, dict] = {}
            for _, r in sub.iterrows():
                wide_rows.setdefault(int(r["baris_ke"]), {})[r["kolom"]] = r["nilai"] or ""
            if wide_rows:
                wide = pd.DataFrame([wide_rows[k] for k in sorted(wide_rows)])
                for k in kolom:
                    if k not in wide.columns:
                        wide[k] = ""
                wide = wide[kolom]
            else:
                wide = pd.DataFrame([{k: "" for k in kolom}])

        ekstraksi_ids_terpakai: list[int] = []
        if ada_pending:
            if is_narasi:
                st.markdown("##### 📝 Draft AI dari dokumen yang diupload")
                st.caption(
                    "Draft di bawah disintesis AI dari dokumen yang diupload -- BELUM tersimpan "
                    "sbg data resmi. Baca & sesuaikan isinya dgn kondisi terkini (bukan cuma cek "
                    "kutipan sumbernya) sebelum klik Simpan."
                )
            else:
                st.warning(
                    "🟡 **Hasil ekstraksi AI — perlu diverifikasi**\n\n"
                    "Nilai di bawah HASIL EKSTRAKSI AI dari file yang diupload, BELUM tersimpan "
                    "sbg data resmi. Cek kutipan sumbernya, edit tabel di bawah kalau perlu, lalu "
                    "klik Simpan untuk mengonfirmasi."
                )
            ekstraksi_ids_terpakai = [int(x) for x in pending_item["id"].tolist()]
            for (baris_ke, nama_kolom), grp in pending_item.groupby(["baris_ke", "nama_kolom"]):
                if nama_kolom not in kolom:
                    continue
                is_konflik = bool(grp["konflik"].iloc[0])
                baris_idx = int(baris_ke) - 1
                if is_konflik:
                    opsi_teks = "; ".join(
                        f"dari `{r['nama_file']}`: \"{r['nilai']}\"" for _, r in grp.iterrows()
                    )
                    st.warning(
                        f"⚠️ **{nama_kolom}** (baris {baris_ke}): {len(grp)} nilai BERBEDA "
                        f"ditemukan dari file berbeda -- {opsi_teks}. Pilih/edit manual di tabel "
                        "bawah (sengaja dikosongkan, tidak dipilihkan otomatis)."
                    )
                    continue
                r0 = grp.iloc[0]
                sudah_terisi_manual = (
                    baris_idx < len(wide) and str(wide.iloc[baris_idx].get(nama_kolom, "")).strip()
                )
                if sudah_terisi_manual:
                    st.caption(
                        f"💬 **{nama_kolom}** (baris {baris_ke}): AI menemukan \"{r0['nilai']}\" "
                        f"(dari `{r0['nama_file']}`) tapi kolom ini SUDAH ada data manual -- "
                        "data manual TIDAK ditimpa, cek tabel di bawah kalau mau ganti sendiri."
                    )
                    continue
                st.info(
                    f"**{nama_kolom}** (baris {baris_ke}): \"{r0['nilai']}\"\n\n"
                    f"📎 Sumber: `{r0['nama_file']}` — kutipan: _{r0['kutipan'] or '-'}_"
                )
                while len(wide) <= baris_idx:
                    wide.loc[len(wide)] = {k: "" for k in kolom}
                wide.at[baris_idx, nama_kolom] = r0["nilai"]

        edited = st.data_editor(
            wide, num_rows="dynamic", width="stretch", key=f"editor_{prodi_id}_{item_id}",
        )

        if st.button("💾 Simpan", key=f"save_{prodi_id}_{item_id}"):
            now = datetime.now()
            rows_to_insert = []
            for baris_ke, (_, row) in enumerate(edited.iterrows(), start=1):
                for k in kolom:
                    nilai = str(row.get(k, "") or "")
                    if not nilai:
                        continue
                    rows_to_insert.append({
                        "prodi_id": prodi_id, "item_id": item_id, "baris_ke": baris_ke, "kolom": k,
                        "tahun": None, "nilai": nilai, "link_bukti": None,
                        "diisi_oleh": diisi_oleh_terverifikasi, "updated_at": now,
                    })

            def _save():
                from sqlalchemy import text
                with engine.begin() as conn:
                    conn.execute(
                        text(f"DELETE FROM `{db.t('data_manual')}` WHERE prodi_id = :prodi_id AND item_id = :item_id"),
                        {"prodi_id": prodi_id, "item_id": item_id},
                    )
                    if rows_to_insert:
                        conn.execute(
                            text(
                                f"INSERT INTO `{db.t('data_manual')}` "
                                "(prodi_id, item_id, baris_ke, kolom, tahun, nilai, link_bukti, diisi_oleh, updated_at) "
                                "VALUES (:prodi_id, :item_id, :baris_ke, :kolom, :tahun, :nilai, :link_bukti, :diisi_oleh, :updated_at)"
                            ),
                            rows_to_insert,
                        )

            ok, _ = db.with_retry(_save, label=f"simpan {prodi_id}/{item_id}")
            if ok and ekstraksi_ids_terpakai:
                from ekstraksi_akreditasi import konfirmasi_ekstraksi
                konfirmasi_ekstraksi(prodi_id, item_id, ekstraksi_ids_terpakai)
            if ok:
                st.success("Tersimpan.")
                load_data_manual.clear()
                st.rerun()
            else:
                st.error("Gagal menyimpan -- cek koneksi MySQL.")


def _render_cuplikan_lkps(kriteria: str, filled_ids: set) -> None:
    """Subsection read-only di tab LED: cuplikan item LKPS ber-kriteria_led
    sama (evidence PPEPP) -- TIDAK ada data_editor/save di sini, cuma badge +
    status + tombol pindah ke mode LKPS. Lihat registry poin 6."""
    cuplikan = lkps_cuplikan_untuk_kriteria(kriteria)
    if not cuplikan:
        return
    st.markdown("**📎 Tabel LKPS terkait**")
    st.caption("Data diisi & dilihat lengkap di mode LKPS -- ditampilkan di sini sebagai cuplikan bukti evaluasi.")
    for item in cuplikan:
        badge = badge_status(item["id"], item["id"] in filled_ids)
        ccol1, ccol2 = st.columns([5, 1])
        ccol1.markdown(f"{badge} Tabel {item['tabel_lkps']} — {item['nama']}")
        if ccol2.button("🔗 Buka di LKPS", key=f"jump_lkps_{item['id']}"):
            st.session_state[_SWITCH_KEY] = "LKPS"
            st.rerun()


def render_tabs_led(engine, df_manual: pd.DataFrame, filled_ids: set,
                     prodi_id: str = PRODI_AKTIF_DEFAULT,
                     pending_ekstraksi: "pd.DataFrame | None" = None,
                     diisi_oleh_terverifikasi: str | None = None) -> None:
    grouped = led_items_by_kriteria()
    kriteria_dengan_item = [k for k in URUTAN_KRITERIA if grouped.get(k)]
    tab_labels = [LABEL_KRITERIA[k] for k in kriteria_dengan_item]
    tabs = st.tabs(tab_labels)

    for tab, kriteria in zip(tabs, kriteria_dengan_item):
        with tab:
            for item in grouped[kriteria]:
                _render_item_form(engine, item, df_manual, filled_ids, prodi_id,
                                   pending_ekstraksi, diisi_oleh_terverifikasi)
            if kriteria not in ("Umum", "D"):
                _render_cuplikan_lkps(kriteria, filled_ids)


def render_tabs_lkps(engine, df_manual: pd.DataFrame, filled_ids: set,
                      prodi_id: str = PRODI_AKTIF_DEFAULT,
                      pending_ekstraksi: "pd.DataFrame | None" = None,
                      diisi_oleh_terverifikasi: str | None = None) -> None:
    grouped = lkps_items_by_bagian()
    bagian_dengan_item = [b for b in URUTAN_BAGIAN_LKPS if grouped.get(b)]
    tab_labels = [LABEL_BAGIAN_LKPS[b] for b in bagian_dengan_item]
    tabs = st.tabs(tab_labels)

    for tab, bagian in zip(tabs, bagian_dengan_item):
        with tab:
            for item in grouped[bagian]:
                _render_item_form(engine, item, df_manual, filled_ids, prodi_id,
                                   pending_ekstraksi, diisi_oleh_terverifikasi)
