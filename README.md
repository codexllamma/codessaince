# IndicGov-Sentinel

### Multilingual Notice-to-Video AI Engine
### Technical Documentation v1.0

| Field | Value |
|---|---|
| Project codename | IndicGov-Sentinel |
| Document type | Engineering reference and operations manual |
| Target hardware | NVIDIA RTX 4050 (6 GB VRAM), modern multi-core CPU |
| Delivery window | 24-hour hackathon sprint |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Frontend | Next.js 14 (App Router), Tailwind CSS, Framer Motion |
| Output | 1080p MP4, 30 to 45 seconds, 6 languages |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Architectural Principles](#3-architectural-principles)
4. [Repository Layout](#4-repository-layout)
5. [Environment Setup](#5-environment-setup)
6. [Configuration Reference](#6-configuration-reference)
7. [Data Contracts](#7-data-contracts)
8. [Pipeline Stage Reference](#8-pipeline-stage-reference)
9. [Ephemeral Worker Protocol](#9-ephemeral-worker-protocol)
10. [Asset Manifest and Tag Matching](#10-asset-manifest-and-tag-matching)
11. [HTTP API Reference](#11-http-api-reference)
12. [MCP Server Tool Reference](#12-mcp-server-tool-reference)
13. [Officer Cockpit Specification](#13-officer-cockpit-specification)
14. [Verification and Telemetry](#14-verification-and-telemetry)
15. [Failure Modes and Fallbacks](#15-failure-modes-and-fallbacks)
16. [Testing and Acceptance Criteria](#16-testing-and-acceptance-criteria)
17. [Performance Budget and Tuning](#17-performance-budget-and-tuning)
18. [Execution Plan and Ownership](#18-execution-plan-and-ownership)
19. [Demo Runbook](#19-demo-runbook)
20. [Troubleshooting Guide](#20-troubleshooting-guide)
21. [Security and Compliance Notes](#21-security-and-compliance-notes)
22. [Known Limitations and Roadmap](#22-known-limitations-and-roadmap)
23. [Appendices](#23-appendices)

---

## 1. Introduction

### 1.1 Purpose

Government departments in India publish scheme circulars and notices as dense, English-heavy PDFs. Citizens who most need the information (farmers, pensioners, small traders) often cannot parse a legal circular, and departments lack the media staff to convert every notice into a short explainer video in six languages within the notice validity window.

IndicGov-Sentinel converts an official notice PDF into verified, broadcast-grade short videos in English, Hindi, Tamil, Telugu, Bengali and Marathi, with a mandatory human sign-off gate before any media is published.

### 1.2 Scope

**In scope**

- Ingestion of text-based and scanned PDF circulars up to 10 pages
- Grounded fact extraction with exact character offsets back to the source
- Deterministic scene scripting with prosody annotation
- Entity-locked translation into five Indic languages
- Neural TTS with word-level timestamps
- Programmatic 1080p video composition (no generative video)
- Officer review cockpit with bidirectional highlighting and inline edits

**Out of scope**

- Generative or diffusion-based video synthesis
- Voice cloning of real officials
- Autonomous publishing to social platforms
- Multi-tenant authentication and role hierarchies (single trusted officer assumed for the sprint)

### 1.3 Audience

| Reader | Sections of interest |
|---|---|
| Backend engineer (M1, M2) | 7, 8, 9, 11, 15 |
| Frontend engineer (M3) | 7, 11, 13, 14 |
| Media/rendering engineer (M4) | 8.5, 8.6, 10, 17, 20 |
| Reviewing officer | 13, 19 |
| Judge or evaluator | 2, 3, 14, 22 |

### 1.4 Glossary

| Term | Definition |
|---|---|
| Fact | An atomic, categorised claim extracted from the notice, anchored to a character span |
| Grounding | The property that every rendered claim traces to an exact substring in the source PDF |
| Entity lock | Masking of proper nouns and numerics before machine translation, restored after |
| HITL gate | Human-in-the-loop checkpoint that blocks media synthesis until an officer approves |
| Ephemeral worker | A short-lived subprocess that allocates VRAM, does one job, and exits |
| Scene | One narrative beat of the video, roughly 6 to 10 seconds |
| Drift | Misalignment between a spoken word and its highlighted caption, measured in milliseconds |
| Tofu | Empty rectangle glyph rendered when a font lacks a codepoint |

---

## 2. System Overview

### 2.1 High-level flow

```
                                      ┌────────────────────────────────────────────────────────┐
                                      │              OFFICER REVIEW COCKPIT                    │
                                      │   (Bidirectional Highlighting & Telemetry Drawer)      │
                                      └──────────────────────────▲─────────────────────────────┘
                                                                 │ (Human-in-the-Loop Gate)
[Source Notice PDF]                                              │
        │                                                        │
        ▼                                                        │
┌───────────────────────┐      ┌─────────────────────────┐       │      ┌─────────────────────────┐
│ 1. Ingestion & OCR    │ ───► │ 2. Fact Extraction      │ ──────┴────► │ 3. Scene Scripting &    │
│    (PaddleOCR on CPU) │      │    (Qwen 2.5 7B JSON)   │              │    Prosody Annotation   │
└───────────────────────┘      └─────────────────────────┘              └────────────┬────────────┘
                                                                                     │
                                                                                     ▼
┌───────────────────────┐      ┌─────────────────────────┐              ┌─────────────────────────┐
│ 6. MP4 Composition    │ ◄─── │ 5. Audio & Word-Level   │ ◄─────────── │ 4. Entity-Locked        │
│    (MoviePy / Remotion│      │    Captions (edge-tts)  │              │    Indic Translation    │
└───────────────────────┘      └─────────────────────────┘              └─────────────────────────┘
```

### 2.2 Job state machine

Every upload creates a `NoticeVideoJob` that advances through a strict, non-skippable state machine. The officer gate is the only state that cannot be advanced by the system itself.

```
CREATED
   │ upload accepted, job dir written
   ▼
OCR_RUNNING ──► OCR_FAILED (terminal, retryable)
   │
   ▼
FACTS_EXTRACTED
   │
   ▼
SCENES_DRAFTED            (master English scenes exist)
   │
   ▼
TRANSLATED                (localized_scenes populated)
   │
   ▼
AWAITING_APPROVAL ◄──────┐  officer edits loop back here
   │ officer_approved=true│  (edit triggers re-translate of touched scenes only)
   ▼                      │
SYNTHESIZING ─────────────┘
   │ audio + word timestamps per scene per language
   ▼
RENDERING
   │
   ▼
COMPLETED                 final_video_paths populated
```

State is persisted to `jobs/<job_id>/state.json` after every transition, so a crashed process resumes from the last committed state instead of restarting OCR.

### 2.3 Process topology

| Process | Lifetime | Device | Responsibility |
|---|---|---|---|
| `api` (uvicorn) | Long-lived | CPU | Orchestration, state, HTTP and WebSocket |
| `ocr_worker.py` | Ephemeral | CPU | PaddleOCR + PyMuPDF text and span extraction |
| `llm_worker.py` | Ephemeral | GPU | Qwen 2.5 fact extraction and scene scripting |
| `tts_worker.py` | Ephemeral | Network/CPU | edge-tts synthesis and WordBoundary capture |
| `render_worker.py` | Ephemeral | CPU + NVENC | Layered composition and H.264 encode |
| `mcp_server.py` | Long-lived | CPU | Exposes pipeline capabilities over MCP |
| `web` (Next.js) | Long-lived | CPU | Officer cockpit |

No two GPU workers are ever scheduled concurrently. The API holds a single asyncio semaphore of size 1 around every GPU dispatch.

---

## 3. Architectural Principles

### 3.1 Zero generative video diffusion

**Rule:** no frame of output is hallucinated by a video model.

Every visual element is one of: a typographic layer rendered by Pillow or Cairo, an SVG or PNG asset from the local manifest, a licensed B-roll loop, or a procedural gradient. This is a correctness requirement, not a performance one. A government notice video that invents imagery is a liability; a video assembled from a fixed asset catalogue is auditable frame by frame.

**Consequence:** the visual quality ceiling is set by the asset catalogue and the typography system, so both deserve real investment (section 10).

### 3.2 Strict memory isolation

The RTX 4050 has 6 GB of VRAM. Qwen 2.5 7B at Q4_K_M occupies roughly 4.3 GB with a 4k context. There is no headroom to co-resident a second model. PyTorch caching allocators also do not reliably return VRAM to the driver inside a long-lived process.

**Rule:** every GPU task is a subprocess that exits. Process exit is the only VRAM deallocation strategy that is trusted. See section 9.

### 3.3 Entity-locked translation

Machine translation systems routinely mangle scheme names, transliterate acronyms inconsistently, reformat currency, and localise digits. "PM-KISAN" becoming "पीएम-किसान" in one scene and "प्रधानमंत्री किसान" in another destroys the trust the product is selling.

**Rule:** the set of extracted fact values is masked out of the text before translation and restored verbatim afterwards. Only connective narrative is ever translated. See section 8.4 for the token format and its failure modes.

### 3.4 Bidirectional grounding

Every `ExtractedFact` carries `source_page`, `source_char_start` and `source_char_end`. This enables two directions of verification:

- **Forward:** click a fact card in the cockpit, the PDF canvas scrolls and highlights the exact span
- **Reverse:** select text in the PDF, the matrix highlights every fact derived from that span

Any fact whose `raw_value` is not an exact substring of the source text at its declared offsets is marked `is_verified=false` and rendered in red in the cockpit. Unverified facts cannot enter a scene without an explicit `officer_override`.

### 3.5 Human-in-the-loop officer gate

The agent halts at `AWAITING_APPROVAL`. No audio is synthesised and no frame is rendered until `officer_approved` flips to true. This is enforced server-side, not by UI convention: the `/render` endpoint returns HTTP 409 if the flag is false.

---

## 4. Repository Layout

```
indicgov-sentinel/
├── api/
│   ├── main.py                  # FastAPI app, routers, WS hub
│   ├── orchestrator.py          # state machine, subprocess dispatch, GPU semaphore
│   ├── routes/
│   │   ├── jobs.py              # upload, status, fact patch, approve, render
│   │   └── assets.py            # manifest listing, preview streaming
│   └── deps.py
├── models/
│   └── schemas.py               # SINGLE SOURCE OF TRUTH, frozen at T+03:00
├── services/
│   ├── ocr_grounding.py         # PyMuPDF spans, PaddleOCR fallback
│   ├── scene_planner.py         # fact -> 3/4 beat narrative slicing
│   ├── ssml_compiler.py         # prosody annotation -> SSML
│   ├── translator.py            # entity-locked translation
│   ├── entailment.py            # NLI verification pass
│   └── asset_matcher.py         # tag scoring against manifest
├── workers/
│   ├── ocr_worker.py
│   ├── llm_worker.py
│   ├── tts_worker.py
│   └── render_worker.py
├── compositor/
│   ├── layers.py                # 5-layer canvas construction
│   ├── kenburns.py              # motion transform
│   ├── karaoke.py               # word-level caption renderer
│   └── typography.py            # Pillow text shaping, font fallback chain
├── mcp_server/
│   └── media_tools.py
├── prompt_templates/
│   ├── fact_extraction.py
│   └── scene_scripting.py
├── assets/
│   ├── manifest.json
│   ├── broll/                   # licensed loops, 1080p, 7 to 12 s
│   ├── fonts/                   # Noto family, bundled, never system-resolved
│   └── audio/                   # news bed, transition whooshes
├── jobs/
│   └── <job_id>/                # per-job artefacts, see 4.1
├── web/                         # Next.js cockpit
│   ├── app/
│   │   ├── page.tsx             # upload
│   │   └── job/[id]/page.tsx    # cockpit
│   └── components/
│       ├── PdfCanvas.tsx
│       ├── FactMatrix.tsx
│       ├── StoryboardCard.tsx
│       └── TelemetryDrawer.tsx
└── tests/
    ├── golden/                  # 3 cached circulars + expected facts
    └── test_grounding.py
```

### 4.1 Per-job artefact layout

```
jobs/job_101/
├── state.json               # NoticeVideoJob, rewritten atomically on transition
├── source.pdf
├── raw_text.json            # page -> text, with global char offset map
├── facts.json               # llm_worker output
├── scenes_en.json
├── scenes_hi.json ...       # one per target language
├── audio/
│   └── hi/scene_1.mp3
├── subs/
│   └── hi/scene_1.json      # List[WordTimestamp]
├── frames/                  # optional debug PNG dumps
├── out/
│   └── notice_hi.mp4
└── logs/
    └── llm_worker.log
```

Atomic write rule: workers write to `<name>.tmp` then `os.replace()`. A half-written `state.json` is the single easiest way to lose a demo.

---

## 5. Environment Setup

### 5.1 Prerequisites

| Component | Version | Verification command |
|---|---|---|
| Python | 3.11.x | `python --version` |
| Node.js | 20 LTS | `node -v` |
| NVIDIA driver | >= 550 | `nvidia-smi` |
| CUDA runtime | 12.1 | `nvcc --version` |
| FFmpeg | 6.x with NVENC | `ffmpeg -encoders \| grep nvenc` |
| Ollama | >= 0.3 | `ollama --version` |

### 5.2 Backend installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip

pip install fastapi uvicorn[standard] pydantic python-multipart
pip install pymupdf paddleocr paddlepaddle
pip install edge-tts deep-translator
pip install moviepy pillow numpy
pip install transformers torch --index-url https://download.pytorch.org/whl/cu121
pip install mcp
```

### 5.3 Model provisioning

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama run qwen2.5:7b-instruct-q4_K_M "reply with {\"ok\":true}" --format json
```

Confirm the JSON mode responds correctly before anything else is built. If the model ignores `format: json`, the whole extraction stage needs a regex-repair fallback and that is a T+00:30 discovery, not a T+06:00 discovery.

Pre-warm PaddleOCR so its model download does not happen mid-demo:

```bash
python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en')"
```

### 5.4 Font provisioning

```bash
mkdir -p assets/fonts
# Required, bundled into the repo, never resolved from the OS:
#   NotoSans-Bold.ttf, NotoSans-Regular.ttf
#   NotoSansDevanagari-Bold.ttf      (hi, mr)
#   NotoSansTamil-Bold.ttf           (ta)
#   NotoSansTelugu-Bold.ttf          (te)
#   NotoSansBengali-Bold.ttf         (bn)
```

Verify each font renders its script before integration:

```bash
python compositor/typography.py --selftest
# writes assets/fonts/_selftest.png with one sample string per language
```

### 5.5 Frontend installation

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

### 5.6 Smoke test

```bash
uvicorn api.main:app --reload --port 8000
curl -F "file=@tests/golden/pm_kisan_17th.pdf" \
     -F "languages=en,hi" \
     http://localhost:8000/api/jobs
```

Expected: HTTP 201 with a `job_id`, and `jobs/<id>/raw_text.json` on disk within 3 seconds.

---

## 6. Configuration Reference

All configuration is environment-driven. No magic numbers in worker code.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama endpoint |
| `LLM_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | Extraction and scripting model |
| `LLM_NUM_CTX` | `4096` | Context window; raising this raises VRAM |
| `LLM_TEMPERATURE` | `0.1` | Kept low for schema stability |
| `GPU_SEMAPHORE` | `1` | Concurrent GPU workers, do not raise on 6 GB |
| `OCR_LANG` | `en` | PaddleOCR language pack |
| `OCR_DPI` | `200` | Rasterisation DPI for scanned pages |
| `TTS_ENGINE` | `edge` | `edge` or `mms` (local fallback) |
| `TTS_TIMEOUT_SEC` | `20` | Per-scene network budget before fallback |
| `TRANSLATE_BACKEND` | `google` | `google` or `indictrans2` |
| `VIDEO_WIDTH` | `1920` | Output width |
| `VIDEO_HEIGHT` | `1080` | Output height |
| `VIDEO_FPS` | `30` | Output frame rate |
| `VIDEO_CODEC` | `h264_nvenc` | Falls back to `libx264` if NVENC absent |
| `KENBURNS_ZOOM_MAX` | `1.12` | End-of-scene zoom factor |
| `SCENE_TAIL_PAD_SEC` | `0.35` | Silence after last word before cut |
| `NLI_THRESHOLD` | `0.85` | Minimum entailment score to pass a scene |
| `DEMO_MODE` | `false` | Serves pre-rendered golden jobs instantly |

---

## 7. Data Contracts

`models/schemas.py` is the single source of truth. It is frozen at T+03:00 and any change after that requires all four engineers to agree in the same breath, because the frontend generates its TypeScript types from it.

```bash
# regenerate TS types after any schema change
python -c "import json;from models.schemas import NoticeVideoJob;print(json.dumps(NoticeVideoJob.model_json_schema()))" > web/types/job.schema.json
npx json-schema-to-typescript web/types/job.schema.json -o web/types/job.d.ts
```

### 7.1 Fact extraction schemas

```python
from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class FactCategory(str, Enum):
    SCHEME_NAME = "SCHEME_NAME"
    AMOUNT = "AMOUNT"
    DEADLINE = "DEADLINE"
    ELIGIBILITY = "ELIGIBILITY"
    BENEFICIARY = "BENEFICIARY"
    AUTHORITY = "AUTHORITY"
    ACTION_REQUIRED = "ACTION_REQUIRED"


class ExtractedFact(BaseModel):
    fact_id: str
    category: FactCategory
    raw_value: str
    normalized_value: str
    source_page: int
    source_char_start: int
    source_char_end: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    is_verified: bool = True
    officer_override: Optional[str] = None
```

| Field | Semantics | Validation rule |
|---|---|---|
| `fact_id` | Stable handle, format `f<n>` | Unique within a job, used as translation mask token seed |
| `category` | Drives scene assignment and visual template | Must be a `FactCategory` member |
| `raw_value` | Verbatim source substring | Must equal `raw_text[start:end]` or `is_verified` becomes false |
| `normalized_value` | Display form (`₹2,000`, `5th October 2026`) | Used in scripts and visuals, never `raw_value` |
| `source_char_start/end` | Global offsets into the concatenated document text | `end > start`, both within document length |
| `confidence_score` | Model self-reported confidence | Below 0.75 renders amber in the cockpit |
| `officer_override` | Manual replacement value | When set, takes precedence over `normalized_value` everywhere |

**Resolution order for display:** `officer_override` > `normalized_value` > `raw_value`.

### 7.2 Prosody and scripting schemas

```python
class ScriptSegment(BaseModel):
    type: Literal["filler", "core_fact"]
    text: str
    emphasis_level: Literal["none", "moderate", "strong"] = "none"
    pause_after_ms: int = 0
    linked_fact_id: Optional[str] = None
```

A segment of type `core_fact` must carry a `linked_fact_id`. This link is what makes karaoke captions able to colour fact words differently from narrative words, and what makes the NLI pass able to check a claim against the right source span.

### 7.3 Visual directive schemas

```python
class TemplateType(str, Enum):
    HERO_ANNOUNCEMENT = "HERO_ANNOUNCEMENT"
    METRIC_FOCUS = "METRIC_FOCUS"
    DEADLINE_ALERT = "DEADLINE_ALERT"
    OUTRO_CALL_TO_ACTION = "OUTRO_CALL_TO_ACTION"


class VisualTextHierarchy(BaseModel):
    badge_tag: str
    headline: str
    subtext: str
    highlight_metric: Optional[str] = None
    highlight_sublabel: Optional[str] = None


class VisualAssetSelection(BaseModel):
    asset_id: str
    asset_type: Literal["video_loop", "static_graphic", "mesh_gradient"]
    file_path: str
    dim_overlay_opacity: float = 0.65


class WordTimestamp(BaseModel):
    word: str
    start_sec: float
    end_sec: float
    is_core_fact: bool = False
```

Character budgets enforced by the compositor (text exceeding these is ellipsised, and the cockpit warns before render):

| Field | Max characters (Latin) | Max characters (Indic) |
|---|---|---|
| `badge_tag` | 22 | 18 |
| `headline` | 58 | 46 |
| `subtext` | 96 | 80 |
| `highlight_metric` | 12 | 12 |
| `highlight_sublabel` | 32 | 26 |

Indic budgets are lower because Devanagari and Tamil glyph clusters are wider at the same point size and because conjunct stacking increases line height.

### 7.4 Scene and master job payload

```python
class SceneDefinition(BaseModel):
    scene_id: int
    template_type: TemplateType
    script_segments: List[ScriptSegment]
    full_spoken_text: str
    visual_hierarchy: VisualTextHierarchy
    asset: VisualAssetSelection
    audio_path: Optional[str] = None
    scene_duration_sec: Optional[float] = None
    subtitles: Optional[List[WordTimestamp]] = None


class PipelineTelemetry(BaseModel):
    ocr_latency_sec: float
    extraction_confidence_avg: float
    nli_entailment_score: float
    entity_preservation_rate: float
    speech_visual_drift_ms: float


class NoticeVideoJob(BaseModel):
    job_id: str
    source_file_name: str
    raw_extracted_text: str
    target_languages: List[Literal["en", "hi", "ta", "te", "bn", "mr"]]
    selected_voice_id: str
    voice_speed_modifier: str = "+0%"
    extracted_facts: List[ExtractedFact]
    master_scenes_en: List[SceneDefinition]
    localized_scenes: Dict[str, List[SceneDefinition]] = {}
    telemetry: Optional[PipelineTelemetry] = None
    officer_approved: bool = False
    final_video_paths: Dict[str, str] = {}
```

**Invariants**

1. `audio_path`, `scene_duration_sec` and `subtitles` are all `None` until synthesis, and all non-`None` after. A scene in a mixed state is a bug.
2. `localized_scenes[lang]` has the same length and the same `scene_id` ordering as `master_scenes_en`.
3. `final_video_paths` keys are a subset of `target_languages`.
4. `officer_approved` is only ever set by `POST /api/jobs/{id}/approve`, never by a worker.

---

## 8. Pipeline Stage Reference

Each stage below documents its inputs, outputs, algorithm, and the specific ways it fails.

### 8.1 Stage 1: Document ingestion and OCR grounding

| Property | Value |
|---|---|
| Worker | `workers/ocr_worker.py` |
| Device | CPU |
| Input | `jobs/<id>/source.pdf` |
| Output | `jobs/<id>/raw_text.json` |
| Budget | 1.4 s per page, 1.2 GB host RAM |

**Algorithm**

1. Open with PyMuPDF. For each page, attempt `page.get_text("dict")`.
2. If the page yields more than 40 characters of embedded text, use it directly. Embedded text gives exact character positions for free and is always preferred.
3. If the page is image-only (scanned circular), rasterise at `OCR_DPI` and run PaddleOCR with angle classification. Reconstruct reading order by sorting boxes top-to-bottom then left-to-right within a line tolerance of 12 px.
4. Concatenate all pages into one global string, recording a page offset table so a global character index maps back to `(page, page_local_index, bbox)`.

**Output shape**

```json
{
  "pages": [
    {
      "page": 1,
      "char_start": 0,
      "char_end": 2841,
      "source": "embedded",
      "spans": [
        {"text": "PM-KISAN", "char_start": 118, "char_end": 126,
         "bbox": [72.0, 190.4, 143.6, 204.1]}
      ]
    }
  ],
  "full_text": "..."
}
```

The `bbox` on each span is what the cockpit uses to draw the yellow highlight rectangle. Without it, click-to-source degrades to a text search and misfires on repeated strings.

**Failure modes**

| Symptom | Cause | Mitigation |
|---|---|---|
| Garbled Devanagari in `full_text` | PaddleOCR running with `lang='en'` on a Hindi circular | Detect script by codepoint histogram, re-run with `lang='devanagari'` |
| Column text interleaved | Two-column circular, naive top-to-bottom sort | Cluster box x-centres into columns before sorting |
| Offsets do not match highlights | Whitespace normalisation applied after offsets were recorded | Normalise once, before offsets are computed, never after |

### 8.2 Stage 2: Grounded fact extraction

| Property | Value |
|---|---|
| Worker | `workers/llm_worker.py` |
| Device | GPU via Ollama |
| Model | `qwen2.5:7b-instruct-q4_K_M`, 4.3 GB VRAM |
| Budget | 2.8 s |

**Prompt**

```python
# prompt_templates/fact_extraction.py
FACT_EXTRACTION_SYSTEM_PROMPT = """You are a legal-grade document parsing agent for government circulars.
Extract all critical facts from the provided text into a strict JSON object.
Rules:
1. Extract exact substring matches for source_char_start and source_char_end.
2. Normalize all currency values (e.g., 'Rs 2000' -> '₹2,000') and dates (e.g., '05/10/26' -> '5th October 2026').
3. Output MUST conform strictly to the ExtractedFact schema.
"""
```

**Post-extraction verification pass (mandatory)**

Language models are unreliable at reporting character offsets. Never trust the returned span. Instead, treat the returned `raw_value` as ground truth and recover the offset deterministically:

```python
def repair_offsets(fact: dict, full_text: str) -> dict:
    """Model-reported offsets are advisory. The substring is authoritative."""
    needle = fact["raw_value"]
    hinted = fact.get("source_char_start", 0)

    # Search near the hint first, then globally.
    window = full_text[max(0, hinted - 400): hinted + 400]
    local = window.find(needle)
    if local != -1:
        start = max(0, hinted - 400) + local
    else:
        start = full_text.find(needle)

    if start == -1:
        fact["is_verified"] = False
        fact["confidence_score"] = min(fact.get("confidence_score", 0.5), 0.4)
        return fact

    fact["source_char_start"] = start
    fact["source_char_end"] = start + len(needle)
    fact["is_verified"] = True
    return fact
```

This single function is responsible for most of the grounding score reported in telemetry. It is the highest value 20 lines in the repository.

**Failure modes**

| Symptom | Cause | Mitigation |
|---|---|---|
| Truncated JSON | Output exceeded `num_predict` | Raise to 2048, and repair with a brace-balancing parser |
| Facts invented (not in text) | Model summarising rather than extracting | `repair_offsets` catches it and flags `is_verified=false` |
| Duplicate facts | Same value stated twice in the circular | Deduplicate on `(category, normalized_value)`, keep earliest offset |
| Currency mis-normalised | "Rs. 2000/-" trailing slash | Post-process with a currency regex rather than trusting the model |

### 8.3 Stage 3: Scene slicing and prosody annotation

A 30 to 45 second video is exactly 3 or 4 beats. Four beats when an `ACTION_REQUIRED` or `AUTHORITY` fact exists, three otherwise.

| Scene | Template | Required fact categories | Target duration |
|---|---|---|---|
| 1 | `HERO_ANNOUNCEMENT` | `AUTHORITY`, `SCHEME_NAME` | 6 to 8 s |
| 2 | `METRIC_FOCUS` | `AMOUNT` or `BENEFICIARY` | 8 to 10 s |
| 3 | `DEADLINE_ALERT` | `DEADLINE`, `ELIGIBILITY` | 7 to 9 s |
| 4 | `OUTRO_CALL_TO_ACTION` | `ACTION_REQUIRED` | 6 to 8 s |

**Prosody segmentation logic**

Monotone synthetic narration is the fastest way to make a government video feel like a robocall. Each sentence is split into `filler` and `core_fact` segments:

- **Filler** segments are synthesised at broadcast pace, `rate="+4%"`
- **Core fact** segments are slowed and lifted, `rate="-8%" pitch="+3%"`, followed by a mandatory breath of at least 300 ms

```python
# services/ssml_compiler.py
def build_ssml_payload(
    segments: List[ScriptSegment], voice_id: str, speed_mod: str = "+0%"
) -> str:
    ssml_body = ""
    for seg in segments:
        clean_text = seg.text.replace("&", "&amp;").replace("<", "&lt;")
        if seg.type == "core_fact":
            ssml_body += (
                f'<prosody rate="-8%" pitch="+3%">{clean_text}</prosody>'
                f'<break time="{max(seg.pause_after_ms, 300)}ms"/> '
            )
        else:
            ssml_body += f'<prosody rate="{speed_mod}">{clean_text}</prosody> '

    return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="hi-IN">
    <voice name="{voice_id}">
        {ssml_body.strip()}
    </voice>
</speak>"""
```

Note the `xml:lang` attribute is hardcoded to `hi-IN` in the reference implementation. It must be parameterised per target language before the Tamil and Bengali paths are exercised, otherwise the voice and the language tag disagree and the endpoint may reject the request.

### 8.4 Stage 4: Entity-locked translation

```python
# services/translator.py
import re
from typing import Dict
from deep_translator import GoogleTranslator


def translate_scene_with_entity_lock(
    text: str, entity_dict: Dict[str, str], target_lang: str
) -> str:
    masked_text = text
    # 1. Mask entities: e.g., "PM-KISAN" -> "__FACT_f1__"
    for fact_id, val in entity_dict.items():
        masked_text = masked_text.replace(val, f"__{fact_id}__")

    # 2. Translate connective narrative
    translated = GoogleTranslator(source="en", target=target_lang).translate(
        masked_text
    )

    # 3. Unmask original entities
    for fact_id, val in entity_dict.items():
        translated = re.sub(rf"__\s*{fact_id}\s*__", val, translated, flags=re.I)

    return translated
```

**Two defects in the reference implementation, both worth fixing before integration:**

1. **Mask token fragility.** Translation engines frequently strip or space-separate underscores, and some lowercase the token. The regex partially compensates with `\s*` and `re.I`, but a safer sentinel is a pure alphanumeric uppercase form that no translator will split, for example `ZQX01ZQX` for `f1`. Keep the existing regex as a second-chance recovery path.

2. **Ordering bug.** Masking iterates the dict in insertion order. If one fact value is a substring of another ("KISAN" and "PM-KISAN"), the shorter one masks first and corrupts the longer. **Sort entity keys by descending value length before masking.**

```python
for fact_id, val in sorted(entity_dict.items(), key=lambda kv: -len(kv[1])):
    masked_text = masked_text.replace(val, sentinel(fact_id))
```

**Post-translation audit.** Compute `entity_preservation_rate` as the fraction of masked entities that reappear verbatim in the output. If any entity is lost, the scene is flagged in the cockpit and the officer sees an amber warning on that language tab rather than a silently broken video.

**Digit policy.** Indic locales may render Western digits or native digits. Fix the policy to Western digits across all languages so that "₹2,000" is identical in every video and the metric card layout does not shift.

### 8.5 Stage 5: Voice synthesis and word-level timestamps

```python
# workers/tts_worker.py
import asyncio
from pathlib import Path
from typing import List
import edge_tts
from models.schemas import WordTimestamp


async def synthesize_scene_audio(
    ssml_text: str, output_audio: Path
) -> List[WordTimestamp]:
    communicate = edge_tts.Communicate(
        text=ssml_text, voice="hi-IN-MadhurNeural", is_ssml=True
    )
    subtitles: List[WordTimestamp] = []

    with open(output_audio, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # Timestamps in edge-tts stream are in 100-nanosecond units
                start = chunk["offset"] / 10_000_000
                end = (chunk["offset"] + chunk["duration"]) / 10_000_000
                subtitles.append(
                    WordTimestamp(word=chunk["text"], start_sec=start, end_sec=end)
                )

    return subtitles
```

The `WordBoundary` stream is the reason this architecture needs no forced-alignment pass. Whisper or MFA alignment would cost 1 to 2 GB of VRAM and several seconds per scene; the TTS engine already knows exactly when it said each word, so drift is structurally zero rather than merely small.

**Marking core-fact words.** After synthesis, walk the returned words and set `is_core_fact=True` for any word falling inside a `core_fact` segment's text span. This drives the yellow highlight colour in the karaoke layer.

**SSML support risk (high priority).** `is_ssml=True` is not reliably supported across edge-tts versions, and the upstream endpoint has historically rejected or ignored `prosody` and `break` tags. Verify at T+00:30, not later. If SSML is rejected, degrade to **per-segment synthesis**: synthesise each `ScriptSegment` separately with `rate`/`pitch` passed as native edge-tts parameters, then concatenate the MP3s with an inserted silence of `pause_after_ms`. Word offsets must then be shifted by the cumulative duration of preceding segments:

```python
offset = 0.0
for seg_words, seg_dur, pause in synthesised_segments:
    for w in seg_words:
        w.start_sec += offset
        w.end_sec += offset
    offset += seg_dur + pause / 1000.0
```

This fallback produces identical output quality and removes the entire SSML dependency. Several teams find it is the safer default.

**Voice catalogue**

| Language | Male voice | Female voice |
|---|---|---|
| English (India) | `en-IN-PrabhatNeural` | `en-IN-NeerjaNeural` |
| Hindi | `hi-IN-MadhurNeural` | `hi-IN-SwaraNeural` |
| Tamil | `ta-IN-ValluvarNeural` | `ta-IN-PallaviNeural` |
| Telugu | `te-IN-MohanNeural` | `te-IN-ShrutiNeural` |
| Bengali | `bn-IN-BashkarNeural` | `bn-IN-TanishaaNeural` |
| Marathi | `mr-IN-ManoharNeural` | `mr-IN-AarohiNeural` |

Voice availability changes upstream without notice. Cache the output of `edge-tts --list-voices` at startup and validate the selected `voice_id` against it before the officer can approve.

### 8.6 Stage 6: Programmatic video composition

The compositor builds a 1920x1080 canvas from five layers, bottom to top:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 5: Top Alert Pill (Pulsing SVG Badge)                             │
│ Layer 4: Primary Headline & Context Subtext (Rendered via Pillow/Cairo) │
│ Layer 3: Central Metric Highlighting Card (Dynamic border glow)         │
│ Layer 2: Kinetic Karaoke Captions (Spoken word in #FACC15, scaled 1.15x)│
│ Layer 1: Ambient Motion B-Roll MP4 (Ken Burns Zoom + 65% Dim Overlay)   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Layer specifications**

| Layer | Element | Safe area | Notes |
|---|---|---|---|
| 1 | B-roll loop | Full bleed | Looped and time-stretched to scene duration, dimmed per `dim_overlay_opacity` |
| 2 | Karaoke captions | Bottom 22%, 140 px side margin | Max 2 lines, spoken word `#FACC15` at 1.15x scale |
| 3 | Metric card | Centre, 720x320 px | Only on `METRIC_FOCUS`, border glow uses asset `accent_color` |
| 4 | Headline and subtext | Upper third, left aligned | Headline 76 pt, subtext 38 pt |
| 5 | Alert pill | Top left, 96 px inset | Pulses at 0.8 Hz, opacity 0.7 to 1.0 |

**Ken Burns motion transformation**

For a scene of duration `D` seconds, at frame time `t`:

```
p(t)      = t / D                              # normalised progress, 0 to 1
ease(p)   = p * p * (3 - 2p)                   # smoothstep, removes linear-pan feel
zoom(t)   = 1 + (Z_max - 1) * ease(p(t))       # Z_max = KENBURNS_ZOOM_MAX = 1.12

crop_w(t) = W / zoom(t)
crop_h(t) = H / zoom(t)

cx(t)     = cx0 + (cx1 - cx0) * ease(p(t))     # centre drift, in source pixels
cy(t)     = cy0 + (cy1 - cy0) * ease(p(t))

crop_box(t) = (cx(t) - crop_w(t)/2,
               cy(t) - crop_h(t)/2,
               cx(t) + crop_w(t)/2,
               cy(t) + crop_h(t)/2)
```

The crop box is then resampled back to 1920x1080 with Lanczos. Constraints:

- The source is upscaled to at least `Z_max * W` before cropping, so the final frame never samples above native resolution
- `(cx1, cy1)` is chosen per template: `HERO_ANNOUNCEMENT` drifts right, `DEADLINE_ALERT` pushes in centre with no pan, which reads as urgency
- Direction alternates between consecutive scenes so the video does not feel like one continuous slow zoom

**Dynamic timing rule**

Visual slide duration is always bound to the synthesised audio track, never the reverse:

```
scene_duration_sec = subtitles[-1].end_sec + SCENE_TAIL_PAD_SEC
```

No caption is ever cut mid-word, and no scene holds silence for more than 350 ms. Total video duration is the sum of scene durations plus 4 transitions of 0.4 s each, targeted at 30 to 45 s. If the sum exceeds 48 s, the scene planner is re-invoked with an instruction to compress subtext.

**Encoding**

```bash
ffmpeg -y -i frames_%05d.png -i mixed_audio.wav \
  -c:v h264_nvenc -preset p5 -rc vbr -cq 23 -b:v 8M -maxrate 12M \
  -pix_fmt yuv420p -c:a aac -b:a 192k -shortest out/notice_hi.mp4
```

`-pix_fmt yuv420p` is mandatory. Without it the file will not play in WhatsApp, which is the single most likely distribution channel for this content.

---

## 9. Ephemeral Worker Protocol

### 9.1 VRAM budget

| Pipeline step | Process type | Device | VRAM | Host RAM | Latency per scene |
|---|---|---|---|---|---|
| PDF parsing and OCR | PaddleOCR | CPU | 0 MB | 1.2 GB | 1.4 s |
| Fact extraction and scripting | qwen2.5:7b-instruct | GPU (Ollama) | 4.3 GB (Q4_K_M) | 1.0 GB | 2.8 s |
| SSML audio synthesis | edge-tts | Network / CPU | 0 MB | 150 MB | 0.8 s |
| Audio fallback (local) | facebook/mms-tts | GPU (subprocess) | 450 MB | 500 MB | 0.6 s |
| Video assembly | MoviePy / Remotion | CPU + NVENC | 0 MB (dedicated NVENC block) | 2.1 GB | 4.5 s |

Peak VRAM at any instant is 4.3 GB, leaving roughly 1.5 GB of headroom on a 6 GB card for the display driver and the browser running the cockpit. That headroom is why concurrency is capped at one.

### 9.2 Lifecycle

1. The API dispatches a CLI command: `python workers/llm_worker.py --job_id job_101`
2. The worker initialises the model, allocates VRAM, writes its output to `jobs/job_101/facts.json`
3. The process exits with code 0
4. The OS kernel reclaims all CUDA pointers and VRAM returns to baseline

### 9.3 Contract every worker must honour

| Requirement | Rationale |
|---|---|
| Accept only `--job_id` and read the rest from `state.json` | Keeps the CLI stable as the schema grows |
| Write output atomically (`.tmp` then `os.replace`) | A partial artefact is worse than no artefact |
| Emit progress as one JSON object per line on stdout | The orchestrator relays these to the cockpit WebSocket |
| Exit non-zero with a diagnostic on stderr for any failure | The orchestrator distinguishes retryable from terminal |
| Never import `torch` at module top level in CPU workers | Avoids a needless CUDA context and 300 MB of VRAM |

**Progress line format**

```json
{"stage": "llm", "pct": 42, "msg": "extracted 7 facts", "ts": 1761900000.12}
```

### 9.4 Orchestrator dispatch

```python
async def run_worker(script: str, job_id: str, gpu: bool) -> None:
    sem = GPU_SEM if gpu else CPU_SEM
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script, "--job_id", job_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        async for raw in proc.stdout:
            await hub.broadcast(job_id, json.loads(raw))
        rc = await proc.wait()
        if rc != 0:
            err = (await proc.stderr.read()).decode()[-2000:]
            raise WorkerFailure(script, rc, err)
```

Reading stdout and stderr concurrently matters. Draining only stdout while the child writes heavily to stderr fills the pipe buffer and deadlocks the child permanently, which presents as a hang with no error at all.

---

## 10. Asset Manifest and Tag Matching

### 10.1 Manifest format

```json
[
  {
    "asset_id": "broll_agri_field_01",
    "type": "video_loop",
    "category": "agriculture",
    "tags": ["farmer", "crops", "pm-kisan", "irrigation", "rural"],
    "file_path": "assets/broll/agri_field_loop.mp4",
    "duration_sec": 10.0,
    "default_dim_opacity": 0.65,
    "accent_color": "#22C55E"
  },
  {
    "asset_id": "broll_bank_transfer_01",
    "type": "video_loop",
    "category": "finance",
    "tags": ["dbt", "rupee", "bank", "subsidy", "welfare", "disbursement"],
    "file_path": "assets/broll/digital_banking_loop.mp4",
    "duration_sec": 8.5,
    "default_dim_opacity": 0.70,
    "accent_color": "#38BDF8"
  },
  {
    "asset_id": "broll_alert_generic_01",
    "type": "video_loop",
    "category": "urgent_notice",
    "tags": ["deadline", "kyc", "alert", "mandatory", "tax"],
    "file_path": "assets/broll/abstract_alert_loop.mp4",
    "duration_sec": 7.0,
    "default_dim_opacity": 0.75,
    "accent_color": "#EF4444"
  }
]
```

### 10.2 Matching algorithm

Scene text and fact values are lowercased and tokenised, then scored against every asset:

```
score(asset, scene) = 3.0 * |exact_tag_hits|
                    + 1.5 * template_category_affinity
                    + 1.0 * |fuzzy_tag_hits(ratio > 0.85)|
                    - 2.0 * recently_used_penalty
```

- `template_category_affinity` is 1.0 when the template is `DEADLINE_ALERT` and the asset category is `urgent_notice`, and similarly for `METRIC_FOCUS` mapping to `finance`
- `recently_used_penalty` applies when the asset was used in the immediately preceding scene, which prevents the same loop appearing twice in a row
- If the top score is below 2.0, fall back to a procedural `mesh_gradient` tinted with the department accent colour, which always looks intentional and never looks broken

### 10.3 Asset requirements

| Property | Requirement |
|---|---|
| Resolution | 1920x1080 minimum, 2560x1440 preferred for Ken Burns headroom |
| Duration | 7 to 12 s, seamlessly loopable |
| Codec | H.264, yuv420p, no alpha |
| Content | No identifiable faces, no branded logos, no text |
| Licence | Recorded in `assets/LICENCES.md` per asset, required for a government deliverable |

Faces are excluded deliberately. A face in a scheme video implies endorsement or beneficiary identity that the notice does not support.

---

## 11. HTTP API Reference

Base URL `http://localhost:8000/api`. All responses are JSON. All errors follow `{"detail": "...", "code": "..."}`.

### 11.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/jobs` | Upload a notice PDF and create a job |
| `GET` | `/jobs/{job_id}` | Full `NoticeVideoJob` payload |
| `GET` | `/jobs/{job_id}/source.pdf` | Stream the original PDF for the canvas |
| `PATCH` | `/jobs/{job_id}/facts/{fact_id}` | Apply an officer override to a fact |
| `PATCH` | `/jobs/{job_id}/scenes/{scene_id}` | Edit spoken script or visual hierarchy |
| `POST` | `/jobs/{job_id}/preview-audio` | Synthesise one scene for preview only |
| `POST` | `/jobs/{job_id}/approve` | Set `officer_approved=true` |
| `POST` | `/jobs/{job_id}/render` | Trigger synthesis and rendering |
| `GET` | `/jobs/{job_id}/video/{lang}` | Stream the finished MP4 |
| `WS` | `/jobs/{job_id}/events` | Live progress stream |
| `GET` | `/assets` | Manifest listing for manual asset override |

### 11.2 Selected contracts

**POST /jobs**

```
Content-Type: multipart/form-data
  file:        <PDF, max 20 MB>
  languages:   "en,hi,ta"
  voice_id:    "hi-IN-MadhurNeural"      (optional, defaults per language)
  speed:       "+0%"                     (optional)

201 Created
{"job_id": "job_101", "status": "OCR_RUNNING"}

413  file exceeds 20 MB
415  not a PDF
```

**PATCH /jobs/{job_id}/facts/{fact_id}**

```json
{"officer_override": "₹2,000 per instalment"}
```

Side effects, executed synchronously before the response returns:

1. The fact's `officer_override` is set and `is_verified` is left untouched (an override is an assertion of human authority, not a claim of grounding)
2. Every scene whose `script_segments` contain a matching `linked_fact_id` is marked stale
3. Stale scenes are re-scripted and re-translated for every target language
4. Any previously synthesised audio and subtitles for those scenes are deleted

Response returns the updated job with a `stale_scene_ids` array so the cockpit can animate exactly the cards that changed.

**POST /jobs/{job_id}/render**

```
202 Accepted   {"status": "SYNTHESIZING"}
409 Conflict   {"detail": "officer approval required", "code": "NOT_APPROVED"}
422            {"detail": "3 facts unverified without override", "code": "UNGROUNDED"}
```

The 409 is the server-side enforcement of the HITL gate described in 3.5.

**WS /jobs/{job_id}/events**

Server pushes one message per progress event:

```json
{"stage": "tts", "lang": "hi", "scene_id": 2, "pct": 55, "msg": "scene 2 of 4"}
{"stage": "done", "pct": 100, "paths": {"hi": "/api/jobs/job_101/video/hi"}}
```

---

## 12. MCP Server Tool Reference

Exposing the media generation tools over the Model Context Protocol allows a reasoning agent to inspect local capabilities, execute rendering, and fetch status dynamically, rather than having the pipeline hardcoded into one script.

```python
# mcp_server/media_tools.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GovMediaSynthesisServer")


@mcp.tool()
def extract_document_facts(pdf_path: str) -> str:
    """Runs PaddleOCR and returns structured grounded facts as JSON."""
    return "facts_extracted_success"


@mcp.tool()
def verify_fact_entailment(source_text: str, generated_claim: str) -> dict:
    """Computes deterministic and NLI entailment score between claim and source."""
    return {"entailed": True, "confidence": 0.97, "exact_match": True}


@mcp.tool()
def synthesize_indic_speech(
    ssml_content: str, voice_id: str, output_path: str
) -> dict:
    """Synthesizes speech via edge-tts and outputs word-level subtitle timestamps."""
    return {"status": "SUCCESS", "audio_path": output_path, "duration_sec": 7.42}


@mcp.tool()
def compose_scene_video(scene_json_path: str, output_mp4: str) -> str:
    """Composes motion graphics, subtitles, B-roll, and audio into an MP4 clip."""
    return f"Rendered scene at {output_mp4}"
```

### 12.1 Tool contract table

| Tool | Input | Output | Idempotent | Typical latency |
|---|---|---|---|---|
| `extract_document_facts` | Absolute PDF path | JSON array of `ExtractedFact` | Yes | 1.4 s per page + 2.8 s |
| `verify_fact_entailment` | Source paragraph, generated claim | `{entailed, confidence, exact_match}` | Yes | 0.3 s |
| `synthesize_indic_speech` | SSML, voice id, output path | `{status, audio_path, duration_sec}` | No (writes a file) | 0.8 s |
| `compose_scene_video` | Scene JSON path, output path | Output path string | No | 4.5 s |

### 12.2 Guidance for tool authors

- Return structured dicts rather than prose strings wherever a caller might branch on the result. `extract_document_facts` returning `"facts_extracted_success"` gives an agent nothing to reason about; return the fact array or a path plus a count.
- Every tool that writes to disk must accept an explicit output path. Never let a tool choose its own filename, or the agent loses track of its own artefacts.
- Tools must validate that the job directory exists and fail fast with a readable message, because an agent will otherwise retry a doomed call several times.

---

## 13. Officer Cockpit Specification

Built with Next.js 14, Tailwind CSS and Framer Motion. Single route carries the entire review experience so nothing is lost to navigation.

### 13.1 Layout

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [STEPPER]: 1. Ingest  ➔  2. Facts (Verified)  ➔  3. Scenes  ➔  [ 4. OFFICER APPROVAL ] ➔ 5. Render│
├───────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│           SOURCE DOCUMENT VIEWER              │            FACT VERIFICATION MATRIX             │
│                                               │                                                 │
│ [PDF Page 1]                                  │  [SCHEME]  PM-KISAN                  [✓ Match]  │
│ "...disbursement of the seventeenth           │  [AMOUNT]  ₹2,000                    [✓ Match]  │
│ installment scheduled for October 5th..."     │  [DATE]    October 5th, 2026         [✓ Match]  │
│ (Yellow bounding box highlights source text)  │  [ACTION]  Complete e-KYC by Sep 30  [Edit]     │
├───────────────────────────────────────────────┴─────────────────────────────────────────────────┤
│ STORYBOARD & MULTILINGUAL SCENES: [ English ] [ हिंदी ] [ தமிழ் ]                              │
│ ┌───────────────────────────┐ ┌───────────────────────────┐ ┌─────────────────────────────────┐ │
│ │ Scene 1: Announcement     │ │ Scene 2: Benefit Card     │ │ Scene 3: Deadline Alert         │ │
│ │ Spoken Script (Editable)  │ │ Metric: [ ₹2,000 ]        │ │ Alert Date: [ 30 Sep 2026 ]     │ │
│ │ Duration: ~6.8s           │ │ Duration: ~8.4s           │ │ Duration: ~7.1s                 │ │
│ └───────────────────────────┘ └───────────────────────────┘ └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [EXPANDABLE TELEMETRY DRAWER]: ⚡ Grounding: 98.4% | NLI Entailment: 0.96 | Speech Drift: 0.00s  │
│ [ACTION BAR]: Voice: [ hi-IN-Madhur (Male) ▼ ]  Speed: [ 1.0x ▼ ]  [ APPROVE & RENDER VIDEO ]  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Component contracts

| Component | Props | Key behaviour |
|---|---|---|
| `PdfCanvas` | `jobId`, `activeSpan` | Renders via pdf.js, draws a yellow rect for `activeSpan`, scrolls it into view with a 300 ms spring |
| `FactMatrix` | `facts[]`, `onSelect`, `onOverride` | Row states: verified (green tick), low confidence (amber), unverified (red), overridden (blue pencil) |
| `StoryboardCard` | `scene`, `lang`, `onEdit` | Inline `contentEditable` script, live character counter against the budgets in 7.3 |
| `TelemetryDrawer` | `telemetry` | Collapsed by default, expands to per-metric breakdown with the formulas in section 14 |
| `LanguageTabs` | `languages[]`, `warnings` | Amber dot on a tab whose entity preservation is below 1.0 |
| `ActionBar` | `job`, `onApprove` | Approve button disabled until every fact is verified or overridden |

### 13.3 Interaction specifications

**Click-to-source highlighting.** Clicking a fact card sets `activeSpan = {page, char_start, char_end}`. `PdfCanvas` resolves the character range to bounding boxes using the span table from `raw_text.json`, unions them into a single rectangle per line, and animates the scroll. The reverse direction is also supported: selecting text in the canvas emits a character range, and every fact overlapping that range pulses in the matrix.

**Inline edit propagation.** Editing a value in the matrix issues the `PATCH` described in 11.2. The UI immediately marks affected storyboard cards with a shimmer skeleton, then swaps in the re-translated text when the response returns. Cards that were not affected must not flicker, because visible churn on untouched content erodes the officer's trust in the edit being surgical.

**Live audio preview.** `POST /preview-audio` synthesises a single scene. Playback drives a karaoke highlight over the script text using the same `WordTimestamp` array the renderer will use, so what the officer hears and sees in preview is exactly what the MP4 will contain.

**Approval.** The button is disabled while any fact has `is_verified=false` and no `officer_override`. The disabled state carries a tooltip naming the specific blocking facts. A disabled button with no explanation is the most common cause of a stalled demo.

### 13.4 State management

A single `useJob(jobId)` hook owns the job object, subscribes to the WebSocket, and applies server events as reducer actions. No component holds a second copy of job state. Optimistic updates are applied for text edits only, and are reverted on error with a toast.

---

## 14. Verification and Telemetry

The telemetry drawer is not decoration. It is the argument that the output is trustworthy, and it is what separates this from a text-to-video toy.

### 14.1 Metric definitions

| Metric | Formula | Target | Interpretation |
|---|---|---|---|
| `ocr_latency_sec` | Wall clock of stage 1 | < 2.0 s per page | Ingestion responsiveness |
| `extraction_confidence_avg` | Mean of `confidence_score` over all facts | > 0.85 | Model self-assessment, weakest of the five |
| Grounding rate | `verified_facts / total_facts` | > 0.95 | Fraction whose `raw_value` is an exact source substring |
| `nli_entailment_score` | Mean entailment probability over all core-fact segments | > 0.90 | Whether generated narration is entailed by the source |
| `entity_preservation_rate` | `entities_present_in_output / entities_masked` | 1.00 | Translation integrity, must be exactly 1.0 |
| `speech_visual_drift_ms` | `max abs(caption_start - word_start)` over all words | < 20 ms | Structurally 0 when using WordBoundary timings |

### 14.2 Grounding verification (deterministic)

Runs after every extraction and after every officer edit:

```python
def grounding_rate(facts, full_text):
    ok = sum(
        1 for f in facts
        if f.officer_override is not None
        or full_text[f.source_char_start:f.source_char_end] == f.raw_value
    )
    return ok / max(len(facts), 1)
```

### 14.3 NLI entailment verification (model-based)

Premise is the source paragraph containing the fact span, hypothesis is the generated core-fact sentence. Use a small multilingual NLI model (`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`) loaded in an ephemeral CPU subprocess so it never competes for VRAM with Qwen.

- Score above `NLI_THRESHOLD` (0.85): scene passes
- Score between 0.60 and 0.85: scene is flagged amber, officer sees the premise and hypothesis side by side
- Score below 0.60: scene blocks approval until edited

Entailment is checked against English master scenes only. Running it per language multiplies cost for little additional signal, since entity-locked translation cannot introduce a new claim, only mangle an existing one, and that is what `entity_preservation_rate` measures.

### 14.4 Reporting

Telemetry is computed once at approval time, persisted into `state.json`, and included in the API response. It is never recomputed at render time, so the numbers an officer approved are the numbers attached to the artefact.

---

## 15. Failure Modes and Fallbacks

| Failure | Detection | Fallback | Degradation visible to user |
|---|---|---|---|
| Missing Devanagari or Tamil glyphs (tofu) | Glyph coverage check at render start | Bundled Noto fonts in `assets/fonts/`, per-script fallback chain | None if fonts bundled |
| Internet loss during TTS | `TTS_TIMEOUT_SEC` exceeded | Local `facebook/mms-tts-hin` / `mms-tts-tam` subprocess, 450 MB VRAM | Slightly lower voice quality, no word boundaries so captions fall back to segment-level timing |
| edge-tts rejects SSML | Non-2xx or missing prosody effect | Per-segment synthesis and concatenation (8.5) | None |
| Ollama unreachable | Connection refused on dispatch | Rule-based regex extractor for `AMOUNT`, `DEADLINE`, `SCHEME_NAME` | Fewer facts, lower confidence, clearly flagged |
| Translation API rate limited | HTTP 429 from `deep_translator` | Exponential backoff, then local IndicTrans2 if provisioned, then English-only output | Language tabs greyed out with reason |
| NVENC unavailable | `ffmpeg -encoders` probe at startup | `libx264 -preset veryfast` | Render time roughly 3x longer |
| CUDA out of memory | Worker exits 137 or raises OOM | Retry once with `num_ctx` halved, then CPU inference | Extraction latency rises to roughly 25 s |
| PDF is a scanned image | Embedded text below threshold | PaddleOCR path with angle classification | Slower ingestion, lower grounding precision |
| Scene exceeds 48 s total | Duration check post-synthesis | Re-script with compression instruction, drop scene 4 if still over | Shorter video |
| Corrupt `state.json` | JSON parse error on resume | Restore from `state.json.bak` written before each transition | Loss of last transition only |

**Demo-day golden cache.** Three government circulars (PM-KISAN instalment, an e-KYC deadline notice, and a subsidy revision) are pre-rendered in all six languages and stored under `tests/golden/`. `DEMO_MODE=true` serves these instantly. This is the last line of defence and it should be verified working at T+19:00, not discovered broken at T+23:30.

---

## 16. Testing and Acceptance Criteria

### 16.1 Unit tests

| Test | Asserts |
|---|---|
| `test_grounding.py` | `repair_offsets` recovers correct spans for 20 synthetic facts including duplicates |
| `test_entity_lock.py` | Nested entities ("KISAN" inside "PM-KISAN") mask correctly under length-descending order |
| `test_ssml_compiler.py` | Every `core_fact` segment yields a `prosody` tag and a break of at least 300 ms |
| `test_kenburns.py` | `zoom(0) == 1.0`, `zoom(D) == Z_max`, crop box stays inside source bounds for all t |
| `test_timing.py` | `scene_duration_sec` always exceeds `subtitles[-1].end_sec` |
| `test_schema_sync.py` | Generated TypeScript types match the current Pydantic schema hash |

### 16.2 Integration tests

1. Upload golden PDF, assert job reaches `AWAITING_APPROVAL` in under 25 s
2. Assert grounding rate above 0.95 on all three golden circulars
3. `POST /render` without approval returns 409
4. Apply a fact override, assert exactly the linked scenes are marked stale and no others
5. Full render for `en` and `hi`, assert both MP4s play, are between 30 and 45 s, and contain an audio stream

### 16.3 Acceptance criteria (definition of done for the sprint)

- [ ] A previously unseen government circular produces a watchable Hindi video end to end with no code changes
- [ ] Every claim spoken in the video traces to a highlighted span in the source PDF via one click
- [ ] Rendering is blocked until an officer approves, enforced server-side
- [ ] An officer edit propagates to all languages without a full pipeline re-run
- [ ] No tofu glyphs in any of the six languages
- [ ] Telemetry drawer shows five live metrics, none hardcoded
- [ ] Peak VRAM never exceeds 5.0 GB, verified with `nvidia-smi --query-gpu=memory.used --format=csv -l 1`

---

## 17. Performance Budget and Tuning

### 17.1 End-to-end budget, 4 scenes, single language

| Stage | Budget | Notes |
|---|---|---|
| OCR (3-page notice) | 4.2 s | CPU-bound, parallelisable across pages |
| Fact extraction | 2.8 s | One LLM call |
| Scene scripting | 3.2 s | One LLM call, reuses the loaded model if batched with extraction |
| Translation | 1.6 s | 4 scenes, network-bound |
| TTS | 3.2 s | 4 scenes at 0.8 s |
| Render | 18.0 s | 4 scenes at 4.5 s |
| **Total** | **≈ 33 s** | Officer review time excluded |

Each additional language adds roughly 24 s (translation, TTS, render), and languages render sequentially because NVENC sessions and CPU frame generation both saturate.

### 17.2 Tuning levers

| Lever | Effect | Cost |
|---|---|---|
| Batch extraction and scripting into one LLM call | Saves one 1.5 s model load | Longer prompt, higher schema-violation risk |
| Cache B-roll frames decoded to numpy | Saves 1.2 s per scene | 400 MB RAM per loop |
| Render at 24 fps instead of 30 | Saves roughly 20% of render time | Slightly less smooth Ken Burns |
| Pre-generate typography layers as PNG once per scene | Saves per-frame Pillow calls | None, do this by default |
| `-preset p1` on NVENC | Roughly 30% faster | Visibly softer text edges, not recommended |

**The single biggest win** is rendering static layers once and compositing them over moving B-roll per frame, rather than rebuilding every layer every frame. Layers 3, 4 and 5 are static within a scene apart from the pill pulse; only layers 1 and 2 change per frame.

---

## 18. Execution Plan and Ownership

```
[00:00 - 03:00] Pipeline Initialization
  ├─ [Team] Lock Pydantic Schemas (`schemas.py`) across all repositories.
  ├─ [M1] Configure PaddleOCR + Ollama `qwen2.5:7b` JSON mode.
  ├─ [M2] Test `edge-tts` SSML prosody compiler and subtitle timing output.
  ├─ [M3] Scaffold Next.js dashboard layout with dummy JSON data.
  └─ [M4] Build MoviePy/FFmpeg 5-layer video compositor script.

[03:00 - 08:00] Core Subsystems
  ├─ [M1] Build grounded fact extraction with character span offsets.
  ├─ [M2] Implement entity-locked translation pipeline (Hindi, Tamil, Telugu).
  ├─ [M3] Build split-screen PDF viewer + fact matrix with click-to-highlight.
  └─ [M4] Implement Ken Burns zoom + karaoke subtitle rendering overlay.

[08:00 - 14:00] Integration & Verification
  ├─ [M1+M2] Wire FastAPI backend endpoints to orchestrate subprocess workers.
  ├─ [M3] Integrate editable storyboard cards and live audio waveform preview.
  └─ [M4] Connect asset manifest matcher to automatically bind B-roll by tags.

[14:00 - 19:00] End-to-End Orchestration & Polish
  ├─ [All] Connect UI approval button to trigger final multi-scene video stitcher.
  ├─ [M3] Build expandable telemetry drawer with NLI scores and latency stats.
  └─ [M2] Add sound design (background news bed audio ducking + transition whooshes).

[19:00 - 22:00] Demo Hardening & Fallbacks
  ├─ [All] Pre-render and cache 3 "Golden Sample" government circulars.
  ├─ [M1] Fix Unicode font rendering for Devanagari and Tamil scripts in video cards.
  └─ [M3] Add one-click "Demo Mode" toggle that loads cached jobs instantly.

[22:00 - 24:00] Rehearsal & Feature Freeze
  └─ [Team] Rehearse live pitch: PDF Upload ➔ Grounding ➔ Officer Edit ➔ Instant Playback.
```

### 18.1 Critical path

The critical path is **schema lock (T+03:00) → fact extraction (T+08:00) → orchestration wiring (T+14:00) → golden cache (T+22:00)**. Everything else has slack. If any of those four slips, cut scope rather than compressing the ones downstream.

### 18.2 Risk register

| Risk | Probability | Impact | Owner | Mitigation deadline |
|---|---|---|---|---|
| edge-tts SSML unsupported | High | High | M2 | T+00:30, fall back to per-segment synthesis |
| Indic font rendering broken in Pillow | High | High | M4 | T+02:00, run the typography selftest before building anything else |
| Schema churn after lock | Medium | High | Team | T+03:00 freeze, changes require all four present |
| Qwen ignores JSON schema mode | Medium | High | M1 | T+00:30, add brace-repair parser |
| Render too slow for live demo | Medium | Medium | M4 | T+19:00 golden cache |
| Translation API rate limits mid-demo | Low | High | M2 | Pre-translate golden samples |

### 18.3 Scope cut order

If time runs short, cut in this order and no other:

1. Bengali and Marathi (keep en, hi, ta, te)
2. Sound design and transition whooshes
3. Scene 4 outro (three-beat video is still complete)
4. NLI entailment (keep deterministic grounding, which is cheaper and more convincing)
5. Reverse highlighting (PDF selection to fact); keep forward highlighting

Never cut: the officer gate, deterministic grounding, or bundled fonts. Those three are the product.

---

## 19. Demo Runbook

**Pre-flight, T minus 30 minutes**

```bash
nvidia-smi                                   # expect < 500 MB used at idle
ollama list | grep qwen2.5                   # model present
ffmpeg -encoders | grep nvenc                # encoder present
python compositor/typography.py --selftest   # inspect the PNG, no tofu
curl localhost:8000/api/assets               # manifest loads
ls tests/golden/*/out/*.mp4 | wc -l          # expect 18 (3 circulars x 6 languages)
```

Close every other GPU consumer. A second browser profile with hardware acceleration on can cost 600 MB of VRAM and turn a working demo into an OOM.

**The four-minute run**

| Time | Action | What to say |
|---|---|---|
| 0:00 | Upload the PM-KISAN circular | "This is a real circular, published last week, entirely in English" |
| 0:30 | Facts appear, click one | "Every fact is clickable and lands on the exact line it came from. Nothing here is summarised, it is extracted" |
| 1:15 | Point at the telemetry drawer | "98.4% grounding, and this number is computed by string comparison, not by asking the model if it was honest" |
| 1:45 | Edit a deadline value | "The officer has authority. One edit, and it propagates to all six languages" |
| 2:30 | Switch to the Tamil tab, play preview | "The scheme name and the rupee amount are byte-identical to the source. Only the narration was translated" |
| 3:00 | Approve and render | "Nothing was synthesised until a human approved it. That gate is enforced by the server, not the interface" |
| 3:30 | Play the finished Hindi video | Say nothing, let it play |

**If something breaks:** switch `DEMO_MODE=true` and continue narrating from the cached job. Do not debug on stage. The story is the architecture, not the uptime.

---

## 20. Troubleshooting Guide

**Empty rectangles instead of Hindi or Tamil text in the video**
The font passed to Pillow lacks those codepoints. Pillow does not fall back automatically. Load the script-specific Noto file from `assets/fonts/` based on the target language, and never rely on a system font path that exists on one laptop and not another.

**Captions drift out of sync with the voice**
Confirm the subtitles were built from `WordBoundary` events and not estimated from character counts. Also confirm `scene_duration_sec` is derived from the audio and the audio was not re-encoded at a different sample rate after timestamps were captured.

**Video plays in VLC but not on WhatsApp or iOS**
Missing `-pix_fmt yuv420p`, or an odd pixel dimension. Both are silent failures on desktop players.

**CUDA out of memory when the LLM worker starts**
A previous worker did not exit. Check `nvidia-smi` for orphaned python processes. This is exactly the failure the ephemeral worker pattern exists to prevent, so an orphan means something is holding the process open, usually an unclosed asyncio loop or a non-daemon thread.

**Fact highlights land on the wrong text**
Whitespace normalisation happened after offsets were computed, or the page offset table was built from a different text concatenation than the one stored in `raw_extracted_text`. There must be exactly one canonical document string.

**Translation returns the mask token in the output**
The translator split or altered the sentinel. Switch to an alphanumeric sentinel and keep the tolerant regex as a recovery path. Log every unrecovered token, since a silently missing entity is far worse than a visible one.

**Render hangs with no output and no error**
Classic pipe buffer deadlock. The parent is reading stdout while the child fills stderr, or the reverse. Drain both streams concurrently.

**Scene text overflows its card**
The character budgets in 7.3 were not enforced for the Indic path. Indic budgets are lower than Latin. Measure with the actual font at the actual point size rather than counting characters, if time allows.

---

## 21. Security and Compliance Notes

| Concern | Position |
|---|---|
| Data residency | All processing is local except edge-tts and the translation API. For a production government deployment both must move to on-premise (IndicTrans2 and a local TTS) |
| PII | Circulars may name officers or beneficiaries. Facts of category `BENEFICIARY` should be treated as categories, never individual names |
| Attribution | Every output video carries the source circular number and issuing authority in scene 4 |
| Tamper evidence | `state.json` records the approving officer, timestamp, and a SHA-256 of the source PDF. Consider signing the final MP4 in production |
| Impersonation | Synthetic voices are generic TTS voices. Never clone the voice of a named official, and label the video as computer-narrated |
| Asset licensing | Every B-roll asset must have its licence recorded in `assets/LICENCES.md` before it enters the manifest |
| Upload safety | PDFs are parsed with PyMuPDF only. No JavaScript execution, no embedded file extraction, 20 MB cap |

---

## 22. Known Limitations and Roadmap

### 22.1 Current limitations

1. **Single-notice scope.** The pipeline handles one circular per job. Multi-circular digests are not modelled.
2. **Fixed narrative structure.** Three or four beats works for scheme announcements and fails for procedural notices with many steps.
3. **Network dependency.** edge-tts and the translation API both require internet. The local fallbacks are noticeably lower quality.
4. **No layout understanding.** Tables in circulars (slab-wise subsidy rates, for example) are flattened to text and often extract poorly.
5. **English source assumed.** A Hindi-source circular will OCR but the extraction prompt and master scenes assume English.
6. **Single officer.** No role hierarchy, no audit of who reviewed what beyond one name field.

### 22.2 Roadmap

| Horizon | Item |
|---|---|
| Next sprint | Table-aware extraction, per-language scene budgets measured in rendered pixels |
| Next sprint | Full offline mode with IndicTrans2 and local TTS |
| Quarter | Multi-officer workflow with maker-checker approval |
| Quarter | Vertical 9:16 output for WhatsApp status and Instagram Reels |
| Quarter | Sign language avatar track for accessibility |
| Longer | Direct integration with department publishing pipelines |

---

## 23. Appendices

### Appendix A: Sample `state.json` (abridged)

```json
{
  "job_id": "job_101",
  "source_file_name": "pm_kisan_17th_installment.pdf",
  "target_languages": ["en", "hi", "ta"],
  "selected_voice_id": "hi-IN-MadhurNeural",
  "voice_speed_modifier": "+0%",
  "extracted_facts": [
    {
      "fact_id": "f1",
      "category": "SCHEME_NAME",
      "raw_value": "PM-KISAN",
      "normalized_value": "PM-KISAN",
      "source_page": 1,
      "source_char_start": 118,
      "source_char_end": 126,
      "confidence_score": 0.98,
      "is_verified": true,
      "officer_override": null
    },
    {
      "fact_id": "f2",
      "category": "AMOUNT",
      "raw_value": "Rs 2000",
      "normalized_value": "₹2,000",
      "source_page": 1,
      "source_char_start": 402,
      "source_char_end": 409,
      "confidence_score": 0.96,
      "is_verified": true,
      "officer_override": null
    }
  ],
  "master_scenes_en": [
    {
      "scene_id": 2,
      "template_type": "METRIC_FOCUS",
      "script_segments": [
        {"type": "filler", "text": "Eligible farmers will receive",
         "emphasis_level": "none", "pause_after_ms": 0, "linked_fact_id": null},
        {"type": "core_fact", "text": "two thousand rupees",
         "emphasis_level": "strong", "pause_after_ms": 350, "linked_fact_id": "f2"},
        {"type": "filler", "text": "directly in their bank account.",
         "emphasis_level": "none", "pause_after_ms": 200, "linked_fact_id": null}
      ],
      "full_spoken_text": "Eligible farmers will receive two thousand rupees directly in their bank account.",
      "visual_hierarchy": {
        "badge_tag": "DIRECT BENEFIT TRANSFER",
        "headline": "₹2,000 per eligible farmer",
        "subtext": "Credited directly to the registered bank account",
        "highlight_metric": "₹2,000",
        "highlight_sublabel": "17th instalment"
      },
      "asset": {
        "asset_id": "broll_bank_transfer_01",
        "asset_type": "video_loop",
        "file_path": "assets/broll/digital_banking_loop.mp4",
        "dim_overlay_opacity": 0.70
      },
      "audio_path": "jobs/job_101/audio/hi/scene_2.mp3",
      "scene_duration_sec": 8.42,
      "subtitles": [
        {"word": "Eligible", "start_sec": 0.0, "end_sec": 0.48, "is_core_fact": false},
        {"word": "two", "start_sec": 1.62, "end_sec": 1.88, "is_core_fact": true}
      ]
    }
  ],
  "telemetry": {
    "ocr_latency_sec": 4.21,
    "extraction_confidence_avg": 0.94,
    "nli_entailment_score": 0.96,
    "entity_preservation_rate": 1.0,
    "speech_visual_drift_ms": 0.0
  },
  "officer_approved": true,
  "final_video_paths": {"hi": "jobs/job_101/out/notice_hi.mp4"}
}
```

### Appendix B: Scene scripting prompt

```python
SCENE_SCRIPTING_SYSTEM_PROMPT = """You are a broadcast scriptwriter for government public service announcements.

Given a list of verified facts, produce exactly 3 or 4 scenes as JSON conforming to SceneDefinition.

Rules:
1. Use ONLY the provided facts. Introduce no new numbers, dates, names, or claims.
2. Every sentence containing a fact value must be split so that the fact value
   is its own segment with type="core_fact" and the correct linked_fact_id.
3. Spoken text per scene: 18 to 28 words. Plain, direct, no bureaucratic phrasing.
4. Speak numbers as words in full_spoken_text; keep digits in visual_hierarchy.
5. headline max 58 characters, subtext max 96 characters.
6. Scene order is fixed: HERO_ANNOUNCEMENT, METRIC_FOCUS, DEADLINE_ALERT,
   then OUTRO_CALL_TO_ACTION only if an ACTION_REQUIRED fact exists.
"""
```

### Appendix C: Font matrix

| Language | Script | Font file | Fallback |
|---|---|---|---|
| en | Latin | `NotoSans-Bold.ttf` | System sans |
| hi, mr | Devanagari | `NotoSansDevanagari-Bold.ttf` | None, must bundle |
| ta | Tamil | `NotoSansTamil-Bold.ttf` | None, must bundle |
| te | Telugu | `NotoSansTelugu-Bold.ttf` | None, must bundle |
| bn | Bengali | `NotoSansBengali-Bold.ttf` | None, must bundle |

### Appendix D: Colour tokens

| Token | Hex | Use |
|---|---|---|
| `caption.spoken` | `#FACC15` | Currently spoken word in karaoke layer |
| `caption.pending` | `#F8FAFC` | Not yet spoken |
| `caption.past` | `#94A3B8` | Already spoken |
| `accent.agriculture` | `#22C55E` | Metric card glow, agriculture assets |
| `accent.finance` | `#38BDF8` | Metric card glow, finance assets |
| `accent.alert` | `#EF4444` | Deadline alert pill and glow |
| `overlay.dim` | `#000000` at 65 to 75% | B-roll dimming |

### Appendix E: Command reference

```bash
# Start everything
ollama serve &
uvicorn api.main:app --port 8000 &
python mcp_server/media_tools.py &
cd web && npm run dev

# Run one stage manually
python workers/ocr_worker.py    --job_id job_101
python workers/llm_worker.py    --job_id job_101
python workers/tts_worker.py    --job_id job_101 --lang hi
python workers/render_worker.py --job_id job_101 --lang hi

# Watch VRAM during a run
nvidia-smi --query-gpu=memory.used --format=csv -l 1

# Rebuild golden cache
python scripts/build_golden_cache.py --all-languages
```

---

*End of document. Schema version 1.0, frozen at T+03:00. Any change to `models/schemas.py` requires a matching revision of sections 7, 11 and 13.*