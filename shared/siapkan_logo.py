"""Siapkan file logo untuk dashboard: rapikan gambar mentah lalu simpan ke
shared/assets/logo/ dengan nama yang dipakai kode.

CARA PAKAI (dari folder root project, D:\\ugm-analytics):

    venv\\Scripts\\python.exe shared\\siapkan_logo.py sumber\\picture\\dampak.png dampak.png

Argumen: <file mentah> <nama file tujuan di shared/assets/logo/>
Opsional: --ukuran 96   (default 96 px; logo badge UGM dipakai 128)

Yang dikerjakan otomatis:
1. Buang pola kotak-kotak semi-transparan (watermark pratinjau situs ikon) --
   terdeteksi kalau BANYAK piksel ber-alpha sangat rendah.
2. Latar putih penuh (PNG tanpa transparansi) dijadikan transparan.
3. Potong margin kosong, jadikan bujur sangkar, perkecil ke ukuran target.

CATATAN: logo BERWARNA GELAP tetap terbaca karena kode menampilkannya di atas
kotak putih kecil ("chip"), baik di sidebar, kartu Beranda, maupun judul
halaman. Logo berwarna terang/putih TIDAK akan terlihat di chip putih itu.
"""

import argparse
from pathlib import Path

from PIL import Image

DIR_LOGO = Path(__file__).resolve().parent / "assets" / "logo"
AMBANG_WATERMARK = 32       # alpha <= ini dianggap pola watermark
MIN_PIKSEL_WATERMARK = 20000  # baru dianggap watermark kalau sebanyak ini
# Latar "putih" sering tidak putih bersih (home.png: sudutnya 238, bukan 255),
# jadi ambangnya sengaja agak longgar.
AMBANG_PUTIH = 232


def siapkan(src: Path, nama_tujuan: str, ukuran: int = 96) -> Path:
    im = Image.open(src).convert("RGBA")
    alpha = im.getchannel("A")

    if sum(alpha.histogram()[1:AMBANG_WATERMARK + 1]) >= MIN_PIKSEL_WATERMARK:
        im.putalpha(alpha.point(lambda v: 0 if v <= AMBANG_WATERMARK else v))
        print("  - pola watermark dibuang")

    sudut = [im.getpixel(p) for p in [(0, 0), (im.width - 1, 0),
                                       (0, im.height - 1), (im.width - 1, im.height - 1)]]
    if all(p[3] == 255 and min(p[:3]) >= AMBANG_PUTIH for p in sudut):
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, a = px[x, y]
                if min(r, g, b) >= AMBANG_PUTIH:
                    px[x, y] = (r, g, b, 0)
        print("  - latar putih dijadikan transparan")

    kotak = im.getbbox()
    if kotak:
        im = im.crop(kotak)
    sisi = max(im.size)
    kanvas = Image.new("RGBA", (sisi, sisi), (0, 0, 0, 0))
    kanvas.alpha_composite(im, ((sisi - im.width) // 2, (sisi - im.height) // 2))

    DIR_LOGO.mkdir(parents=True, exist_ok=True)
    tujuan = DIR_LOGO / nama_tujuan
    kanvas.resize((ukuran, ukuran), Image.LANCZOS).save(tujuan, optimize=True)
    return tujuan


def main() -> None:
    p = argparse.ArgumentParser(description="Siapkan logo untuk dashboard.")
    p.add_argument("sumber", type=Path, help="file gambar mentah (mis. sumber/picture/x.png)")
    p.add_argument("nama", help="nama file tujuan di shared/assets/logo/ (mis. dampak.png)")
    p.add_argument("--ukuran", type=int, default=96, help="ukuran sisi hasil, px (default 96)")
    a = p.parse_args()
    if not a.sumber.is_file():
        raise SystemExit(f"File tidak ditemukan: {a.sumber}")
    print(f"Menyiapkan {a.sumber} -> {a.nama}")
    hasil = siapkan(a.sumber, a.nama, a.ukuran)
    print(f"OK -- tersimpan di {hasil} ({hasil.stat().st_size // 1024} KB)")
    print("Restart Streamlit supaya logo baru terbaca.")


if __name__ == "__main__":
    main()
