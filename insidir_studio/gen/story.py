"""AI filmmaking: a description or script -> scenes -> shots -> storyboard -> generated shots -> film.

Planning is local and deterministic (the optional Claude path can write a richer shot list as
JSON in the same shape). Each shot is generated as its own job input, so any shot can be edited
and regenerated without touching the rest; the film is then assembled from the latest take of
every shot, with transitions, speed ramps, beat-synced cuts, dialogue, ambience and music.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import numpy as np

from .. import config, media

# a classic coverage pattern: establish, then get closer, keep the camera alive
COVERAGE = [
    {"shot": "Wide establishing shot", "camera": ["drone"], "lens": "24"},
    {"shot": "Medium shot", "camera": ["tracking"], "lens": "35"},
    {"shot": "Close-up", "camera": ["push_in"], "lens": "85"},
    {"shot": "Over-the-shoulder medium shot", "camera": ["handheld"], "lens": "50"},
    {"shot": "Extreme close-up detail", "camera": ["macro"], "lens": "135"},
    {"shot": "Low-angle hero shot", "camera": ["crane"], "lens": "24"},
    {"shot": "Wide shot", "camera": ["orbit"], "lens": "35"},
]
TRANSITIONS = {"cut": "Cut", "crossfade": "Crossfade", "dip": "Dip to black", "whip": "Whip pan", "flash": "Flash"}


def plan(text: str, characters: list[dict] | None = None, seconds_per_shot: float = 5.0, style: str = "photoreal",
         lighting: str = "") -> dict:
    """Break a description or script into scenes and shots."""
    characters = characters or []
    text = text.strip()
    blocks = [b.strip() for b in re.split(r"\n\s*\n|(?=^(?:INT\.|EXT\.|SCENE)\b)", text, flags=re.M) if b and b.strip()]
    scenes = []
    k = 0
    for bi, block in enumerate(blocks or [text]):
        lines = block.splitlines()
        heading = lines[0].strip() if re.match(r"^(INT\.|EXT\.|SCENE)", lines[0].strip()) else f"Scene {bi + 1}"
        body = " ".join(l.strip() for l in (lines[1:] if heading != f"Scene {bi + 1}" else lines))
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if len(s.strip()) > 3] or [body]
        shots = []
        for si, sent in enumerate(sentences):
            quoted = re.findall(r'"([^"]+)"', sent)
            rest = re.sub(r'"[^"]*"', "", sent).strip(" ,.")
            if quoted and shots and len(rest.split()) <= 4:
                # '"We're late," she says.' is a line of dialogue for the shot before, not a new shot
                shots[-1]["dialogue"] = (shots[-1]["dialogue"] + " " + quoted[0]).strip()
                shots[-1]["speaker"] = shots[-1]["speaker"] or (shots[-1]["characters"] or [""])[0]
                continue
            cov = COVERAGE[0] if si == 0 else COVERAGE[1 + (k % (len(COVERAGE) - 1))]
            k += 1
            dialogue = re.findall(r'"([^"]+)"', sent)
            in_shot = [c["id"] for c in characters if c.get("name") and re.search(rf"\b{re.escape(c['name'])}\b", sent, re.I)]
            shots.append({
                "id": f"s{bi + 1}_{si + 1}", "prompt": re.sub(r'"[^"]+"', "", sent).strip() or sent,
                "shot": cov["shot"], "camera": cov["camera"], "lens": cov["lens"], "lighting": lighting,
                "style": style, "seconds": seconds_per_shot, "characters": in_shot,
                "dialogue": dialogue[0] if dialogue else "", "speaker": in_shot[0] if in_shot and dialogue else "",
                "transition": "cut" if si else ("crossfade" if bi else "cut"), "speed": 1.0, "take": None,
            })
        scenes.append({"heading": heading, "shots": shots})
    return {"scenes": scenes, "characters": [c["id"] for c in characters]}


def claude_prompt(text: str) -> str:
    """A prompt for claude.ai (free) that returns a shot list in this module's JSON shape."""
    return (
        "You are a film director. Turn this idea into a shot list for an AI video generator.\n"
        "Reply with ONLY JSON: {\"scenes\":[{\"heading\":\"...\",\"shots\":[{\"prompt\":\"what is seen, literally: "
        "subject, appearance, action, setting\",\"shot\":\"Wide establishing shot|Medium shot|Close-up|...\","
        "\"camera\":[one or two of push_in,pull_out,dolly_zoom,orbit,drone,fpv,crash_zoom,tracking,handheld,crane,"
        "jib_down,gimbal,rack_focus,macro,pan_left,pan_right,tilt_up,static],\"lens\":\"24|35|50|85|135|anamorphic\","
        "\"lighting\":\"dusk|blue_hour|overcast|noon|night_neon|studio|low_key|practical\",\"seconds\":5,"
        "\"dialogue\":\"\",\"transition\":\"cut|crossfade|dip|whip|flash\"}]}]}\n"
        "Rules: 3-10 shots, each a single continuous camera move of 3-8 seconds; describe characters the same way "
        "in every shot; no on-screen text.\n\nIdea:\n" + text.strip()
    )


