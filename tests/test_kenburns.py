"""README §16.1: zoom(0)==1.0, zoom(D)==Z_max, crop box stays inside source bounds for all t."""

import pytest

from compositor.kenburns import Z_MAX_DEFAULT, crop_box, pan_targets_for_template, zoom

DURATION = 7.0
OUTPUT_W, OUTPUT_H = 1920, 1080
SOURCE_W, SOURCE_H = round(Z_MAX_DEFAULT * OUTPUT_W), round(Z_MAX_DEFAULT * OUTPUT_H)


def test_zoom_starts_at_one():
    assert zoom(0.0, DURATION) == pytest.approx(1.0)


def test_zoom_ends_at_z_max():
    assert zoom(DURATION, DURATION) == pytest.approx(Z_MAX_DEFAULT)


def test_zoom_monotonic_increasing():
    samples = [zoom(t, DURATION) for t in [0, 1, 2, 3, 4, 5, 6, 7]]
    assert samples == sorted(samples)


@pytest.mark.parametrize("template_type", [
    "HERO_ANNOUNCEMENT", "METRIC_FOCUS", "DEADLINE_ALERT", "OUTRO_CALL_TO_ACTION",
])
@pytest.mark.parametrize("alternate", [False, True])
def test_crop_box_stays_inside_source_bounds(template_type, alternate):
    cx0, cy0, cx1, cy1 = pan_targets_for_template(template_type, SOURCE_W, SOURCE_H, alternate)
    for i in range(101):
        t = DURATION * i / 100
        left, top, right, bottom = crop_box(
            t, DURATION, OUTPUT_W, OUTPUT_H, cx0, cy0, cx1, cy1, SOURCE_W, SOURCE_H,
        )
        assert left >= -1e-6
        assert top >= -1e-6
        assert right <= SOURCE_W + 1e-6
        assert bottom <= SOURCE_H + 1e-6
        assert right > left
        assert bottom > top


def test_deadline_alert_has_no_pan():
    cx0, cy0, cx1, cy1 = pan_targets_for_template("DEADLINE_ALERT", SOURCE_W, SOURCE_H)
    assert (cx0, cy0) == (cx1, cy1)


def test_hero_announcement_drifts_right():
    cx0, cy0, cx1, cy1 = pan_targets_for_template("HERO_ANNOUNCEMENT", SOURCE_W, SOURCE_H)
    assert cx1 > cx0
    assert cy0 == cy1
