"""Continuous narration: scene spans, scene-local subtitles, pauses, and wav format.

Nothing here touches the network: `narration._synthesize_segment` is the only
coroutine that talks to edge-tts, and every test swaps it for a fake that
returns real (silent) WAV bytes so the decode/resample/concat path still runs.
"""

import io

import numpy as np
import pytest
import soundfile as sf

from models.schemas import (
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
)
from services import narration
from services.audio_synthesizer import SCENE_TAIL_PAD_SEC

# edge-tts hands back 24 kHz audio; the fake mimics that so the resample to
# 16 kHz is exercised rather than short-circuited.
TTS_RATE = 24000
WORD_SEC = 0.3


# --- builders -------------------------------------------------------------


def _wav_bytes(duration_sec, sample_rate=TTS_RATE, channels=2):
    frames = int(round(duration_sec * sample_rate))
    buf = io.BytesIO()
    sf.write(
        buf, np.zeros((frames, channels), dtype=np.float32), sample_rate,
        format="WAV", subtype="PCM_16",
    )
    return buf.getvalue()


def _segment(text, type_="filler", emphasis="none", pause_ms=0):
    return ScriptSegment(
        type=type_,
        text=text,
        emphasis_level=emphasis,
        pause_after_ms=pause_ms,
        linked_fact_id="f1" if type_ == "core_fact" else None,
    )


def _scene(scene_id, segments):
    return SceneDefinition(
        scene_id=scene_id,
        template_type=TemplateType.HERO_ANNOUNCEMENT,
        script_segments=segments,
        full_spoken_text=" ".join(s.text for s in segments),
        visual_hierarchy=VisualTextHierarchy(
            badge_tag="TAG", headline="Headline", subtext="Subtext"
        ),
        asset=VisualAssetSelection(
            asset_id="a1", asset_type="mesh_gradient", file_path="assets/a1.png"
        ),
    )


def _fake_tts(monkeypatch, emit_boundaries=True, calls=None):
    """Replace the network seam. Each word lasts WORD_SEC exactly."""

    async def _synth(text, voice, rate, volume, pitch):
        if calls is not None:
            calls.append(
                {"text": text, "voice": voice, "rate": rate, "volume": volume, "pitch": pitch}
            )
        words = text.split()
        boundaries = [(w, i * WORD_SEC, (i + 1) * WORD_SEC) for i, w in enumerate(words)]
        audio = _wav_bytes(len(words) * WORD_SEC)
        return audio, (boundaries if emit_boundaries else [])

    monkeypatch.setattr(narration, "_synthesize_segment", _synth)


def _build(tmp_path, scenes, **kw):
    return narration.build_narration_sync(
        scenes=scenes, lang="en", out_wav=tmp_path / "narration.wav", **kw
    )


def _two_scenes():
    return [
        _scene(1, [_segment("alpha beta"), _segment("gamma delta", "core_fact")]),
        _scene(2, [_segment("epsilon zeta theta")]),
    ]


# --- spans ----------------------------------------------------------------


def test_spans_are_ordered_contiguous_and_non_overlapping(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, _two_scenes())

    assert [s.scene_id for s in timeline.spans] == [1, 2]
    assert timeline.spans[0].start_sec == pytest.approx(0.0)
    for earlier, later in zip(timeline.spans, timeline.spans[1:]):
        assert later.start_sec == pytest.approx(earlier.end_sec, abs=1e-3)
        assert earlier.end_sec > earlier.start_sec


def test_total_duration_matches_last_span_end(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, _two_scenes())
    assert timeline.total_duration_sec == pytest.approx(timeline.spans[-1].end_sec, abs=1e-3)


def test_scene_end_includes_the_tail_pad(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, [_scene(1, [_segment("one two")])])
    span = timeline.spans[0]
    assert span.end_sec == pytest.approx(2 * WORD_SEC + SCENE_TAIL_PAD_SEC, abs=1e-3)


def test_scenes_are_not_mutated(tmp_path, monkeypatch):
    """The caller assigns durations itself; we only report spans."""
    _fake_tts(monkeypatch)
    scenes = _two_scenes()
    _build(tmp_path, scenes)
    for scene in scenes:
        assert scene.scene_duration_sec is None
        assert scene.subtitles is None
        assert scene.audio_path is None


# --- subtitles ------------------------------------------------------------


