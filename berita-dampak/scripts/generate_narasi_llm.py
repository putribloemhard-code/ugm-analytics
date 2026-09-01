"""Generate narasi ringkasan/insight pakai Gemini API (LLM), simpan ke cache
MySQL (tabel berita_narasi_cache).

Dipanggil sebagai step di update_mingguan.py, SETELAH sync_mysql.py (supaya
angka yang dipakai sudah dari data MySQL terbaru). LLM di sini CUMA diminta
merangkai angka yang SUDAH dihitung pandas (lihat scripts/narasi_logic.py --
satu sumber kebenaran yang sama dipakai dashboard) jadi satu paragraf narasi
-- bukan diminta menghitung atau mengarang angka sendiri.

Cache ini hanya representatif untuk kondisi filter DEFAULT di dashboard
(semua tahun/tema/sumber/pilar/SDG). Begitu user mengubah filter, dashboard
otomatis balik pakai narasi template pandas (selalu akurat untuk filter
apa pun) -- lihat narasi_llm_atau_fallback() di dashboard_berita_dampak.py.

Kalau GEMINI_API_KEY belum diisi di .env, package google-genai belum
terinstall, atau panggilan API gagal (down/quota habis), script ini SELALU
skip dengan aman (exit 0) -- TIDAK PERNAH menggagalkan pipeline mingguan.
Dashboard tetap jalan normal pakai narasi template kalau cache kosong/stale.

Jalankan (dari folder berita-dampak):
  python scripts/generate_narasi_llm.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_engine  # noqa: E402
from narasi_logic import (  # noqa: E402
    generate_executive_summary,
    generate_impact_insight,
    generate_sdg_saja_summary,
    hitung_stats_pilar,
    hitung_stats_sdg_saja,
)

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")

MODEL = "gemini-flash-lite-latest"

SYSTEM_PROMPT = (
    "Kamu adalah asisten penulis untuk dashboard analitik dampak universitas. "
    "Tugasmu HANYA merangkai angka-angka yang diberikan menjadi SATU paragraf "
    "narasi Bahasa Indonesia yang enak dibaca dan profesional, gaya laporan "
    "eksekutif. ATURAN KETAT: jangan mengubah, membulatkan, atau mengarang "
    "angka apa pun di luar yang diberikan; jangan tambahkan klaim yang tidak "
    "didukung angka yang diberikan; jangan pakai markdown/heading/bullet, "
    "cukup satu paragraf teks biasa, 3-5 kalimat."
)


def rangkai_narasi(client, label: str, fallback_text: str, data_ringkas: str) -> str:
    """Minta Gemini merangkai `data_ringkas` jadi narasi; kalau gagal apa pun,
    balikin `fallback_text` (template pandas) supaya cache tetap terisi valid."""
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=(
                f"{SYSTEM_PROMPT}\n\nKonteks: {label}.\n\n"
                f"Data (semua angka WAJIB dipakai apa adanya, jangan diubah):\n{data_ringkas}\n\n"
                f"Contoh gaya kalimat yang diharapkan (JANGAN disalin persis, "
                f"cuma referensi nada/gaya):\n{fallback_text}"
            ),
        )
        teks = (resp.text or "").strip()
        return teks if teks else fallback_text
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] Gagal generate narasi LLM utk '{label}': {e}")
        return fallback_text


def main() -> None:
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("[SKIP] GEMINI_API_KEY belum diset di .env -- lewati generate narasi LLM "
              "(dashboard tetap jalan pakai narasi template pandas).")
        return

    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[SKIP] Env MySQL belum lengkap ({', '.join(missing)}).")
        return

    try:
        from google import genai
    except ImportError:
        print("[SKIP] Package google-genai belum terinstall (`pip install google-genai`).")
        return

    engine = get_engine()  # pool_pre_ping + pool_recycle, lihat scripts/db.py

    try:
        berita = pd.read_sql("SELECT * FROM berita_berita", engine)
        bk = pd.read_sql("SELECT * FROM berita_berita_kepmen_all", engine)
        bs = pd.read_sql("SELECT * FROM berita_berita_sdg_all", engine)
        sitemap = pd.read_sql("SELECT url, lastmod FROM berita_sitemap", engine)
        ss = pd.read_sql("SELECT * FROM berita_sitemap_sdg", engine)
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] Gagal baca data dari MySQL: {e}")
        return

    if not len(berita):
        print("[SKIP] Tabel berita_berita kosong.")
        return

    # Rentang tahun default HARUS sama persis dengan tahun_opsi dashboard
    # (dashboard_berita_dampak.py: tahun_opsi = sorted(berita["tanggal"]...)),
    # supaya narasi cache ini cocok dgn posisi slider default di sidebar.
    tahun_opsi = sorted(berita["tanggal"].dropna().str[:4].unique())
    if not tahun_opsi:
        print("[SKIP] Tidak ada tanggal valid di tabel berita_berita.")
        return
    tahun_awal, tahun_akhir = tahun_opsi[0], tahun_opsi[-1]

    b = berita.copy()
    b["tahun"] = b["tanggal"].str[:4]
    b = b[b["tahun"].between(tahun_awal, tahun_akhir) & b["sumber"].isin(["sitemap", "rss"])]
    t = bk[bk["dampak"].isin(["Lingkungan", "Ekonomi", "Sosial"])]
    t = t[t["url"].isin(set(b["url"]))]
    b_t = b.merge(t, on="url", how="inner")
    urls_t = set(b_t["url"])
    bk_f = t[t["url"].isin(urls_t)].copy()
    bs_f = bs[bs["url"].isin(urls_t)].copy()

    client = genai.Client(api_key=gemini_key)
    hasil: dict[str, str] = {}

    # 1-2. Ringkasan eksekutif (2 mode: Berdampak x SDGs, Berdampak)
    for cache_key, mode_val in [
        ("exec_berdampak_sdgs", "Berdampak × SDGs"),
        ("exec_berdampak", "Berdampak"),
    ]:
        stats = generate_executive_summary(b, t, bs_f, mode_val, tahun_awal, tahun_akhir)
        if stats["total_berita"] == 0:
            continue
        data_ringkas = (
            f"- Total berita dampak: {stats['total_berita']:,}\n"
            f"- Dampak dengan pertumbuhan tercepat: {stats['pilar_top']} "
            f"({stats['pilar_top_naik']:+d} berita dari {tahun_awal} ke {tahun_akhir})\n"
            f"- {stats['topik_top_kind_label']}: {stats['topik_top_label']}\n"
            f"- Berita pada tahun terbaru ({tahun_akhir}): {stats['berita_tahun_ini']:,}\n"
            f"- Rentang tahun data: {tahun_awal}–{tahun_akhir}"
        )
        hasil[cache_key] = rangkai_narasi(
            client, f"Ringkasan eksekutif mode {mode_val}", stats["narasi"], data_ringkas,
        )
        print(f"  [OK] {cache_key}")

    # 3-5. Insight per dampak (mode Berdampak x SDGs, paling lengkap)
    for pilar in ["Lingkungan", "Ekonomi", "Sosial"]:
        selected_t = t[t["dampak"] == pilar].copy()
        selected_news = b[b["url"].isin(set(selected_t["url"]))].copy()
        if not len(selected_news):
            continue
        selected_news["tahun"] = selected_news["tanggal"].str[:4]
        bk_f_pilar = bk_f[bk_f["dampak"] == pilar].copy()
        bs_f_pilar = bs_f[bs_f["url"].isin(set(bk_f_pilar["url"]))].copy()
        stats = hitung_stats_pilar(
            selected_news, pilar, tahun_awal, tahun_akhir, selected_t, "Berdampak × SDGs", bs_f_pilar,
        )
        if stats is None:
            continue
        fallback = generate_impact_insight(
            selected_news, pilar, tahun_awal, tahun_akhir, selected_t, "Berdampak × SDGs", bs_f_pilar,
        )
        data_ringkas = (
            f"- Dampak: {pilar}\n"
            f"- Total berita unik dampak ini: {stats['total_berita']:,} ({tahun_awal}–{tahun_akhir})\n"
            f"- Tren volume berita: {stats['trend_text']}\n"
            f"- Tema resmi Kepmen paling dominan di dampak ini: {stats['tema_display']} "
            f"dengan {stats['tema_jumlah']:,} berita\n"
            + (f"- Indikator resmi Kepmen terkait tema itu: \"{stats['indikator_resmi']}\"\n"
               if stats['indikator_resmi'] else "")
            + f"- Cakupan tema: {stats['tema_aktif']} dari {stats['total_tema_pilar']} tema resmi "
              f"Kepmen pada dampak ini sudah terekam aktivitasnya\n"
            + (f"- SDG paling banyak disentuh pada dampak ini: {stats['top_sdg_label']} "
               f"(dari total {stats['n_sdg']} klaster SDG yang tersentuh)"
               if stats['top_sdg_label'] else "")
        )
        cache_key = f"pilar_{pilar.lower()}"
        hasil[cache_key] = rangkai_narasi(client, f"Insight dampak {pilar}", fallback, data_ringkas)
        print(f"  [OK] {cache_key}")

    # 6. Mode "SDGs saja" -- rentang tahun_awal/tahun_akhir SAMA dgn di atas
    # (satu slider dipakai bersama semua mode di dashboard).
    sitemap["tahun"] = sitemap["lastmod"].str[:4]
    sm = sitemap[sitemap["tahun"].between(tahun_awal, tahun_akhir)].copy()
    ss_f = ss[ss["url"].isin(set(sm["url"]))]
    sdg_stats = hitung_stats_sdg_saja(sm, ss_f, tahun_awal, tahun_akhir)
    if sdg_stats is not None:
        fallback_sdg = generate_sdg_saja_summary(sm, ss_f, tahun_awal, tahun_akhir)
        cakupan_pct = 100 * sdg_stats["n_tag"] / sdg_stats["n_url"]
        data_ringkas = (
            f"- Total URL sitemap dalam rentang tahun: {sdg_stats['n_url']:,}\n"
            f"- Berita bertanda minimal 1 SDG: {sdg_stats['n_tag']:,} ({cakupan_pct:.1f}% dari total URL)\n"
            f"- SDG paling banyak disentuh: {sdg_stats['top_sdg_label']} "
            f"dengan {sdg_stats['top_sdg_n']:,} berita\n"
            f"- Tren SDG teratas itu: {sdg_stats['delta_text']}\n"
            f"- Rentang tahun: {tahun_awal}–{tahun_akhir}"
        )
        hasil["sdg_saja"] = rangkai_narasi(client, "Ringkasan mode SDGs saja", fallback_sdg, data_ringkas)
        print("  [OK] sdg_saja")

    if not hasil:
        print("[SKIP] Tidak ada narasi yang berhasil digenerate.")
        return

    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS berita_narasi_cache (
                cache_key VARCHAR(64) PRIMARY KEY,
                narasi TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            )
            """
        ))
        for key, narasi in hasil.items():
            conn.execute(
                text(
                    """
                    INSERT INTO berita_narasi_cache (cache_key, narasi)
                    VALUES (:key, :narasi)
                    ON DUPLICATE KEY UPDATE narasi = :narasi
                    """
                ),
                {"key": key, "narasi": narasi},
            )
    print(f"SELESAI. {len(hasil)} narasi tersimpan ke berita_narasi_cache.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        # Step ini TIDAK BOLEH menggagalkan pipeline mingguan -- error tak
        # terduga cukup dilog; dashboard otomatis fallback ke narasi template.
        print(f"[ERROR] generate_narasi_llm gagal tak terduga: {e}")
