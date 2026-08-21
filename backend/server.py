import json
from pathlib import Path
from typing import Dict, List, Literal, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from models.schemas import (
    ExtractedFact,
    FactCategory,
    NoticeVideoJob,
    PipelineTelemetry,
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
    WordTimestamp,
)
from services.audio_synthesizer import process_job_audio
from services.scene_generator import build_scenes_from_facts
from services.video_renderer import render_notice_video
from services.translator import localize_scenes
from services.fact_extractor import extract_facts_from_text

from fastapi.responses import FileResponse
from PIL import Image
from services.video_renderer import render_scene_card_image

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)
Path("static/audio").mkdir(parents=True, exist_ok=True)
Path("static/videos").mkdir(parents=True, exist_ok=True)

from api.routes.upload import router as upload_router
from api.routes.warmup import router as warmup_router

app = FastAPI(
    title="IndicGov-Sentinel Server",
    version="1.0.0",
)

app.include_router(upload_router)
app.include_router(warmup_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/avatars", StaticFiles(directory="assets/avatars"), name="avatars")

# run_pipeline writes finished videos to out/, which nothing served. The
# /api/jobs/run-e2e response hands the browser that path, so without this
# mount the citizen-facing flow renders a video successfully and then has no
# way to play it.
Path("out").mkdir(parents=True, exist_ok=True)
app.mount("/out", StaticFiles(directory="out"), name="out")


def save_job(job: NoticeVideoJob) -> None:
  job_file = JOBS_DIR / f"{job.job_id}.json"
  with open(job_file, "w", encoding="utf-8") as f:
    f.write(job.model_dump_json(indent=2))


def load_job(job_id: str) -> NoticeVideoJob:
  job_file = JOBS_DIR / f"{job_id}.json"
  if not job_file.exists():
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job {job_id} not found on disk.",
    )
  with open(job_file, "r", encoding="utf-8") as f:
    data = json.load(f)
  return NoticeVideoJob.model_validate(data)


class CreateJobRequest(BaseModel):
  raw_extracted_text: Optional[str] = None
  source_file_name: str = "notice.pdf"
  target_languages: List[Literal["en", "hi", "ta", "te", "bn", "mr"]] = [
      "en",
      "hi",
      "ta",
  ]
  selected_voice_id: str = "hi-IN-MadhurNeural"
  voice_speed_modifier: str = "+0%"
  primary_lang: Optional[str] = None


class UpdateFactsRequest(BaseModel):
  extracted_facts: List[ExtractedFact]


class UpdateScenesRequest(BaseModel):
  language: Optional[str] = "en"
  scenes: List[SceneDefinition]


class ApproveJobRequest(BaseModel):
  approved: bool = True
  notes: Optional[str] = None


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
  return {"status": "HEALTHY"}


@app.post(
    "/api/jobs",
    response_model=NoticeVideoJob,
    status_code=status.HTTP_201_CREATED,
)
def create_job(payload: CreateJobRequest):
  existing_jobs = list(JOBS_DIR.glob("job_*.json"))
  job_id = f"job_{len(existing_jobs) + 1:03d}"

  raw_text = payload.raw_extracted_text or ""
  if payload.primary_lang:
      from ocr_engine.executor import run_ephemeral_ocr
      pdf_path = Path("ocr_engine") / f"extensive_test_{payload.primary_lang}.pdf"
      if not pdf_path.exists():
          pdf_path = Path("ocr_engine") / "complex_layout_test.pdf"
      
      try:
          ocr_result = run_ephemeral_ocr(str(pdf_path), lang=payload.primary_lang)
          raw_text = ocr_result.get("raw_text", "")
      except Exception as e:
          raise HTTPException(
              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
              detail=f"Failed to process local PDF for language {payload.primary_lang}: {e}"
          )

  job = NoticeVideoJob(
      job_id=job_id,
      source_file_name=payload.source_file_name,
      raw_extracted_text=raw_text,
      target_languages=payload.target_languages,
      selected_voice_id=payload.selected_voice_id,
      voice_speed_modifier=payload.voice_speed_modifier,
      extracted_facts=[],
      master_scenes_en=[],
      localized_scenes={},
      telemetry=PipelineTelemetry(),
      officer_approved=False,
      final_video_paths={},
      final_srt_paths={},
  )

  save_job(job)
  return job


