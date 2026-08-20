"""Gesture scheduling: vocabulary loading, cue placement, and playback mapping."""

import json

import pytest

from compositor import gestures
from models.schemas import TemplateType, WordTimestamp


def _vocab(**over):
    spec = {
        "rest": {"start": 5.0, "end": 9.0, "role": "neutral"},
        "open": {"start": 1.0, "end": 2.2, "role": "present"},
        "tight": {"start": 3.8, "end": 4.8, "role": "stress"},
    }
    spec.update(over)
    return gestures.GestureVocabulary(
        [gestures.Gesture(n, v["start"], v["end"], v["role"]) for n, v in spec.items()]
    )


def _words(spec):
    """spec: [(word, start, end, is_core)]"""
    return [WordTimestamp(word=w, start_sec=s, end_sec=e, is_core_fact=c) for w, s, e, c in spec]


def _write_sidecar(tmp_path, gestures_spec, name="av.mp4", default="neutral"):
    (tmp_path / name).write_bytes(b"stub")
    (tmp_path / "av.gestures.json").write_text(
        json.dumps({"clip": name, "default": default, "gestures": gestures_spec}), encoding="utf-8"
    )
    return tmp_path / name


# --- vocabulary -----------------------------------------------------------


def test_vocabulary_loads_from_sidecar(tmp_path):
    clip = _write_sidecar(tmp_path, {"rest": {"start": 1.0, "end": 4.0, "role": "neutral"}})
    vocab = gestures.load_vocabulary(clip)
    assert vocab is not None
    assert vocab.by_role("neutral").name == "rest"


def test_missing_sidecar_returns_none(tmp_path):
    """An unsegmented avatar is normal — it just loops instead."""
    (tmp_path / "av.mp4").write_bytes(b"stub")
    assert gestures.load_vocabulary(tmp_path / "av.mp4") is None


def test_malformed_sidecar_degrades_instead_of_raising(tmp_path):
    (tmp_path / "av.mp4").write_bytes(b"stub")
    (tmp_path / "av.gestures.json").write_text("{not json", encoding="utf-8")
    assert gestures.load_vocabulary(tmp_path / "av.mp4") is None


def test_too_short_gesture_is_rejected(tmp_path):
    """Below the minimum a gesture reads as a twitch, so it is dropped."""
    clip = _write_sidecar(tmp_path, {"blip": {"start": 1.0, "end": 1.1, "role": "neutral"}})
    assert gestures.load_vocabulary(clip) is None


# --- core-fact spans ------------------------------------------------------


def test_adjacent_core_facts_merge_into_one_span():
    """'two thousand rupees' is one gesture, not three."""
    words = _words([("two", 1.0, 1.3, True), ("thousand", 1.35, 1.8, True), ("rupees", 1.85, 2.4, True)])
    assert gestures.core_fact_spans(words) == [(1.0, 2.4)]


def test_distant_core_facts_stay_separate():
    words = _words([("first", 1.0, 1.3, True), ("second", 5.0, 5.4, True)])
    assert len(gestures.core_fact_spans(words)) == 2


def test_non_core_words_are_ignored():
    assert gestures.core_fact_spans(_words([("the", 0.0, 0.4, False)])) == []


# --- scheduling -----------------------------------------------------------


def test_core_fact_gets_the_present_gesture():
    words = _words([("the", 0.0, 0.5, False), ("PM-KISAN", 2.0, 2.6, True)])
    cues = gestures.schedule(words, TemplateType.HERO_ANNOUNCEMENT, 5.0, _vocab())
    accent = [c for c in cues if c.gesture.role == "present"]
    assert len(accent) == 1


def test_gesture_leads_the_word_it_emphasises():
    """A real gesture stroke starts before the stressed syllable, not on it."""
    words = _words([("PM-KISAN", 2.0, 2.6, True)])
    cues = gestures.schedule(words, TemplateType.HERO_ANNOUNCEMENT, 5.0, _vocab())
    accent = next(c for c in cues if c.gesture.role == "present")
    assert accent.start == pytest.approx(2.0 - gestures.GESTURE_LEAD_SEC)


def test_short_core_fact_is_widened_to_the_minimum():
    words = _words([("Rs", 2.0, 2.1, True)])
    cues = gestures.schedule(words, TemplateType.HERO_ANNOUNCEMENT, 5.0, _vocab())
    accent = next(c for c in cues if c.gesture.role == "present")
    # Subtracting the cue bounds lands a float ulp under the minimum (2.4-1.8
    # is 0.5999999999999996), so compare with a tolerance rather than exactly.
    assert accent.end - accent.start == pytest.approx(gestures.MIN_GESTURE_SEC, abs=1e-9) or (
        accent.end - accent.start > gestures.MIN_GESTURE_SEC
    )


