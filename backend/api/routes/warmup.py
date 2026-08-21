"""Pre-load slow models before the officer starts a real job.

Two things in this pipeline pay a real cold-start cost on first use:

- Ollama (services/fact_extractor.try_ollama_extraction) loads llama3.2:3b
  into memory on its first /api/generate call. Ollama unloads an idle model
  after a few minutes, so this cost repeats after any gap in the demo.
- Wav2Lip (services/wav2lip_service) lazily loads its checkpoint, the S3FD
  face detector and (optionally) GFPGAN the first time a video actually
  needs lip-sync -- exactly when an officer is watching a progress bar and
  least wants to wait on a multi-second one-time load.

Both use the same lazy-singleton pattern (a module-level cache filled by a
get_*() call), so warming them up is just calling those getters once, ahead
of time, from a button instead of from the first real render.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["warmup"])

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


class ComponentStatus(BaseModel):
    ok: bool
    detail: str
    elapsed_sec: float


class WarmupResponse(BaseModel):
    wav2lip: ComponentStatus
    ollama: ComponentStatus
    total_elapsed_sec: float


def _warm_wav2lip() -> ComponentStatus:
    t0 = time.time()
    try:
        from services.wav2lip_service import get_device, get_face_detector, get_wav2lip_model

        device = get_device()
        get_wav2lip_model()
        get_face_detector()
        return ComponentStatus(ok=True, detail=f"loaded on {device}", elapsed_sec=round(time.time() - t0, 2))
    except Exception as exc:
        # A cold GPU/checkpoint load failing here must not block the officer
        # from working -- render() will attempt the same load again later and
        # surface the same error there if it is still broken.
        logger.warning("wav2lip warmup failed", exc_info=True)
        return ComponentStatus(ok=False, detail=str(exc)[:300], elapsed_sec=round(time.time() - t0, 2))


def _warm_ollama() -> ComponentStatus:
    t0 = time.time()
    try:
        import requests

        # No "prompt" field: Ollama's documented way to load a model into
        # memory without generating anything. keep_alive extends how long it
        # stays resident, so it survives the gap between warmup and the
        # officer actually starting a job.
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "keep_alive": "30m"},
            timeout=120,
        )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            return ComponentStatus(ok=True, detail=f"{OLLAMA_MODEL} loaded", elapsed_sec=elapsed)
        return ComponentStatus(ok=False, detail=f"HTTP {resp.status_code}: {resp.text[:200]}", elapsed_sec=elapsed)
    except Exception as exc:
        # Ollama is a supplementary extraction path (fact_extractor falls
        # back to regex extraction without it), not a requirement -- an
        # officer on a machine with no Ollama installed should see that
        # plainly, not get a failed warmup that looks like something broke.
        logger.info("ollama warmup skipped: %s", exc)
        return ComponentStatus(ok=False, detail=f"unreachable: {exc}"[:300], elapsed_sec=round(time.time() - t0, 2))


def _run_warmup() -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as ex:
        wav2lip_future = ex.submit(_warm_wav2lip)
        ollama_future = ex.submit(_warm_ollama)
        wav2lip_status = wav2lip_future.result()
        ollama_status = ollama_future.result()

    return {
        "wav2lip": wav2lip_status,
        "ollama": ollama_status,
        "total_elapsed_sec": round(time.time() - t0, 2),
    }


@router.post("/api/warmup", response_model=WarmupResponse)
async def warmup() -> Dict[str, Any]:
    """Load Wav2Lip and Ollama in parallel; report per-component status.

    Never raises for a component failure -- a broken/missing Ollama install
    is a normal, expected state (see _warm_ollama), and a Wav2Lip load
    failure here is diagnostic information for the officer, not a reason to
    5xx a button whose only job is "make the next real request faster."
    """
    return await run_in_threadpool(_run_warmup)
