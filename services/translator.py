import copy
from typing import Dict, List
from deep_translator import GoogleTranslator

from models.schemas import (
    SceneDefinition,
    ScriptSegment,
    VisualTextHierarchy,
)


def batch_translate_strings(
    texts: List[str], target_lang: str
) -> Dict[str, str]:
  unique_texts = [t for t in dict.fromkeys(texts) if t and t.strip()]
  if not unique_texts or target_lang == "en":
    return {t: t for t in texts}

  try:
    translator = GoogleTranslator(source="en", target=target_lang)
    translated_list = translator.translate_batch(unique_texts)
    return dict(zip(unique_texts, translated_list))
  except Exception as e:
    print(
        f"[WARN] Batch translation to {target_lang} failed: {e}. Keeping"
        " original text."
    )
    return {t: t for t in unique_texts}


def localize_scenes(
    master_scenes: List[SceneDefinition], target_languages: List[str]
) -> Dict[str, List[SceneDefinition]]:
  localized_map: Dict[str, List[SceneDefinition]] = {}

  # 1. Harvest all distinct strings across all master scenes
  raw_strings: List[str] = []
  for master in master_scenes:
    for seg in master.script_segments:
      if seg.text:
        raw_strings.append(seg.text)
    vh = master.visual_hierarchy
    if vh.badge_tag:
      raw_strings.append(vh.badge_tag)
    if vh.headline:
      raw_strings.append(vh.headline)
    if vh.subtext:
      raw_strings.append(vh.subtext)
    if vh.highlight_metric:
      raw_strings.append(vh.highlight_metric)
    if vh.highlight_sublabel:
      raw_strings.append(vh.highlight_sublabel)

  # 2. Perform 1 batch translation request per non-English target language
  for lang in target_languages:
    if lang == "en":
      continue

    lookup = batch_translate_strings(raw_strings, target_lang=lang)
    lang_scenes: List[SceneDefinition] = []

    for master in master_scenes:
      scene_copy = copy.deepcopy(master)

      translated_segments: List[ScriptSegment] = []
      translated_tokens = []
      for seg in master.script_segments:
        tr_text = lookup.get(seg.text, seg.text)
        translated_segments.append(
            ScriptSegment(
                type=seg.type,
                text=tr_text,
                emphasis_level=seg.emphasis_level,
                pause_after_ms=seg.pause_after_ms,
                linked_fact_id=seg.linked_fact_id,
            )
        )
        translated_tokens.append(tr_text)

      scene_copy.script_segments = translated_segments
      scene_copy.full_spoken_text = " ".join(translated_tokens)

      vh = master.visual_hierarchy
      scene_copy.visual_hierarchy = VisualTextHierarchy(
          badge_tag=lookup.get(vh.badge_tag, vh.badge_tag),
          headline=lookup.get(vh.headline, vh.headline),
          subtext=lookup.get(vh.subtext, vh.subtext),
          highlight_metric=lookup.get(vh.highlight_metric, vh.highlight_metric)
          if vh.highlight_metric
          else None,
          highlight_sublabel=lookup.get(
              vh.highlight_sublabel, vh.highlight_sublabel
          )
          if vh.highlight_sublabel
          else None,
      )

      # Reset media parameters for subsequent synthesis pass
      scene_copy.audio_path = None
      scene_copy.scene_duration_sec = None
      scene_copy.subtitles = None

      lang_scenes.append(scene_copy)

    localized_map[lang] = lang_scenes
    print(f"[OK] Batch localized {len(lang_scenes)} scenes for '{lang}'")

  return localized_map