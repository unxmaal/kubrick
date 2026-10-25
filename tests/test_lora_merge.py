import json

import pytest
import torch
from safetensors.torch import load_file, save_file

from kubrick import lora


def checkpoint(tmp_path):
    d = tmp_path / "transformer"
    d.mkdir()
    torch.manual_seed(0)
    a = {"blocks.0.attn.qkv_proj.weight": torch.randn(6, 4, dtype=torch.bfloat16),
         "blocks.0.norm1.weight": torch.ones(4, dtype=torch.bfloat16)}
    b = {"blocks.1.mlp.fc1.weight": torch.randn(8, 4, dtype=torch.bfloat16)}
    save_file(a, str(d / "model-00001-of-00002.safetensors"))
    save_file(b, str(d / "model-00002-of-00002.safetensors"))
    wm = {**{k: "model-00001-of-00002.safetensors" for k in a}, **{k: "model-00002-of-00002.safetensors" for k in b}}
    (d / "model.safetensors.index.json").write_text(json.dumps({"metadata": {}, "weight_map": wm}))
    (d / "config.json").write_text("{}")
    return d, a, b


def adapter(tmp_path, rank=2, key="blocks.0.attn.qkv_proj", out=6, inp=4):
    torch.manual_seed(1)
    A, B = torch.randn(rank, inp, dtype=torch.bfloat16), torch.randn(out, rank, dtype=torch.bfloat16)
    p = tmp_path / "style.safetensors"
    save_file({f"diffusion_model.{key}.lora_A.weight": A, f"diffusion_model.{key}.lora_B.weight": B}, str(p))
    return p, A, B


def test_merging_adds_scale_times_b_a_to_the_named_weight_only(tmp_path):
    d, a, b = checkpoint(tmp_path)
    p, A, B = adapter(tmp_path)
    out = tmp_path / "merged"
    lora.merge(p, d, out, scale=0.8)
    m = load_file(str(out / "model-00001-of-00002.safetensors"))
    want = (a["blocks.0.attn.qkv_proj.weight"].float() + 0.8 * (B.float() @ A.float())).to(torch.bfloat16)
    assert torch.equal(m["blocks.0.attn.qkv_proj.weight"], want)
    assert torch.equal(m["blocks.0.norm1.weight"], a["blocks.0.norm1.weight"])


def test_a_shard_the_adapter_does_not_touch_is_linked_not_copied(tmp_path):
    d, _, _ = checkpoint(tmp_path)
    p, _, _ = adapter(tmp_path)
    out = tmp_path / "merged"
    lora.merge(p, d, out, scale=1.0)
    assert (out / "model-00002-of-00002.safetensors").is_symlink()
    assert not (out / "model-00001-of-00002.safetensors").is_symlink()
    assert json.loads((out / "model.safetensors.index.json").read_text())["weight_map"]
    assert (out / "config.json").exists()
    assert (d / "model-00001-of-00002.safetensors").stat().st_size > 0  # the original is untouched


def test_an_adapter_layer_the_checkpoint_does_not_have_is_refused(tmp_path):
    d, _, _ = checkpoint(tmp_path)
    p, _, _ = adapter(tmp_path, key="blocks.9.attn.qkv_proj")
    with pytest.raises(ValueError, match="blocks.9.attn.qkv_proj"):
        lora.merge(p, d, tmp_path / "merged", scale=1.0)


def test_alpha_scales_the_update_by_alpha_over_rank(tmp_path):
    d, a, _ = checkpoint(tmp_path)
    p, A, B = adapter(tmp_path, rank=2)
    t = load_file(str(p))
    t["diffusion_model.blocks.0.attn.qkv_proj.alpha"] = torch.tensor(1.0)
    save_file(t, str(p))
    lora.merge(p, d, tmp_path / "merged", scale=1.0)
    m = load_file(str(tmp_path / "merged" / "model-00001-of-00002.safetensors"))
    want = (a["blocks.0.attn.qkv_proj.weight"].float() + 0.5 * (B.float() @ A.float())).to(torch.bfloat16)
    assert torch.equal(m["blocks.0.attn.qkv_proj.weight"], want)
