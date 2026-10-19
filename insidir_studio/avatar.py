"""Optional local talking-avatar step.

Off by default. The studio never downloads or bundles an avatar model. You install
one yourself, check its licence (code AND every weight file it loads), and give the
studio a command line to run. It only runs when:

1. an NVIDIA GPU with enough memory is detected,
2. the engine is not known to forbid commercial use (when you mark the project commercial),
3. you have ticked "I checked the licence of this model and its weights".

Every avatar shot is labelled "AI-generated presenter" on screen, whatever the engine.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from . import media

# What we know about popular open models, as of October 2026. Licences change:
# read the current LICENSE of the code and of every checkpoint before use.
KNOWN_ENGINES = {
    "infinitetalk": {
        "name": "InfiniteTalk (MeiGen-AI) - most realistic",
        "url": "https://github.com/MeiGen-AI/InfiniteTalk",
        "commercial": "check",
        "note": "Photo to talking video with natural head, shoulder and hand motion as well as lip sync, built on the "
                "Wan2.1 image-to-video model. The closest open model to commercial avatar services. Code and Wan2.1 "
                "weights were published under Apache-2.0; it also loads an audio encoder with its own terms. Verify all "
                "of them. Needs a 24 GB+ NVIDIA GPU for good speed (smaller cards work with offloading, much slower). "
                "Call it through a small wrapper script that writes one MP4.",
        "min_vram_gb": 24,
        "example": 'python infinitetalk_wrapper.py --image "{image}" --audio "{audio}" --out "{output}" --size 720',
    },
    "echomimic": {
        "name": "EchoMimic (Ant Group)",
        "url": "https://github.com/antgroup/echomimic_v2",
        "commercial": "check",
        "note": "Audio-driven portrait animation with head motion and expressions. Code Apache-2.0; check the weights' "
                "and every bundled model's licence. A 12-16 GB GPU is comfortable. Use a wrapper script.",
        "min_vram_gb": 12,
        "example": 'python echomimic_wrapper.py --image "{image}" --audio "{audio}" --out "{output}"',
    },
    "musetalk": {
        "name": "MuseTalk (TMElyralab)",
        "url": "https://github.com/TMElyralab/MuseTalk",
        "commercial": "check",
        "note": "Code is MIT. It also loads third-party weights (e.g. sd-vae, Whisper, DWPose, face parsing), each with its own licence. Verify all of them. MuseTalk reads a YAML config, so call it from a small wrapper script.",
        "min_vram_gb": 6,
        "example": 'python musetalk_wrapper.py --image "{image}" --audio "{audio}" --out "{output}"',
    },
    "sadtalker": {
        "name": "SadTalker",
        "url": "https://github.com/OpenTalker/SadTalker",
        "commercial": "check",
        "note": "Repository licence is Apache-2.0 in recent versions; it downloads face-enhancement and detection weights with separate terms. Verify them.",
        "min_vram_gb": 6,
        "example": 'python inference.py --driven_audio "{audio}" --source_image "{image}" --result_dir "{outdir}" --still --preprocess full',
    },
    "wav2lip": {
        "name": "Wav2Lip",
        "url": "https://github.com/Rudrabha/Wav2Lip",
        "commercial": "no",
        "note": "Released for research and non-commercial use only. Blocked for commercial projects.",
        "min_vram_gb": 4,
        "example": "",
    },
    "custom": {
        "name": "Other / custom",
        "url": "",
        "commercial": "check",
        "note": "Any command that takes an image and a WAV and writes a video.",
        "min_vram_gb": 6,
        "example": 'python my_avatar.py --image "{image}" --audio "{audio}" --out "{output}"',
    },
}

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def detect_gpus() -> list[dict]:
    """NVIDIA GPUs via nvidia-smi (ships with the driver). Empty list if none."""
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8, creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    gpus = []
    for line in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                gpus.append({"name": parts[0], "vram_gb": round(float(parts[1]) / 1024, 1)})
            except ValueError:
                continue
    return gpus


def status(settings: dict) -> dict:
    av = settings.get("avatar", {})
    gpus = detect_gpus()
    best = max((g["vram_gb"] for g in gpus), default=0.0)
    engine = KNOWN_ENGINES.get(av.get("engine") or "", None)
    need = float(av.get("min_vram_gb") or (engine or {}).get("min_vram_gb", 8))
    reasons = []
    if not av.get("enabled"):
        reasons.append("Avatar step is turned off.")
    if not gpus:
        reasons.append("No NVIDIA GPU detected. Presenters will use the still image with camera motion.")
    elif best < need:
        reasons.append(f"GPU has {best} GB; this engine needs about {need:g} GB.")
    if engine and engine["commercial"] == "no" and av.get("commercial_use", True):
        reasons.append(f"{engine['name']} does not allow commercial use.")
    if not av.get("command"):
        reasons.append("No avatar command is configured.")
    if not av.get("license_confirmed"):
        reasons.append("Licence not confirmed.")
    return {
        "gpus": gpus,
        "usable": not reasons,
        "reasons": reasons,
        "engines": KNOWN_ENGINES,
    }


def generate(settings: dict, image: Path, audio: Path, output: Path, log=None) -> Path:
    st = status(settings)
    if not st["usable"]:
        raise RuntimeError("Avatar step unavailable: " + " ".join(st["reasons"]))
    av = settings["avatar"]
    output.parent.mkdir(parents=True, exist_ok=True)
    values = {"image": str(image), "audio": str(audio), "output": str(output), "outdir": str(output.parent)}
    cmd_text = av["command"].format(**values)
    args = shlex.split(cmd_text, posix=sys.platform != "win32")
    if log:
        log("avatar: " + cmd_text)
    proc = subprocess.run(args, cwd=av.get("workdir") or None, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60 * 30)
    if proc.returncode != 0:
        raise RuntimeError("Avatar command failed: " + (proc.stderr or proc.stdout)[-1500:])
    if not output.exists():
        # many tools write into the output folder with their own name; take the newest video
        vids = sorted(output.parent.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not vids:
            raise RuntimeError("Avatar command finished but wrote no video.")
        vids[0].replace(output)
    info = media.probe(output)
    if not info["has_video"]:
        raise RuntimeError("Avatar output has no video stream.")
    return output
