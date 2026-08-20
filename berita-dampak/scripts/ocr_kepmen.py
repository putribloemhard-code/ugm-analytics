"""OCR semua halaman Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf
ke docs/kepmen_361_ocr.txt (tanda halaman per blok)."""

import sys
from pathlib import Path

import pymupdf
from rapidocr_onnxruntime import RapidOCR

PDF = Path(r"D:\ugm-analytics\Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf")
OUT = Path(r"D:\ugm-analytics\docs\kepmen_361_ocr.txt")
TMP = Path(r"D:\ugm-analytics\docs\_ocr_tmp")
TMP.mkdir(parents=True, exist_ok=True)

ocr = RapidOCR()
doc = pymupdf.open(PDF)
out = []
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=200)
    png = TMP / f"kepmen_p{i+1}.png"
    pix.save(png)
    result, _ = ocr(str(png))
    teks = "\n".join(item[1] for item in result) if result else ""
    out.append(f"\n===== HALAMAN {i+1} =====\n{teks}")
    print(f"hal {i+1}/{len(doc)}: {len(teks)} chars", flush=True)
    png.unlink(missing_ok=True)
doc.close()
OUT.write_text("\n".join(out), encoding="utf-8")
print(f"SELESAI -> {OUT}")