@app.get("/api/jobs/{job_id}", response_model=NoticeVideoJob)
def get_job(job_id: str):
  return load_job(job_id)


@app.post("/api/jobs/{job_id}/extract-facts", response_model=NoticeVideoJob)
def extract_facts(job_id: str):
  job = load_job(job_id)

  extracted = extract_facts_from_text(job.raw_extracted_text)
  job.extracted_facts = extracted

  if job.telemetry:
    if extracted:
      avg_conf = sum(f.confidence_score for f in extracted) / len(extracted)
      job.telemetry.extraction_confidence_avg = round(avg_conf, 3)
    else:
      job.telemetry.extraction_confidence_avg = 0.0
    job.telemetry.ocr_latency_sec = 0.45

  save_job(job)
  return job



class GestureInfo(BaseModel):
  name: str
  role: str
  duration_sec: float


class AvatarInfo(BaseModel):
  avatar_id: str
  display_name: str
  languages: List[str]
  source: str
  licence: str
  disclosure_label: str
  gestures: List[GestureInfo]


@app.get("/api/avatars", response_model=List[AvatarInfo])
def list_avatars():
  """Registered presenters and the gestures each can perform.

  Surfaced so the approval step can tell an officer that a synthetic
  presenter will front the broadcast, and under what label. That is a
  disclosure question, not a cosmetic one — approving a video with a
  photoreal presenter without being told is exactly what the mandatory
  disclosure_label exists to prevent.

  An empty list is a normal response: with no avatars installed the
  compositor renders its full-width layout instead.
  """
  from compositor import gestures as gesture_mod
  from services import avatar_registry

  out: List[AvatarInfo] = []
  for avatar in avatar_registry.load_registry():
    vocab = gesture_mod.load_vocabulary(avatar.file_path)
    out.append(
        AvatarInfo(
            avatar_id=avatar.avatar_id,
            display_name=avatar.display_name,
            languages=list(avatar.languages),
            source=avatar.source,
            licence=avatar.licence,
            disclosure_label=avatar.disclosure_label,
            gestures=[
                GestureInfo(name=g.name, role=g.role, duration_sec=round(g.duration, 2))
                for g in (vocab.gestures if vocab else ())
            ],
        )
    )
  return out


# 1. Quick Image Preview Endpoint for Font Verification
@app.get("/api/test/preview-card/{lang}")
def preview_language_card(lang: str):
  valid_langs = ["en", "hi", "ta", "te"]
  if lang not in valid_langs:
    raise HTTPException(
        status_code=400,
        detail=f"Language must be one of {valid_langs}",
    )

  sample_hierarchies = {
      "en": VisualTextHierarchy(
          badge_tag="OFFICIAL NOTICE",
          headline="PM-KISAN 17th Installment",
          subtext="Ministry of Agriculture & Farmers Welfare",
          highlight_metric="₹2,000",
          highlight_sublabel="Direct Benefit Transfer",
      ),
      "hi": VisualTextHierarchy(
          badge_tag="आधिकारिक सूचना",
          headline="पीएम-किसान 17वीं किस्त जारी",
          subtext="कृषि एवं किसान कल्याण मंत्रालय",
          highlight_metric="₹2,000",
          highlight_sublabel="प्रत्यक्ष लाभ अंतरण",
      ),
      "ta": VisualTextHierarchy(
          badge_tag="அதிகாரப்பூர்வ அறிவிப்பு",
          headline="பிஎம்-கிசான் 17வது தவணை வெளியீடு",
          subtext="வேளாண்மை மற்றும் விவசாயிகள் நல அமைச்சகம்",
          highlight_metric="₹2,000",
          highlight_sublabel="நேரடி பலன் பரிமாற்றம்",
      ),
      "te": VisualTextHierarchy(
          badge_tag="అధికారిక ప్రకటన",
          headline="పీఎం-కిసాన్ 17వ విడత విడుదల",
          subtext="వ్యవసాయ మరియు రైతు సంక్షేమ మంత్రిత్వ శాఖ",
          highlight_metric="₹2,000",
          highlight_sublabel="ప్రత్యక్ష ప్రయోజన బదిలీ",
      ),
  }

  sample_spoken = {
      "en": (
          "Official notice: PM-KISAN 17th installment has been transferred"
          " directly to beneficiary accounts."
      ),
      "hi": (
          "आधिकारिक सूचना: पीएम-किसान की 17वीं किस्त सीधे लाभार्थियों के खातों"
          " में स्थानांतरित कर दी गई है।"
      ),
      "ta": (
          "அதிகாரப்பூர்வ அறிவிப்பு: பிஎம்-கிசான் 17வது தவணை பயனாளிகளின்"
          " கணக்குகளுக்கு நேரடியாக மாற்றப்பட்டுள்ளது."
      ),
      "te": (
          "అధికారిక ప్రకటన: పీఎం-కిసాన్ 17వ విడత నేరుగా లబ్ధిదారుల ఖాతాలకు బదిలీ"
          " చేయబడింది."
      ),
  }

  dummy_scene = SceneDefinition(
      scene_id=1,
      template_type=TemplateType.METRIC_FOCUS,
      script_segments=[
          ScriptSegment(type="filler", text=sample_spoken[lang])
      ],
      full_spoken_text=sample_spoken[lang],
      visual_hierarchy=sample_hierarchies[lang],
      asset=VisualAssetSelection(
          asset_id="default",
          asset_type="static_graphic",
          file_path="",
      ),
  )

  img_array = render_scene_card_image(dummy_scene, lang=lang)
  output_preview_path = Path(f"static/preview_{lang}.png")
  Image.fromarray(img_array).save(output_preview_path)

  return FileResponse(output_preview_path, media_type="image/png")


