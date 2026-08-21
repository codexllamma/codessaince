import sys
import logging
from pathlib import Path
from mcp.server.fastmcp import FastMCP

BACKEND_DIR = Path(__file__).parent.resolve()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ocr_engine.executor import run_ephemeral_ocr
from services.pipeline import run_pipeline

mcp = FastMCP("VaaniReach Pipeline")

@mcp.tool()
def trigger_e2e_pipeline(primary_lang: str, voice_id: str, avatar_id: str) -> str:
    """Trigger the end-to-end VaaniReach video generation pipeline directly.
    
    Args:
        primary_lang: The 2-letter language code of the local test PDF (e.g., "hi", "ta", "en", "te", "bn", "mr")
        voice_id: The Neural voice ID to use (e.g., "hi-IN-MadhurNeural")
        avatar_id: The visual presenter ID to use (e.g., "female_saree_raw")
    """
    logging.info(f"Triggering E2E pipeline for lang: {primary_lang}, voice: {voice_id}, avatar: {avatar_id}")
    
    pdf_path = BACKEND_DIR / "ocr_engine" / f"extensive_test_{primary_lang}.pdf"
    if not pdf_path.exists():
        pdf_path = BACKEND_DIR / "ocr_engine" / "complex_layout_test.pdf"
        
    ocr_result = run_ephemeral_ocr(str(pdf_path), lang=primary_lang)
    raw_text = ocr_result.get("raw_text", "")
    
    if not raw_text:
        return "Failed to extract text from PDF."
        
    import uuid
    job_id = f"mcp_job_{uuid.uuid4().hex[:6]}"
    
    result = run_pipeline(
        raw_text=raw_text,
        job_id=job_id,
        lang=primary_lang,
        voice_id=voice_id,
        avatar_id=avatar_id,
    )
    
    return f"Pipeline completed successfully. Video saved to: {result.video_path}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
