"""Cut detectors. Thresholds are registered with the range to sweep, never taken on trust."""

import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Knob:
    default: float
    sweep: tuple[float, ...]


DETECTORS = {
    "content": Knob(27.0, (15, 20, 24, 27, 30, 35, 40)),
    "adaptive": Knob(3.5, (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)),  # chosen on known set seed 0, confirmed seed 1
    "framejump": Knob(33.0, (15, 20, 25, 33, 40, 50)),  # Chris's thumbnail heuristic
    "transnet": Knob(0.5, (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)),  # TransNetV2 single-frame head
}
TRANSNET_SPAN = Knob(0.3, (0.2, 0.3, 0.4, 0.5))  # whole-transition head, catches dissolves and fades
GAP_CLOSE = Knob(4, (0, 4, 8, 12))
CUT_RUN = Knob(2, (1, 2, 3))  # a run this short is a cut; longer is a gradual transition  # runs this close are one transition, not two
# a candidate cut whose frames FLASH_SPAN either side still match (mean abs diff below this) is a flash
FLASH_GUARD = Knob(6.0, (0, 6, 10, 15, 20))
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
    elif detector == "transnet":
        found = _transnet(path, t)
    else:
        import scenedetect

        det = (scenedetect.ContentDetector(threshold=t, min_scene_len=1) if detector == "content"
               else scenedetect.AdaptiveDetector(adaptive_threshold=t, min_scene_len=1))
        found = [start.frame_num for start, _ in scenedetect.detect(path, det)[1:]]
    # TransNetV2 reports a dissolve at its end, where both sides match, so the guard would delete it;
    # it ignores flashes unguarded (known sets: 0-8% of negatives triggered at 0.5)
    if g and detector != "transnet":
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
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vf", f"scale={w}:{h}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)


@cache
def transnet_probs(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame (single-frame head, whole-transition head) probabilities.
    CPU only: the package documents MPS disagreeing with CPU."""
    import torch
    import transnetv2_pytorch
    from transnetv2_pytorch import TransNetV2

    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vf", "scale=48:27",
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    frames = torch.from_numpy(np.frombuffer(raw, np.uint8).reshape(-1, 27, 48, 3).copy())
    model = TransNetV2(device="cpu")
    weights = Path(transnetv2_pytorch.__file__).parent / "transnetv2-pytorch-weights.pth"
    model.load_state_dict(torch.load(weights, map_location="cpu"))
    model.eval()
    with torch.no_grad():
        single, span = model.predict_frames(frames, quiet=True)
    return single.cpu().numpy().reshape(-1), span.cpu().numpy().reshape(-1)


def _transnet(path: str, threshold: float, span_threshold: float | None = None,
              gap: int | None = None) -> list[int]:
    """First frame after each run of above-threshold frames, the start of the next shot."""
    single, span = transnet_probs(path)
    sp = TRANSNET_SPAN.default if span_threshold is None else span_threshold
    gap = GAP_CLOSE.default if gap is None else gap
    return _run_ends(close_gaps((single > threshold) | (span > sp), gap))


def close_gaps(above: np.ndarray, gap: int) -> np.ndarray:
    above = above.copy()
    idx = np.flatnonzero(above)
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= gap + 1:
            above[a:b] = True
    return above


def _runs(above: np.ndarray) -> list[dict]:
    """Each closed run of above-threshold frames as a transition. A short run is a cut, placed at the first
    frame after it. A long run is gradual, placed at its midpoint, because the span head stays high a frame
    or two past the transition's last frame."""
    out, start = [], None
    for i in range(len(above)):
        if above[i] and start is None:
            start = i
        elif not above[i] and start is not None:
            if start > 0:
                cut = i - start <= CUT_RUN.default
                out.append({"at": i if cut else (start + i) // 2, "kind": "cut" if cut else "gradual",
                            "first": start, "last": i - 1})
            start = None
    return out


def _run_ends(above: np.ndarray) -> list[int]:
    return [r["at"] for r in _runs(above)]


def transitions(path: str, threshold: float | None = None, min_len: int | None = None) -> list[dict]:
    """TransNetV2 transitions with kind and frame span, after the same gap closing and min_len as detect."""
    single, span = transnet_probs(path)
    t = DETECTORS["transnet"].default if threshold is None else threshold
    runs = _runs(close_gaps((single > t) | (span > TRANSNET_SPAN.default), GAP_CLOSE.default))
    kept = set(_min_len([r["at"] for r in runs], MIN_LEN.default if min_len is None else min_len))
    return [r for r in runs if r["at"] in kept]


def _framejump(path: str, threshold: float) -> list[int]:
    diffs = np.abs(np.diff(thumbnails(path), axis=0)).mean(axis=(1, 2))
    return [i for i, d in enumerate(diffs, start=1) if d >= threshold]
