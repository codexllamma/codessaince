import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.scene_generator import build_scenes_from_facts
from compositor import layers
from models.schemas import ExtractedFact, FactCategory, WordTimestamp

facts = [
    ExtractedFact(
        fact_id="f1", category=FactCategory.AUTHORITY, raw_value="Ministry of Agriculture",
        normalized_value="Ministry of Agriculture & Farmers Welfare", source_page=1,
        source_char_start=0, source_char_end=23, confidence_score=0.98, is_verified=True,
    ),
    ExtractedFact(
        fact_id="f2", category=FactCategory.SCHEME_NAME, raw_value="PM-KISAN 17th installment",
        normalized_value="PM-KISAN 17th Installment", source_page=1,
        source_char_start=25, source_char_end=50, confidence_score=0.99, is_verified=True,
    ),
]

scenes = build_scenes_from_facts(facts)
for s in scenes:
    s.scene_duration_sec = 1.5
    words = s.full_spoken_text.split()
    s.subtitles = [WordTimestamp(word=w, start_sec=i * 0.2, end_sec=(i + 1) * 0.2) for i, w in enumerate(words)]

t0 = time.time()
print(f"[{time.time()-t0:.2f}s] Resolving presenter...")
presenter_source, presenter_layout = layers.resolve_presenter("en", (1920, 1080))

print(f"[{time.time()-t0:.2f}s] Building clip 0...")
clip = layers.render_scene_clip(scenes[0], "en", 0, (1920, 1080), presenter_source, presenter_layout)

print(f"[{time.time()-t0:.2f}s] Writing videofile...")
t_write = time.time()
layers._write_with_fallback(clip, "static/videos/timing_test.mp4", "h264_nvenc")
print(f"[{time.time()-t0:.2f}s] Write took {time.time()-t_write:.2f}s")

print(f"[{time.time()-t0:.2f}s] Closing clip...")
t_close = time.time()
try:
    clip.close()
except Exception as e:
    print("Error on close:", e)
print(f"[{time.time()-t0:.2f}s] Close took {time.time()-t_close:.2f}s")
