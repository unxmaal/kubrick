"""The animatic: storyboard panels timed to the shot list, as an OTIO timeline and an ffmpeg render.
Eric reviews the render and gives notes in words; agents edit the timeline."""

import subprocess
from pathlib import Path

import opentimelineio as otio

from kubrick import stages

FPS = 24
W, H = 1280, 720


def timeline(p: dict) -> otio.schema.Timeline:
    panels = {panel["shot"]: panel for panel in p["storyboard.json"]["panels"]}
    track = otio.schema.Track(name="storyboard", kind=otio.schema.TrackKind.Video)
    for scene in p["shotlist.json"]["scenes"]:
        for shot in scene["shots"]:
            panel = panels[shot["id"]]
            frames = round(shot["duration_s"] * FPS)
            clip = otio.schema.Clip(
                name=shot["id"],
                media_reference=otio.schema.ExternalReference(target_url=panel["image"]),
                source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0, FPS),
                                                     otio.opentime.RationalTime(frames, FPS)))
            meta = {"shot": shot["id"], "source": panel["source"]}
            if "vo" in shot:
                meta["vo"] = shot["vo"]
            clip.metadata["kubrick"] = meta
            clip.markers.append(otio.schema.Marker(name=shot["id"], marked_range=otio.opentime.TimeRange(
                otio.opentime.RationalTime(0, FPS), otio.opentime.RationalTime(0, FPS))))
            track.append(clip)
    tl = otio.schema.Timeline(name="animatic")
    tl.tracks.append(track)
    return tl


def card(shot_id: str, text: str, out: Path) -> None:
    """A text panel: the shot id and its description, for an animatic made before any image exists."""
    import textwrap

    import cv2
    import numpy as np

    w, h = W // 2, H // 2
    img = np.full((h, w, 3), 24, np.uint8)
    cv2.putText(img, shot_id, (24, 56), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (230, 230, 230), 2, cv2.LINE_AA)
    for i, line in enumerate(textwrap.wrap(text, 44)[:8]):
        cv2.putText(img, line, (24, 110 + 30 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(out), img):
        raise RuntimeError(f"could not write {out}")


def render(tl: otio.schema.Timeline, root: Path, out: Path) -> None:
    """Each panel held for exactly its clip's frames, letterboxed to W x H at FPS."""
    clips = list(tl.find_clips())
    args, graph = [], []
    for i, clip in enumerate(clips):
        args += ["-loop", "1", "-framerate", str(FPS), "-i", str(Path(root) / clip.media_reference.target_url)]
        n = round(clip.duration().to_seconds() * FPS)
        graph.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                     f"setsar=1,format=yuv420p,trim=end_frame={n},setpts=PTS-STARTPTS,settb=1/{FPS}[v{i}]")
    graph.append("".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[out]")
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args,
                    "-filter_complex", ";".join(graph), "-map", "[out]", "-r", str(FPS),
                    "-c:v", "libx264", "-crf", "20", str(out)], check=True)


def build(root: Path, out_dir: Path) -> tuple[Path, Path]:
    """Validate the project, then write animatic.otio and animatic.mp4 to `out_dir`."""
    errors = stages.validate_project(root)
    if errors:
        raise ValueError("project does not validate:\n" + "\n".join(errors))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tl = timeline(stages.load_project(root))
    otio.adapters.write_to_file(tl, str(out_dir / "animatic.otio"))
    render(tl, root, out_dir / "animatic.mp4")
    return out_dir / "animatic.otio", out_dir / "animatic.mp4"
