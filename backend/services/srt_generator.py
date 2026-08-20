"""External SRT (SubRip) subtitle generator for multi-scene notice deliverables.

Generates broadcast-compliant .srt files with cumulative multi-scene timestamps,
natural phrasing, and millisecond accuracy.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from models.schemas import SceneDefinition, WordTimestamp


def _format_srt_time(seconds: float) -> str:
    """Format float seconds to SRT time string: HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    hours = total_ms // (3600 * 1000)
    remainder = total_ms % (3600 * 1000)
    minutes = remainder // (60 * 1000)
    remainder %= 60 * 1000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_content(scenes: List[SceneDefinition]) -> str:
    """Constructs complete SRT subtitle file content from a sequence of scenes."""
    srt_blocks: List[str] = []
    cue_index = 1
    cumulative_offset = 0.0

    for scene in scenes:
        scene_dur = scene.scene_duration_sec or 6.0
        words = scene.subtitles or []

        if words:
            # Group words into natural subtitle chunks (approx 5-8 words per cue)
            chunk_size = 7
            for i in range(0, len(words), chunk_size):
                chunk = words[i : i + chunk_size]
                if not chunk:
                    continue

                cue_start = cumulative_offset + chunk[0].start_sec
                cue_end = cumulative_offset + chunk[-1].end_sec
                # Ensure minimum cue duration for readability
                if cue_end <= cue_start:
                    cue_end = cue_start + 1.2

                cue_text = " ".join(w.word for w in chunk).strip()
                if cue_text:
                    time_header = f"{_format_srt_time(cue_start)} --> {_format_srt_time(cue_end)}"
                    srt_blocks.append(f"{cue_index}\n{time_header}\n{cue_text}\n")
                    cue_index += 1
        else:
            # Fallback to full scene text if word timestamps are not present
            cue_start = cumulative_offset
            cue_end = cumulative_offset + max(scene_dur - 0.2, 1.0)
            cue_text = scene.full_spoken_text.strip()
            if cue_text:
                time_header = f"{_format_srt_time(cue_start)} --> {_format_srt_time(cue_end)}"
                srt_blocks.append(f"{cue_index}\n{time_header}\n{cue_text}\n")
                cue_index += 1

        cumulative_offset += scene_dur

    return "\n".join(srt_blocks)


def export_srt_file(scenes: List[SceneDefinition], output_path: Path | str) -> str:
    """Generates and writes an .srt file to disk. Returns the absolute or relative file path."""
    content = generate_srt_content(scenes)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8")
    return str(out_file)
