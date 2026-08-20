"""README §16.1: scene_duration_sec always exceeds subtitles[-1].end_sec."""

from tests.fixtures.scenes_en_fixture import SCENE_TAIL_PAD_SEC, get_fixture_scenes


def test_scene_duration_exceeds_last_word_end():
    for scene in get_fixture_scenes():
        assert scene.scene_duration_sec > scene.subtitles[-1].end_sec


def test_scene_duration_matches_dynamic_timing_rule():
    for scene in get_fixture_scenes():
        expected = scene.subtitles[-1].end_sec + SCENE_TAIL_PAD_SEC
        assert scene.scene_duration_sec == expected


def test_no_word_state_is_mixed():
    """README §7.4 invariant 1: audio_path/scene_duration_sec/subtitles are
    all None until synthesis, all non-None after — never a mix."""
    for scene in get_fixture_scenes():
        fields = [scene.audio_path, scene.scene_duration_sec, scene.subtitles]
        assert all(f is not None for f in fields) or all(f is None for f in fields)
