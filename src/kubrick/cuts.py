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


def detect(path: str, detector: str, threshold: float | None = None, min_len: int = 8) -> list[int]:
    """First frame of every shot after the first."""
    t = DETECTORS[detector].default if threshold is None else threshold
    if detector == "framejump":
        return _framejump(path, t, min_len)
    import scenedetect

    det = (scenedetect.ContentDetector(threshold=t, min_scene_len=min_len) if detector == "content"
           else scenedetect.AdaptiveDetector(adaptive_threshold=t, min_scene_len=min_len))
    scenes = scenedetect.detect(path, det)
    return [start.frame_num for start, _ in scenes[1:]]


def thumbnails(path: str, w: int = 64, h: int = 36) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-vf", f"scale={w}:{h}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)


def _framejump(path: str, threshold: float, min_len: int) -> list[int]:
    diffs = np.abs(np.diff(thumbnails(path), axis=0)).mean(axis=(1, 2))
    cuts, last = [], -min_len
    for i, d in enumerate(diffs, start=1):
        if d >= threshold and i - last >= min_len:
            cuts.append(i)
            last = i
    return cuts
