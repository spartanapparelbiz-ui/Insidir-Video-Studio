"""Persistent characters for generation: name, a fixed text description and reference images.

Consistency comes from two real mechanisms used together:
  1. The same detailed description is written into every shot's prompt (identity drift starts
     when the text describing a person changes between shots).
  2. With Wan VACE, the reference images are given to the model itself (reference-to-video),
     so the face, hair and outfit are taken from the pictures, not re-imagined.
"""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from .. import config


def root() -> Path:
    d = config.studio_home() / "characters"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dir(cid: str) -> Path:
    if not re.fullmatch(r"ch[a-f0-9]{8}", cid or ""):
        raise ValueError("Bad character id")
    return root() / cid


def list_characters() -> list[dict]:
    out = []
    for d in sorted(root().iterdir()):
        f = d / "character.json"
        if f.exists():
            c = json.loads(f.read_text(encoding="utf-8"))
            c["images"] = [str(d / n) for n in c.get("files", [])]
            out.append(c)
    return out


def save(c: dict) -> dict:
    d = _dir(c["id"])
    d.mkdir(parents=True, exist_ok=True)
    keep = {k: c[k] for k in ("id", "name", "description", "voice", "files", "created") if k in c}
    (d / "character.json").write_text(json.dumps(keep, indent=2), encoding="utf-8")
    return {**keep, "images": [str(d / n) for n in keep.get("files", [])]}


def create(name: str, description: str = "", voice: str = "") -> dict:
    return save({"id": "ch" + uuid.uuid4().hex[:8], "name": name.strip()[:40] or "Character",
                 "description": description.strip()[:600], "voice": voice, "files": [], "created": time.time()})


def add_image(cid: str, src: Path, filename: str) -> dict:
    c = json.loads((_dir(cid) / "character.json").read_text(encoding="utf-8"))
    ext = Path(filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Use PNG, JPG or WebP reference images.")
    name = f"ref{len(c.get('files', [])) + 1}_{uuid.uuid4().hex[:4]}{ext}"
    shutil.move(str(src), _dir(cid) / name)
    c.setdefault("files", []).append(name)
    return save(c)


def update(cid: str, changes: dict) -> dict:
    c = json.loads((_dir(cid) / "character.json").read_text(encoding="utf-8"))
    for k in ("name", "description", "voice"):
        if k in changes:
            c[k] = str(changes[k])[:600]
    return save(c)


def delete(cid: str) -> None:
    shutil.rmtree(_dir(cid), ignore_errors=True)
