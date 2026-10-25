"""Camera movement from global optical flow, validated on clips whose motion is known exactly."""

import cv2
import numpy as np

from kubrick.cuts import Knob

W, H = 640, 360
FLOW_W = 160  # flow is estimated on a small grey copy; motion is reported in full-frame pixels
# per-frame thresholds, chosen on known-answer seed 0 and confirmed on seed 1
ZOOM = Knob(0.001, (0.001, 0.002, 0.003, 0.005))  # mean relative scale change per frame
SHIFT = Knob(0.3, (0.3, 0.6, 1.0, 1.5))  # mean translation per frame, full-frame pixels
JITTER = Knob(0.4, (0.4, 0.8, 1.2, 2.0))  # sd of per-frame translation
MIN_TEXTURE = Knob(12.0, (5.0, 12.0, 25.0))  # Laplacian variance, 160-px grey; black frame 4.4, faintest real still 30.9


def render(still: np.ndarray, kind: str, frames: int = 48, seed: int = 0, amount: float = 1.0) -> np.ndarray:
    """A clip made by moving a W x H crop over `still` (scaled to 1.6x the frame). `amount` scales the motion."""
    rng = np.random.default_rng(seed)
    big = cv2.resize(still, (int(W * 1.6), int(H * 1.6)), interpolation=cv2.INTER_AREA)
    bh, bw = big.shape[:2]
    cx, cy, size = bw / 2, bh / 2, 1.0
    t = np.linspace(0, 1, frames)
    sign = rng.choice([-1, 1])
    shake = np.cumsum(rng.normal(0, 1.5, (frames, 2)), axis=0)
    shake -= np.linspace(shake[0], shake[-1], frames)  # jitter with no net travel
    out = []
    for i in range(frames):
        x, y, s = cx, cy, size
        if kind == "pan":
            x += sign * amount * (t[i] - 0.5) * W * 0.4
        elif kind == "tilt":
            y += sign * amount * (t[i] - 0.5) * H * 0.4
        elif kind == "push":
            s = 1.0 - amount * 0.3 * t[i]
        elif kind == "pull":
            s = 0.7 + amount * 0.3 * t[i]
        elif kind == "handheld":
            x, y = x + amount * shake[i, 0], y + amount * shake[i, 1]
        elif kind != "static":
            raise ValueError(f"unknown movement {kind!r}")
        w, h = W * s, H * s
        x0, y0 = int(round(x - w / 2)), int(round(y - h / 2))
        crop = big[max(y0, 0):y0 + int(h), max(x0, 0):x0 + int(w)]
        out.append(cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA))
    return np.array(out)


def motion(clip: np.ndarray) -> dict:
    """Per-frame translation (tx, ty, full-frame px) and relative scale change, fitted to dense flow."""
    fh = int(FLOW_W * clip.shape[1] / clip.shape[2])
    k = clip.shape[2] / FLOW_W
    grey = [cv2.cvtColor(cv2.resize(f, (FLOW_W, fh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY) for f in clip]
    ys, xs = np.mgrid[0:fh, 0:FLOW_W].astype(np.float32)
    xc, yc = (xs - FLOW_W / 2).ravel(), (ys - fh / 2).ravel()
    A = np.zeros((2 * xc.size, 3), np.float32)
    A[0::2, 0], A[0::2, 2] = 1, xc
    A[1::2, 1], A[1::2, 2] = 1, yc
    rows = []
    for a, b in zip(grey[:-1], grey[1:]):
        f = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        sol, *_ = np.linalg.lstsq(A, f.reshape(-1), rcond=None)  # u = tx + s x, v = ty + s y
        rows.append(sol)
    m = np.array(rows)
    tx, ty, s = m[:, 0] * k, m[:, 1] * k, m[:, 2]
    # a steady pan has constant per-frame translation; shake is its spread from frame to frame
    return {"tx": float(tx.mean()), "ty": float(ty.mean()), "zoom": float(s.mean()),
            "jitter": float(np.hypot(tx.std(), ty.std())), "texture": texture_of(grey[0])}


def texture_of(grey: np.ndarray) -> float:
    """Laplacian variance of the small grey frame: how much detail flow has to lock on to."""
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


def classify(m: dict, zoom: float | None = None, shift: float | None = None, jitter: float | None = None) -> str:
    """One label from the taxonomy. Content moves opposite to the camera: a push in makes flow expand."""
    if m.get("texture", np.inf) < MIN_TEXTURE.default:
        return "unknown:no-texture"
    zoom = ZOOM.default if zoom is None else zoom
    shift = SHIFT.default if shift is None else shift
    jitter = JITTER.default if jitter is None else jitter
    travel = max(abs(m["tx"]), abs(m["ty"]))
    # compare like with like: a zoom of s moves the frame edge s * W/2 px per frame; picture entering
    # one edge during a pan reads as a small zoom, so zoom wins only when its edge motion beats the travel
    if abs(m["zoom"]) >= zoom and abs(m["zoom"]) * W / 2 > travel:
        return "push" if m["zoom"] > 0 else "pull"
    if travel >= shift:
        return "pan" if abs(m["tx"]) >= abs(m["ty"]) else "tilt"
    if m["jitter"] >= jitter:
        return "handheld"
    return "static"


KINDS = ("static", "pan", "tilt", "push", "pull", "handheld")


def known_set(stills: list[np.ndarray], seed: int, amounts: tuple[float, ...] = (0.5, 1.0)) -> list[dict]:
    """Every kind at every amount over every still with detail, with its measured motion.
    Stills below MIN_TEXTURE are skipped (count in known_set.skipped): their motion cannot be seen."""
    cases, i = [], 0
    known_set.skipped = 0
    for still in stills:
        small = cv2.resize(still, (FLOW_W, int(FLOW_W * still.shape[0] / still.shape[1])), interpolation=cv2.INTER_AREA)
        if texture_of(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)) < MIN_TEXTURE.default:
            known_set.skipped += 1
            continue
        for kind in KINDS:
            for amount in amounts:
                cases.append({"kind": kind, "amount": amount,
                              "motion": motion(render(still, kind, seed=seed * 100003 + i, amount=amount))})
                i += 1
    return cases


def score(cases: list[dict], **thresholds) -> dict[str, float]:
    """Share of each kind's cases classified as that kind."""
    out = {}
    for kind in KINDS:
        own = [c for c in cases if c["kind"] == kind]
        out[kind] = sum(classify(c["motion"], **thresholds) == kind for c in own) / len(own) if own else float("nan")
    return out


def direction(m: dict) -> str:
    """Where the camera moves, for screen-direction bookkeeping: opposite to the content's flow."""
    if abs(m["tx"]) >= abs(m["ty"]):
        return "right" if m["tx"] < 0 else "left"
    return "down" if m["ty"] < 0 else "up"
