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
    bf16 = cpu_bf16()
    return {"device": "cpu", "name": "CPU only" + (" (bf16 matrix units)" if bf16 else ""), "vram_gb": 0.0,
            "dtype": "bfloat16" if bf16 else "float32", "torch": torch.__version__, "ready": True,
            "reason": "No GPU found: real models run on the CPU, which takes a very long time "
                      "(use small sizes and few steps, or connect a GPU machine)."
                      + (" This CPU has bf16 matrix units (AMX / AVX-512 BF16), so the models run in bfloat16: "
                         "about 3-4x faster than float32." if bf16 else "")}


def cpu_bf16() -> bool:
    """CPUs with AMX or AVX-512 BF16 (recent Intel Xeon/Core, AMD Zen 4+) do bfloat16 matrix maths
    ~4x faster than float32; Wan was trained in bf16, so nothing is lost. INSIDIR_CPU_DTYPE=float32
    forces the old behaviour."""
    import os
    import torch
    forced = os.environ.get("INSIDIR_CPU_DTYPE", "").lower()
    if forced in ("float32", "bfloat16"):
        return forced == "bfloat16"
    cpu = getattr(torch, "cpu", None)
    try:
        return bool(cpu._is_amx_tile_supported() or cpu._is_avx512_bf16_supported())
    except Exception:
        return False


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