def parse_claude(reply: str) -> dict:
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        raise ValueError("No JSON found in the reply.")
    data = json.loads(m.group(0))
    for bi, sc in enumerate(data.get("scenes", [])):
        for si, sh in enumerate(sc.get("shots", [])):
            sh.setdefault("id", f"s{bi + 1}_{si + 1}")
            sh.setdefault("camera", [])
            sh.setdefault("seconds", 5)
            sh.setdefault("transition", "cut")
            sh.setdefault("speed", 1.0)
            sh.setdefault("characters", [])
            sh.setdefault("take", None)
    return data


# ------------------------------------------------------------------ assembly

def beats(audio: Path) -> list[float]:
    """Beat times of a music track: onset-strength envelope + autocorrelation tempo + peak picking."""
    from .. import whisper_align
    sr = 22050
    x = whisper_align.decode(audio, sr)
    hop = 512
    frames = len(x) // hop
    env = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) for i in range(frames)])
    onset = np.maximum(0, np.diff(np.log1p(env * 50), prepend=0))
    ac = np.correlate(onset - onset.mean(), onset - onset.mean(), "full")[len(onset) - 1:]
    lo, hi = int(60 / 180 * sr / hop), int(60 / 70 * sr / hop)   # 70..180 BPM
    period = lo + int(np.argmax(ac[lo:hi])) if hi > lo and len(ac) > hi else int(0.5 * sr / hop)
    phase = int(np.argmax([onset[p::period].sum() for p in range(period)]))
    return [round((phase + i * period) * hop / sr, 3) for i in range((frames - phase) // period + 1)]


def _xfade_name(t: str) -> str:
    return {"crossfade": "fade", "dip": "fadeblack", "whip": "slideleft", "flash": "fadewhite"}.get(t, "fade")


def assemble(takes: list[dict], out: Path, fps: int, w: int, h: int, music: str = "", dialogue_wavs: list | None = None,
             beat_sync: bool = False, log=None) -> Path:
    """Join shot takes with transitions and per-shot speed, then mix dialogue, ambience and music."""
    work = out.parent / "assemble"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    durs = []
    norm = []
    cut_points = beats(Path(music)) if (music and beat_sync) else []
    t_acc = 0.0
    for i, tk in enumerate(takes):
        info = media.probe(Path(tk["path"]))
        speed = float(tk.get("speed") or 1.0)
        d = info["duration"] / speed
        if cut_points and i < len(takes) - 1:
            # end this shot on the nearest beat (never longer than the footage allows)
            target = min((b for b in cut_points if b > t_acc + 0.6), key=lambda b: abs(b - (t_acc + d)), default=None)
            if target and target - t_acc <= d:
                d = target - t_acc
        p = work / f"n{i:03d}.mp4"
        vf = f"setpts=PTS/{speed},fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
        media.run(["-i", tk["path"], "-vf", vf, "-t", f"{d:.3f}", "-an", "-c:v", "libx264", "-crf", "12",
                   "-pix_fmt", "yuv420p", str(p)], log=log)
        norm.append(p)
        durs.append(d)
        t_acc += d
    inputs = sum((["-i", str(p)] for p in norm), [])
    parts, cur, off = [], "0:v", durs[0]
    for i in range(1, len(norm)):
        tr = takes[i].get("transition") or "cut"
        dur = 0.0 if tr == "cut" else 0.4
        nxt = f"v{i}"
        if dur:
            parts.append(f"[{cur}][{i}:v]xfade=transition={_xfade_name(tr)}:duration={dur}:offset={off - dur:.3f}[{nxt}]")
            off += durs[i] - dur
        else:
            parts.append(f"[{cur}][{i}:v]concat=n=2:v=1:a=0[{nxt}]")
            off += durs[i]
        cur = nxt
    video = work / "video.mp4"
    if parts:
        media.run([*inputs, "-filter_complex", ";".join(parts), "-map", f"[{cur}]", "-c:v", "libx264", "-crf", "12",
                   "-pix_fmt", "yuv420p", str(video)], log=log)
    else:
        shutil.copyfile(norm[0], video)
    # the Insidir logo and the no-yellow guard, once over the whole cut
    from .. import brand
    video = brand.apply(video, work / "video_branded.mp4", log)
    total = off
    # audio: dialogue placed at each shot's start, music under it (ducked), all mastered together
    a_in, a_parts, labels = [], [], []
    k = 1
    starts = np.cumsum([0] + durs[:-1])
    for i, wav in enumerate(dialogue_wavs or []):
        if wav:
            a_in += ["-i", str(wav)]
            a_parts.append(f"[{k}:a]adelay={int(starts[i] * 1000 + 300)}|{int(starts[i] * 1000 + 300)}[d{k}]")
            labels.append(f"[d{k}]")
            k += 1
    if music:
        a_in += ["-stream_loop", "-1", "-i", music]
        a_parts.append(f"[{k}:a]volume=-14dB,atrim=0:{total:.3f},afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[m]")
        labels.append("[m]")
    if not labels:
        shutil.copyfile(video, out)
        return out
    mix = f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,loudnorm=I=-14:TP=-1[a]"
    media.run(["-i", str(video), *a_in, "-filter_complex", ";".join(a_parts + [mix]), "-map", "0:v", "-map", "[a]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", str(out)], log=log)
    return out


def render_film(payload: dict, out_dir: Path, progress, cancel, log) -> dict:
    """Generate every shot that has no take yet, then assemble the film."""
    from . import characters as chars
    from .engine import Spec, generate
    out_dir.mkdir(parents=True, exist_ok=True)
    film = payload["film"]
    model = payload["model"]
    base = payload.get("settings") or {}
    shots = [s for sc in film["scenes"] for s in sc["shots"]]
    takes = []
    char_lib = {c["id"]: c for c in chars.list_characters()}
    for i, sh in enumerate(shots):
        if cancel.is_set():
            from .engine import Cancelled
            raise Cancelled()
        if sh.get("take") and Path(sh["take"]).exists() and not payload.get("regenerate_all"):
            takes.append({**sh, "path": sh["take"]})
            continue
        cs = [char_lib[c] for c in sh.get("characters", []) if c in char_lib]
        spec = Spec(task="r2v" if cs and "r2v" in _tasks(model) else "t2v", model=model, prompt=sh["prompt"],
                    camera=sh.get("camera", []), lens=sh.get("lens", ""), lighting=sh.get("lighting", ""),
                    style=sh.get("style", "photoreal"), seconds=float(sh.get("seconds") or 5),
                    characters=[{"name": c["name"], "description": c.get("description", ""),
                                 "images": c.get("images", [])} for c in cs],
                    seed=int(base.get("seed", -1)), aspect=base.get("aspect", "16:9"),
                    steps=int(base.get("steps") or 0), post={"brand": False})   # logo goes on once, on the cut
        log(f"shot {i + 1}/{len(shots)}: {sh['shot']} - {sh['prompt'][:60]}")
        r = generate(spec, out_dir / sh["id"], lambda f, m="", i=i: progress((i + f * 0.92) / (len(shots) + 0.5), f"Shot {i + 1}: {m}"),
                     cancel, log)
        sh["take"] = r["final"]
        takes.append({**sh, "path": r["final"]})
    progress(0.95, "Assembling the film")
    first = media.probe(Path(takes[0]["path"]))
    fps = int(base.get("fps") or 24)
    dialogue = []
    if any(s.get("dialogue") for s in shots):
        from .. import tts
        for s in shots:
            if s.get("dialogue"):
                c = char_lib.get(s.get("speaker") or "")
                wav = out_dir / f"{s['id']}_line.wav"
                tts.preview(s["dialogue"], (c or {}).get("voice") or tts.DEFAULT_VOICE, 1.0, wav)
                dialogue.append(wav)
            else:
                dialogue.append(None)
    final = assemble(takes, out_dir / "film.mp4", fps, first["width"], first["height"], base.get("music", ""),
                     dialogue, bool(base.get("beat_sync")), log)
    (out_dir / "film.json").write_text(json.dumps(film, indent=1))
    return {"final": str(final), "film": film, "shots": len(shots)}


def _tasks(model: str) -> list:
    from .models import MODELS
    return MODELS[model]["tasks"]


def storyboard_frame_spec(shot: dict, model: str, aspect: str) -> dict:
    """A one-frame generation (Wan renders single images too) to preview a shot cheaply."""
    return {"task": "t2v", "model": model, "prompt": shot["prompt"], "camera": shot.get("camera", []),
            "lens": shot.get("lens", ""), "lighting": shot.get("lighting", ""), "style": shot.get("style", "photoreal"),
            "seconds": 0.0, "aspect": aspect}


def config_dir() -> Path:
    return config.studio_home()
