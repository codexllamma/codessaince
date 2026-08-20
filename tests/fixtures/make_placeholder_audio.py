"""Generates placeholder audio for compositor fixtures.

Real synthesized audio (edge-tts, README §8.5) doesn't exist yet since the
TTS stage isn't built. .gitignore excludes *.wav, so this is regenerated at
dev/test time rather than committed. A quiet fading tone (not silence) gives
something audible to scrub against the hand-written word timestamps.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

AUDIO_DIR = Path(__file__).resolve().parent / "audio"


def make_tone_wav(path: Path, duration_sec: float, sr: int = 24000, freq_hz: float = 220.0) -> Path:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    tone = 0.15 * np.sin(2 * np.pi * freq_hz * t)
    fade = min(int(sr * 0.05), len(tone) // 4)
    if fade > 0:
        tone[:fade] *= np.linspace(0, 1, fade)
        tone[-fade:] *= np.linspace(1, 0, fade)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), tone.astype(np.float32), sr)
    return path


def ensure_fixture_audio(scene_id: int, lang: str, duration_sec: float, freq_hz: float = 220.0) -> str:
    """Idempotent: only regenerates if missing, so repeated test runs are cheap."""
    path = AUDIO_DIR / f"scene_{scene_id}_{lang}.wav"
    if not path.exists():
        make_tone_wav(path, duration_sec, freq_hz=freq_hz)
    return str(path)


if __name__ == "__main__":
    make_tone_wav(AUDIO_DIR / "scene_1_en.wav", 5.80, freq_hz=220.0)
    make_tone_wav(AUDIO_DIR / "scene_2_en.wav", 5.30, freq_hz=330.0)
    print(f"Wrote placeholder audio to {AUDIO_DIR}")
