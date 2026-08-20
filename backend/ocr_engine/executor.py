import os
import sys
import json
import subprocess
try:
    from ocr_engine.config import SUPPORTED_LANGUAGES, DEFAULT_CONFIG
except ImportError:
    from config import SUPPORTED_LANGUAGES, DEFAULT_CONFIG

class OCRExecutionError(Exception):
    """Raised when the OCR worker subprocess encounters an error."""
    pass

def run_ephemeral_ocr(
    pdf_path: str,
    lang: str = "en",
    dpi: int | None = None,
    use_gpu: bool | None = None,
    min_confidence: float | None = None
) -> dict[str, any]: 
    """
    Executes PDF OCR inside a standalone subprocess to prevent CUDA VRAM leaks.
    
    Returns a dictionary containing:
      - 'raw_text': Complete document text concatenated
      - 'pages': Detailed list of pages with bounding boxes and line confidences
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Target PDF does not exist: {pdf_path}")

    # Resolve target language using configuration mapping
    paddle_lang = SUPPORTED_LANGUAGES.get(lang.lower(), DEFAULT_CONFIG["default_lang"])
    target_dpi = str(dpi or DEFAULT_CONFIG["dpi"])
    target_min_conf = str(min_confidence or DEFAULT_CONFIG["min_confidence"])
    target_gpu = use_gpu if use_gpu is not None else DEFAULT_CONFIG["use_gpu"]

    worker_script = os.path.join(os.path.dirname(__file__), "worker.py")

    cmd = [
        sys.executable,
        worker_script,
        "--pdf_path", os.path.abspath(pdf_path),
        "--lang", paddle_lang,
        "--dpi", target_dpi,
        "--min_conf", target_min_conf
    ]

    if target_gpu:
        cmd.append("--use_gpu")

    # Run the worker process
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if process.returncode != 0:
        raise OCRExecutionError(
            f"Worker failed with exit code {process.returncode}.\nStderr: {process.stderr.strip()}"
        )

    stdout = process.stdout

    # Extract JSON payload enclosed by delimiters
    try:
        start_tag = "===OCR_START==="
        end_tag = "===OCR_END==="
        
        start_idx = stdout.index(start_tag) + len(start_tag)
        end_idx = stdout.index(end_tag)
        
        raw_json_str = stdout[start_idx:end_idx].strip()
        pages_data = json.loads(raw_json_str)
    except (ValueError, json.JSONDecodeError) as e:
        raise OCRExecutionError(
            f"Failed to parse OCR worker output.\nRaw Stdout: {stdout}\nError: {str(e)}"
        )

    # Compile aggregated text across all pages
    full_document_text = "\n\n".join([page["full_text"] for page in pages_data if page["full_text"]])

    return {
        "raw_text": full_document_text,
        "pages": pages_data
    }


# ==========================================
# CLI / TESTING ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run GPU-Accelerated Ephemeral OCR")
    parser.add_argument("pdf_path", help="Path to PDF")
    parser.add_argument("--lang", default="en", help="Language code (e.g., en, hi, ta, te)")
    args = parser.parse_args()

    print(f"[+] Processing '{args.pdf_path}' with language '{args.lang}'...")
    result = run_ephemeral_ocr(args.pdf_path, lang=args.lang)

    print("\n--- EXTRACTED TEXT SUMMARY ---")
    print(result["raw_text"][:600] + ("..." if len(result["raw_text"]) > 600 else ""))
    print("------------------------------")
    print(f"[✓] Total Pages Processed: {len(result['pages'])}")