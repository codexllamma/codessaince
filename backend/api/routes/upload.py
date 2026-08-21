"""FastAPI Upload & Ephemeral OCR + Fact Extraction Route.

Handles multipart PDF file streaming to temporary storage, non-blocking synchronous OCR
execution via worker subprocess, grounded fact extraction, and guaranteed temporary file cleanup.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from ocr_engine.executor import run_ephemeral_ocr
from services.fact_extractor import FactExtractor

router = APIRouter(tags=["upload"])


def _process_pdf_sync(temp_pdf_path: str, lang: str) -> Dict[str, Any]:
    """Synchronously executes ephemeral OCR and extracts grounded facts."""
    ocr_result = run_ephemeral_ocr(temp_pdf_path, lang=lang)
    raw_text = ocr_result.get("raw_text", "")
    pages = ocr_result.get("pages", [])

    extractor = FactExtractor()
    facts = extractor.extract_facts(raw_text, source_lang=lang)
    facts_data = [f.model_dump() for f in facts]

    return {
        "raw_text": raw_text,
        "pages_count": len(pages),
        "facts": facts_data,
    }


@router.post("/api/jobs/upload-doc", status_code=status.HTTP_200_OK)
async def upload_document(
    file: UploadFile = File(...),
    lang: str = Form("en"),
):
    """Streams uploaded circular PDF to a temp file, runs OCR + fact extraction, and cleans up."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    # Generate a unique temp file path in OS temp directory
    temp_dir = tempfile.gettempdir()
    unique_suffix = f"_{uuid.uuid4().hex[:8]}.pdf"
    temp_pdf_path = os.path.join(temp_dir, f"circular_upload{unique_suffix}")

    try:
        # Stream file in chunks to disk to avoid reading entire file into memory
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run blocking OCR subprocess in threadpool to keep ASGI event loop unblocked
        result = await run_in_threadpool(_process_pdf_sync, temp_pdf_path, lang)

        return {
            "status": "success",
            "extracted_facts": result["facts"],
            "results": result["facts"],
            "raw_text": result["raw_text"],
            "pages_processed": result["pages_count"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {str(e)}",
        )
    finally:
        # Guaranteed cleanup of temporary PDF file
        if os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except OSError:
                pass
        await file.close()

from pydantic import BaseModel

class RunE2ERequest(BaseModel):
    lang: str
    character: str
    voice: str

# LanguageSelect.tsx offers Gujarati, Kannada, Malayalam and Punjabi, but
# services.audio_synthesizer.VOICE_MAPPING has no edge-tts voice for any of
# them. narration.py falls back to the English voice when a language is
# unmapped -- so those four would silently narrate in English while the UI
# claims to be speaking the selected language. That is worse than an error:
# a wrong video that looks right. Gate on it explicitly rather than let it
# through quietly. Keep in sync with VOICE_MAPPING in audio_synthesizer.py.
E2E_SUPPORTED_LANGS = {"en", "hi", "ta", "te", "bn", "mr"}

def _run_e2e_sync(req: RunE2ERequest) -> dict:
    from ocr_engine.executor import run_ephemeral_ocr
    from services.fact_extractor import FactExtractor
    from services.pipeline import run_pipeline
    import time

    if req.lang not in E2E_SUPPORTED_LANGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"lang={req.lang!r} has no text-to-speech voice configured "
                f"(supported: {sorted(E2E_SUPPORTED_LANGS)}). Narrating it "
                "anyway would silently fall back to an English voice while "
                "claiming to be this language."
            ),
        )

    pdf_path = Path(__file__).resolve().parent.parent.parent / "ocr_engine" / f"extensive_test_{req.lang}.pdf"
    if not pdf_path.exists():
        pdf_path = Path(__file__).resolve().parent.parent.parent / "ocr_engine" / "extensive_test_en.pdf"

    ocr_result = run_ephemeral_ocr(str(pdf_path), lang=req.lang)
    raw_text = ocr_result.get("raw_text", "")
    
    extractor = FactExtractor()
    facts = extractor.extract_facts(raw_text, source_lang=req.lang)
    
    job_id = f"e2e_{int(time.time())}"
    pipeline_result = run_pipeline(
        raw_text=raw_text,
        job_id=job_id,
        lang=req.lang,
        use_lipsync=True,
        facts=facts,
        avatar_id=req.character,
        voice_id=req.voice
    )
    
    # Hand back a URL the browser can actually fetch, not the absolute path on
    # this machine. run_pipeline writes into backend/out/, which server.py
    # mounts at /out; returning str(video_path) gave the frontend something
    # like "C:\...\backend\out\x.mp4", which it can only concatenate onto the
    # API base to produce a dead link.
    backend_dir = Path(__file__).resolve().parent.parent.parent
    video_path = Path(pipeline_result.video_path)
    try:
        rel = video_path.relative_to(backend_dir)
        video_url = "/" + rel.as_posix()
    except ValueError:
        # Rendered somewhere outside the tree; serving it is the caller's
        # problem, but say so plainly rather than emitting a broken path.
        video_url = video_path.as_uri()

    return {
        "status": "success",
        "video_path": video_url,
        "facts": [f.model_dump() for f in facts]
    }

@router.post("/api/jobs/run-e2e", status_code=status.HTTP_200_OK)
async def run_e2e_pipeline(req: RunE2ERequest):
    """Runs the entire pipeline end-to-end based on a selected language, character, and voice."""
    result = await run_in_threadpool(_run_e2e_sync, req)
    return result

