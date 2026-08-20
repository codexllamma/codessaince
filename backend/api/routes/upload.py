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
    facts = extractor.extract_facts(raw_text)
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
