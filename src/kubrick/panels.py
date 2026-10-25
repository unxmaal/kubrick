"""Storyboard panels drawn two at a time, checked, kept or redrawn within a fixed budget (#29)."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

CLOSE = {"ECU", "CU", "MCU", "MS"}  # close enough that a person the detector misses is worth a doubt
HARD, SOFT = 10, 1
PER_TRY = 2  # candidates per wording; prompts() has four wordings, so eight images at most
UNIFORM_STD = 3.0
SCALE_WORDS = {"ECU": "An extreme close-up", "CU": "A close-up", "MCU": "A medium close-up", "MS": "A medium shot",
               "MLS": "A medium long shot, whole figures", "LS": "A long shot, figures small in the frame",
               "ELS": "An extreme long shot, figures tiny in the frame", "INS": "A close insert of a detail",
               "FS": "A shot with a figure close in the foreground"}


def judge(shot: dict, humans: int, faces: int, uniform: bool) -> dict:
    """Hard reasons fail a panel; soft ones only lower its score."""
    n, hard, soft = len(shot["subjects"]), [], []
    if uniform:
        hard.append("blank or near-uniform image")
    if humans > n:
        hard.append(f"{humans} people where the shot list has {n}")
    if faces > max(humans, n):
        hard.append(f"{faces} faces for {max(humans, n)} people")
    if humans < n and shot["scale"] in CLOSE:
        soft.append(f"found {humans} of {n} people")
    return {"hard": hard, "soft": soft, "score": -HARD * len(hard) - SOFT * len(soft), "flagged": bool(hard)}


def prompts(shot: dict, style: str) -> list[str]:
    """The first wording, then a ladder: state the count, lead with scale and count, then keep only the first
    sentence and say nothing else is there."""
    n = len(shot["subjects"])
    count = "No people in the frame. " if n == 0 else f"Exactly {n} {'person' if n == 1 else 'people'} in the frame. "
    scale = SCALE_WORDS.get(shot["scale"], "") + ". "
    first = shot["description"].split(". ")[0].rstrip(".") + "."
    return [style + shot["description"], style + count + shot["description"],
            style + scale + count + shot["description"], style + scale + count + first + " Nothing else in the frame."]


def vision_count(path: Path) -> tuple[int, int]:
    import Vision
    from Foundation import NSData

    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(NSData.dataWithContentsOfFile_(str(path)), None)
    humans, faces = Vision.VNDetectHumanRectanglesRequest.alloc().init(), Vision.VNDetectFaceRectanglesRequest.alloc().init()
    humans.setUpperBodyOnly_(False)
    ok, err = handler.performRequests_error_([humans, faces], None)
    if not ok:
        raise RuntimeError(f"Vision failed on {path}: {err}")
    return len(humans.results() or []), len(faces.results() or [])


def _uniform(path: Path) -> bool:
    import cv2

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return img is None or float(img.std()) < UNIFORM_STD


def make(shot: dict, style: str, out_dir: Path, generate, count=vision_count, seed: int = 1) -> dict:
    """Draw PER_TRY candidates per wording until one passes or the wordings run out; keep the best."""
    out_dir = Path(out_dir)
    (out_dir / "attempts").mkdir(parents=True, exist_ok=True)
    best, k = None, 0
    with open(out_dir / "attempts.jsonl", "a", encoding="utf-8") as log:
        for t, prompt in enumerate(prompts(shot, style)):
            for _ in range(PER_TRY):
                image = generate(prompt, seed + k, out_dir / "attempts" / f"{shot['id']}-{k}.png")
                humans, faces = count(image)
                v = {**judge(shot, humans, faces, _uniform(image)), "candidate": k, "image": str(image)}
                log.write(json.dumps({"shot": shot["id"], "try": t, "prompt": prompt, "seed": seed + k,
                                      "humans": humans, "faces": faces, **v}) + "\n")
                if best is None or v["score"] > best["score"]:
                    best = v
                k += 1
            if not best["flagged"]:
                break
    shutil.copyfile(best["image"], out_dir / f"{shot['id']}.png")
    return best


def run(root: Path, style: str, generate, count=vision_count, seed: int = 1, only=None) -> list[dict]:
    """Every shot without an Eric sketch gets a checked panel; storyboard.json records which are still flagged."""
    root = Path(root)
    shots = [s for sc in json.loads((root / "shotlist.json").read_text(encoding="utf-8"))["scenes"] for s in sc["shots"]]
    sb_path = root / "storyboard.json"
    board = {p["shot"]: p for p in json.loads(sb_path.read_text(encoding="utf-8"))["panels"]} if sb_path.exists() else {}
    out = []
    for s in shots:
        kept = board.get(s["id"], {})
        if kept.get("source") in ("sketch", "card") or (only and s["id"] not in only):
            continue
        v = make(s, style, root / "panels", generate, count, seed)
        board[s["id"]] = {"shot": s["id"], "image": f"panels/{s['id']}.png", "source": "generated",
                          **({"flagged": v["hard"]} if v["flagged"] else {})}
        out.append({"shot": s["id"], **{k: v[k] for k in ("flagged", "hard", "soft", "candidate")}})
    order = [s["id"] for s in shots]
    sb_path.write_text(json.dumps({"panels": sorted(board.values(), key=lambda p: order.index(p["shot"]))}, indent=1),
                       encoding="utf-8")
    return out


def soh_generate(model: str | None = None, width: int = 768, height: int = 432):
    """A generate() over SoHoT's queue, so it waits its turn for memory like every other job."""
    def generate(prompt, seed, out):
        args = ["uv", "run", "soh", "image", "--width", str(width), "--height", str(height), "--seed", str(seed),
                "-o", str(Path(out).resolve()), prompt, "--json"] + (["-m", model] if model else [])
        r = subprocess.run(args, cwd=Path.home() / "localharness" / "deploy", capture_output=True, text=True)
        if r.returncode or not Path(out).is_file() or Path(out).stat().st_size == 0:
            raise RuntimeError(f"soh image failed for {out}: {r.stdout[-300:]} {r.stderr[-300:]}")
        return Path(out)
    return generate
