from collections import defaultdict


def score(truth: dict, predicted: list[int], tol: int = 2) -> dict:
    """Match each predicted cut to at most one transition; a gradual one matches anywhere in its span."""
    unmatched = sorted(predicted)
    per = defaultdict(lambda: {"tp": 0, "fn": 0})
    for t in truth["transitions"]:
        lo, hi = t["first"] - tol, t["last"] + tol
        hit = next((p for p in unmatched if lo <= p <= hi), None)
        if hit is None:
            per[t["kind"]]["fn"] += 1
        else:
            per[t["kind"]]["tp"] += 1
            unmatched.remove(hit)
    on_negative = [p for p in unmatched
                   if any(n["first"] - tol <= p <= n["last"] + tol for n in truth["negatives"])]
    tp = sum(v["tp"] for v in per.values())
    fn = sum(v["fn"] for v in per.values())
    fp = len(unmatched)
    minutes = truth["frames"] / truth["fps"] / 60
    for v in per.values():
        v["recall"] = v["tp"] / (v["tp"] + v["fn"]) if v["tp"] + v["fn"] else None
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    cut = per.get("cut", {"tp": 0, "fn": 0})
    cut_fp = fp  # every false detection counts against hard-cut precision
    cut_p = cut["tp"] / (cut["tp"] + cut_fp) if cut["tp"] + cut_fp else None
    cut_r = cut.get("recall")
    return {
        "per_kind": dict(per),
        "precision": precision,
        "recall": recall,
        "false": fp,
        "false_on_negatives": len(on_negative),
        "false_on_negatives_per_10min": len(on_negative) / minutes * 10 if minutes else None,
        "cut_f1": 2 * cut_p * cut_r / (cut_p + cut_r) if cut_p and cut_r else 0.0,
    }
