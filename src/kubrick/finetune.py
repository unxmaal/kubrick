"""Shot-scale labelling by fine-tuning an image backbone end to end on frames at the labelled seconds."""

import subprocess

import numpy as np

from kubrick.scale import EMBED_MODEL, frame_size

SIZE = 224
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


def frames_at(path: str, size: int = SIZE) -> np.ndarray:
    """One frame per second, the whole frame squashed to size x size so no edge of the composition is cropped.
    Frame i is second i, the same sampling scale.featurise uses, so it lines up with a film's labels."""
    frame_size(path)  # fails early on an unreadable file
    raw = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vf",
                          f"fps=1,scale={size}:{size}:flags=area,setsar=1", "-pix_fmt", "rgb24", "-f", "rawvideo",
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, size, size, 3)


class Dinov2:
    """last_hidden_state of a Hugging Face DINOv2, the backbone the frozen labeller used."""

    def __new__(cls, model: str = EMBED_MODEL):
        import torch
        from transformers import AutoModel

        class Wrapped(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.net = AutoModel.from_pretrained(model)
                self.hidden = self.net.config.hidden_size

            def forward(self, x):
                return self.net(pixel_values=x).last_hidden_state

        return Wrapped()


def _device(device):
    import torch

    return device or ("mps" if torch.backends.mps.is_available() else "cpu")


def _batch(X, size, device, augment, rng):
    import torch

    x = torch.from_numpy(np.ascontiguousarray(X)).to(device).permute(0, 3, 1, 2).float() / 255
    if x.shape[-1] != size:
        x = torch.nn.functional.interpolate(x, size=(size, size), mode="bilinear", antialias=True)
    if augment:
        flip = torch.from_numpy(rng.random(len(x)) < 0.5).to(device)
        x = torch.where(flip[:, None, None, None], x.flip(-1), x)  # mirror keeps shot scale; crops would not
        x = x * torch.from_numpy(rng.uniform(0.8, 1.2, (len(x), 1, 1, 1))).float().to(device)
    mean = torch.tensor(MEAN, device=device)[None, :, None, None]
    std = torch.tensor(STD, device=device)[None, :, None, None]
    return (x.clamp(0, 1) - mean) / std


def train(X: np.ndarray, y: np.ndarray, n_classes: int | None = None, backbone=Dinov2, epochs: int = 3,
          lr_backbone: float = 1e-5, lr_head: float = 1e-3, batch: int = 32, size: int = SIZE,
          device: str | None = None, seed: int = 0, log=None) -> dict:
    """Backbone plus a linear head on CLS and mean token, trained with class-balanced cross-entropy.
    Labels may be any integer codes; the model maps them back on predict."""
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = _device(device)
    codes = np.unique(y) if n_classes is None else np.arange(n_classes)
    index = {int(c): i for i, c in enumerate(codes)}
    t = torch.tensor([index[int(v)] for v in y], device=device)
    body = backbone().to(device)
    head = torch.nn.Linear(2 * body.hidden, len(codes)).to(device)
    counts = np.bincount(t.cpu().numpy(), minlength=len(codes)).astype(float)
    weight = torch.tensor(np.where(counts > 0, counts.sum() / np.maximum(counts, 1) / len(codes), 0.0),
                          dtype=torch.float32, device=device)
    opt = torch.optim.AdamW([{"params": body.parameters(), "lr": lr_backbone},
                             {"params": head.parameters(), "lr": lr_head}], weight_decay=0.01)
    steps = epochs * ((len(X) + batch - 1) // batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[lr_backbone, lr_head], total_steps=steps,
                                                pct_start=0.1)
    body.train()
    for epoch in range(epochs):
        order = rng.permutation(len(X))
        total = 0.0
        for k in range(0, len(X), batch):
            pick = order[k:k + batch]
            h = body(_batch(X[pick], size, device, True, rng))
            loss = torch.nn.functional.cross_entropy(head(torch.cat([h[:, 0], h.mean(1)], 1)), t[pick],
                                                     weight=weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            total += float(loss) * len(pick)
        if log:
            log(f"epoch {epoch + 1}/{epochs} loss {total / len(X):.4f}")
    return {"body": body.eval(), "head": head.eval(), "codes": codes, "size": size, "device": device}


def predict(model: dict, X: np.ndarray, batch: int = 64) -> np.ndarray:
    import torch

    out = []
    with torch.no_grad():
        for k in range(0, len(X), batch):
            h = model["body"](_batch(X[k:k + batch], model["size"], model["device"], False, None))
            out.append(model["head"](torch.cat([h[:, 0], h.mean(1)], 1)).argmax(1).cpu().numpy())
    return model["codes"][np.concatenate(out)] if out else np.array([], int)


def leave_one_out(films: dict[str, dict], frames: dict[str, np.ndarray], cuts: dict[str, dict], epochs: int = 3,
                  stride: int = 2, shuffle: bool = False, draws: int = 100, boots: int = 200, log=None) -> dict:
    """Fine-tune on the other films (every `stride`-th labelled second), label the held-out film, and return
    per-film kappa beside fitness.leave_one_out_with's per-rule verdicts. `shuffle` permutes training labels."""
    from sklearn.metrics import cohen_kappa_score

    from kubrick import fitness, scale

    kappa = {}

    def fit_predict(others, test):
        idx = {n: np.flatnonzero(films[n]["y"] >= 0)[::stride] for n in others}
        X = np.concatenate([frames[n][idx[n]] for n in others])
        y = np.concatenate([films[n]["y"][idx[n]] for n in others])
        if shuffle:
            y = np.random.default_rng(0).permutation(y)
        model = train(X, y, epochs=epochs, log=log)
        m = np.flatnonzero(films[test]["y"] >= 0)
        pred = np.full(len(films[test]["y"]), -1)
        pred[m] = predict(model, frames[test][m])
        t, p = films[test]["y"][m], pred[m]
        o = np.isin(t, scale.ORDINAL) & np.isin(p, scale.ORDINAL)
        kappa[test] = {"kappa_linear": float(cohen_kappa_score(t[o], p[o], weights="linear")),
                       "within_one": float(np.mean(np.abs(t[o] - p[o]) <= 1)), "accuracy": float(np.mean(t == p))}
        return pred

    fit = fitness.leave_one_out_with(films, cuts, fit_predict, draws=draws, boots=boots)
    return {n: {**kappa[n], "fitness": fit[n]} for n in films}
