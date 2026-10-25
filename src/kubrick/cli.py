import argparse
import json
import sys
from pathlib import Path

from kubrick import cuts, knownset, synth
from kubrick.score import score


def commands() -> set[str]:
    return set(next(a for a in parser()._actions if a.dest == "cmd").choices)


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    return run(a)


def parser() -> argparse.ArgumentParser:
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
    e = sub.add_parser("scale-eval", help="leave-one-film-out shot-scale evaluation against CineScale")
    e.add_argument("films", nargs="+", help="features.npz:labels.csv[:pose.npz] per film")
    e.add_argument("--kind", choices=("linear", "boost"), default="boost")
    e.add_argument("--shuffles", type=int, default=2)
    b = sub.add_parser("breakdown", help="one row per shot (rows.jsonl) plus frame grabs")
    b.add_argument("video")
    b.add_argument("out_dir", type=Path)
    b.add_argument("--scale-model", type=Path)
    t = sub.add_parser("scale-train", help="train and save the shot-scale model on aligned films")
    t.add_argument("films", nargs="+", help="features.npz:labels.csv[:pose.npz] per film")
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--kind", choices=("linear", "boost"), default="boost")
    k = sub.add_parser("card", help="a text storyboard panel for one shot")
    k.add_argument("shot")
    k.add_argument("text")
    k.add_argument("out", type=Path)
    v = sub.add_parser("validate", help="check a project's stage documents and the joins between them")
    v.add_argument("project", type=Path)
    o = sub.add_parser("continuity", help="continuity violations per scene, one JSON line each")
    o.add_argument("project", type=Path)
    n = sub.add_parser("animatic", help="animatic.otio and animatic.mp4 from a valid project")
    n.add_argument("project", type=Path)
    n.add_argument("out_dir", type=Path)
    return p


def run(a: argparse.Namespace) -> int:

    if a.cmd == "card":
        from kubrick import animatic

        animatic.card(a.shot, a.text, a.out)
        return 0
    if a.cmd == "validate":
        from kubrick import stages

        errors = stages.validate_project(a.project)
        print("\n".join(errors) if errors else "ok")
        return 1 if errors else 0
    if a.cmd == "continuity":
        from kubrick import continuity, stages

        errors = stages.validate_project(a.project)
        if errors:
            print("\n".join(errors))
            return 2
        proj, found = stages.load_project(a.project), 0
        for scene in proj["shotlist.json"]["scenes"]:
            for v in continuity.check(stages.assemble(proj, scene["id"])):
                print(json.dumps({"scene": scene["id"], **v}))
                found += 1
        return 1 if found else 0
    if a.cmd == "animatic":
        from kubrick import animatic

        otio_path, mp4 = animatic.build(a.project, a.out_dir)
        print(json.dumps({"otio": str(otio_path), "mp4": str(mp4)}))
        return 0

    if a.cmd == "breakdown":
        from kubrick import breakdown

        rows = breakdown.breakdown(a.video, a.out_dir, a.scale_model)
        breakdown.write_jsonl(rows, a.out_dir / "rows.jsonl")
        print(json.dumps({"shots": len(rows), "rows": str(a.out_dir / "rows.jsonl")}))
        return 0

    if a.cmd == "scale-train":
        import numpy as np

        from kubrick import scale

        films = {}
        for spec in a.films:
            parts = spec.split(":")
            film = scale.load_film(Path(parts[0]), Path(parts[1]))
            if len(parts) > 2:
                film["pose"] = np.load(parts[2])["pose"]
            if film["align"]["accepted"]:
                films[Path(parts[0]).stem] = film
        model = scale.train_model(films, a.kind)
        scale.save_model(model, a.out)
        print(json.dumps({"trained_on": model["trained_on"], "features": list(model["features"]), "out": str(a.out)}))
        return 0

    if a.cmd == "scale-eval":
        import numpy as np

        from kubrick import scale

        films = {}
        for spec in a.films:
            parts = spec.split(":")
            film = scale.load_film(Path(parts[0]), Path(parts[1]))
            if len(parts) > 2:
                film["pose"] = np.load(parts[2])["pose"]
            print(json.dumps({"film": Path(parts[0]).stem, "aligned": film["align"]["accepted"],
                              "z": round(film["align"]["z"], 1)}), flush=True)
            if film["align"]["accepted"]:
                films[Path(parts[0]).stem] = film
        for te in films:
            tr = [n for n in films if n != te]
            r = scale.evaluate(films, tr, [te], kind=a.kind)[te]
            ctl = [scale.evaluate(films, tr, [te], shuffle=True, seed=s, kind=a.kind)[te]["kappa_linear"]
                   for s in range(a.shuffles)]
            print(json.dumps({"test": te, **{k: round(v, 3) for k, v in r.items()},
                              "shuffled_kappa_max": round(max(ctl), 3) if ctl else None}), flush=True)
        return 0

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
