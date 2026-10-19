"""Animated templates: Motion Canvas + Rough.js, rendered headlessly through Node.

The Python side prepares a job folder (data.json + media) and runs
motion/scripts/render.mjs, which renders the frames in a headless browser and pipes
them into FFmpeg. Voice, captions, labels and the final mix stay in render.py.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import config, media

MOTION_DIR = config.REPO_DIR / "motion"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

PALETTE = {"bg": "#0c0c0b", "ink": "#e9e4da", "accent": "#ffd84d",
           "up": "#2f996a", "down": "#f94144", "muted": "#77736c"}

ICONS = ["document", "form", "magnifier", "clock", "calendar", "bell", "link", "check", "cross",
         "building", "chart", "phone", "laptop", "eye", "lock", "people", "cabinet", "question",
         "bulb", "arrow", "tag", "list", "pen"]
POSES = ["stand", "wave", "point", "pointleft", "pointup", "think", "shrug", "cheer", "explain", "walk", "sad"]

TEMPLATES = {
    "dot-explainer": {
        "name": "Dot explainer",
        "description": "The Insidir dot figure explains one idea per beat while a doodle is drawn beside it.",
        "best_for": "Any topic; the default.",
        "fields": ["headline", "icon", "pose", "emphasis", "asset"],
        "prompt": "Each beat gets a 2-5 word headline, one doodle icon and a pose for the dot figure. "
                  "Use 'emphasis' only for an approved figure (e.g. '2 business days').",
    },
    "myth-fact": {
        "name": "Myth vs fact",
        "description": "Cards slide in; myths get scribbled out in red, facts get a green check.",
        "best_for": "Correcting misconceptions about insider trades.",
        "fields": ["headline", "label", "pose"],
        "prompt": "Alternate MYTH and FACT beats (label). A MYTH headline states a common misconception "
                  "that the very next FACT beat corrects; the narration must say plainly that the myth is false. "
                  "The hook and the call to action have no label.",
    },
    "steps": {
        "name": "Step by step",
        "description": "Numbered hand-drawn boxes joined by arrows, ticked off one by one.",
        "best_for": "How-tos: reading a Form 4, following an insider.",
        "fields": ["headline", "pose"],
        "prompt": "Beat 1 is the hook (its headline is the title). Every later beat is one step; its headline "
                  "is the step in 2-6 words.",
    },
    "big-number": {
        "name": "Big number",
        "description": "An approved figure written huge and circled, with doodles between.",
        "best_for": "Facts with a number: 2 business days, every 15 minutes, $1 for 3 days.",
        "fields": ["headline", "emphasis", "icon", "pose"],
        "prompt": "Put an approved figure in 'emphasis' on 2-3 beats (number first, e.g. '15 minutes', "
                  "'2 business days', '$1 for 3 days'). Other beats use an icon.",
    },
    "screen-sketch": {
        "name": "Screen sketch",
        "description": "Real Insidir screenshots or recordings in a hand-drawn window, circled where it matters.",
        "best_for": "Showing the real product with the dot figure pointing at it.",
        "fields": ["headline", "asset", "focus", "icon", "pose"],
        "prompt": "Use the uploaded genuine Insidir footage on most beats (visual.asset); describe in 'shot' "
                  "what should be circled. Beats without footage use an icon.",
    },
}


# ------------------------------------------------------------------ tools

def node_path() -> str | None:
    env = os.environ.get("INSIDIR_NODE")
    if env and Path(env).exists():
        return env
    exe = "node.exe" if sys.platform == "win32" else "node"
    for base in (config.REPO_DIR / "tools" / "node", config.studio_home() / "tools" / "node"):
        for cand in (base / exe, base / "bin" / exe):
            if cand.exists():
                return str(cand)
    return shutil.which("node")


def status() -> dict:
    node = node_path()
    version = None
    if node:
        try:
            version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10,
                                     creationflags=_NO_WINDOW).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            version = None
    deps = (MOTION_DIR / "node_modules" / "@motion-canvas" / "core").exists() and \
        (MOTION_DIR / "node_modules" / "roughjs").exists()
    major = int(re.sub(r"\D.*", "", (version or "v0").lstrip("v")) or 0)
    return {
        "node": node,
        "node_version": version,
        "node_ok": major >= 18,
        "motion_installed": deps,
        "ready": bool(node and major >= 18 and deps),
        "templates": TEMPLATES,
        "icons": ICONS,
        "poses": POSES,
    }


def check_browser(timeout: int = 90) -> tuple[bool, str]:
    node = node_path()
    if not node:
        return False, "Node.js not found"
    proc = subprocess.run([node, "scripts/check-browser.mjs"], cwd=MOTION_DIR, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, creationflags=_NO_WINDOW)
    out = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, out.splitlines()[-1] if out else ""


# ------------------------------------------------------------------ job

def _prepare_media(asset: dict, project_dir: Path, job: Path, start: float, seconds: float, log=None) -> dict:
    src = project_dir / asset["file"]
    out_dir = job / "media"
    out_dir.mkdir(parents=True, exist_ok=True)
    if asset["type"] == "image":
        ext = src.suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            dest = out_dir / f"{asset['id']}.png"
            media.run(["-i", str(src), "-frames:v", "1", str(dest)], log=log)
        else:
            dest = out_dir / f"{asset['id']}{ext}"
            shutil.copyfile(src, dest)
        return {"src": f"/media/{dest.name}", "type": "image", "width": asset["width"],
                "height": asset["height"], "genuine": bool(asset.get("genuine"))}
    # browsers can't always decode H.264 headlessly: hand them a short VP8 WebM clip
    dest = out_dir / f"{asset['id']}_{int(start * 10)}.webm"
    if not dest.exists():
        w = min(1280, asset["width"] or 1280)
        media.run(["-ss", f"{max(0.0, start):.2f}", "-i", str(src), "-t", f"{seconds + 1:.2f}", "-an",
                   "-vf", f"scale={w}:-2,fps=30", "-c:v", "libvpx", "-b:v", "4M", "-deadline", "realtime",
                   "-cpu-used", "8", str(dest)], log=log)
    return {"src": f"/media/{dest.name}", "type": "video", "width": asset["width"],
            "height": asset["height"], "genuine": bool(asset.get("genuine"))}


def build_job(proj: dict, beats: list[dict], spans: list[tuple[float, float]], beat_times: list[dict],
              words: list, total: float, end_card_start: float | None, project_dir: Path, build: Path,
              log=None, fps: int = config.FPS) -> Path:
    job = build / "motion"
    if job.exists():
        shutil.rmtree(job)
    job.mkdir(parents=True)
    assets = {a["id"]: a for a in proj.get("assets", [])}
    template = proj.get("template") or "dot-explainer"
    cursors: dict[str, float] = {}
    out_beats = []
    for b, (s0, s1), bt in zip(beats, spans, beat_times):
        vis = b.get("visual") or {}
        a = assets.get(vis.get("asset"))
        ref = None
        if a and a.get("rights_confirmed") and a["type"] in ("image", "video"):
            start = float(vis.get("start") if vis.get("start") is not None else cursors.get(a["id"], 0.0))
            ref = _prepare_media(a, project_dir, job, start, s1 - s0, log)
            cursors[a["id"]] = start + (s1 - s0)
        out_beats.append({
            "id": b["id"],
            "start": round(s0, 3),
            "end": round(s1, 3),
            "speech_start": bt["speech_start"],
            "text": b.get("text", ""),
            "headline": (b.get("overlay") or "").strip(),
            "icon": vis.get("icon") if vis.get("icon") in ICONS else "",
            "pose": vis.get("pose") if vis.get("pose") in POSES else "",
            "label": (vis.get("label") or "").strip()[:12],
            "emphasis": (vis.get("emphasis") or "").strip()[:28],
            "asset": ref,
            "focus": vis.get("focus") or [0.5, 0.5],
        })
    data = {
        "template": template if template in TEMPLATES else "dot-explainer",
        "width": config.WIDTH,
        "height": config.HEIGHT,
        "fps": fps,
        "total": round(total, 4),
        "end_card_start": round(end_card_start, 3) if end_card_start is not None else None,
        "title": (proj.get("script") or {}).get("title") or proj.get("name", ""),
        "palette": PALETTE,
        "beats": out_beats,
        "words": [{"text": w.text, "start": w.start, "end": w.end, "beat": w.beat} for w in words],
    }
    (job / "data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    return job


def render_job(job: Path, out: Path, log=None, progress=None) -> Path:
    st = status()
    if not st["ready"]:
        raise RuntimeError("Animated templates need Node.js 18+ and the motion packages. Run install.bat.")
    cmd = [st["node"], "scripts/render.mjs", "--job", str(job), "--out", str(out), "--ffmpeg", config.ffmpeg()]
    proc = subprocess.Popen(cmd, cwd=MOTION_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    tail: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        m = re.match(r"PROGRESS (\d+) (\d+)", line)
        if m:
            if progress:
                progress(int(m.group(1)) / max(1, int(m.group(2))))
            continue
        if line and not line.startswith("[debug]"):
            tail.append(line)
            del tail[:-40]
            if log:
                log("motion: " + line)
    code = proc.wait()
    if code != 0 or not out.exists():
        raise RuntimeError("Motion Canvas render failed:\n" + "\n".join(tail[-15:]))
    return out
