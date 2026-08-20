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

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)
Path("static/audio").mkdir(parents=True, exist_ok=True)
Path("static/videos").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="IndicGov-Sentinel Server",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


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
  raw_extracted_text: str
  source_file_name: str = "notice.pdf"
  target_languages: List[Literal["en", "hi", "ta", "te", "bn", "mr"]] = [
      "en",
      "hi",
      "ta",
  ]
  selected_voice_id: str = "hi-IN-MadhurNeural"
  voice_speed_modifier: str = "+0%"


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

  job = NoticeVideoJob(
      job_id=job_id,
      source_file_name=payload.source_file_name,
      raw_extracted_text=payload.raw_extracted_text,
      target_languages=payload.target_languages,
      selected_voice_id=payload.selected_voice_id,
      voice_speed_modifier=payload.voice_speed_modifier,
      extracted_facts=[],
      master_scenes_en=[],
      localized_scenes={},
      telemetry=PipelineTelemetry(),
      officer_approved=False,
      final_video_paths={},
  )

  save_job(job)
  return job


@app.get("/api/jobs/{job_id}", response_model=NoticeVideoJob)
def get_job(job_id: str):
  return load_job(job_id)


@app.post("/api/jobs/{job_id}/extract-facts", response_model=NoticeVideoJob)
def extract_facts(job_id: str):
  job = load_job(job_id)

  mock_facts = [
      ExtractedFact(
          fact_id="f1",
          category=FactCategory.AUTHORITY,
          raw_value="Ministry of Agriculture",
          normalized_value="Ministry of Agriculture & Farmers Welfare",
          source_page=1,
          source_char_start=0,
          source_char_end=23,
          confidence_score=0.98,
          is_verified=True,
      ),
      ExtractedFact(
          fact_id="f2",
          category=FactCategory.SCHEME_NAME,
          raw_value="PM-KISAN 17th installment",
          normalized_value="PM-KISAN 17th Installment",
          source_page=1,
          source_char_start=38,
          source_char_end=63,
          confidence_score=0.99,
          is_verified=True,
      ),
      ExtractedFact(
          fact_id="f3",
          category=FactCategory.AMOUNT,
          raw_value="Rs 2000",
          normalized_value="₹2,000",
          source_page=1,
          source_char_start=67,
          source_char_end=74,
          confidence_score=0.96,
          is_verified=True,
      ),
      ExtractedFact(
          fact_id="f4",
          category=FactCategory.ACTION_REQUIRED,
          raw_value="Complete Aadhaar e-KYC",
          normalized_value="Complete Aadhaar-based e-KYC",
          source_page=1,
          source_char_start=102,
          source_char_end=124,
          confidence_score=0.95,
          is_verified=True,
      ),
      ExtractedFact(
          fact_id="f5",
          category=FactCategory.DEADLINE,
          raw_value="31-10-2026",
          normalized_value="31st October 2026",
          source_page=1,
          source_char_start=132,
          source_char_end=142,
          confidence_score=0.97,
          is_verified=True,
      ),
  ]

  job.extracted_facts = mock_facts
  if job.telemetry:
    job.telemetry.extraction_confidence_avg = 0.97
    job.telemetry.ocr_latency_sec = 1.15

  save_job(job)
  return job


@app.put("/api/jobs/{job_id}/facts", response_model=NoticeVideoJob)
def update_facts(job_id: str, payload: UpdateFactsRequest):
  job = load_job(job_id)
  job.extracted_facts = payload.extracted_facts
  save_job(job)
  return job


@app.post("/api/jobs/{job_id}/generate-scenes", response_model=NoticeVideoJob)
def generate_scenes(job_id: str):
  job = load_job(job_id)

  if not job.extracted_facts:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot generate scenes without extracted facts.",
    )

  master_en = build_scenes_from_facts(job.extracted_facts)
  job.master_scenes_en = master_en
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
def render_video(job_id: str):
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
    for lang in job.target_languages:
      if lang == "en" or lang in job.localized_scenes:
        video_url = render_notice_video(job, lang=lang)
        job.final_video_paths[lang] = video_url

    save_job(job)
    return job
  except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Video rendering failed: {str(e)}",
    )


if __name__ == "__main__":
  uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)