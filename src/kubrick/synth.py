"""Known-answer clips: segments spliced at known frames, with planted in-shot negatives."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

XFADE = {"dissolve": "fade", "fade": "fadeblack"}


@dataclass
class Segment:
    source: str  # a file path, or "lavfi:<filtergraph>"
    frames: int
    start: float = 0.0
    flash: list[int] = field(default_factory=list)  # [first, last] frame, segment-relative
    whip: list[int] = field(default_factory=list)  # [first, last] frame of a fast horizontal pan


@dataclass
class Join:
    kind: str  # cut | dissolve | fade
    frames: int = 0  # transition length; 0 for a cut


@dataclass
class Spec:
    segments: list[Segment]
    joins: list[Join]
    fps: int = 24
    width: int = 640
    height: int = 360

    @classmethod
    def from_dict(cls, d: dict) -> "Spec":
        segs = [Segment(**s) for s in d["segments"]]
        joins = [Join(**j) for j in d["joins"]]
        if len(joins) != len(segs) - 1:
            raise ValueError(f"{len(segs)} segments need {len(segs) - 1} joins, got {len(joins)}")
        for j in joins:
            if j.kind not in ("cut", *XFADE):
                raise ValueError(f"unknown join kind {j.kind!r}")
            if (j.kind == "cut") != (j.frames == 0):
                raise ValueError(f"{j.kind} with {j.frames} transition frames")
        return cls(segs, joins, d.get("fps", 24), d.get("width", 640), d.get("height", 360))


def truth(spec: Spec) -> dict:
    """Transitions and negative windows in output frame numbers. A cut is the first frame of the new shot."""
    transitions, negatives = [], []
    pos = 0
    for i, seg in enumerate(spec.segments):
        for kind in ("flash", "whip"):
            win = getattr(seg, kind)
            if win:
                negatives.append({"kind": kind, "first": pos + win[0], "last": pos + win[1]})
        if i == len(spec.joins):
            pos += seg.frames
            break
        join = spec.joins[i]
        if join.kind == "cut":
            pos += seg.frames
            transitions.append({"kind": "cut", "first": pos, "last": pos})
        else:
            pos += seg.frames - join.frames
            transitions.append({"kind": join.kind, "first": pos, "last": pos + join.frames - 1})
    return {"fps": spec.fps, "frames": pos, "transitions": transitions, "negatives": negatives}


def _segment_filter(i: int, seg: Segment, spec: Spec) -> str:
    chain = [f"fps={spec.fps}", f"trim=start_frame=0:end_frame={seg.frames}", "setpts=PTS-STARTPTS"]
    if seg.whip:
        a, b = seg.whip
        chain.insert(0, f"scale={2 * spec.width}:{spec.height}")
        chain.insert(1, f"crop={spec.width}:{spec.height}:x='if(lt(n,{a}),0,if(lt(n,{b}),(n-{a})/({b}-{a})*{spec.width},{spec.width}))':y=0")
    else:
        chain.insert(0, f"scale={spec.width}:{spec.height}")
    chain += ["setsar=1", "format=yuv420p", f"settb=1/{spec.fps}"]
    if seg.flash:
        a, b = seg.flash
        chain.append(f"lutyuv=y=235:enable='between(n,{a},{b})'")
    return f"[{i}:v]{','.join(chain)}[s{i}]"


def _inputs(spec: Spec) -> list[str]:
    args = []
    for seg in spec.segments:
        if seg.source.startswith("lavfi:"):
            args += ["-f", "lavfi", "-i", seg.source.removeprefix("lavfi:")]
        else:
            args += ["-ss", str(seg.start), "-i", seg.source]
    return args


def build(spec: Spec, out: Path) -> dict:
    graph = [_segment_filter(i, s, spec) for i, s in enumerate(spec.segments)]
    cur, length = "s0", spec.segments[0].frames
    for i, join in enumerate(spec.joins, start=1):
        nxt, label = f"s{i}", f"j{i}"
        if join.kind == "cut":
            # concat outputs a 1/1000000 timebase, which xfade refuses to join to a 1/fps one
            graph.append(f"[{cur}][{nxt}]concat=n=2:v=1:a=0,settb=1/{spec.fps},fps={spec.fps}[{label}]")
            length += spec.segments[i].frames
        else:
            offset = (length - join.frames) / spec.fps
            graph.append(
                f"[{cur}][{nxt}]xfade=transition={XFADE[join.kind]}:duration={join.frames / spec.fps}:offset={offset}[{label}]"
            )
            length += spec.segments[i].frames - join.frames
        cur = label
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *_inputs(spec),
           "-filter_complex", ";".join(graph), "-map", f"[{cur}]", "-an",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)
    t = truth(spec)
    out.with_suffix(".truth.json").write_text(json.dumps(t, indent=1))
    return t
