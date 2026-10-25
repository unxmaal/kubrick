"""Shot-scale labelling validated against CineScale's human labels."""

import csv
import subprocess
from pathlib import Path

import numpy as np

from kubrick import taxonomy

EMBED_MODEL = "facebook/dinov2-small"
# film, NTSC (24000/1001) and PAL (25) ratios: 25/24 alone drifts ~3 s an hour against 23.976 -> 25
SPEEDS = (1.0, 24 / 25, 25 / 24, 1000 / 1001, 1001 / 1000, 24000 / 25025, 25025 / 24000)
H = 224


def read_cinescale(path: Path) -> np.ndarray:
    """Label code per annotated second; -1 where CineScale says not available."""
    codes = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = int(row["shotscale"])
            codes.append(c if str(c) in taxonomy.load()["scale"]["cinescale_codes"] else -1)
    return np.array(codes)


def sample_frames(path: str, fps: float = 1.0):
    """Yield (second, RGB frame of height H) at `fps`, decoded in one pass."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,sample_aspect_ratio", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    sar = probe[2] if len(probe) > 2 and ":" in probe[2] else "1:1"
    num, den = (int(x) for x in sar.split(":"))
    width = int(round(w * num / den / h * H / 2)) * 2
    proc = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vf",
         f"fps={fps},scale={width}:{H},setsar=1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE)
    size = width * H * 3
    i = 0
    while chunk := proc.stdout.read(size):
        if len(chunk) < size:
            break
        yield i / fps, np.frombuffer(chunk, np.uint8).reshape(H, width, 3)
        i += 1
    proc.wait()


def change_signal(thumbs: np.ndarray) -> np.ndarray:
    """d[t] = mean abs difference between samples t-1 and t; d[0] = 0."""
    d = np.abs(np.diff(thumbs.astype(np.int16), axis=0)).mean(axis=(1, 2))
    return np.concatenate([[0.0], d])


MIN_MARKS = 50  # label changes a whole-film fit needs; windows pass fewer


def align(labels: np.ndarray, change: np.ndarray, max_offset: int = 600, min_marks: int = MIN_MARKS) -> dict:
    """Find speed and offset mapping annotated second t to our second t*speed + offset.

    Score: mean picture change at our seconds where the human label changes. A real alignment puts
    label changes on cuts; the null is the same score with label-change times shuffled."""
    marks = np.flatnonzero((labels[1:] != labels[:-1]) & (labels[1:] >= 0) & (labels[:-1] >= 0)) + 1
    best = {"score": -np.inf}
    for s in SPEEDS:
        for o in range(-max_offset, max_offset + 1):
            ours = np.rint(marks * s + o).astype(int)
            ok = (ours > 0) & (ours < len(change))
            if ok.sum() < min_marks:
                continue
            sc = change[ours[ok]].mean()
            if sc > best["score"]:
                best = {"score": float(sc), "speed": s, "offset": o, "marks": int(ok.sum())}
    if "marks" not in best:
        return {"score": None, "speed": None, "offset": None, "marks": 0, "z": float("-inf"),
                "reason": f"fewer than {min_marks} label changes land inside the copy"}
    rng = np.random.default_rng(0)
    null = [change[rng.integers(1, len(change), best["marks"])].mean() for _ in range(200)]
    best["null_mean"], best["null_sd"] = float(np.mean(null)), float(np.std(null))
    best["z"] = (best["score"] - best["null_mean"]) / best["null_sd"]
    return best


def map_labels(labels: np.ndarray, n_ours: int, speed: float, offset: int) -> np.ndarray:
    """Label for each of our seconds, -1 where no annotated second maps to it."""
    out = np.full(n_ours, -1)
    ours = np.rint(np.arange(len(labels)) * speed + offset).astype(int)
    ok = (ours >= 0) & (ours < n_ours)
    out[ours[ok]] = labels[ok]
    return out


def _ordinal_codes() -> tuple[int, ...]:
    """CineScale codes of the scales on the ordinal ladder (ECU..ELS), in ladder order, from taxonomy.toml."""
    s = taxonomy.load()["scale"]
    by_name = {v: int(k) for k, v in s["cinescale_codes"].items()}
    return tuple(by_name[name] for name in s["ordinal"])


ORDINAL = _ordinal_codes()  # FS and INS are not on the ladder
MIN_Z = 8.0  # alignment must beat shuffled label-change times by this many sd to be used


HALF_OFFSET_TOLERANCE = 2  # seconds the two halves' offsets may differ by


def check_alignment(labels: np.ndarray, change: np.ndarray, min_marks: int = MIN_MARKS,
                    min_z: float | None = None) -> dict:
    """Align the whole film and each half alone. A real alignment agrees with itself; a spurious one
    (a different edition, a partial copy) gives halves with different speeds or offsets."""
    min_z = MIN_Z if min_z is None else min_z
    whole = align(labels, change, min_marks=min_marks)
    if whole["marks"] == 0:
        return {**whole, "halves": [], "accepted": False}
    # split only the labels that land inside the copy, so a partial copy (disc 1 of 2) is tested on
    # the part it holds rather than on a second half that cannot match anything
    mapped = np.rint(np.arange(len(labels)) * whole["speed"] + whole["offset"])
    idx = np.flatnonzero((labels >= 0) & (mapped >= 0) & (mapped < len(change)))
    mid = (idx[0] + idx[-1]) // 2
    first, second = np.full_like(labels, -1), np.full_like(labels, -1)
    first[idx[idx < mid]] = labels[idx[idx < mid]]
    second[idx[idx >= mid]] = labels[idx[idx >= mid]]
    halves = [align(h, change, min_marks=max(min_marks // 2, 10)) for h in (first, second)]
    agree = all(h["marks"] and h["speed"] == whole["speed"]
                and abs(h["offset"] - whole["offset"]) <= HALF_OFFSET_TOLERANCE
                and h["z"] >= min_z / 2 ** 0.5 for h in halves)  # half the marks, z shrinks by sqrt 2
    return {**whole, "halves": [(h["speed"], h["offset"], round(h["z"], 1)) for h in halves],
            "accepted": bool(agree and whole["z"] >= min_z)}


def load_film(npz: Path, csv_path: Path) -> dict:
    """Features and per-second labels; labels are all -1 unless the alignment is accepted."""
    d = np.load(npz)
    labels = read_cinescale(csv_path)
    a = check_alignment(labels, change_signal(d["thumbs"]))
    y = (map_labels(labels, len(d["feats"]), a["speed"], a["offset"]) if a["accepted"]
         else np.full(len(d["feats"]), -1))
    features = (str(d["model"]), int(d["grid"])) if "model" in d else ("unknown", -1)
    return {"X": d["feats"], "y": y, "align": a, "features": features}


PCA_DIMS = 64  # image features reduced before boosting; pose features are appended whole
THREE = {1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 2, 7: 2}  # close / medium / long, as in CineScale's earlier work


def _classifier(kind: str):
    from sklearn.decomposition import PCA
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if kind == "linear":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1))
    if kind == "boost":
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0), \
            PCA(PCA_DIMS, random_state=0)
    raise ValueError(f"unknown classifier {kind!r}")


def evaluate(films: dict[str, dict], train: list[str], test: list[str], shuffle: bool = False,
             seed: int = 0, kind: str = "linear") -> dict:
    """Train on `train`, score each of `test`. A film may carry "pose" features, appended to the image
    features (linear) or to their PCA reduction (boost)."""
    from sklearn.metrics import accuracy_score, cohen_kappa_score

    configs = {films[n].get("features") for n in train + test}
    if len(configs) > 1:
        raise ValueError(f"films carry different feature configurations: {sorted(map(str, configs))}")
    rng = np.random.default_rng(seed)

    model = _classifier(kind)
    clf, pca = model if isinstance(model, tuple) else (model, None)

    def raw(names):
        X, P, y = [], [], []
        for n in names:
            m = films[n]["y"] >= 0
            X.append(films[n]["X"][m])
            P.append(films[n]["pose"][m] if "pose" in films[n] else np.zeros((m.sum(), 0)))
            yy = films[n]["y"][m]
            y.append(rng.permutation(yy) if shuffle else yy)
        return np.concatenate(X), np.concatenate(P), np.concatenate(y)

    def feats(X, P):
        return np.hstack([pca.transform(X) if pca is not None else X, P])

    Xtr, Ptr, ytr = raw(train)
    if pca is not None:
        pca.fit(Xtr)
    clf.fit(feats(Xtr, Ptr), ytr)
    out = {}
    for n in test:
        X, P, y = _unshuffled(films[n])  # only training labels are ever shuffled
        p = clf.predict(feats(X, P))
        o = np.isin(y, ORDINAL) & np.isin(p, ORDINAL)
        t = np.isin(y, list(THREE)) & np.isin(p, list(THREE))
        out[n] = {"n": len(y), "accuracy": float(accuracy_score(y, p)),
                  "kappa_linear": float(cohen_kappa_score(y[o], p[o], weights="linear")),
                  "within_one": float(np.mean(np.abs(y[o] - p[o]) <= 1)),
                  "three_class_accuracy": float(np.mean([THREE[a] == THREE[b] for a, b in zip(y[t], p[t])]))}
    return out


def _unshuffled(film: dict):
    m = film["y"] >= 0
    P = film["pose"][m] if "pose" in film else np.zeros((m.sum(), 0))
    return film["X"][m], P, film["y"][m]


GRID = 4  # patch tokens pooled to GRID x GRID cells; 0 keeps CLS + mean only


class Embedder:
    def __init__(self, model: str = EMBED_MODEL, device: str | None = None, grid: int = GRID):
        self.grid = grid
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self.torch = torch
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.proc = AutoImageProcessor.from_pretrained(model)
        self.model = AutoModel.from_pretrained(model).to(self.device).eval()

    def __call__(self, frames: list[np.ndarray]) -> np.ndarray:
        with self.torch.no_grad():
            x = self.proc(images=frames, return_tensors="pt").to(self.device)
            h = self.model(**x).last_hidden_state
            parts = [h[:, 0], h[:, 1:].mean(1)]
            if self.grid:
                # shot scale is how big the subject is in the frame, so keep where things are
                side = int((h.shape[1] - 1) ** 0.5)
                patches = h[:, 1:].reshape(h.shape[0], side, side, -1).permute(0, 3, 1, 2)
                parts.append(self.torch.nn.functional.adaptive_avg_pool2d(patches, self.grid).flatten(1))
            return self.torch.cat(parts, dim=1).cpu().numpy()


def featurise(path: str, out: Path, batch: int = 64, model: str = EMBED_MODEL, grid: int = GRID) -> None:
    """Per-second image features and 32x18 grey thumbnails for alignment, saved to `out` (.npz)."""
    emb = Embedder(model, grid=grid)
    feats, thumbs, buf = [], [], []
    for _, frame in sample_frames(path):
        buf.append(frame)
        g = frame.mean(axis=2)
        hh, ww = g.shape
        thumbs.append(g[: hh - hh % 18, : ww - ww % 32].reshape(18, hh // 18, 32, ww // 32).mean(axis=(1, 3)))
        if len(buf) == batch:
            feats.append(emb(buf))
            buf = []
    if buf:
        feats.append(emb(buf))
    np.savez_compressed(out, feats=np.concatenate(feats), thumbs=np.array(thumbs, np.uint8),
                        model=np.array(model), grid=np.array(grid))
