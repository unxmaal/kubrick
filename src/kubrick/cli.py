import argparse
import json
import sys
from pathlib import Path

from kubrick import cuts, knownset, synth
from kubrick.score import score


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kubrick")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth", help="build a known-answer clip from a spec")
    s.add_argument("spec", type=Path)
    s.add_argument("out", type=Path)
    k = sub.add_parser("knownset", help="known-answer set from single-shot segments of real films")
    k.add_argument("out_dir", type=Path)
    k.add_argument("films", nargs="+")
    k.add_argument("--segments", type=int, default=60)
    k.add_argument("--seed", type=int, default=0)
    c = sub.add_parser("cuts", help="detect cuts")
    c.add_argument("video")
    c.add_argument("--detector", choices=cuts.DETECTORS, default="adaptive")
    c.add_argument("--threshold", type=float)
    c.add_argument("--flash-guard", type=float)
    c.add_argument("--min-len", type=int)
    w = sub.add_parser("sweep", help="score every detector across its registered thresholds")
    w.add_argument("video", type=Path)
    a = p.parse_args(argv)

    if a.cmd == "synth":
        synth.build(synth.Spec.from_dict(json.loads(a.spec.read_text())), a.out)
    elif a.cmd == "knownset":
        t = knownset.make(a.films, a.segments, a.seed, a.out_dir)
        print(json.dumps({"frames": t["frames"], "transitions": len(t["transitions"]),
                          "negatives": len(t["negatives"])}))
    elif a.cmd == "cuts":
        print(json.dumps(cuts.detect(a.video, a.detector, a.threshold, a.min_len, a.flash_guard)))
    elif a.cmd == "sweep":
        truth = json.loads(a.video.with_suffix(".truth.json").read_text())
        video = str(a.video)
        for name, knob in cuts.DETECTORS.items():
            for t in knob.sweep:
                raw = cuts.detect(video, name, t, min_len=1, flash_guard=0)
                for g in cuts.FLASH_GUARD.sweep:
                    found = cuts._min_len(cuts._drop_flashes(video, raw, g) if g else raw, cuts.MIN_LEN.default)
                    r = score(truth, found)
                    print(json.dumps({
                        "detector": name, "threshold": t, "flash_guard": g, "cut_f1": round(r["cut_f1"], 3),
                        **{f"{k}_recall": round(v["recall"], 3) for k, v in r["per_kind"].items()},
                        "false": r["false"], "negatives_triggered": round(r["negatives_triggered"], 3),
                        "false_elsewhere_per_10min": round(r["false_elsewhere_per_10min"], 2)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
