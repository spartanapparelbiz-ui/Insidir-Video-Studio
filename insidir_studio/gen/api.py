"""HTTP API for the Generate workspace (mounted at /api/gen/ by the studio server)."""

from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path

from . import characters, hardware, jobs, manager, models, post, prompt, story

UPLOAD_RE = re.compile(r"^up_[a-f0-9]{10}\.(png|jpe?g|webp|mp4|mov|webm|mkv|wav|mp3|m4a)$")
FILE_FIELDS = ("image", "last_image", "video", "mask")


def uploads_dir() -> Path:
    d = jobs.gen_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dev_mode() -> bool:
    return os.environ.get("INSIDIR_GEN_DEV") == "1"


def resolve(ref: str) -> str:
    """An upload id -> its file path (requests can't point the engine at arbitrary files)."""
    if not ref:
        return ""
    if not UPLOAD_RE.match(ref):
        raise ValueError("Unknown upload")
    p = uploads_dir() / ref
    if not p.exists():
        raise ValueError("That upload no longer exists")
    return str(p)


def status() -> dict:
    hw = hardware.detect()
    have = manager.installed_set() if hw["torch"] else set()
    ms = {}
    for k, m in models.public(dev_mode()).items():
        need = m["vram_gb"]
        # sequential offload lets a model run in well under its comfortable VRAM, just slower
        fits = bool(m.get("test_only")) or hw["device"] == "mps" or (hw["device"] == "cuda" and hw["vram_gb"] >= need * 0.4)
        ms[k] = {**{x: m[x] for x in ("name", "family", "license", "tasks", "vram_gb", "disk_gb", "default", "note")},
                 "license_url": m.get("license_url", ""), "repo": m["repo"], "installed": k in have,
                 "fits": fits,
                 "strategy": hardware.strategy(hw, need) if hw["ready"] else "n/a"}
    return {"hardware": hw, "models": ms, "tasks": models.TASKS, "camera": prompt.CAMERA, "speeds": prompt.SPEED,
            "lenses": prompt.LENSES, "lighting": prompt.LIGHTING, "styles": prompt.STYLES,
            "transitions": story.TRANSITIONS, "tools": post.tools(), "recommended": {
                t: models.best_for(t, hw["vram_gb"], have, dev_mode()) for t in models.TASKS}}


