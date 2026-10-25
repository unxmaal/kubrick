"""Cut detectors. Thresholds are registered with the range to sweep, never taken on trust."""

import subprocess
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Knob:
    default: float
    sweep: tuple[float, ...]


DETECTORS = {
    "content": Knob(27.0, (15, 20, 24, 27, 30, 35, 40)),
    "adaptive": Knob(3.0, (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)),
    "framejump": Knob(33.0, (15, 20, 25, 33, 40, 50)),  # Chris's thumbnail heuristic
}
# a candidate cut whose frames FLASH_SPAN either side still match (mean abs diff below this) is a flash
FLASH_GUARD = Knob(0.0, (0, 6, 10, 15, 20))
FLASH_SPAN = Knob(4, (2, 3, 4, 6))
MIN_LEN = Knob(8, (1, 4, 8, 12))


def detect(path: str, detector: str, threshold: float | None = None, min_len: int | None = None,
           flash_guard: float | None = None) -> list[int]:
    """First frame of every shot after the first."""
    t = DETECTORS[detector].default if threshold is None else threshold
    g = FLASH_GUARD.default if flash_guard is None else flash_guard
    min_len = MIN_LEN.default if min_len is None else min_len
    # the guard runs before min_len, so a dropped flash cannot suppress a real cut just after it
    if detector == "framejump":
        found = _framejump(path, t)
    else:
        import scenedetect

        det = (scenedetect.ContentDetector(threshold=t, min_scene_len=1) if detector == "content"
               else scenedetect.AdaptiveDetector(adaptive_threshold=t, min_scene_len=1))
        found = [start.frame_num for start, _ in scenedetect.detect(path, det)[1:]]
    if g:
        found = _drop_flashes(path, found, g)
    return _min_len(found, min_len)


def _min_len(found: list[int], min_len: int) -> list[int]:
    kept, last = [], -min_len
    for c in found:
        if c - last >= min_len:
            kept.append(c)
            last = c
    return kept


def _drop_flashes(path: str, found: list[int], guard: float, span: int | None = None) -> list[int]:
    th = thumbnails(path)
    span = FLASH_SPAN.default if span is None else span
    kept = []
    for c in found:
        a, b = c - 1 - span, c + span
        if a >= 0 and b < len(th) and np.abs(th[a] - th[b]).mean() < guard:
            continue
        kept.append(c)
    return kept


def thumbnails(path: str, w: int = 64, h: int = 36) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-vf", f"scale={w}:{h}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)


def _framejump(path: str, threshold: float) -> list[int]:
    diffs = np.abs(np.diff(thumbnails(path), axis=0)).mean(axis=(1, 2))
    return [i for i, d in enumerate(diffs, start=1) if d >= threshold]
