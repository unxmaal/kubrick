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
    c.add_argument("--detector", choices=cuts.DETECTORS, default="transnet")
    c.add_argument("--threshold", type=float)
    c.add_argument("--flash-guard", type=float)
    c.add_argument("--min-len", type=int)
    w = sub.add_parser("sweep", help="score every detector across its registered thresholds")
    w.add_argument("video", type=Path)
    f = sub.add_parser("features", help="per-second image features and thumbnails (.npz)")
    f.add_argument("video")
    f.add_argument("out", type=Path)
    f.add_argument("--model")
    f.add_argument("--grid", type=int)
    q = sub.add_parser("pose", help="per-second body-pose and face features (.npz)")
    q.add_argument("video")
    q.add_argument("out", type=Path)
    a = p.parse_args(argv)

    if a.cmd == "pose":
        import numpy as np

        from kubrick import pose, scale

        rows = [pose.features(frame) for _, frame in scale.sample_frames(a.video)]
        np.savez_compressed(a.out, pose=np.array(rows, np.float32), n_features=pose.N_FEATURES,
                            min_confidence=pose.MIN_CONFIDENCE, height=scale.H)
        return 0

    if a.cmd == "features":
        from kubrick import scale

        scale.featurise(a.video, a.out, model=a.model or scale.EMBED_MODEL,
                        grid=scale.GRID if a.grid is None else a.grid)
        return 0

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

        def emit(found: list[int], **setting) -> None:
            r = score(truth, cuts._min_len(found, cuts.MIN_LEN.default))
            print(json.dumps({
                **setting, "cut_f1": round(r["cut_f1"], 3),
                **{f"{k}_recall": round(v["recall"], 3) for k, v in r["per_kind"].items()},
                "false": r["false"], "negatives_triggered": round(r["negatives_triggered"], 3),
                "false_elsewhere_per_10min": round(r["false_elsewhere_per_10min"], 2)}), flush=True)

        for name, knob in cuts.DETECTORS.items():
            for t in knob.sweep:
                if name == "transnet":
                    for sp in cuts.TRANSNET_SPAN.sweep:
                        for gap in cuts.GAP_CLOSE.sweep:
                            emit(cuts._transnet(video, t, sp, gap), detector=name, threshold=t, span=sp, gap=gap)
                    continue
                raw = cuts.detect(video, name, t, min_len=1, flash_guard=0)
                for g in cuts.FLASH_GUARD.sweep:
                    emit(cuts._drop_flashes(video, raw, g) if g else raw, detector=name, threshold=t, flash_guard=g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