def handle(h, method: str, p: list[str], q: dict):
    """h: the request handler (has _json, _body_json, _serve_file, _receive_upload)."""
    from ..server import ApiError
    Q = jobs.queue_()
    route = (method, *p[:1])
    try:
        if route == ("GET", "status"):
            return h._json(status())
        if route == ("POST", "prompt"):
            b = h._body_json()
            return h._json(prompt.enhance(b.get("prompt", ""), camera=b.get("camera") or [],
                                          camera_speed=b.get("camera_speed", "medium"), lens=b.get("lens", ""),
                                          lighting=b.get("lighting", ""), style=b.get("style", "photoreal"),
                                          motion=float(b.get("motion", 0.5)), extra_negative=b.get("negative", "")))
        if route == ("POST", "uploads"):
            ext = Path(q.get("filename") or "file").suffix.lower().lstrip(".")
            name = f"up_{uuid.uuid4().hex[:10]}.{ext}"
            if not UPLOAD_RE.match(name):
                raise ApiError(400, "Use an image (PNG/JPG/WebP), a video (MP4/MOV/WebM) or audio (WAV/MP3/M4A).")
            tmp = h._receive_upload(uploads_dir() / "_in")
            shutil.move(str(tmp), uploads_dir() / name)
            shutil.rmtree(tmp.parent, ignore_errors=True)
            return h._json({"id": name, "url": f"/api/gen/uploads/{name}"})
        if method == "GET" and p[:1] == ["uploads"] and len(p) == 2:
            return h._serve_file(Path(resolve(p[1])))
        if route == ("GET", "jobs"):
            return h._json({"jobs": [{k: v for k, v in j.items() if k != "log"} for j in Q.list()]})
        if route == ("POST", "jobs"):
            b = h._body_json()
            kind = b.get("kind") or "generate"
            payload = dict(b.get("payload") or {})
            if kind == "generate":
                for f in FILE_FIELDS:
                    payload[f] = resolve(payload.get(f, ""))
                payload["references"] = [resolve(r) for r in payload.get("references") or []]
                chars = {c["id"]: c for c in characters.list_characters()}
                payload["characters"] = [{"name": chars[c]["name"], "description": chars[c].get("description", ""),
                                          "images": chars[c]["images"]} for c in payload.get("character_ids") or []
                                         if c in chars]
                payload.pop("character_ids", None)
                m = models.MODELS.get(payload.get("model"))
                if not m or (m.get("test_only") and not dev_mode()):
                    raise ApiError(400, "Pick a model")
            elif kind == "download":
                if payload.get("model") not in models.MODELS or models.MODELS[payload["model"]].get("test_only"):
                    raise ApiError(400, "Unknown model")
            elif kind == "film":
                if payload.get("settings", {}).get("music"):
                    payload["settings"]["music"] = resolve(payload["settings"]["music"])
            else:
                raise ApiError(400, "Unknown job kind")
            return h._json(Q.submit(kind, payload, b.get("title", "")))
        if method == "GET" and p[:1] == ["jobs"] and len(p) == 2:
            try:
                return h._json(Q.get(p[1]))
            except KeyError:
                raise ApiError(404, "No such job")
        if method == "POST" and p[:1] == ["jobs"] and len(p) == 3 and p[2] == "cancel":
            return h._json(Q.cancel(p[1]))
        if method == "DELETE" and p[:1] == ["jobs"] and len(p) == 2:
            Q.delete(p[1])
            return h._json({"deleted": p[1]})
        if method == "GET" and p[:1] == ["file"] and len(p) >= 3:
            job = Q.get(p[1])
            base = Path(job["dir"]).resolve()
            target = (base / Path(*p[2:])).resolve()
            if base not in target.parents:
                raise ApiError(404, "Not found")
            return h._serve_file(target)
        if route == ("GET", "characters"):
            return h._json({"characters": characters.list_characters()})
        if route == ("POST", "characters") and len(p) == 1:
            b = h._body_json()
            return h._json(characters.create(b.get("name", ""), b.get("description", ""), b.get("voice", "")))
        if method == "POST" and p[:1] == ["characters"] and len(p) == 3 and p[2] == "images":
            tmp = h._receive_upload(characters.root() / "_in")
            try:
                return h._json(characters.add_image(p[1], tmp, q.get("filename") or "ref.png"))
            finally:
                shutil.rmtree(tmp.parent, ignore_errors=True)
        if method == "GET" and p[:1] == ["characters"] and len(p) == 4 and p[2] == "images":
            f = characters._dir(p[1]) / Path(p[3]).name
            return h._serve_file(f)
        if method == "PUT" and p[:1] == ["characters"] and len(p) == 2:
            return h._json(characters.update(p[1], h._body_json()))
        if method == "DELETE" and p[:1] == ["characters"] and len(p) == 2:
            characters.delete(p[1])
            return h._json({"deleted": p[1]})
        if route == ("POST", "story"):
            b = h._body_json()
            what = p[1] if len(p) > 1 else ""
            if what == "plan":
                chars = [c for c in characters.list_characters() if c["id"] in (b.get("characters") or [])]
                return h._json(story.plan(b.get("text", ""), chars, float(b.get("seconds", 5)),
                                          b.get("style", "photoreal"), b.get("lighting", "")))
            if what == "claude-prompt":
                return h._json({"prompt": story.claude_prompt(b.get("text", ""))})
            if what == "parse":
                return h._json(story.parse_claude(b.get("reply", "")))
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(404, "Unknown generate endpoint")
