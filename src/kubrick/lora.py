"""Bake a LoRA into a copy of a sharded safetensors checkpoint, for engines that cannot load one (h3.c, #17)."""

import json
import shutil
from pathlib import Path

PREFIX = "diffusion_model."


def _pairs(adapter: dict) -> dict[str, tuple]:
    """Base weight name -> (A, B, alpha or None), from ai-toolkit / PEFT style keys."""
    out = {}
    for k in adapter:
        if k.endswith(".lora_A.weight"):
            layer = k[: -len(".lora_A.weight")]
            alpha = adapter.get(layer + ".alpha")
            out[layer.removeprefix(PREFIX) + ".weight"] = (adapter[k], adapter[layer + ".lora_B.weight"], alpha)
    return out


def merge(adapter_path: Path, checkpoint: Path, out: Path, scale: float = 1.0) -> dict:
    """W += scale * (alpha / rank) * B @ A for every adapted weight, computed in float32 and stored in the
    weight's own dtype. Shards with no adapted weight are symlinked; the source checkpoint is never written."""
    import torch
    from safetensors.torch import load_file, save_file

    checkpoint, out = Path(checkpoint), Path(out)
    pairs = _pairs(load_file(str(adapter_path)))
    index = json.loads((checkpoint / "model.safetensors.index.json").read_text(encoding="utf-8"))
    missing = sorted(k for k in pairs if k not in index["weight_map"])
    if missing:
        raise ValueError(f"adapter layers not in the checkpoint: {', '.join(m.removesuffix('.weight') for m in missing[:5])}")
    out.mkdir(parents=True, exist_ok=True)
    by_shard = {}
    for k in pairs:
        by_shard.setdefault(index["weight_map"][k], []).append(k)
    for shard in sorted(set(index["weight_map"].values())):
        dst = out / shard
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        if shard not in by_shard:
            dst.symlink_to((checkpoint / shard).resolve())
            continue
        tensors = load_file(str(checkpoint / shard))
        for k in by_shard[shard]:
            A, B, alpha = pairs[k]
            factor = scale * (float(alpha) / A.shape[0] if alpha is not None else 1.0)
            w = tensors[k]
            tensors[k] = (w.float() + factor * (B.float() @ A.float())).to(w.dtype)
        save_file(tensors, str(dst), metadata={"format": "pt"})
    for name in ("model.safetensors.index.json", "config.json"):
        if (checkpoint / name).exists():
            shutil.copyfile(checkpoint / name, out / name)
    return {"layers": len(pairs), "shards_written": len(by_shard), "scale": scale}
