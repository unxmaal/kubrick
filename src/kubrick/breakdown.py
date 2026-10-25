"""One row per shot: where it is, how it begins, what it looks like, and what made the row."""

import hashlib
import json
import subprocess
from importlib.metadata import version
from pathlib import Path

import numpy as np

from kubrick import cuts, movement

PACKAGES = ("kubrick", "transnetv2-pytorch", "scenedetect", "torch", "numpy")
# consecutive frames from the middle of a shot used for its movement. Known-answer clips hold every kind at
# 24 and 48 frames; at 12, shake has real net drift and reads as tilt, so shorter shots are not judged
MOVEMENT_FRAMES = cuts.Knob(24, (24, 48))


def movement_of(clip: np.ndarray) -> str:
    if len(clip) < MOVEMENT_FRAMES.default:
        return "unknown:too-short"
    return movement.classify(movement.motion(clip[:MOVEMENT_FRAMES.default]))


def digest(path: Path) -> str:
    """sha256 of the whole file, so a re-encode or a different edition never shares rows."""
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def versions() -> dict[str, str]:
    import cv2

    # opencv ships under several distribution names (opencv-python, -headless, -contrib); ask the module
    return {**{p: version(p) for p in PACKAGES}, "opencv": cv2.__version__}


def settings() -> dict:
    return {"transnet": cuts.DETECTORS["transnet"].default, "transnet_span": cuts.TRANSNET_SPAN.default,
            "gap_close": cuts.GAP_CLOSE.default, "cut_run": cuts.CUT_RUN.default, "min_len": cuts.MIN_LEN.default,
            "zoom": movement.ZOOM.default, "shift": movement.SHIFT.default, "jitter": movement.JITTER.default,
            "min_texture": movement.MIN_TEXTURE.default, "movement_frames": MOVEMENT_FRAMES.default}


def shots_from_transitions(found: list[dict], n_frames: int) -> list[dict]:
    """Shots tiling [0, n_frames): each starts at a transition's frame and names the transition into it."""
    starts = [(0, "start")] + [(t["at"], t["kind"]) for t in found]
    return [{"in": a, "out": (starts[i + 1][0] if i + 1 < len(starts) else n_frames) - 1, "into": kind}
            for i, (a, kind) in enumerate(starts)]


def fps_of(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()
    num, den = r.split("/")
    return int(num) / int(den)


def frames_at(path: str, start_s: float, n: int, w: int = movement.W, h: int = movement.H) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", f"{start_s:.3f}", "-i", path,
                          "-frames:v", str(n), "-vf", f"scale={w}:{h}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def grab(path: str, t: float, out: Path) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", path,
                    "-frames:v", "1", "-q:v", "3", str(out)], check=True)


def breakdown(path: str, out_dir: Path, scale_model: Path | None = None) -> list[dict]:
    """Rows for every shot in `path`; frame grabs are written to `out_dir` and named relative to it.
    Shot scale comes from `scale_model` when given, and is always marked an estimate."""
    from kubrick import scale

    out_dir.mkdir(parents=True, exist_ok=True)
    model = scale.load_model(scale_model) if scale_model else None
    fps, d = fps_of(path), digest(Path(path))
    n_frames = len(cuts.transnet_probs(path)[0])
    shots = shots_from_transitions(cuts.transitions(path), n_frames)
    vers, sets = versions(), settings()
    rows = []
    for i, s in enumerate(shots):
        grabs = []
        for pos, f in (("start", s["in"] + min(2, s["out"] - s["in"])), ("middle", (s["in"] + s["out"]) // 2),
                       ("end", s["out"] - min(2, s["out"] - s["in"]))):
            name = f"{d[:12]}_{i:04d}_{pos}.jpg"
            grab(path, f / fps, out_dir / name)
            grabs.append(name)
        length = s["out"] - s["in"] + 1
        n = min(MOVEMENT_FRAMES.default, length)
        clip = frames_at(path, (s["in"] + (length - n) // 2) / fps, n)
        mv = movement_of(clip)
        row = {"digest": d, "shot": i, "in": s["in"], "out": s["out"], "fps": fps,
               "timecode_in": round(s["in"] / fps, 3), "timecode_out": round((s["out"] + 1) / fps, 3),
               "duration_s": length / fps, "into": s["into"], "grabs": grabs, "movement": mv,
               "scale": "unknown:no-model", "scale_estimate": True, "versions": vers, "settings": sets}
        if model is not None:
            fw, fh = scale.frame_size(path)
            middle = frames_at(path, ((s["in"] + s["out"]) // 2) / fps, 1, w=fw, h=fh)
            row["scale"] = scale.predict_frame(model, middle[0])
            row["scale_model"] = {"features": list(model["features"]), "kind": model["kind"],
                                  "trained_on": model["trained_on"]}
        rows.append(row)
    return rows


def write_jsonl(rows: list[dict], out: Path) -> None:
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
