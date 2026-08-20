import os
import sys
import time
import json
import logging
from pathlib import Path

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ocr_engine.executor import run_ephemeral_ocr
from services.fact_extractor import FactExtractor
from services.pipeline import run_pipeline

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # Silence noisy libs
    for noisy in ("PIL", "matplotlib", "moviepy", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

import requests

def warmup_engines(logger):
    """Pre-load local LLM and Wav2Lip into GPU VRAM for true metrics."""
    logger.info("=" * 60)
    logger.info("[WARMUP] Pre-loading models into RTX 4050 VRAM...")
    
    # 1. Warm up Ollama (llama3.2:3b)
    start = time.time()
    try:
        requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2:3b", "prompt": "hi", "stream": False
        }, timeout=45)
        logger.info(f" -> Ollama loaded in {time.time()-start:.2f}s")
    except Exception as e:
        logger.warning(f" -> Ollama warmup failed (is it running?): {e}")

    # 2. Warm up Wav2Lip
    # We can import and load the model directly to cache it in torch memory
    start = time.time()
    try:
        from services.wav2lip_service import get_wav2lip_model, DEFAULT_CHECKPOINT
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        _ = get_wav2lip_model(str(DEFAULT_CHECKPOINT))
        logger.info(f" -> Wav2Lip PyTorch model loaded in {time.time()-start:.2f}s")
    except Exception as e:
        logger.warning(f" -> Wav2Lip warmup failed: {e}")
        
    logger.info("[WARMUP] Complete!")
    logger.info("=" * 60)

def run():
    setup_logging()
    logger = logging.getLogger("pdf_to_video")
    
    warmup_engines(logger)
    
    pdf_path = BACKEND_DIR / "ocr_engine" / "complex_layout_test.pdf"
    out_dir = BACKEND_DIR / "out"
    out_dir.mkdir(exist_ok=True)
    
    facts_out_path = out_dir / "facts.json"
    
    logger.info("=" * 60)
    logger.info(f"STARTING END-TO-END PIPELINE FROM PDF")
    logger.info(f"PDF Input: {pdf_path}")
    logger.info("=" * 60)
    
    overall_start = time.time()
    
    # ---------------------------------------------------------
    # STAGE 1: OCR Extraction
    # ---------------------------------------------------------
    logger.info("[STAGE 1] Running OCR on PDF...")
    start_time = time.time()
    
    if not pdf_path.exists():
        logger.error(f"PDF not found at {pdf_path}")
        return
        
    ocr_result = run_ephemeral_ocr(str(pdf_path), lang="en")
    raw_text = ocr_result.get("raw_text", "")
    pages = ocr_result.get("pages", [])
    
    ocr_time = time.time() - start_time
    logger.info(f"[STAGE 1 DONE] OCR completed in {ocr_time:.2f}s")
    logger.info(f" -> Extracted text length: {len(raw_text)} characters from {len(pages)} page(s).")
    
    # ---------------------------------------------------------
    # STAGE 2: Fact Extraction (Local LLM / Regex)
    # ---------------------------------------------------------
    logger.info("-" * 60)
    logger.info("[STAGE 2] Extracting facts from raw text...")
    start_time = time.time()
    
    extractor = FactExtractor()
    facts = extractor.extract_facts(raw_text)
    
    # Dump to facts.json
    facts_data = [f.model_dump() for f in facts]
    with open(facts_out_path, "w", encoding="utf-8") as f:
        json.dump(facts_data, f, indent=2, ensure_ascii=False)
        
    ext_time = time.time() - start_time
    logger.info(f"[STAGE 2 DONE] Fact Extraction completed in {ext_time:.2f}s")
    logger.info(f" -> Extracted {len(facts)} facts. Saved to {facts_out_path}")
    
    # ---------------------------------------------------------
    # STAGE 3: Audio, Scenes, Wav2Lip & Video Rendering
    # ---------------------------------------------------------
    logger.info("-" * 60)
    logger.info("[STAGE 3] Running Full Video Pipeline Synthesis...")
    logger.info("This will generate audio, build scenes, run Wav2Lip, and compose the final video.")
    logger.info("Using static UI elements for visual selection (RAG layer deferred).")
    start_time = time.time()
    
    # We pass the raw_text to run_pipeline, which handles the entire chain
    # Note: run_pipeline also re-extracts facts internally for schema mapping,
    # which is perfectly fine (LLM result will be identical).
    pipeline_result = run_pipeline(
        raw_text=raw_text,
        job_id="complex_pdf_demo",
        lang="en", # You can change this to 'hi', 'ta', etc.
        use_lipsync=True,
        facts=facts,
    )
    
    vid_time = time.time() - start_time
    logger.info(f"[STAGE 3 DONE] Video Pipeline completed in {vid_time:.2f}s")
    logger.info(f" -> Audio Narration: {pipeline_result.narration_wav}")
    if pipeline_result.lipsync_video:
        logger.info(f" -> LipSync Output:  {pipeline_result.lipsync_video}")
    else:
        logger.info(f" -> LipSync skipped or failed (fallback to static loop)")
    logger.info(f" -> Final Render:    {pipeline_result.video_path}")
    
    # ---------------------------------------------------------
    # FINISHED
    # ---------------------------------------------------------
    total_time = time.time() - overall_start
    logger.info("=" * 60)
    logger.info(f"PIPELINE COMPLETE in {total_time:.2f}s total.")
    logger.info(f"Your video is ready at: {pipeline_result.video_path}")
    logger.info("=" * 60)

if __name__ == "__main__":
    run()
