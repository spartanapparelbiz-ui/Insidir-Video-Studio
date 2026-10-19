"""Projects on disk: <home>/projects/<id>/{project.json, assets/, build/, out/}."""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import config, media

ROLES = ("screen", "image", "presenter", "music")

# the web server is threaded: serialise read-modify-write of project.json
LOCK = threading.RLock()


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s[:48] or "video"


def project_dir(pid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{3,80}", pid or ""):
        raise ValueError("Bad project id")
    return config.projects_dir() / pid


def new(name: str, brief: dict | None = None) -> dict:
    pid = slug(name)[:30] + "-" + uuid.uuid4().hex[:6]
    d = config.projects_dir() / pid
    (d / "assets").mkdir(parents=True)
    settings = config.load_settings()
    proj = {
        "id": pid,
        "name": name,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "brief": {
            "topic": "",
            "audience": "Retail investors who read their own research",
            "angle": "",
            "hook_style": "question",
            "target_seconds": 28,
            "cta": "Try Insidir",
            **{k: v for k, v in (brief or {}).items() if k not in ("mode", "template")},
        },
        # "demo" cuts real screen recordings; "animated" draws a Motion Canvas template
        "mode": (brief or {}).get("mode") or "animated",
        "template": (brief or {}).get("template") or "viral",
        "voice": {"voice": settings.get("voice", "studio_male"), "speed": settings.get("speed", 1.0)},
        "style": {"caption_highlight": settings.get("caption_highlight", "#FFFFFF"),
                  "transitions": settings.get("transitions", "cinematic"), "end_card": True,
                  "captions": "auto", "quality": "high", "ai_voice_label": False,
                  "sfx": True, "music_bed": True},
        "presenter": {"use_avatar": False},
        "music": {"enabled": True, "volume_db": -20},
        "assets": [],
        "script": {"title": "", "beats": [], "facts_used": []},
    }
    save(d, proj)
    return proj


def load(d: Path) -> dict:
    return json.loads((Path(d) / "project.json").read_text(encoding="utf-8"))


def save(d: Path, proj: dict) -> dict:
    d = Path(d)
    tmp = d / "project.json.tmp"
    tmp.write_text(json.dumps(proj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "project.json")
    return proj


def list_projects() -> list[dict]:
    out = []
    for d in sorted(config.projects_dir().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if (d / "project.json").exists():
            try:
                p = load(d)
            except ValueError:
                continue
            renders = sorted((d / "out").glob("*.mp4")) if (d / "out").exists() else []
            out.append({"id": p["id"], "name": p.get("name"), "created": p.get("created"),
                        "beats": len(p.get("script", {}).get("beats", [])),
                        "renders": [r.name for r in renders]})
    return out


def guess_role(filename: str, mtype: str) -> str:
    n = filename.lower()
    if mtype == "audio":
        return "music"
    if any(k in n for k in ("presenter", "avatar", "host", "face", "portrait")):
        return "presenter"
    if mtype == "video" or any(k in n for k in ("screen", "insidir", "demo", "capture", "recording")):
        return "screen"
    return "image"


def add_asset(d: Path, filename: str, data_path: Path, role: str | None = None) -> dict:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)[-80:] or "file"
    aid = "a" + uuid.uuid4().hex[:8]
    dest = Path(d) / "assets" / f"{aid}_{safe}"
    shutil.move(str(data_path), dest)
    mtype = media.media_type(dest)
    if mtype == "unknown":
        dest.unlink(missing_ok=True)
        raise ValueError("Unsupported file type. Use MP4/MOV/WebM, PNG/JPG/WebP, or MP3/WAV/M4A.")
    try:
        info = media.probe(dest)
    except media.FFmpegError:
        dest.unlink(missing_ok=True)
        raise
    role = role if role in ROLES else guess_role(filename, mtype)
    asset = {
        "id": aid,
        "file": f"assets/{dest.name}",
        "label": Path(filename).stem[:60],
        "type": mtype,
        "role": role,
        "width": info["width"],
        "height": info["height"],
        "duration": round(info["duration"], 3),
        "has_audio": info["has_audio"],
        # honesty flags the user confirms in the UI
        "genuine": False,          # a real recording/screenshot of the Insidir product
        "ai_generated": False,     # an AI-generated person or image
        "rights_confirmed": False, # you own it or are licensed to use it commercially
        "notes": "",
    }
    with LOCK:
        proj = load(d)
        proj["assets"].append(asset)
        save(d, proj)
    return asset


def remove_asset(d: Path, aid: str) -> dict:
    with LOCK:
        return _remove_asset(d, aid)


def _remove_asset(d: Path, aid: str) -> dict:
    proj = load(d)
    keep = []
    for a in proj["assets"]:
        if a["id"] == aid:
            (Path(d) / a["file"]).unlink(missing_ok=True)
        else:
            keep.append(a)
    proj["assets"] = keep
    for b in proj.get("script", {}).get("beats", []):
        if (b.get("visual") or {}).get("asset") == aid:
            b["visual"]["asset"] = None
    return save(d, proj)
