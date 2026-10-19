"""Download, cache, load and unload the video models.

Weights live in <studio home>/models/hf (Hugging Face cache layout), or wherever HF_HOME
points. One pipeline is kept loaded at a time; switching models unloads the previous one.
"""

from __future__ import annotations

import gc
import os
import threading
from pathlib import Path

from .. import config
from . import hardware
from .models import MODELS


def cache_dir() -> Path:
    d = Path(os.environ.get("INSIDIR_HF_CACHE") or (config.studio_home() / "models" / "hf"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def installed(model_id: str) -> bool:
    m = MODELS[model_id]
    if m.get("test_only"):
        return True
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(m["repo"], cache_dir=str(cache_dir()), local_files_only=True)
        return True
    except Exception:
        return False


def installed_set() -> set[str]:
    return {m for m in MODELS if installed(m)}


def local_path(model_id: str) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(MODELS[model_id]["repo"], cache_dir=str(cache_dir()), local_files_only=True)


def download(model_id: str, progress=None, cancel: threading.Event | None = None) -> str:
    """Download a model's weights (resumable). progress(fraction, message)."""
    from huggingface_hub import HfApi, snapshot_download
    from tqdm.auto import tqdm

    repo = MODELS[model_id]["repo"]
    total = 0
    try:
        total = sum((f.size or 0) for f in HfApi().model_info(repo, files_metadata=True).siblings)
    except Exception:
        pass
    done = {"n": 0}

    class Bar(tqdm):  # receives byte counts from huggingface_hub
        def update(self, n=1):
            if cancel is not None and cancel.is_set():
                raise InterruptedError("Download cancelled")
            if self.unit == "B":
                done["n"] += n or 0
                if progress and total:
                    progress(min(0.99, done["n"] / total), f"Downloading {MODELS[model_id]['name']}: "
                                                           f"{done['n'] / 1e9:.1f} of {total / 1e9:.1f} GB")
            return super().update(n)

    return snapshot_download(repo, cache_dir=str(cache_dir()), tqdm_class=Bar, max_workers=4)


# ------------------------------------------------------------------ loading

_lock = threading.RLock()
_loaded: dict = {"key": None, "pipe": None}


def unload() -> None:
    with _lock:
        _loaded["pipe"] = None
        _loaded["key"] = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def _place(pipe, hw: dict, need_gb: float) -> str:
    how = hardware.strategy(hw, need_gb)
    if how == "gpu":
        pipe.to(hw["device"])
    elif how == "offload":
        pipe.enable_model_cpu_offload()
    elif how == "sequential":
        pipe.enable_sequential_cpu_offload()
    vae = getattr(pipe, "vae", None)
    if vae is not None and hasattr(vae, "enable_tiling"):
        vae.enable_tiling()   # decode big frames in tiles: same pixels, far less memory
    return how


def pipeline_class(family: str, task: str):
    import diffusers as D
    if family == "wan-vace":
        return D.WanVACEPipeline          # one model for every task
    if family == "wan-tiny":              # exercise all three Wan pipelines in tests
        return {"t2v": D.WanPipeline, "v2v": D.WanVideoToVideoPipeline}.get(task, D.WanVACEPipeline)
    if family == "wan":
        if task in ("i2v", "flf2v", "extend"):
            return D.WanImageToVideoPipeline
        return D.WanVideoToVideoPipeline if task == "v2v" else D.WanPipeline
    if family == "ltx":
        return D.LTXConditionPipeline
    if family == "skyreels-df":
        return D.SkyReelsV2DiffusionForcingVideoToVideoPipeline if task == "extend" else D.SkyReelsV2DiffusionForcingPipeline
    if family == "hunyuan":
        return D.HunyuanVideoPipeline
    if family == "cogvideox":
        return D.CogVideoXPipeline
    raise ValueError(f"Unknown model family {family}")


def load(model_id: str, task: str, log=None, without_text_encoder: bool = False):
    """The diffusers pipeline for a model and task, loaded once and reused.

    without_text_encoder: skip the (large) text encoder; the caller passes prompt embeddings."""
    m = MODELS[model_id]
    cls = pipeline_class(m["family"], task)
    key = (model_id, cls.__name__, without_text_encoder)
    with _lock:
        if _loaded["key"] == key:
            return _loaded["pipe"]
        unload()
        hw = hardware.detect()
        if not hw["ready"]:
            raise RuntimeError(hw["reason"])
        if m["family"] == "wan-tiny":
            pipe = tiny_pipeline(cls)
            how = "cpu"
        else:
            import torch
            if not installed(model_id):
                raise RuntimeError(f"{m['name']} isn't downloaded yet. Download it on the Models tab.")
            dtype = hardware.torch_dtype(hw["dtype"])
            path = local_path(model_id)
            kwargs = {"torch_dtype": dtype}
            if without_text_encoder:
                kwargs["text_encoder"] = None
            if m["family"].startswith("wan"):
                # Wan's VAE is numerically sensitive: keep it in float32 (as the authors recommend)
                from diffusers import AutoencoderKLWan
                kwargs["vae"] = AutoencoderKLWan.from_pretrained(path, subfolder="vae", torch_dtype=torch.float32)
            pipe = cls.from_pretrained(path, **kwargs)
            how = _place(pipe, hw, m["vram_gb"])
        if log:
            log(f"loaded {m['name']} ({cls.__name__}) on {hw['name']} [{how}]")
        _loaded.update(key=key, pipe=pipe)
        return pipe


def tiny_pipeline(cls):
    """A Wan pipeline with tiny random weights (test model). Real code path, meaningless pixels."""
    import torch
    from diffusers import AutoencoderKLWan, FlowMatchEulerDiscreteScheduler, WanTransformer3DModel
    from diffusers.models import WanVACETransformer3DModel
    from transformers import AutoTokenizer, T5Config, T5EncoderModel

    torch.manual_seed(0)
    vae = AutoencoderKLWan(base_dim=3, z_dim=16, dim_mult=[1, 1, 1, 1], num_res_blocks=1,
                           temperal_downsample=[False, True, True])
    common = dict(patch_size=(1, 2, 2), num_attention_heads=2, attention_head_dim=12, in_channels=16,
                  out_channels=16, text_dim=32, freq_dim=256, ffn_dim=32, num_layers=2, cross_attn_norm=True,
                  qk_norm="rms_norm_across_heads", rope_max_seq_len=32)
    if cls.__name__ == "WanVACEPipeline":
        transformer = WanVACETransformer3DModel(**common, vace_layers=[0], vace_in_channels=96)
    else:
        transformer = WanTransformer3DModel(**common)
    try:
        tokenizer = AutoTokenizer.from_pretrained("hf-internal-testing/tiny-random-t5")
    except Exception as e:  # offline: the tokenizer is the only download
        raise RuntimeError(f"The tiny test model needs a one-time 1 MB tokenizer download: {e}")
    text_encoder = T5EncoderModel(T5Config(vocab_size=tokenizer.vocab_size + 100, d_model=32, d_kv=8, d_ff=37,
                                           num_layers=2, num_heads=4, relative_attention_num_buckets=8))
    scheduler = FlowMatchEulerDiscreteScheduler(shift=7.0)
    return cls(tokenizer=tokenizer, text_encoder=text_encoder, vae=vae, scheduler=scheduler, transformer=transformer)
