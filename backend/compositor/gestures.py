"""Choose the presenter's gesture from what is being said, not at random.

A presenter loop played straight through drifts against the narration: the
speaker throws their hands open while the script is reading a filler line,
and sits still through the number that matters. This module schedules named
gesture windows against the word timings the pipeline already has, so the
open-handed beat lands on the core fact.

Nothing here generates motion. The gestures are windows into footage that was
already shot, chosen by rules you can read, which is the same reason README
section 3.1 rules out generative video: for a government notice, every frame
should be traceable to something a person recorded and approved.

Two details are deliberate:

*Gestures lead the word.* A real speaker's gesture stroke begins slightly
before the syllable it emphasises, not on it. Landing the gesture exactly on
the word looks reactive, a beat late. GESTURE_LEAD_SEC pulls it forward.

*Windows are played ping-pong.* Forward to the end of the window, then back.
A short gesture window looped forward-only snaps back to its opening pose on
every wrap; reversing instead means the clip always returns the way it came,
and the gesture reads as a stroke and its retraction, which is the shape a
real gesture has.
"""

from __future__ import annotations

import json
import logging
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from models.schemas import TemplateType, WordTimestamp

logger = logging.getLogger(__name__)

# A gesture stroke begins before the stressed syllable, not on it.
GESTURE_LEAD_SEC = 0.20
# Below this a gesture reads as a twitch rather than a movement.
MIN_GESTURE_SEC = 0.60
# Core-fact runs closer together than this become one gesture instead of two.
MERGE_GAP_SEC = 0.50
# Blend time between one gesture window and the next.
CROSSFADE_SEC = 0.25

NEUTRAL_ROLE = "neutral"
# Scenes whose whole point is urgency get the tighter gesture throughout.
TEMPLATE_ROLE: Dict[TemplateType, str] = {
    TemplateType.DEADLINE_ALERT: "stress",
}


@dataclass(frozen=True)
class Gesture:
    """One named window of the source clip."""

    name: str
    start: float
    end: float
    role: str

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


@dataclass(frozen=True)
class GestureCue:
    """A gesture scheduled to play over a stretch of scene time."""

    start: float
    end: float
    gesture: Gesture


class GestureVocabulary:
    """The gestures available for one avatar, indexed by role."""

    def __init__(self, gestures: Sequence[Gesture], default_role: str = NEUTRAL_ROLE):
        self.gestures = tuple(gestures)
        self.default_role = default_role

    def by_role(self, role: str) -> Optional[Gesture]:
        for gesture in self.gestures:
            if gesture.role == role:
                return gesture
        return None

    def default(self) -> Optional[Gesture]:
        return self.by_role(self.default_role) or (self.gestures[0] if self.gestures else None)

    def __bool__(self) -> bool:
        return bool(self.gestures)


def sidecar_path(clip_path: Path) -> Path:
    """`presenter_01.mp4` -> `presenter_01.gestures.json`."""
    return clip_path.with_suffix("").with_suffix(".gestures.json") if clip_path.suffix else clip_path


def load_vocabulary(clip_path: Path) -> Optional[GestureVocabulary]:
    """Read the sidecar beside an avatar clip, or None if it has none.

    A missing sidecar is the normal case for an avatar that was never
    segmented; the caller falls back to playing the loop straight through.
    """
    path = clip_path.parent / (clip_path.stem + ".gestures.json")
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("gesture sidecar %s is not valid JSON (%s); ignoring", path, exc)
        return None

    gestures: List[Gesture] = []
    for name, raw in (data.get("gestures") or {}).items():
        try:
            start, end = float(raw["start"]), float(raw["end"])
        except (KeyError, TypeError, ValueError):
            logger.warning("gesture %r in %s lacks numeric start/end; skipping", name, path.name)
            continue
        if end - start < MIN_GESTURE_SEC:
            logger.warning(
                "gesture %r in %s is %.2fs, shorter than the %.2fs minimum; skipping",
                name, path.name, end - start, MIN_GESTURE_SEC,
            )
            continue
        gestures.append(Gesture(name=name, start=start, end=end, role=raw.get("role", NEUTRAL_ROLE)))

    if not gestures:
        logger.warning("gesture sidecar %s defines no usable gestures", path.name)
        return None

    vocab = GestureVocabulary(gestures, data.get("default", NEUTRAL_ROLE))
    logger.info(
        "gesture vocabulary %s: %s",
        path.name, ", ".join(f"{g.name}({g.role})" for g in vocab.gestures),
    )
    return vocab