def test_scene_without_core_facts_is_all_neutral():
    words = _words([("just", 0.0, 0.4, False), ("filler", 0.5, 1.0, False)])
    cues = gestures.schedule(words, TemplateType.HERO_ANNOUNCEMENT, 4.0, _vocab())
    assert {c.gesture.role for c in cues} == {"neutral"}


def test_deadline_alert_uses_the_stress_gesture_throughout():
    """The whole scene is the emphasis, so punching one word inside it fights it."""
    words = _words([("31st", 1.0, 1.6, True)])
    cues = gestures.schedule(words, TemplateType.DEADLINE_ALERT, 4.0, _vocab())
    assert {c.gesture.role for c in cues} == {"stress"}


def test_cues_tile_the_scene_without_gaps():
    words = _words([("a", 0.5, 0.9, False), ("KEY", 2.0, 2.5, True), ("b", 3.0, 3.4, False)])
    cues = gestures.schedule(words, TemplateType.HERO_ANNOUNCEMENT, 5.0, _vocab())
    assert cues[0].start == 0.0
    assert cues[-1].end == pytest.approx(5.0)
    for earlier, later in zip(cues, cues[1:]):
        assert later.start == pytest.approx(earlier.end)


# --- playback -------------------------------------------------------------


def test_sampled_time_stays_inside_the_gesture_window():
    """Playback must never wander outside the window a human vetted."""
    g = gestures.Gesture("open", 1.0, 2.2, "present")
    track = gestures.GestureTrack([gestures.GestureCue(0.0, 30.0, g)], crossfade=0.0)
    for i in range(600):
        a, _, _ = track.sample_at(i * 0.05)
        assert 1.0 - 1e-6 <= a <= 2.2 + 1e-6


def test_pingpong_returns_to_the_opening_pose():
    """Forward-then-back means the window never snaps, so it can loop forever."""
    g = gestures.Gesture("open", 1.0, 2.0, "present")
    cue = gestures.GestureCue(0.0, 10.0, g)
    track = gestures.GestureTrack([cue], crossfade=0.0)
    assert track.sample_at(0.0)[0] == pytest.approx(1.0)
    assert track.sample_at(1.0)[0] == pytest.approx(2.0)  # far end
    assert track.sample_at(2.0)[0] == pytest.approx(1.0)  # back home


def test_crossfade_blends_towards_the_next_cue():
    rest = gestures.Gesture("rest", 5.0, 9.0, "neutral")
    open_ = gestures.Gesture("open", 1.0, 2.2, "present")
    track = gestures.GestureTrack(
        [gestures.GestureCue(0.0, 2.0, rest), gestures.GestureCue(2.0, 4.0, open_)], crossfade=0.5
    )
    _, _, w_mid = track.sample_at(1.0)
    assert w_mid == 0.0, "no blend well before the boundary"
    _, _, w_edge = track.sample_at(1.9)
    assert 0.0 < w_edge <= 1.0, "should be blending into the next gesture"


def test_last_cue_does_not_blend_off_the_end():
    g = gestures.Gesture("rest", 5.0, 9.0, "neutral")
    track = gestures.GestureTrack([gestures.GestureCue(0.0, 3.0, g)], crossfade=0.5)
    assert track.sample_at(2.95)[2] == 0.0


# --- regression -----------------------------------------------------------


def test_each_scene_gets_its_own_track(tmp_path):
    """Tracks must not be stored on the shared PresenterSource.

    MoviePy builds every scene clip before pulling a single frame, so a track
    held on the per-job source is overwritten by the last scene and all scenes
    render with the wrong choreography. Threading it through the call keeps
    each scene's schedule independent.
    """
    clip = _write_sidecar(
        tmp_path,
        {
            "rest": {"start": 5.0, "end": 9.0, "role": "neutral"},
            "open": {"start": 1.0, "end": 2.2, "role": "present"},
        },
    )
    a = gestures.build_track(_words([("X", 1.0, 1.5, True)]), TemplateType.HERO_ANNOUNCEMENT, 5.0, clip)
    b = gestures.build_track(_words([("Y", 3.5, 4.0, True)]), TemplateType.HERO_ANNOUNCEMENT, 5.0, clip)

    def accent_start(track):
        return next(c.start for c in track.cues if c.gesture.role == "present")

    assert accent_start(a) != accent_start(b)
    assert accent_start(a) == pytest.approx(1.0 - gestures.GESTURE_LEAD_SEC)
