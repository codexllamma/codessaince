import os
import sys
import json
import argparse
from pathlib import Path
import numpy as np
import fitz  # PyMuPDF
import logging

# Force UTF-8 encoding for standard streams to prevent charmap errors on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Suppress internal warnings
logging.getLogger("ppocr").setLevel(logging.ERROR)

# Ensure environment stability across platforms
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from paddleocr import PaddleOCR

def parse_args():
    parser = argparse.ArgumentParser(description="Ephemeral PaddleOCR Worker")
    parser.add_argument("--pdf_path", required=True, type=str, help="Path to input PDF file")
    parser.add_argument("--lang", default="en", type=str, help="Language code")
    parser.add_argument("--dpi", default=300, type=int, help="Render DPI")
    parser.add_argument("--use_gpu", action="store_true", default=True, help="Enable GPU acceleration")
    parser.add_argument("--min_conf", default=0.5, type=float, help="Minimum confidence threshold")
    return parser.parse_args()

def _build_ocr(lang: str, use_gpu: bool):
    """PaddleOCR across the 2.x/3.x API break.

    3.x dropped use_gpu and show_log (device= replaces the former) and renamed
    use_angle_cls to use_textline_orientation. Trying the new signature first
    and falling back to the old one keeps this working on either, rather than
    pinning the whole project to one PaddleOCR line.
    """
    # The doc-orientation classifier and UVDoc unwarping model are off: a
    # rasterised PDF page is already upright and flat, so they only add load
    # time, and on paddle 3.3.1 their oneDNN kernels abort the whole run with
    # "ConvertPirAttribute2RuntimeAttribute not support". enable_mkldnn=False
    # keeps the detection and recognition models off that same backend.
    attempts = [
        {"lang": lang, "use_textline_orientation": False,
         "use_doc_orientation_classify": False, "use_doc_unwarping": False,
         "enable_mkldnn": False,
         "device": "gpu" if use_gpu else "cpu"},
        {"lang": lang, "use_angle_cls": False,
         "use_gpu": use_gpu, "show_log": False},
    ]
    last_err = None
    for kwargs in attempts:
        try:
            return PaddleOCR(**kwargs)
        except Exception as err:
            last_err = err
    raise last_err


def _normalize(result, min_conf: float):
    """Flatten either result format into (text, confidence, box) triples.

    2.x returns [[ [box, (text, conf)], ... ]]; 3.x returns a list of result
    objects carrying parallel rec_texts / rec_scores / poly arrays.
    """
    out = []
    if not result:
        return out

    first = result[0]

    # 3.x: mapping-like with parallel arrays.
    texts = None
    if hasattr(first, "get") or isinstance(first, dict):
        try:
            texts = first["rec_texts"]
        except Exception:
            texts = None

    if texts is not None:
        try:
            scores = first["rec_scores"]
        except Exception:
            scores = [1.0] * len(texts)
        polys = None
        for key in ("rec_polys", "dt_polys", "rec_boxes"):
            try:
                polys = first[key]
                break
            except Exception:
                continue
        for i, text in enumerate(texts):
            conf = float(scores[i]) if i < len(scores) else 1.0
            if conf < min_conf:
                continue
            if polys is not None and i < len(polys):
                box = [[float(x), float(y)] for x, y in polys[i]]
            else:
                box = [[0.0, 0.0]] * 4
            out.append((str(text).strip(), conf, box))
        return out

    # 2.x: nested [box, (text, conf)] lines.
    if first is None:
        return out
    for line in first:
        box, (text, conf) = line[0], line[1]
        if float(conf) >= min_conf:
            out.append((str(text).strip(), float(conf),
                        [[float(x), float(y)] for x, y in box]))
    return out


def _run(ocr, img_np):
    """3.x prefers predict(); 2.x only has ocr(..., cls=)."""
    if hasattr(ocr, "predict"):
        return ocr.predict(img_np)
    return ocr.ocr(img_np, cls=False)


def extract_pdf(pdf_path: str, lang: str, dpi: int, use_gpu: bool, min_conf: float):
    # Initialize PaddleOCR with graceful fallback
    try:
        ocr = _build_ocr(lang, use_gpu)
    except Exception:
        ocr = _build_ocr(lang, False)
        use_gpu = False

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    extracted_pages = []

    for page_idx, page in enumerate(doc):
        # Direct rasterization to raw RGB byte buffer
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Fast zero-copy / buffer conversion to NumPy array
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

        # Run inference with dynamic fallback
        try:
            result = _run(ocr, img_np)
        except Exception as ocr_err:
            if use_gpu:
                ocr = _build_ocr(lang, False)
                use_gpu = False
                result = _run(ocr, img_np)
            else:
                raise ocr_err

        page_blocks = []
        for text, conf, box in _normalize(result, min_conf):
            page_blocks.append({
                "text": text,
                "confidence": round(conf, 4),
                "bounding_box": box,
                "top": box[0][1],
                "left": box[0][0]
            })

        # Natural reading order sort: primary = Top (Y), secondary = Left (X)
        # Grouping by roughly similar Y (within 10px) ensures multi-column stability
        page_blocks.sort(key=lambda b: (round(b["top"] / 12) * 12, b["left"]))

        extracted_pages.append({
            "page_number": page_idx + 1,
            "blocks": page_blocks,
            "full_text": "\n".join([b["text"] for b in page_blocks])
        })

    doc.close()
    return extracted_pages

if __name__ == "__main__":
    args = parse_args()

    try:
        results = extract_pdf(
            pdf_path=args.pdf_path,
            lang=args.lang,
            dpi=args.dpi,
            use_gpu=args.use_gpu,
            min_conf=args.min_conf
        )

        # Output payload using strict delimiters for safe parsing by the parent
        print("===OCR_START===")
        print(json.dumps(results, ensure_ascii=False))
        print("===OCR_END===")
        sys.exit(0)

    except Exception as e:
        print(f"[WORKER ERROR] {str(e)}", file=sys.stderr)
        sys.exit(1)