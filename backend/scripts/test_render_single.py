import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import (
    ExtractedFact,
    FactCategory,
    NoticeVideoJob,
    PipelineTelemetry,
)
from services.scene_generator import build_scenes_from_facts
from services.translator import localize_scenes
from services.audio_synthesizer import process_job_audio
from services.video_renderer import render_notice_video

async def main():
    print("[1] Building Job and Facts...")
    facts = [
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

    job = NoticeVideoJob(
        job_id="test_render_001",
        source_file_name="pmkisan.pdf",
        raw_extracted_text="Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000. Complete verification before 31-10-2026.",
        target_languages=["en", "hi"],
        selected_voice_id="en-IN-PrabhatNeural",
        voice_speed_modifier="+0%",
        extracted_facts=facts,
        master_scenes_en=[],
        localized_scenes={},
        telemetry=PipelineTelemetry(),
        officer_approved=True,
    )

    print("[2] Generating Scenes...")
    job.master_scenes_en = build_scenes_from_facts(job.extracted_facts)
    job.localized_scenes = localize_scenes(job.master_scenes_en, ["hi"])

    print("[3] Synthesizing Audio & Subtitle Timings...")
    job = await process_job_audio(job)

    print(f"Master Scenes count: {len(job.master_scenes_en)}")
    for s in job.master_scenes_en:
        print(f"Scene {s.scene_id} ({s.template_type.value}) dur: {s.scene_duration_sec}s, subtitles count: {len(s.subtitles or [])}")

    print("[4] Rendering Final Video (English)...")
    url_en = render_notice_video(job, "en")
    print(f"[SUCCESS] Rendered EN Video: {url_en}")

    print("[5] Rendering Final Video (Hindi)...")
    url_hi = render_notice_video(job, "hi")
    print(f"[SUCCESS] Rendered HI Video: {url_hi}")

if __name__ == "__main__":
    asyncio.run(main())
