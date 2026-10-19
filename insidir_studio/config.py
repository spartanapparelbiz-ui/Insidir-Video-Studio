"""Paths and settings for Insidir Video Studio.

Everything lives under one home folder (default: %USERPROFILE%\\InsidirStudio on
Windows, ~/InsidirStudio elsewhere). Override with INSIDIR_STUDIO_HOME.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Insidir Video Studio"
VERSION = "1.0.0"

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent
FONTS_DIR = PACKAGE_DIR / "fonts"
WEB_DIR = PACKAGE_DIR / "web"
DEFAULT_FACTS = REPO_DIR / "facts" / "insidir_facts.json"

WIDTH = 1080
HEIGHT = 1920
FPS = 30
MIN_SECONDS = 20.0
MAX_SECONDS = 35.0

# Kokoro-82M weights converted to ONNX (Apache-2.0), published by the kokoro-onnx project.
KOKORO_FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "kokoro-v1.0.int8.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}

DEFAULT_SETTINGS = {
    "voice": "studio_male",
    "speed": 1.0,
    "caption_highlight": "#FFFFFF",
    "transitions": "cinematic",  # or "cuts"
    "claude": {
        # Free path: copy the prompt into claude.ai and paste the reply back.
        # The API path is optional and billed by Anthropic; it stays off unless a key is set.
        "api_enabled": False,
        "model": "claude-opus-5-5",
    },
    "avatar": {
        "enabled": False,
        "engine": "",
        "command": "",
        "license_confirmed": False,
        "commercial_use": True,
        "min_vram_gb": 8,
    },
}


def studio_home() -> Path:
    env = os.environ.get("INSIDIR_STUDIO_HOME")
    if env:
        home = Path(env)
    else:
        home = Path.home() / "InsidirStudio"
    home.mkdir(parents=True, exist_ok=True)
    return home


def projects_dir() -> Path:
    p = studio_home() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def models_dir() -> Path:
    env = os.environ.get("INSIDIR_MODELS_DIR")
    p = Path(env) if env else studio_home() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def facts_path() -> Path:
    """User-editable copy of the approved facts. Seeded from the repo on first run."""
    p = studio_home() / "facts.json"
    if not p.exists() and DEFAULT_FACTS.exists():
        shutil.copyfile(DEFAULT_FACTS, p)
    return p


def settings_path() -> Path:
    return studio_home() / "settings.json"


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> dict:
    p = settings_path()
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    return _merge(DEFAULT_SETTINGS, data)


def save_settings(settings: dict) -> dict:
    merged = _merge(DEFAULT_SETTINGS, settings)
    settings_path().write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def _exe(name: str) -> str:
    return name + (".exe" if sys.platform == "win32" else "")


def find_tool(name: str) -> str | None:
    """Locate ffmpeg/ffprobe: env override, bundled tools folder, then PATH."""
    env = os.environ.get("INSIDIR_" + name.upper())
    if env and Path(env).exists():
        return env
    for base in (REPO_DIR / "tools" / "ffmpeg" / "bin", studio_home() / "tools" / "ffmpeg" / "bin"):
        cand = base / _exe(name)
        if cand.exists():
            return str(cand)
    return shutil.which(name)


def ffmpeg() -> str:
    path = find_tool("ffmpeg")
    if not path:
        raise RuntimeError("FFmpeg was not found. Run install.bat, or install it with: winget install Gyan.FFmpeg")
    return path


def ffprobe() -> str:
    path = find_tool("ffprobe")
    if not path:
        raise RuntimeError("ffprobe was not found. It ships with FFmpeg; run install.bat.")
    return path
