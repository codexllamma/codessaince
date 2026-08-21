import os
import sys
import time
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from executor import run_ephemeral_ocr # Assuming executor.py is in the same directory
from generate_mock_pdf import create_complex_pdf

def run_end_to_end_test():
    test_pdf_path = "complex_layout_test.pdf"
    
    print("\n" + "="*50)
    print("🚀 STARTING E2E OCR PIPELINE TEST")
    print("="*50)

    # 1. Ensure test PDF exists
    if not os.path.exists(test_pdf_path):
        print("[*] Test PDF not found. Generating one now...")
        create_complex_pdf(test_pdf_path)
    else:
        print(f"[*] Found existing test PDF: {test_pdf_path}")

    # 2. Execute Ephemeral OCR Worker
    print("\n[*] Invoking Ephemeral GPU Worker...")
    start_time = time.time()
    
    try:
        # We pass use_gpu=True. The config handles the rest.
        result = run_ephemeral_ocr(
            pdf_path=test_pdf_path, 
            lang="en",
            dpi=300
        )
    except Exception as e:
        print(f"\n[❌] PIPELINE FAILED: {str(e)}")
        return

    execution_time = time.time() - start_time

    # 3. Validation & Metrics
    print(f"[✅] OCR Extraction Successful in {execution_time:.2f} seconds.")
    print("\n" + "="*50)
    print("📊 EXTRACTION METRICS")
    print("="*50)
    
    pages = result.get("pages", [])
    print(f"Total Pages Processed : {len(pages)}")
    
    total_blocks = sum(len(p.get("blocks", [])) for p in pages)
    print(f"Total Text Blocks     : {total_blocks}")
    
    # Calculate average confidence
    all_confs = [block["confidence"] for page in pages for block in page["blocks"]]
    avg_conf = sum(all_confs) / len(all_confs) if all_confs else 0
    print(f"Average Confidence    : {avg_conf * 100:.2f}%")

    print("\n" + "="*50)
    print("📄 EXTRACTED TEXT (READING ORDER VALIDATION)")
    print("="*50)
    
    # Print the raw text to verify the 2-column header and table stayed in sync
    raw_text = result.get("raw_text", "")
    print(raw_text)
    
    print("\n" + "="*50)
    print("🕵️ STRUCTURAL JSON VALIDATION (First 3 Blocks)")
    print("="*50)
    
    # Prove that bounding boxes and coordinates made it back to the parent process safely
    if pages and pages[0]["blocks"]:
        sample_blocks = pages[0]["blocks"][:3]
        print(json.dumps(sample_blocks, indent=2))

if __name__ == "__main__":
    # Note: Ensure config.py, worker.py, and executor.py from the previous step 
    # are in the same module structure before running this.
    run_end_to_end_test()