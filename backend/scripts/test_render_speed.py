import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.scene_generator import build_scenes_from_facts
from services.translator import localize_scenes
from compositor import layers
from models.schemas import ExtractedFact, FactCategory, WordTimestamp

facts = [
    ExtractedFact(
        fact_id="f1",
        category=FactCategory.AUTHORITY,
        raw_value="Ministry of Agriculture",
        normalized_value="Ministry of Agriculture & Farmers Welfare",
        source_page=1, source_char_start=0, source_char_end=23,
        confidence_score=0.98, is_verified=True,
    ),
    ExtractedFact(
        fact_id="f2",
        category=FactCategory.SCHEME_NAME,
        raw_value="PM-KISAN 17th installment",
        normalized_value="PM-KISAN 17th Installment",
        source_page=1, source_char_start=25, source_char_end=50,
        confidence_score=0.99, is_verified=True,
    ),
    ExtractedFact(
        fact_id="f3",
        category=FactCategory.AMOUNT,
        raw_value="Rs 2000",
        normalized_value="₹2,000",
        source_page=1, source_char_start=54, source_char_end=61,
        confidence_score=0.96, is_verified=True,
    ),
]

scenes_en = build_scenes_from_facts(facts)
for s in scenes_en:
    s.scene_duration_sec = 2.0  # 2.0s test
    words = s.full_spoken_text.split()
    s.subtitles = [
        WordTimestamp(word=w, start_sec=i * 0.25, end_sec=(i + 1) * 0.25)
        for i, w in enumerate(words)
    ]

out_test = Path("static/videos/test_speed_run.mp4")
print("[TEST] Starting benchmark render with live frame logging...")
layers.render_job(scenes_en[:1], "en", str(out_test))
print(f"[TEST SUCCESS] Rendered test MP4 to {out_test}")
