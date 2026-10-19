"""Saved avatars: import a presenter once, use it in every project.

An avatar lives in <home>/avatars/<id>/ with avatar.json and, for a photo avatar, the photo:

  kind "photo"    a picture of a person, lip-synced by the local talking-avatar model
  kind "cartoon"  one of the Motion Canvas hosts (Dot, Maya, Leo, Sam) with its own voice

Each avatar keeps its voice and speaking rate, so a project that picks the avatar also picks
how it sounds. Photo avatars carry the honesty flags the render checks:
  consent_confirmed   it's you, or the person shown gave written consent to be animated
  ai_generated        the face itself was made by AI (no real person)
Every video made from a photo avatar is labelled "AI-generated presenter" either way.
"""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from . import config, media, project, tts

KINDS = ("photo", "cartoon")
CARTOONS = ("dot", "maya", "leo", "sam")


def avatars_dir() -> Path:
    d = config.studio_home() / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def avatar_dir(aid: str) -> Path:
    if not re.fullmatch(r"av[a-f0-9]{8}", aid or ""):
        raise ValueError("Bad avatar id")
    return avatars_dir() / aid


def _save(av: dict) -> dict:
    d = avatar_dir(av["id"])
    tmp = d / "avatar.json.tmp"
    tmp.write_text(json.dumps(av, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "avatar.json")
    return av


def load(aid: str) -> dict:
    return json.loads((avatar_dir(aid) / "avatar.json").read_text(encoding="utf-8"))


def photo_path(av: dict) -> Path | None:
    return avatar_dir(av["id"]) / av["photo"] if av.get("photo") else None


def list_avatars() -> list[dict]:
    out = []
    for d in sorted(avatars_dir().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        f = d / "avatar.json"
        if f.exists():
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except ValueError:
                continue
    return out


def create(name: str, kind: str, photo_src: Path | None = None, filename: str = "", character: str = "dot",
           voice: str | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError("Unknown avatar kind")
    aid = "av" + uuid.uuid4().hex[:8]
    d = avatar_dir(aid)
    d.mkdir(parents=True)
    av = {
        "id": aid,
        "name": (name or "My avatar").strip()[:40],
        "kind": kind,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "voice": tts.valid_voice(voice),
        "speed": 1.0,
        "character": character if character in CARTOONS else "dot",
        "photo": None,
        "width": None,
        "height": None,
        "focus": [0.5, 0.4],
        "consent_confirmed": False,
        "ai_generated": False,
        "notes": "",
    }
    if kind == "photo":
        if not photo_src:
            shutil.rmtree(d)
            raise ValueError("A photo avatar needs a photo.")
        ext = (Path(filename).suffix.lower() or ".png")
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            shutil.rmtree(d)
            raise ValueError("Use a PNG, JPG or WebP photo.")
        dest = d / f"photo{ext}"
        shutil.move(str(photo_src), dest)
        try:
            info = media.probe(dest)
        except media.FFmpegError:
            shutil.rmtree(d)
            raise ValueError("That file isn't a readable image.")
        if min(info["width"], info["height"]) < 256:
            shutil.rmtree(d)
            raise ValueError("Use a photo at least 256 px on its short side (512 px or more looks best).")
        av.update(photo=dest.name, width=info["width"], height=info["height"])
    return _save(av)


EDITABLE = ("name", "voice", "speed", "character", "focus", "consent_confirmed", "ai_generated", "notes")


def update(aid: str, changes: dict) -> dict:
    with project.LOCK:
        av = load(aid)
        for k in EDITABLE:
            if k not in changes:
                continue
            v = changes[k]
            if k == "name":
                v = str(v).strip()[:40] or av["name"]
            elif k == "voice":
                v = tts.valid_voice(v)
            elif k == "speed":
                v = min(1.2, max(0.85, float(v)))
            elif k == "character":
                v = v if v in CARTOONS else av["character"]
            elif k == "focus":
                if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in v)):
                    continue
            elif k in ("consent_confirmed", "ai_generated"):
                v = bool(v)
            else:
                v = str(v)[:300]
            av[k] = v
        return _save(av)


def delete(aid: str) -> None:
    shutil.rmtree(avatar_dir(aid), ignore_errors=True)


def usable_photo(av: dict) -> list[str]:
    """Why a photo avatar can't be rendered yet (empty when it can)."""
    why = []
    if av.get("kind") != "photo" or not av.get("photo"):
        why.append("This avatar has no photo.")
    elif not (av.get("consent_confirmed") or av.get("ai_generated")):
        why.append(f'Confirm consent for "{av.get("name")}" (it is you, the person agreed in writing, or the face is AI-generated).')
    return why
