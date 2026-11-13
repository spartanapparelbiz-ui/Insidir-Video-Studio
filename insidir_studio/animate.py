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

from . import config, fonts, media

MOTION_DIR = config.REPO_DIR / "motion"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

PALETTE = {"bg": "#0c0c0b", "ink": "#e9e4da", "accent": "#ffffff",
           "up": "#2f996a", "down": "#f94144", "muted": "#77736c"}

ICONS = ["document", "form", "magnifier", "clock", "calendar", "bell", "link", "check", "cross",
         "building", "chart", "phone", "laptop", "eye", "lock", "people", "cabinet", "question",
         "bulb", "arrow", "tag", "list", "pen"]
POSES = ["stand", "wave", "point", "pointleft", "pointup", "think", "shrug", "cheer", "explain", "walk", "sad"]

TEMPLATES = {
    "editorial-story": {
        "name": "Insidir: editorial finance",
        "description": "Slower story-led SEC explainer with an Insidir dot-matrix narrator, original financial documents, source trails, no scene numbers.",
        "best_for": "Black-and-ivory, precise financial explainers that explain one real concept per Reel.",
        "fields": ["headline", "icon", "pose"],
        "frame_format": "jpeg",
        "prompt": "Write eight connected short beats for a single true finance story. The Insidir dot character follows the evidence from headline, through public filings, categories and transaction codes, to SEC source links and a plain-language takeaway. Avoid unsupported claims. Use 68-82 words total with readable 2-5 word headings and a calmer pace. Do not add numbered labels or a corner watermark.",
    },
    "viral": {
        "name": "Viral cinematic",
        "description": "Huge kinetic captions, camera punch-ins, whip transitions, cinematic light and real Insidir screens under a spotlight.",
        "best_for": "Short-form reach: TikTok, Reels, Shorts.",
        "fields": ["headline", "icon", "emphasis", "asset", "focus"],
        "own_captions": True,
        "frame_format": "jpeg",
        "prompt": "Write for retention. Beat 1 is a pattern-interrupt hook of 4-9 words that opens a curiosity gap "
                  "(a question or a surprising true fact); the payoff comes in a later beat. Keep every sentence short "
                  "and spoken, one idea per beat, 1.5-3.5 seconds each. Each beat's headline is 1-4 punchy words shown huge "
                  "on screen. Put an approved figure in 'emphasis' on 1-2 beats (it counts up on screen). Use real Insidir "
                  "footage (visual.asset) on 1-3 beats and say in 'shot' what to spotlight. End with a clear call to action.",
    },
    "avatar-host": {
        "name": "Avatar host",
        "category": "avatar",
        "description": "A cartoon presenter talks to camera with real lip sync, blinks and gestures, and points up at real Insidir screens.",
        "best_for": "A face for the channel without filming yourself. No GPU needed.",
        "fields": ["headline", "icon", "emphasis", "asset", "focus", "pose"],
        "own_captions": True,
        "frame_format": "jpeg",
        "lipsync": True,
        "prompt": "A friendly cartoon host speaks straight to camera, so write it as one person talking to a friend. "
                  "Beat 1 is a 4-9 word hook. Beats with real Insidir footage (visual.asset) or an approved figure "
                  "(emphasis) show it above the host; the others are close-ups with a 1-4 word headline. Use footage on "
                  "2-3 beats. Pick a pose per beat: wave, point (at the screen), explain, think, shrug or cheer.",
    },
    "chat": {
        "name": "Text chat",
        "description": "The video plays out as a phone text conversation: typing dots, message bubbles, real screenshots sent as photos.",
        "best_for": "Relatable hooks: a friend asks, Insidir answers.",
        "fields": ["label", "emphasis", "asset"],
        "own_captions": True,
        "frame_format": "jpeg",
        "prompt": "Write the script as a text conversation read aloud. Set visual.label to THEM for the friend asking "
                  "and ME for the person answering (alternate, starting with THEM). Each message is one short text "
                  "(under 14 words). Attach real Insidir footage (visual.asset) to 1-2 ME messages as photos. "
                  "An approved figure in 'emphasis' appears as a stat card. End with a ME message that is the call to action.",
    },
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
        "characters": CHARACTERS,
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
              log=None, fps: int = config.FPS, voice_wav: Path | None = None) -> Path:
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
        "frame_format": TEMPLATES.get(template, {}).get("frame_format", "png"),
    }
    st = proj.get("style") or {}
    data["captions"] = {"position": st.get("caption_position") or "lower", "size": float(st.get("caption_size") or 1.0),
                        "case": st.get("caption_case") or "upper", "words": int(st.get("caption_words") or 3)}
    cap = fonts.get(st.get("caption_font"))
    head = fonts.get(st.get("headline_font"), None)  # None: each template's own headline face
    data["fonts"] = {
        "caption": {w: f"/studio-fonts/{n}" for w, n in fonts.web_faces(cap).items()},
        "head": {w: f"/studio-fonts/{n}" for w, n in fonts.web_faces(head).items()} if head else None,
    }
    if TEMPLATES.get(template, {}).get("lipsync") and voice_wav:
        data["character"] = (proj.get("avatar") or {}).get("character") or "dot"
        data["mouth"], data["mouth_w"] = mouth_track(Path(voice_wav), fps, total)
    if template == "chat":
        chat = proj.get("chat") or {}
        data["chat"] = {"me": (chat.get("me") or "Insidir")[:24], "them": (chat.get("them") or "Alex")[:24]}
    (job / "data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    return job


CHARACTERS = {"dot": "Dot (the Insidir mascot)", "maya": "Maya", "leo": "Leo", "sam": "Sam"}


def mouth_track(wav: Path, fps: int, total: float) -> tuple[list[float], list[float]]:
    """Mouth openness and width (0-1) for every video frame, measured from the narration.

    Openness follows the loudness envelope (fast attack, softer release, so syllables pop and
    the mouth doesn't flutter); width follows the share of high-frequency energy, so "ee"/"s"
    sounds spread the lips and "oo"/"oh" sounds round them."""
    import numpy as np
    from . import whisper_align

    sr = 16000
    pcm = whisper_align.decode(wav, sr)
    hop = sr / fps
    n = int(round(total * fps))
    rms = np.zeros(n, dtype=np.float32)
    hi = np.zeros(n, dtype=np.float32)
    win = int(hop * 1.5)
    for i in range(n):
        a = int(i * hop)
        x = pcm[a:a + win]
        if len(x) < 32:
            continue
        rms[i] = float(np.sqrt(np.mean(x * x)))
        d = np.diff(x)
        hi[i] = float(np.sqrt(np.mean(d * d)) / (rms[i] + 1e-6))
    ref = float(np.percentile(rms[rms > 0], 95)) if (rms > 0).any() else 1.0
    db = 20 * np.log10(np.maximum(rms, 1e-6) / max(ref, 1e-6))
    target = np.clip((db + 32) / 30, 0, 1) ** 1.3          # -32 dB -> closed, 0 dB -> fully open
    open_ = np.zeros(n, dtype=np.float32)
    for i in range(n):
        prev = open_[i - 1] if i else 0.0
        k = 0.75 if target[i] > prev else 0.35            # fast attack, slower release
        open_[i] = prev + (target[i] - prev) * k
    width = np.clip((hi - 0.25) / 0.9, 0, 1)
    width = np.convolve(width, np.ones(3) / 3, mode="same") * (open_ > 0.05)
    return [round(float(v), 3) for v in open_], [round(float(v), 3) for v in width]


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
