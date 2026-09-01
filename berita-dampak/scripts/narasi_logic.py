"""Logika narasi dinamis (template pandas) -- dipakai dashboard DAN
scripts/generate_narasi_llm.py.

Satu sumber kebenaran: dashboard_berita_dampak.py dan generate_narasi_llm.py
sama-sama import fungsi di sini, supaya angka yang dikirim ke LLM (buat
dirangkai jadi kalimat) selalu identik dengan angka yang dipakai template
fallback saat LLM gagal/belum jalan. Tidak ada dependency Streamlit di sini
(cuma pandas) supaya bisa dipanggil dari script biasa di luar `streamlit run`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Robust baik saat diimport sebagai `scripts.narasi_logic` (dari dashboard,
# root sys.path = berita-dampak/) maupun sebagai `narasi_logic` polos (dari
# script sibling di scripts/, pola sys.path yang sama dipakai tag_kepmen_all.py dkk).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kepmen_sdg import LABEL_TOPIC_ALL as LABEL_TOPIC
from kepmen_sdg import TOPIK_KEPMEN_ALL, sdg_label


def _top_tied(counts: pd.Series) -> tuple[list, int]:
    """Semua index yang nilainya = nilai maksimum -- kalau ada seri/tie
    (mis. dua SDG sama-sama jadi yang terbanyak), JANGAN cuma ambil satu
    secara sembarang (bekas bug: .sort_values().index[0] diam-diam
    membuang tema/SDG lain yang sama tingginya). Return ([], 0) kalau
    `counts` kosong."""
    if not len(counts):
        return [], 0
    max_val = int(counts.max())
    tied = [idx for idx, v in counts.items() if v == max_val]
    return tied, max_val


def _join_labels(labels: list[str]) -> str:
    """Gabung label jadi kalimat Indonesia wajar: 'A', 'A dan B', 'A, B, dan C'."""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} dan {labels[1]}"
    return f"{', '.join(labels[:-1])}, dan {labels[-1]}"


def hitung_stats_pilar(
    df: pd.DataFrame,
    pilar: str,
    tahun_awal: str,
    tahun_akhir: str,
    selected_t: pd.DataFrame,
    mode: str,
    sdg_df: pd.DataFrame | None = None,
) -> dict | None:
    """Angka mentah di balik generate_impact_insight -- dipisah supaya bisa
    dipakai ulang oleh generate_narasi_llm.py (data lengkap yang dikirim ke
    LLM), bukan cuma kalimat jadinya. None kalau df kosong (belum ada data)."""
    if df.empty:
        return None

    total_berita = int(df["url"].nunique())
    tahun_df = df.groupby("tahun")["url"].nunique().reset_index(name="jumlah")
    if len(tahun_df) > 1:
        awal = int(tahun_df.iloc[0]["jumlah"])
        akhir = int(tahun_df.iloc[-1]["jumlah"])
        y_awal, y_akhir = tahun_df.iloc[0]["tahun"], tahun_df.iloc[-1]["tahun"]
        if awal >= 5:
            # Persentase hanya bermakna kalau basis awalnya cukup besar --
            # basis <5 berita bisa menghasilkan persentase ratusan/ribuan % yang menyesatkan.
            delta = (akhir - awal) / awal * 100
            trend_text = f"dengan tren {akhir - awal:+d} berita dari {y_awal} ke {y_akhir} ({delta:+.1f}%)"
        elif akhir != awal:
            trend_text = f"meningkat dari {awal} menjadi {akhir} berita antara {y_awal} dan {y_akhir}" if akhir > awal else f"menurun dari {awal} menjadi {akhir} berita antara {y_awal} dan {y_akhir}"
        else:
            trend_text = f"dengan konsistensi {akhir} berita antara {y_awal} dan {y_akhir}"
    else:
        trend_text = "dengan konsistensi volume yang stabil di rentang waktu tersebut"

    tema_counts = selected_t.groupby("topik")["url"].nunique()
    tied_topik, tema_jumlah = _top_tied(tema_counts)
    tema_jamak = len(tied_topik) > 1
    if tied_topik:
        tema_labels = []
        for topik_id in tied_topik:
            label_x = LABEL_TOPIC.get(topik_id, topik_id)
            meta_x = TOPIK_KEPMEN_ALL.get(topik_id, {})
            nama_x = meta_x.get("topik_kepmen", label_x)
            tema_labels.append(f"{nama_x} ({label_x})" if nama_x != label_x else label_x)
        tema_display = _join_labels(tema_labels)
        # Indikator resmi cuma ditampilkan kalau satu tema teratas (jelas
        # tunggal) -- ambigu kalau ada beberapa tema seri, masing-masing
        # punya indikator resmi sendiri, jangan cuma tampilkan salah satu.
        indikator_resmi = (
            TOPIK_KEPMEN_ALL.get(tied_topik[0], {}).get("indikator", "") if len(tied_topik) == 1 else ""
        )
    else:
        tema_display, indikator_resmi = "tema utama", ""

    indikator_text = (
        f" Tema ini searah dengan indikator resmi Kepmen 361/M/KEP/2025: “{indikator_resmi}”."
        if indikator_resmi else ""
    )

    total_tema_pilar = sum(1 for v in TOPIK_KEPMEN_ALL.values() if v["dampak"] == pilar)
    tema_aktif = selected_t["topik"].nunique() if len(selected_t) else 0
    cakupan_text = (
        f"Dari {total_tema_pilar} tema resmi Kepmen pada dampak ini, {tema_aktif} di antaranya "
        f"sudah terekam aktivitasnya dalam pemberitaan."
    )

    n_sdg, top_sdg_label = None, None
    sdg_text = ""
    if mode != "Berdampak" and sdg_df is not None and len(sdg_df):
        n_sdg = int(sdg_df["sdg"].nunique())
        tied_sdg, _sdg_top_n = _top_tied(sdg_df.groupby("sdg")["url"].nunique())
        top_sdg_label = _join_labels([sdg_label(int(s)) for s in tied_sdg])
        kata_kerja_sdg = "sebagai yang paling banyak disentuh" if len(tied_sdg) == 1 else "sama-sama sebagai yang paling banyak disentuh"
        sdg_text = (
            f" Aktivitas pada dampak ini turut menyentuh {n_sdg} klaster SDG, dengan {top_sdg_label} "
            f"{kata_kerja_sdg}."
        )

    return {
        "pilar": pilar,
        "total_berita": total_berita,
        "trend_text": trend_text,
        "tema_display": tema_display,
        "tema_jumlah": tema_jumlah,
        "tema_jamak": tema_jamak,
        "indikator_resmi": indikator_resmi,
        "indikator_text": indikator_text,
        "total_tema_pilar": total_tema_pilar,
        "tema_aktif": tema_aktif,
        "cakupan_text": cakupan_text,
        "n_sdg": n_sdg,
        "top_sdg_label": top_sdg_label,
        "sdg_text": sdg_text,
    }


PILAR_INTRO = {
    "Ekonomi": "kinerja program, kolaborasi riset, serta penguatan ekosistem ekonomi berbasis inovasi",
    "Sosial": "peningkatan akses, kesejahteraan, edukasi, dan pemberdayaan masyarakat",
    "Lingkungan": "pengelolaan lingkungan, keberlanjutan, dan adaptasi ekosistem alam",
}
PILAR_LEAD = {
    "Ekonomi": "UGM menunjukkan kinerja ekonomi yang konsisten dan terukur",
    "Sosial": "UGM memperlihatkan kontribusi sosial yang luas dan berdampak nyata",
    "Lingkungan": "UGM menegaskan komitmen lingkungan yang kuat dalam agenda keberlanjutan",
}
PILAR_PENUTUP = {
    "Ekonomi": "UGM berfungsi sebagai enabler bagi penguatan kewirausahaan, hilirisasi riset, "
               "dan kolaborasi ekonomi berbasis inovasi kampus",
    "Sosial": "UGM berfungsi sebagai enabler pemberdayaan masyarakat dan perluasan akses "
              "pendidikan yang inklusif",
    "Lingkungan": "UGM berfungsi sebagai enabler transisi menuju kampus dan masyarakat yang "
                  "berkelanjutan",
}


def generate_impact_insight(
    df: pd.DataFrame,
    pilar: str,
    tahun_awal: str,
    tahun_akhir: str,
    selected_t: pd.DataFrame,
    mode: str,
    sdg_df: pd.DataFrame | None = None,
) -> str:
    """Narasi dinamis pilar -- dihitung ulang tiap render dari data ter-filter.

    Bukan animasi: tiap dashboard dimuat ulang (mis. setelah update berita
    mingguan menambah data baru), angka & kalimat di sini otomatis mengikuti.
    """
    s = hitung_stats_pilar(df, pilar, tahun_awal, tahun_akhir, selected_t, mode, sdg_df)
    if s is None:
        return f"Belum ada data untuk dampak {pilar} pada rentang {tahun_awal}–{tahun_akhir}."

    kata_tema = "menjadi tema-tema paling dominan" if s["tema_jamak"] else "menjadi tema paling dominan"
    return (
        f"{PILAR_LEAD[pilar]} pada dampak {pilar}. Dalam rentang {tahun_awal}–{tahun_akhir}, terdapat {s['total_berita']:,} berita unik yang mencerminkan "
        f"{PILAR_INTRO[pilar]}. {s['tema_display']} {kata_tema} dengan {s['tema_jumlah']:,} berita, {s['trend_text']}.{s['indikator_text']} "
        f"{s['cakupan_text']}{s['sdg_text']} Kondisi ini menunjukkan bahwa fokus narasi media dan program akademik UGM secara konsisten "
        f"bergerak pada isu yang memberi dampak nyata, di mana {PILAR_PENUTUP[pilar]}."
    )


def generate_executive_summary(
    b: pd.DataFrame,
    t: pd.DataFrame,
    bs_f: pd.DataFrame,
    mode: str,
    tahun_awal: str,
    tahun_akhir: str,
) -> dict:
    """Ringkasan naratif lintas-pilar untuk bagian paling atas dashboard.

    Sama seperti generate_impact_insight: dihitung ulang dari data ter-filter
    saat render, jadi otomatis ter-update begitu ada berita baru masuk.
    """
    bt = b.merge(t, on="url", how="inner")
    total_berita = int(bt["url"].nunique())
    if total_berita == 0:
        return {
            "total_berita": 0,
            "pilar_top": "-",
            "pilar_top_naik": 0,
            "pilar_top_pct": None,
            "topik_top_label": "-",
            "topik_top_short": "-",
            "topik_top_kind_label": "SDG terbanyak",
            "berita_tahun_ini": 0,
            "narasi": f"Belum ada data pada rentang {tahun_awal}–{tahun_akhir} untuk filter ini.",
        }

    # Pilar "pertumbuhan tertinggi" dipilih dari kenaikan ABSOLUT (bukan %) --
    # basis awal yang sangat kecil (mis. 2 berita) bisa membuat persentase
    # meledak jadi ribuan % dan menyesatkan pembaca laporan. Persentase cuma
    # ditampilkan kalau basis awalnya cukup besar (>=5) supaya bermakna.
    pilar_tahun = bt.groupby(["dampak", "tahun"])["url"].nunique().reset_index(name="jumlah")
    pilar_top, pilar_top_naik, pilar_top_pct = "-", None, None
    for pilar in ["Lingkungan", "Ekonomi", "Sosial"]:
        sub = pilar_tahun[pilar_tahun["dampak"] == pilar].sort_values("tahun")
        if len(sub) > 1:
            awal, akhir = int(sub.iloc[0]["jumlah"]), int(sub.iloc[-1]["jumlah"])
            naik = akhir - awal
            pct = (naik / awal * 100) if awal >= 5 else None
        else:
            naik, pct = 0, None
        if pilar_top_naik is None or naik > pilar_top_naik:
            pilar_top, pilar_top_naik, pilar_top_pct = pilar, naik, pct
    pilar_top_naik = pilar_top_naik or 0

    if mode != "Berdampak" and len(bs_f):
        tied_sdg, topik_top_n = _top_tied(bs_f.groupby("sdg")["url"].nunique())
        tied_sdg = [int(s) for s in tied_sdg]
        topik_top_label = _join_labels([sdg_label(s) for s in tied_sdg]) if tied_sdg else "-"
        topik_top_short = " & ".join(f"SDG {s}" for s in tied_sdg) if tied_sdg else "-"
        topik_top_kind_label = "SDG terbanyak"
        topik_kind = "SDG" if len(tied_sdg) == 1 else "SDG (seri)"
    else:
        tied_tema, topik_top_n = _top_tied(t.groupby("topik_kepmen")["url"].nunique())
        topik_top_label = _join_labels(tied_tema) if tied_tema else "-"
        topik_top_short = " & ".join(tied_tema) if tied_tema else "-"
        topik_top_kind_label = "Tema Kepmen terbanyak"
        topik_kind = "tema resmi Kepmen" if len(tied_tema) == 1 else "tema resmi Kepmen (seri)"

    berita_tahun_ini = int(bt[bt["tahun"] == tahun_akhir]["url"].nunique())
    if pilar_top_pct is not None:
        delta_text = f"tumbuh {pilar_top_pct:+.1f}% ({pilar_top_naik:+d} berita) dari {tahun_awal} ke {tahun_akhir}"
    elif pilar_top_naik:
        delta_text = f"bertambah {pilar_top_naik} berita dari {tahun_awal} ke {tahun_akhir}"
    else:
        delta_text = "menunjukkan volume pemberitaan yang stabil"

    narasi = (
        f"Sepanjang {tahun_awal}–{tahun_akhir}, UGM mencatat {total_berita:,} berita dampak yang tersebar di tiga dampak "
        f"Lingkungan, Ekonomi, dan Sosial. Dampak {pilar_top} mencatat pertumbuhan tercepat, {delta_text}. "
        f"Pada sisi capaian resmi, {topik_top_label} menjadi {topik_kind} yang paling banyak disentuh dengan {topik_top_n:,} berita. "
        f"Di tahun terbaru pada rentang ini ({tahun_akhir}), tercatat {berita_tahun_ini:,} berita dampak — mencerminkan "
        f"konsistensi UGM menjalankan tridarma yang memberi dampak nyata bagi masyarakat, ekonomi, dan lingkungan."
    )

    return {
        "total_berita": total_berita,
        "pilar_top": pilar_top,
        "pilar_top_naik": pilar_top_naik,
        "pilar_top_pct": pilar_top_pct,
        "topik_top_label": topik_top_label,
        "topik_top_short": topik_top_short,
        "topik_top_kind_label": topik_top_kind_label,
        "berita_tahun_ini": berita_tahun_ini,
        "narasi": narasi,
    }


def hitung_stats_sdg_saja(
    sm: pd.DataFrame,
    ss_f: pd.DataFrame,
    tahun_awal: str,
    tahun_akhir: str,
) -> dict | None:
    """Angka mentah di balik generate_sdg_saja_summary -- dipisah supaya bisa
    dipakai ulang oleh generate_narasi_llm.py. None kalau belum ada data."""
    n_url = len(sm)
    n_tag = ss_f["url"].nunique()
    if not n_url or not n_tag:
        return None

    tied_sdg, top_sdg_n = _top_tied(ss_f.groupby("sdg")["url"].nunique())
    tied_sdg = [int(s) for s in tied_sdg]
    # Label lengkap sudah termasuk "SDG n — Nama" per SDG, digabung "dan"/koma
    # kalau ada beberapa yang seri di angka tertinggi -- JANGAN cuma tampilkan
    # satu secara sembarang.
    top_sdg_label = _join_labels([sdg_label(s) for s in tied_sdg]) if tied_sdg else "-"

    tren_top = (
        ss_f[ss_f["sdg"].isin(tied_sdg)]
        .merge(sm[["url", "tahun"]], on="url", how="left")
        .drop_duplicates(subset=["url"])
        .groupby("tahun")["url"].nunique().sort_index()
    )
    if len(tren_top) > 1:
        delta_top = int(tren_top.iloc[-1]) - int(tren_top.iloc[0])
        delta_text = f"berubah {delta_top:+d} berita dari {tahun_awal} ke {tahun_akhir}"
    else:
        delta_text = "menunjukkan volume pemberitaan yang stabil"

    return {
        "n_url": n_url,
        "n_tag": n_tag,
        "top_sdg": tied_sdg,
        "top_sdg_n": top_sdg_n,
        "top_sdg_label": top_sdg_label,
        "delta_text": delta_text,
    }


def generate_sdg_saja_summary(
    sm: pd.DataFrame,
    ss_f: pd.DataFrame,
    tahun_awal: str,
    tahun_akhir: str,
) -> str:
    """Narasi mode 'SDGs saja' (mapping langsung seluruh sitemap ke SDG,
    tanpa tema dampak Kepmen). sm = sitemap ter-filter tahun, ss_f = sitemap_sdg
    ter-filter SDG + tahun."""
    s = hitung_stats_sdg_saja(sm, ss_f, tahun_awal, tahun_akhir)
    if s is None:
        return f"Belum ada data SDG pada rentang {tahun_awal}–{tahun_akhir} untuk filter ini."

    kata_sdg = "SDG paling banyak disentuh adalah" if len(s["top_sdg"]) == 1 else "SDG paling banyak disentuh (sama tinggi) adalah"
    return (
        f"Sepanjang {tahun_awal}–{tahun_akhir}, dari {s['n_url']:,} URL berita UGM (seluruh sitemap), "
        f"{s['n_tag']:,} ({100 * s['n_tag'] / s['n_url']:.1f}%) teridentifikasi menyentuh minimal satu SDG "
        f"(bisa lebih dari satu SDG sekaligus). {kata_sdg} {s['top_sdg_label']} "
        f"dengan {s['top_sdg_n']:,} berita, {s['delta_text']}."
    )