@app.post("/api/jobs/{job_id}/generate-scenes", response_model=NoticeVideoJob)
def generate_scenes(job_id: str):
  job = load_job(job_id)

  if not job.extracted_facts:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot generate scenes without extracted facts.",
    )

  # 1. Build Master English Scenes
  master_en = build_scenes_from_facts(job.extracted_facts)
  job.master_scenes_en = master_en

  # 2. Localize for requested target languages (hi, ta, te, bn, mr)
  job.localized_scenes = localize_scenes(master_en, job.target_languages)

  save_job(job)
  return job


@app.put("/api/jobs/{job_id}/facts", response_model=NoticeVideoJob)
def update_facts(job_id: str, payload: UpdateFactsRequest):
  job = load_job(job_id)
  job.extracted_facts = payload.extracted_facts
  save_job(job)
  return job



@app.put("/api/jobs/{job_id}/scenes", response_model=NoticeVideoJob)
def update_scenes(job_id: str, payload: UpdateScenesRequest):
  job = load_job(job_id)
  lang = payload.language or "en"

  if lang == "en":
    job.master_scenes_en = payload.scenes
  else:
    job.localized_scenes[lang] = payload.scenes

  save_job(job)
  return job


@app.post("/api/jobs/{job_id}/synthesize", response_model=NoticeVideoJob)
async def synthesize_media(job_id: str):
  job = load_job(job_id)

  if not job.master_scenes_en:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Master scenes must be generated before audio synthesis.",
    )

  try:
    updated_job = await process_job_audio(job)
    save_job(updated_job)
    return updated_job
  except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Audio synthesis failed: {str(e)}",
    )


@app.post("/api/jobs/{job_id}/approve", response_model=NoticeVideoJob)
def approve_job(job_id: str, payload: ApproveJobRequest):
  job = load_job(job_id)
  job.officer_approved = payload.approved
  save_job(job)
  return job





@app.post("/api/jobs/{job_id}/render", response_model=NoticeVideoJob)
def render_video(job_id: str, lang: Optional[str] = None, avatar_id: Optional[str] = None):
  job = load_job(job_id)

  if not job.officer_approved:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Officer approval required before rendering video.",
    )

  if not job.master_scenes_en or not job.master_scenes_en[0].audio_path:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Audio synthesis must be completed prior to final video rendering."
        ),
    )

  try:
    langs_to_render = [lang] if lang else job.target_languages
    print(f"\n=======================================================", flush=True)
    print(f"[API RENDER] Job ID: {job.job_id} | Rendering languages: {langs_to_render}", flush=True)
    print(f"=======================================================", flush=True)

    for l in langs_to_render:
      if l == "en" or l in job.localized_scenes:
        video_url = render_notice_video(job, lang=l, avatar_id=avatar_id)
        job.final_video_paths[l] = video_url
        job.final_srt_paths[l] = f"/static/videos/{job.job_id}_final_{l}.srt"

    save_job(job)
    return job
  except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Video rendering failed: {str(e)}",
    )


if __name__ == "__main__":
  uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)