def test_subtitle_times_are_scene_local(tmp_path, monkeypatch):
    """Scene 2 starts well into the stream, but its first word must read ~0."""
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, _two_scenes())

    second = timeline.spans[1]
    assert second.start_sec > 1.0, "precondition: scene 2 is offset in the stream"
    assert second.subtitles[0].start_sec == pytest.approx(0.0, abs=1e-3)
    assert second.subtitles[-1].end_sec < second.end_sec - second.start_sec + 1e-3


def test_segment_offsets_accumulate_within_a_scene(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, [_scene(1, [_segment("a b"), _segment("c d")])])
    starts = [s.start_sec for s in timeline.spans[0].subtitles]
    assert starts == pytest.approx([0.0, 0.3, 0.6, 0.9], abs=1e-3)


def test_core_fact_segments_flag_their_words(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(
        tmp_path,
        [_scene(1, [_segment("filler words here"), _segment("two thousand rupees", "core_fact")])],
    )
    flagged = {s.word for s in timeline.spans[0].subtitles if s.is_core_fact}
    plain = {s.word for s in timeline.spans[0].subtitles if not s.is_core_fact}
    assert flagged == {"two", "thousand", "rupees"}
    assert plain == {"filler", "words", "here"}


# --- fallback -------------------------------------------------------------


def test_fallback_emits_one_timestamp_per_word(tmp_path, monkeypatch):
    _fake_tts(monkeypatch, emit_boundaries=False)
    timeline = _build(tmp_path, [_scene(1, [_segment("one two three four", "core_fact")])])
    subs = timeline.spans[0].subtitles

    assert [s.word for s in subs] == ["one", "two", "three", "four"]
    assert all(s.is_core_fact for s in subs)
    assert subs[0].start_sec == pytest.approx(0.0, abs=1e-3)
    assert subs[-1].end_sec == pytest.approx(4 * WORD_SEC, abs=1e-2)
    for earlier, later in zip(subs, subs[1:]):
        assert later.start_sec >= earlier.end_sec - 1e-3


# --- pauses ---------------------------------------------------------------


def test_pause_after_ms_lengthens_the_narration(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    quick = _build(tmp_path / "quick", [_scene(1, [_segment("a b", pause_ms=0)])])
    slow = _build(tmp_path / "slow", [_scene(1, [_segment("a b", pause_ms=800)])])

    assert slow.total_duration_sec == pytest.approx(quick.total_duration_sec + 0.8, abs=1e-2)


def test_pause_pushes_the_next_segments_subtitles_later(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(
        tmp_path, [_scene(1, [_segment("a b", pause_ms=500), _segment("c d")])]
    )
    starts = [s.start_sec for s in timeline.spans[0].subtitles]
    assert starts == pytest.approx([0.0, 0.3, 1.1, 1.4], abs=1e-3)


# --- output wav -----------------------------------------------------------


def test_wav_is_mono_at_the_requested_sample_rate(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, _two_scenes())

    info = sf.info(str(timeline.wav_path))
    assert info.channels == 1, "Wav2Lip requires mono"
    assert info.samplerate == narration.DEFAULT_SAMPLE_RATE == 16000
    assert timeline.sample_rate == info.samplerate
    assert info.duration == pytest.approx(timeline.total_duration_sec, abs=1e-2)


def test_sample_rate_is_configurable(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, [_scene(1, [_segment("a b")])], sample_rate=22050)
    info = sf.info(str(timeline.wav_path))
    assert info.samplerate == 22050
    assert info.channels == 1


# --- prosody --------------------------------------------------------------


def test_emphasis_slows_the_delivery(tmp_path, monkeypatch):
    """Emphasis has to buy its weight with rate, not volume alone."""
    calls = []
    _fake_tts(monkeypatch, calls=calls)
    _build(
        tmp_path,
        [
            _scene(
                1,
                [
                    _segment("plain"),
                    _segment("louder", emphasis="moderate"),
                    _segment("biggest", "core_fact", emphasis="strong"),
                ],
            )
        ],
    )
    rates = [narration._parse_percent(c["rate"]) for c in calls]
    assert rates[0] > rates[1] > rates[2]
    assert calls[2]["pitch"] != calls[0]["pitch"]


def test_caller_rate_and_emphasis_delta_combine(tmp_path, monkeypatch):
    calls = []
    _fake_tts(monkeypatch, calls=calls)
    _build(tmp_path, [_scene(1, [_segment("x", emphasis="strong")])], rate="+10%")
    expected = 10 + narration.EMPHASIS_PROSODY["strong"]["rate_delta_pct"]
    assert narration._parse_percent(calls[0]["rate"]) == expected


def test_rate_is_clamped_to_service_limits():
    rate, _, _ = narration._prosody_for("strong", "-95%")
    assert narration._parse_percent(rate) == narration._RATE_MIN_PCT


def test_voice_defaults_from_the_language_mapping(tmp_path, monkeypatch):
    calls = []
    _fake_tts(monkeypatch, calls=calls)
    narration.build_narration_sync(
        scenes=[_scene(1, [_segment("x")])], lang="hi", out_wav=tmp_path / "n.wav"
    )
    assert calls[0]["voice"] == narration.VOICE_MAPPING["hi"]


# --- decoding -------------------------------------------------------------


def test_decode_downmixes_and_resamples():
    stereo = _wav_bytes(1.0, sample_rate=TTS_RATE, channels=2)
    mono = narration._decode_to_mono(stereo, 16000)
    assert mono.ndim == 1
    assert mono.dtype == np.float32
    assert len(mono) == pytest.approx(16000, abs=8)


def test_decode_handles_real_mp3(tmp_path):
    """The live path gets MP3 from edge-tts, so make sure that actually decodes."""
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    import subprocess

    src = tmp_path / "src.wav"
    dst = tmp_path / "src.mp3"
    sf.write(str(src), np.zeros(TTS_RATE // 2, dtype=np.float32), TTS_RATE, subtype="PCM_16")
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(src), str(dst)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    mono = narration._decode_to_mono(dst.read_bytes(), 16000)
    assert mono.ndim == 1
    # MP3 encoder priming makes this longer than the source, never shorter.
    assert 8000 <= len(mono) <= 8000 + 16000


# --- edge silence trimming ------------------------------------------------


def _padded_tone(lead_sec, tone_sec, tail_sec, sample_rate=16000):
    def block(sec, amp):
        n = int(round(sec * sample_rate))
        return np.full(n, amp, dtype=np.float32)

    return np.concatenate([block(lead_sec, 0.0), block(tone_sec, 0.5), block(tail_sec, 0.0)])


def test_trim_removes_engine_padding():
    """Without this, per-segment synthesis stacks ~1s of dead air per phrase."""
    audio = _padded_tone(0.2, 1.0, 0.9)
    trimmed, lead = narration._trim_edge_silence(audio, 16000)

    keep = narration.SILENCE_KEEP_SEC
    assert lead == pytest.approx(0.2 - keep, abs=1e-3)
    assert len(trimmed) / 16000 == pytest.approx(1.0 + 2 * keep, abs=1e-3)


def test_trim_keeps_a_wholly_silent_segment_intact():
    """A silent segment is a deliberate beat or a TTS failure, never a delete."""
    audio = np.zeros(16000, dtype=np.float32)
    trimmed, lead = narration._trim_edge_silence(audio, 16000)
    assert len(trimmed) == 16000
    assert lead == 0.0


def test_boundaries_shift_back_by_the_trimmed_lead(tmp_path, monkeypatch):
    """Boundaries are reported against the untrimmed stream, so they must move."""
    lead = 0.25

    async def _synth(text, voice, rate, volume, pitch):
        buf = io.BytesIO()
        sf.write(buf, _padded_tone(lead, 0.6, 0.5), 16000, format="WAV", subtype="PCM_16")
        return buf.getvalue(), [("word", lead, lead + 0.6)]

    monkeypatch.setattr(narration, "_synthesize_segment", _synth)
    timeline = _build(tmp_path, [_scene(1, [_segment("word")])])

    sub = timeline.spans[0].subtitles[0]
    assert sub.start_sec == pytest.approx(narration.SILENCE_KEEP_SEC, abs=1e-2)


def test_empty_scene_list_still_writes_a_wav(tmp_path, monkeypatch):
    _fake_tts(monkeypatch)
    timeline = _build(tmp_path, [])
    assert timeline.spans == []
    assert timeline.total_duration_sec == pytest.approx(0.0)
    assert timeline.wav_path.exists()