def core_fact_spans(subtitles: Sequence[WordTimestamp]) -> List[Tuple[float, float]]:
    """Contiguous runs of core-fact words, merged across short gaps."""
    spans: List[Tuple[float, float]] = []
    for wt in subtitles:
        if not wt.is_core_fact:
            continue
        if spans and wt.start_sec - spans[-1][1] <= MERGE_GAP_SEC:
            spans[-1] = (spans[-1][0], wt.end_sec)
        else:
            spans.append((wt.start_sec, wt.end_sec))
    return spans


def schedule(
    subtitles: Sequence[WordTimestamp],
    template: TemplateType,
    duration: float,
    vocab: GestureVocabulary,
) -> List[GestureCue]:
    """Lay gestures over `duration` seconds of scene time.

    The neutral gesture holds the floor; core-fact runs displace it. On a
    template with its own role, that role replaces neutral throughout, since
    the whole scene carries the emphasis rather than one phrase in it.
    """
    base_role = TEMPLATE_ROLE.get(template, vocab.default_role)
    base = vocab.by_role(base_role) or vocab.default()
    if base is None:
        return []

    accent = vocab.by_role("present")
    # On a scene that is already emphatic, punching individual facts with a
    # second gesture just fights the first one.
    if accent is None or base_role != vocab.default_role:
        return [GestureCue(0.0, duration, base)]

    cues: List[GestureCue] = []
    cursor = 0.0
    for start, end in core_fact_spans(subtitles):
        start = max(0.0, start - GESTURE_LEAD_SEC)
        end = min(duration, max(end, start + MIN_GESTURE_SEC))
        if start <= cursor:
            # Overlaps the gesture already scheduled — extend it rather than
            # cutting away and back, which would read as a stutter.
            if cues and cues[-1].gesture is accent:
                cues[-1] = GestureCue(cues[-1].start, end, accent)
                cursor = end
            continue
        if start > cursor:
            cues.append(GestureCue(cursor, start, base))
        cues.append(GestureCue(start, end, accent))
        cursor = end

    if cursor < duration:
        cues.append(GestureCue(cursor, duration, base))
    return cues


class GestureTrack:
    """Maps scene time to a position in the source clip, plus crossfades.

    `sample_at` returns two source times and a blend weight rather than a
    frame, so the caller can look both up in whatever frame cache it already
    holds and blend them there.
    """

    def __init__(self, cues: Sequence[GestureCue], crossfade: float = CROSSFADE_SEC):
        self.cues = tuple(cues)
        self.crossfade = crossfade
        self._starts = [c.start for c in self.cues]

    def _cue_at(self, t: float) -> GestureCue:
        idx = max(0, bisect_right(self._starts, t) - 1)
        return self.cues[idx]

    @staticmethod
    def _source_time(cue: GestureCue, t: float) -> float:
        """Position within the gesture window, ping-ponged."""
        span = cue.gesture.duration
        if span <= 0:
            return cue.gesture.start
        elapsed = max(t - cue.start, 0.0)
        cycle = elapsed % (2 * span)
        offset = cycle if cycle <= span else (2 * span - cycle)
        return cue.gesture.start + offset

    def sample_at(self, t: float) -> Tuple[float, float, float]:
        """(source_time_a, source_time_b, weight_b) for scene time `t`."""
        cue = self._cue_at(t)
        a = self._source_time(cue, t)

        # Crossfade into the next cue over the last `crossfade` seconds of
        # this one, so the hands move between poses instead of cutting.
        if self.crossfade > 0:
            remaining = cue.end - t
            if 0 <= remaining < self.crossfade:
                idx = self.cues.index(cue)
                if idx + 1 < len(self.cues):
                    nxt = self.cues[idx + 1]
                    w = 1.0 - (remaining / self.crossfade)
                    return a, self._source_time(nxt, nxt.start + (t - cue.end) + self.crossfade), w
        return a, a, 0.0

    def describe(self) -> str:
        return " | ".join(f"{c.start:.2f}-{c.end:.2f}s {c.gesture.name}" for c in self.cues)


def build_track(
    subtitles: Sequence[WordTimestamp],
    template: TemplateType,
    duration: float,
    clip_path: Path,
) -> Optional[GestureTrack]:
    """The whole pipeline: sidecar -> schedule -> track, or None if unavailable."""
    vocab = load_vocabulary(clip_path)
    if not vocab:
        return None
    cues = schedule(subtitles, template, duration, vocab)
    if not cues:
        return None
    track = GestureTrack(cues)
    logger.info("gesture track: %s", track.describe())
    return track
