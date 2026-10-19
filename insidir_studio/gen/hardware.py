"""What this computer can run, and how to fit a model into it."""

from __future__ import annotations


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def detect() -> dict:
    """Device, memory and the dtype the engine will use."""
    if not torch_available():
        return {"device": "none", "name": "PyTorch not installed", "vram_gb": 0.0, "dtype": None, "torch": None,
                "ready": False, "reason": "Install the generation extras (install.bat, step Generate)."}
    import torch
    if torch.cuda.is_available():
        i = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(i)
        bf16 = torch.cuda.is_bf16_supported()
        return {"device": "cuda", "name": props.name, "vram_gb": round(props.total_memory / 1024 ** 3, 1),
                "dtype": "bfloat16" if bf16 else "float16", "torch": torch.__version__, "ready": True,
                "reason": ""}
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return {"device": "mps", "name": "Apple GPU (MPS)", "vram_gb": 0.0, "dtype": "float16",
                "torch": torch.__version__, "ready": True,
                "reason": "Apple GPUs work but are much slower than NVIDIA for these models."}
    return {"device": "cpu", "name": "CPU only", "vram_gb": 0.0, "dtype": "float32", "torch": torch.__version__,
            "ready": True, "reason": "No GPU found: real models run on the CPU, which takes a very long time "
                                      "(use small sizes and few steps, or connect a GPU machine)."}


def strategy(hw: dict, need_gb: float) -> str:
    """How to place a model: 'gpu' (all on the GPU), 'offload' (models move to the GPU in turn),
    'sequential' (layer by layer: slowest, smallest), or 'cpu'."""
    if hw["device"] == "cpu":
        return "cpu"
    if hw["device"] == "mps":
        return "gpu"
    v = hw["vram_gb"]
    if v >= need_gb * 1.6:
        return "gpu"
    if v >= need_gb * 0.75:
        return "offload"
    return "sequential"


def torch_dtype(name: str | None):
    import torch
    return {"bfloat16": torch.bfloat16, "float16": torch.float16}.get(name or "", torch.float32)
