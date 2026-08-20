import os
import sys
import json
import argparse
import numpy as np
import fitz  # PyMuPDF
import logging

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

def extract_pdf(pdf_path: str, lang: str, dpi: int, use_gpu: bool, min_conf: float):
    # Initialize PaddleOCR with graceful fallback
    try:
        ocr = PaddleOCR(
            use_angle_cls=False,
            lang=lang,
            use_gpu=use_gpu,
            show_log=False,
        )
    except Exception:
        ocr = PaddleOCR(
            use_angle_cls=False,
            lang=lang,
            use_gpu=False,
            show_log=False,
        )
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
            result = ocr.ocr(img_np, cls=False)
        except Exception as ocr_err:
            if use_gpu:
                ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang=lang,
                    use_gpu=False,
                    show_log=False,
                )
                use_gpu = False
                result = ocr.ocr(img_np, cls=False)
            else:
                raise ocr_err

        page_blocks = []
        if result and result[0] is not None:
            for line in result[0]:
                box = line[0]           # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text, conf = line[1]

                if float(conf) >= min_conf:
                    page_blocks.append({
                        "text": text.strip(),
                        "confidence": round(float(conf), 4),
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