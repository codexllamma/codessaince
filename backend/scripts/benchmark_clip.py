import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.scene_generator import build_scenes_from_facts
from compositor import layers, karaoke, kenburns
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
scene = scenes[0]
scene.scene_duration_sec = 2.0
words = scene.full_spoken_text.split()
scene.subtitles = [WordTimestamp(word=w, start_sec=i * 0.2, end_sec=(i + 1) * 0.2) for i, w in enumerate(words)]

canvas_size = (1920, 1080)
lang = "en"

t0 = time.time()
bg_source = layers.build_background_source(scene.asset, *canvas_size)
print(f"1. build_background_source took {time.time()-t0:.4f}s")

t0 = time.time()
bg_video = layers.build_background_video(scene.asset, *canvas_size)
print(f"2. build_background_video took {time.time()-t0:.4f}s")

t0 = time.time()
static_layers = layers.build_static_layers(scene, lang, canvas_size)
print(f"3. build_static_layers took {time.time()-t0:.4f}s")

t0 = time.time()
caption_layout = karaoke.build_caption_layout(scene.subtitles, lang, canvas_size)
print(f"4. build_caption_layout took {time.time()-t0:.4f}s")

t0 = time.time()
caption_cache = karaoke.build_caption_frame_cache(caption_layout)
print(f"5. build_caption_frame_cache took {time.time()-t0:.4f}s (Cache size: {len(caption_cache)})")

t0 = time.time()
from moviepy import VideoClip
frame_fn = layers.make_frame_function(
    scene, static_layers, caption_cache, bg_source, (0, 0, 0, 0), canvas_size, lang=lang
)
clip = VideoClip(frame_function=frame_fn, duration=scene.scene_duration_sec).with_fps(30)
print(f"6. VideoClip init took {time.time()-t0:.4f}s")
