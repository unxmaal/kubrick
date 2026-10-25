"""Known-answer sets from real footage: single-shot segments joined at known frames."""

import json
import random
import subprocess
from pathlib import Path

from kubrick import cuts, synth


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def _single_shot(src: str, start: float, frames: int, fps: int, scratch: Path) -> bool:
    """Reject a candidate if either detector, at its most sensitive setting, sees a cut inside it."""
    probe = scratch / "probe.mp4"
    spec = synth.Spec([synth.Segment(src, frames, start)], [], fps)
    synth.build(spec, probe)
    return not cuts.detect(str(probe), "framejump", min(cuts.DETECTORS["framejump"].sweep)) and \
        not cuts.detect(str(probe), "content", min(cuts.DETECTORS["content"].sweep))


def make(films: list[str], n_segments: int, seed: int, out_dir: Path, fps: int = 24) -> dict:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    lengths = {f: duration(f) for f in films}
    segments, tries = [], 0
    while len(segments) < n_segments:
        tries += 1
        if tries > n_segments * 20:
            raise RuntimeError(f"found {len(segments)} single-shot segments in {tries} tries")
        film = rng.choice(films)
        frames = rng.randint(36, 96)
        start = rng.uniform(120, lengths[film] - 120)
        if not _single_shot(film, start, frames, fps, out_dir):
            continue
        seg = {"source": film, "start": round(start, 3), "frames": frames}
        roll = rng.random()
        if roll < 0.15:
            a = rng.randint(4, frames - 6)
            seg["flash"] = [a, a + rng.randint(0, 2)]
        elif roll < 0.25:
            a = rng.randint(2, frames - 14)
            seg["whip"] = [a, a + rng.randint(6, 10)]
        segments.append(seg)
    joins = []
    for _ in segments[1:]:
        r = rng.random()
        joins.append({"kind": "cut"} if r < 0.6 else
                     {"kind": "dissolve" if r < 0.85 else "fade", "frames": rng.choice([6, 12, 24])})
    # a gradual join must fit inside both neighbours
    for i, j in enumerate(joins):
        j["frames"] = min(j.get("frames", 0), segments[i]["frames"] // 2, segments[i + 1]["frames"] // 2) \
            if j["kind"] != "cut" else 0
    spec_d = {"segments": segments, "joins": joins, "fps": fps, "seed": seed}
    (out_dir / "spec.json").write_text(json.dumps(spec_d, indent=1))
    truth = synth.build(synth.Spec.from_dict({k: v for k, v in spec_d.items() if k != "seed"}), out_dir / "known.mp4")
    (out_dir / "probe.mp4").unlink(missing_ok=True)
    (out_dir / "probe.truth.json").unlink(missing_ok=True)
    return truth
