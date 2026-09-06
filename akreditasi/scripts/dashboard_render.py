"""Komponen UI Streamlit yang dipakai BARENG oleh dua entry point:
- akreditasi/dashboard_akreditasi.py (app berdiri sendiri)
- berita-dampak/page_akreditasi.py (menu "Akreditasi" di dashboard berita-dampak)

Diekstrak ke sini supaya form input manual, badge status, dan generator
dokumen SATU sumber kebenaran -- data yang diisi lewat salah satu entry
point otomatis muncul di entry point lainnya (sama-sama baca/tulis tabel
MySQL akreditasi_data_manual).
"""

import sys
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
    led_items_by_kriteria,
    lkps_cuplikan_untuk_kriteria,
    lkps_items_by_bagian,
    ringkasan_status,
)


@st.cache_resource
def get_engine():
    return db.get_engine()


@st.cache_data(ttl=60)
def load_data_manual() -> pd.DataFrame:
    engine = get_engine()
    if not db.table_exists(engine, db.t("data_manual")):
        return pd.DataFrame(columns=["item_id", "baris_ke", "kolom", "tahun", "nilai", "link_bukti",
                                      "diisi_oleh", "updated_at"])
    return db.read_sql_retry(engine, f"SELECT * FROM `{db.t('data_manual')}`", label="load data_manual")


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
    c1.metric("Total item data", ringkasan["total"])
    c2.metric("🟢 Tersedia otomatis", ringkasan["tersedia_otomatis"])
    c3.metric("🟡🟠 Perlu input manual", f"{ringkasan['perlu_manual_terisi']}/{ringkasan['perlu_manual_total']} terisi")
    c4.metric("🔴 Belum tersedia", ringkasan["belum_tersedia"])
    pct = ringkasan["lengkap"] / ringkasan["total"] if ringkasan["total"] else 0
    st.progress(pct, text=f"Kelengkapan keseluruhan: {ringkasan['lengkap']}/{ringkasan['total']} ({pct * 100:.0f}%)")
    return ringkasan, filled_ids


def _render_item_form(engine, item: dict, df_manual: pd.DataFrame, filled_ids: set) -> None:
    """Satu item = satu expander dengan form input manual (data_editor + simpan).
    Dipakai APA ADANYA oleh render_tabs_led (item narasi/D1-D3) dan
    render_tabs_lkps (item tabel Bagian 1-6) -- satu-satunya tempat form
    disimpan ke MySQL, lihat docstring modul poin 6 di registry_kebutuhan_data."""
    item_id = item["id"]
    ada_data = item_id in filled_ids
    badge = badge_status(item_id, ada_data)
    label = f"{badge} {item['nama']}"
    if item["tabel_lkps"]:
        label += f"  ·  Tabel LKPS {item['tabel_lkps']}"
    with st.expander(label):
        st.caption(item["deskripsi_singkat"])
        mcol1, mcol2 = st.columns(2)
        mcol1.markdown(f"**Sumber data:** {item['sumber_data']}")
        mcol2.markdown(f"**Status:** {STATUS_LABEL[item['status_ketersediaan']]}")

        if item["status_ketersediaan"] == "belum_tersedia":
            st.info(
                "Belum ada pipeline/form untuk item ini. Sumber data seharusnya: "
                f"**{item['sumber_data']}**. Ubah status_ketersediaan di registry "
                "kalau sudah bisa diisi manual."
            )
            return

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

        edited = st.data_editor(
            wide, num_rows="dynamic", width="stretch", key=f"editor_{item_id}",
        )

        if st.button("💾 Simpan", key=f"save_{item_id}"):
            now = datetime.now()
            rows_to_insert = []
            for baris_ke, (_, row) in enumerate(edited.iterrows(), start=1):
                for k in kolom:
                    nilai = str(row.get(k, "") or "")
                    if not nilai:
                        continue
                    rows_to_insert.append({
                        "item_id": item_id, "baris_ke": baris_ke, "kolom": k,
                        "tahun": None, "nilai": nilai, "link_bukti": None,
                        "diisi_oleh": None, "updated_at": now,
                    })

            def _save():
                from sqlalchemy import text
                with engine.begin() as conn:
                    conn.execute(
                        text(f"DELETE FROM `{db.t('data_manual')}` WHERE item_id = :item_id"),
                        {"item_id": item_id},
                    )
                    if rows_to_insert:
                        conn.execute(
                            text(
                                f"INSERT INTO `{db.t('data_manual')}` "
                                "(item_id, baris_ke, kolom, tahun, nilai, link_bukti, diisi_oleh, updated_at) "
                                "VALUES (:item_id, :baris_ke, :kolom, :tahun, :nilai, :link_bukti, :diisi_oleh, :updated_at)"
                            ),
                            rows_to_insert,
                        )

            ok, _ = db.with_retry(_save, label=f"simpan {item_id}")
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


def render_tabs_led(engine, df_manual: pd.DataFrame, filled_ids: set) -> None:
    grouped = led_items_by_kriteria()
    kriteria_dengan_item = [k for k in URUTAN_KRITERIA if grouped.get(k)]
    tab_labels = [LABEL_KRITERIA[k] for k in kriteria_dengan_item]
    tabs = st.tabs(tab_labels)

    for tab, kriteria in zip(tabs, kriteria_dengan_item):
        with tab:
            for item in grouped[kriteria]:
                _render_item_form(engine, item, df_manual, filled_ids)
            if kriteria not in ("Umum", "D"):
                _render_cuplikan_lkps(kriteria, filled_ids)


def render_tabs_lkps(engine, df_manual: pd.DataFrame, filled_ids: set) -> None:
    grouped = lkps_items_by_bagian()
    bagian_dengan_item = [b for b in URUTAN_BAGIAN_LKPS if grouped.get(b)]
    tab_labels = [LABEL_BAGIAN_LKPS[b] for b in bagian_dengan_item]
    tabs = st.tabs(tab_labels)

    for tab, bagian in zip(tabs, bagian_dengan_item):
        with tab:
            for item in grouped[bagian]:
                _render_item_form(engine, item, df_manual, filled_ids)
