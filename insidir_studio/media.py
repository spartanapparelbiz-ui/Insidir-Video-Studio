"""FFmpeg / ffprobe helpers."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from . import config

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

# Hide console windows FFmpeg would otherwise open on Windows.
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], cwd: Path | None = None, log=None) -> None:
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args]
    if log:
        log("ffmpeg " + " ".join(a if " " not in a else f'"{a}"' for a in args[:40]) + (" ..." if len(args) > 40 else ""))
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip()[-3000:] or f"ffmpeg exited with {proc.returncode}")


def probe(path: Path) -> dict:
    cmd = [config.ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise FFmpegError(f"Could not read {Path(path).name}: {proc.stderr.strip()[-500:]}")
    data = json.loads(proc.stdout or "{}")
    info = {"duration": 0.0, "width": 0, "height": 0, "has_audio": False, "has_video": False}
    try:
        info["duration"] = float(data.get("format", {}).get("duration") or 0)
    except ValueError:
        pass
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["has_video"]:
            info["has_video"] = True
            info["width"] = int(s.get("width") or 0)
            info["height"] = int(s.get("height") or 0)
            rot = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = int(sd["rotation"])
            if s.get("tags", {}).get("rotate"):
                rot = int(s["tags"]["rotate"])
            if abs(rot) in (90, 270):
                info["width"], info["height"] = info["height"], info["width"]
            if not info["duration"]:
                try:
                    info["duration"] = float(s.get("duration") or 0)
                except ValueError:
                    pass
        elif s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


def media_type(path: Path) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    return "unknown"


def thumbnail(src: Path, out: Path, t: float = 0.0, width: int = 480) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    args = []
    if media_type(src) == "video":
        args += ["-ss", f"{max(0.0, t):.3f}"]
    args += ["-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out)]
    run(args)
    return out


def content_start(path: Path, cache_dir: Path, scan: float = 6.0) -> float:
    """Seconds until a screen recording shows something (skips a blank white/black opening,
    like a page still loading), so a cut never opens on an empty frame. Cached per file."""
    import json
    import subprocess
    import sys

    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_dir / (Path(path).stem + ".start.json")
    if key.exists():
        try:
            return float(json.loads(key.read_text())["start"])
        except (ValueError, KeyError, OSError):
            pass
    cmd = [config.ffmpeg(), "-hide_banner", "-nostats", "-t", str(scan), "-i", str(path), "-vf",
           "fps=10,scale=160:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=0x08000000 if sys.platform == "win32" else 0)
    start, t = 0.0, None
    for line in proc.stdout.splitlines():
        if line.startswith("frame:"):
            m = re.search(r"pts_time:([\d.]+)", line)
            t = float(m.group(1)) if m else None
        elif "YAVG=" in line and t is not None:
            y = float(line.split("=")[1])
            if 18 < y < 225:          # neither a blank white page nor a black frame
                start = t
                break
    else:
        start = 0.0
    key.write_text(json.dumps({"start": start}))
    return start
