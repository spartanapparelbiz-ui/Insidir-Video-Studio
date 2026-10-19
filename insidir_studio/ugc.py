"""UGC: videos made from a real person's own footage (or an AI photo avatar).

1. Transcribe each creator clip with Faster Whisper (word timestamps).
2. One beat per sentence; you choose which to keep and a layout for each:
   face (full-screen talking head), split (Insidir screen on top, face below),
   bubble (Insidir screen with the face in a circle) or screen (screen only).
3. Cut silences and filler words into tight jump cuts, alternating the framing
   so every cut lands as a punch-in.
4. The creator's own voice is cleaned (denoise, EQ, loudness); captions come from
   what they actually said.
"""

from __future__ import annotations

import json
import re
import shutil
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config, media, tts, whisper_align

W, H = config.WIDTH, config.HEIGHT
SR = 48000
FILLERS = {"um", "uh", "er", "ah", "erm", "hmm", "mm", "uhm"}
LAYOUTS = ["face", "split", "bubble", "screen", "broll"]
GAP = 0.30        # silences longer than this are cut out
PAD_IN = 0.06     # keep a breath before the first word
PAD_OUT = 0.10    # and a little after the last
PUSH = 0.035      # each face shot pushes in this much, eased, for a smooth handheld-camera feel


def _w(text: str) -> str:
    return re.sub(r"[^a-z']", "", text.lower())


def creator_assets(proj: dict) -> list[dict]:
    return [a for a in proj.get("assets", []) if a.get("role") == "creator" and a["type"] == "video"]


def real_person(proj: dict) -> bool:
    """True when a real creator is speaking on camera (not an AI avatar)."""
    clips = creator_assets(proj)
    return proj.get("mode") == "ugc" and bool(clips) and not any(a.get("ai_generated") for a in clips)


def sentences(words: list[dict], max_words: int = 22) -> list[list[dict]]:
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = re.search(r"[.!?]$", w["text"]) or (nxt and nxt["start"] - w["end"] > 0.8) or len(cur) >= max_words
        if end or nxt is None:
            out.append(cur)
            cur = []
    return [s for s in out if s]


def transcribe(proj: dict, project_dir: Path, log=None) -> dict:
    """Build a UGC script (one beat per spoken sentence) from the creator clips."""
    if not whisper_align.available():
        raise RuntimeError("UGC needs Faster Whisper to transcribe your footage. Run install.bat.")
    clips = creator_assets(proj)
    if not clips:
        raise RuntimeError("Upload a talking-head video and set it to Creator on the Footage tab first.")
    cache = project_dir / "build" / "transcripts"
    cache.mkdir(parents=True, exist_ok=True)
    beats = []
    for a in clips:
        cf = cache / f"{a['id']}.json"
        if cf.exists():
            words = json.loads(cf.read_text(encoding="utf-8"))
        else:
            if log:
                log(f"transcribing {a.get('label')}")
            words = whisper_align.transcribe(project_dir / a["file"])
            cf.write_text(json.dumps(words), encoding="utf-8")
        for s in sentences(words):
            text = tidy(" ".join(w["text"] for w in s))
            if len(text.split()) == len(s):
                s = [{**w, "text": t} for w, t in zip(s, text.split())]
            beats.append({
                "id": f"b{len(beats) + 1}",
                "text": " ".join(w["text"] for w in s),
                "keep": True,
                "overlay": "",
                "source": {"asset": a["id"], "start": s[0]["start"], "end": s[-1]["end"]},
                "words": s,
                "visual": {"kind": "ugc", "layout": "face", "asset": None, "focus": [0.5, 0.5]},
            })
    if not beats:
        raise RuntimeError("No speech was found in the footage.")
    return {"title": proj.get("name", ""), "beats": beats, "facts_used": []}


# Whisper hears the spoken form; captions should show the written one.
SPOKEN = [
    (re.compile(r"\bform (four|for)\b", re.I), "Form 4"),
    (re.compile(r"\bedgar\b", re.I), "EDGAR"),
]


def tidy(text: str) -> str:
    for pat, rep in SPOKEN:
        text = pat.sub(rep, text)
    return text


def corrected_words(beat: dict) -> list[dict]:
    """The beat's words with any caption fixes the user typed applied.

    The text box on the Script tab can fix spellings ("Insider" -> "Insidir") as long as the
    number of words stays the same; timing still comes from the recording."""
    ws = beat.get("words", [])
    toks = (beat.get("text") or "").split()
    if len(toks) != len(ws):
        return ws
    return [{**w, "text": t} for w, t in zip(ws, toks)]


# ------------------------------------------------------------------ geometry

def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def cover(sw: int, sh: int, aspect: float, focus, zoom: float = 1.0) -> tuple[int, int, int, int]:
    """Crop (x, y, w, h) of aspect w/h around focus, zoomed in by `zoom`."""
    if sw / sh > aspect:
        rh = sh / zoom
        rw = rh * aspect
    else:
        rw = sw / zoom
        rh = rw / aspect
    fx, fy = float(focus[0]), float(focus[1])
    x = min(max(0.0, fx * sw - rw / 2), sw - rw)
    y = min(max(0.0, fy * sh - rh / 2), sh - rh)
    return _even(x) if x >= 2 else 0, _even(y) if y >= 2 else 0, _even(rw), _even(rh)


# ------------------------------------------------------------------ edit

@dataclass
class Seg:
    beat: str
    asset: str
    start: float
    end: float
    layout: str
    screen: str | None
    focus: list
    zoom: float = 1.0
    out_start: float = 0.0
    frames: int = 0
    screen_start: float = 0.0
    move: str = "push_in"
    strength: float = 1.0


@dataclass
class Built:
    video: Path
    voice: Path
    words: list
    beat_times: list
    total: float
    end_card_start: float | None
    shots: list = field(default_factory=list)
    segments: list = field(default_factory=list)


CAMERA_STYLES = {
    "dynamic": "Dynamic: crash zoom on the hook, then push-ins, drifts and pull-outs",
    "calm": "Calm: slow push-ins only",
    "energetic": "Energetic: a crash zoom on every new sentence, impact shakes",
    "handheld": "Handheld: everything floats like a phone held in the hand",
    "static": "Locked off: no camera movement",
}


def auto_move(style: str, i: int, first_of_beat: bool, layout: str) -> str:
    if style == "static":
        return "static"
    if style == "calm":
        return "push_in"
    if style == "handheld":
        return "drift"
    if style == "energetic":
        return "crash_zoom" if first_of_beat else ("shake" if i % 5 == 4 else "push_in")
    if i == 0:
        return "crash_zoom"
    if layout in ("screen", "bubble"):
        return "push_in"
    return ["push_in", "drift", "pull_out", "push_in"][i % 4]


def plan(beats: list[dict], fps: int, gap: float | None = GAP, camera_style: str = "dynamic",
         strength: float = 1.0) -> list[Seg]:
    """gap: pauses longer than this become jump cuts (None keeps each sentence whole).
    camera_style picks a move per shot unless the beat sets visual.move itself."""
    segs: list[Seg] = []
    for b in beats:
        if not b.get("keep", True):
            continue
        vis = b.get("visual") or {}
        layout = vis.get("layout") if vis.get("layout") in LAYOUTS else "face"
        screen = vis.get("asset") if layout != "face" else None
        if layout != "face" and not screen:
            layout = "face"
        ws = [w for w in b.get("words", []) if _w(w["text"]) not in FILLERS]
        if not ws:
            continue
        groups, cur = [], [ws[0]]
        for w in ws[1:]:
            if gap is not None and w["start"] - cur[-1]["end"] > gap:
                groups.append(cur)
                cur = []
            cur.append(w)
        groups.append(cur)
        src = (b.get("source") or {}).get("asset")
        full = b.get("words", [])
        for g in groups:
            # pad for breath, but never into a dropped filler or the neighbouring word
            i0, i1 = full.index(g[0]), full.index(g[-1])
            lo = full[i0 - 1]["end"] if i0 > 0 else 0.0
            hi = full[i1 + 1]["start"] - 0.01 if i1 + 1 < len(full) else g[-1]["end"] + PAD_OUT
            s = max(0.0, lo, g[0]["start"] - PAD_IN)
            e = min(g[-1]["end"] + PAD_OUT, max(g[-1]["end"], hi))
            if segs and segs[-1].asset == src and s < segs[-1].end:
                s = segs[-1].end
            if e - s < 0.12:
                continue
            first = not segs or segs[-1].beat != b["id"]
            move = vis.get("move") if vis.get("move") in MOVES else auto_move(camera_style, len(segs), first, layout)
            segs.append(Seg(b["id"], src, s, e, layout, screen, vis.get("focus") or [0.5, 0.5],
                            move=move, strength=strength))
    # jump cuts: alternate the framing on consecutive face shots
    face_n = 0
    for sg in segs:
        if sg.layout in ("face", "split"):
            sg.zoom = 1.0 if face_n % 2 == 0 else 1.16
            face_n += 1
    t = 0.0
    cursors: dict = {}
    for sg in segs:
        if sg.screen:  # a screen recording keeps playing across cuts instead of restarting
            sg.screen_start = cursors.get(sg.screen, 0.0)
        sg.frames = max(1, int((sg.end - sg.start) * fps + 1e-6))  # floor: never run into the next word
        sg.end = sg.start + sg.frames / fps
        sg.out_start = t
        t += sg.frames / fps
        if sg.screen:
            cursors[sg.screen] = sg.screen_start + sg.frames / fps
    return segs


def _ring_png(path: Path, size: int) -> Path:
    if not path.exists():
        r = size / 2
        media.run(["-f", "lavfi", "-i", f"color=c=white:s={size}x{size}", "-frames:v", "1", "-vf",
                   f"format=rgba,geq=r=255:g=255:b=255:a='if(lte(hypot(X-{r}+0.5,Y-{r}+0.5),{r - 1}),255,0)'",
                   str(path)])
    return path


def _screen_input(a: dict, project_dir: Path, start: float, seconds: float) -> list[str]:
    path = str(project_dir / a["file"])
    if a["type"] == "video":
        dur = float(a.get("duration") or 0)
        if dur > 1 and start + seconds > dur:
            start = start % max(0.5, dur - seconds) if dur > seconds else 0.0
        return ["-ss", f"{start:.3f}", "-i", path]
    return ["-loop", "1", "-framerate", "30", "-t", f"{seconds + 0.5:.3f}", "-i", path]


# Camera moves (Higgsfield-style presets, done with FFmpeg's zoompan on a 2x supersampled frame
# so every move travels in half-pixel steps). `e` is an eased 0->1 progress over the shot.
MOVES = {
    "push_in": "Slow push-in",
    "pull_out": "Slow pull-out",
    "crash_zoom": "Crash zoom",
    "pan_left": "Pan left",
    "pan_right": "Pan right",
    "tilt_up": "Tilt up",
    "drift": "Handheld drift",
    "shake": "Impact shake",
    "static": "Locked off",
}


def camera(move: str, frames: int, fps: int, fy: float = 0.5, strength: float = 1.0) -> tuple[str, str, str]:
    """zoompan z, x, y expressions for a camera move."""
    n = max(1, frames - 1)
    e = f"((1-cos(PI*min(on/{n}\\,1)))/2)"
    cx, cy = "(iw-iw/zoom)/2", f"(ih-ih/zoom)*{fy:.3f}"
    k = strength
    if move == "pull_out":
        return f"{1 + 0.06 * k:.4f}-{0.06 * k:.4f}*{e}", cx, cy
    if move == "crash_zoom":
        q = max(1, int(fps * 0.28))
        return f"1+{0.2 * k:.4f}*(1-pow(1-min(on/{q}\\,1)\\,3))+{0.02 * k:.4f}*{e}", cx, cy
    if move in ("pan_left", "pan_right"):
        a, b = (0.85, 0.15) if move == "pan_left" else (0.15, 0.85)
        return f"{1 + 0.14 * k:.4f}", f"(iw-iw/zoom)*({a}+({b - a})*{e})", cy
    if move == "tilt_up":
        return f"{1 + 0.14 * k:.4f}", cx, f"(ih-ih/zoom)*(0.85-0.7*{e})"
    if move == "drift":
        return (f"{1 + 0.07 * k:.4f}+{0.015 * k:.4f}*sin(on/{fps}*0.9)",
                f"(iw-iw/zoom)*(0.5+0.18*sin(on/{fps}*0.7))", f"(ih-ih/zoom)*({fy:.3f}+0.12*sin(on/{fps}*0.53))")
    if move == "shake":
        decay = f"exp(-on/{fps * 0.35:.2f})"
        return (f"{1 + 0.08 * k:.4f}", f"(iw-iw/zoom)*(0.5+0.35*{decay}*sin(on*2.1))",
                f"(ih-ih/zoom)*({fy:.3f}+0.3*{decay}*sin(on*2.9+1))")
    if move == "static":
        return "1", cx, cy
    return f"1+{PUSH * k:.4f}*{e}", cx, cy   # push_in (default)


def _zp(move: str, frames: int, fps: int, w: int, h: int, fy: float, strength: float) -> str:
    z, x, y = camera(move, frames, fps, fy, strength)
    return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={fps}"


def bubble_size() -> int:
    return _even(min(W, H) * 0.42)


def _card(idx: int, a: dict, focus, fps: int, seconds: float, cy: int | None = None, max_w: float | None = None,
          max_h: float | None = None, move: str = "push_in", strength: float = 1.0) -> str:
    """Screen asset as a card on its own blurred backdrop, with a camera move toward the focus."""
    cy = int(H * 0.45) if cy is None else cy
    max_w = W * (0.93 if W < H else 0.62) if max_w is None else max_w
    max_h = H * (0.62 if W < H else 0.84) if max_h is None else max_h
    sw, sh = int(a["width"]), int(a["height"])
    k = min(max_w / sw, max_h / sh)
    fw, fh = _even(sw * k), _even(sh * k)
    n = max(1, int(seconds * fps))
    fx, fy = float(focus[0]), float(focus[1])
    tp = f",tpad=stop_mode=clone:stop_duration={seconds + 1:.2f}" if a["type"] == "video" else ""
    z, x, y = camera(move, n, fps, fy, strength * 1.2)
    x = x.replace("*0.5+", f"*{fx:.3f}+").replace("(iw-iw/zoom)/2", f"(iw-iw/zoom)*{fx:.3f}")
    bw, bh = _even(W / 4), _even(H / 4)
    return (
        f"[{idx}:v]fps={fps},setsar=1{tp},split=2[sa{idx}][sb{idx}];"
        f"[sa{idx}]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},boxblur=14:2,"
        f"scale={W}:{H},eq=brightness=-0.28:saturation=0.7[bg{idx}];"
        f"[sb{idx}]scale={fw * 2}:{fh * 2}:flags=lanczos,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={fw}x{fh}:fps={fps}[fg{idx}];"
        f"[bg{idx}][fg{idx}]overlay=x=(W-w)/2:y={cy}-h/2:shortest=1[card{idx}]"
    )


def render_segment(sg: Seg, creator: dict, screen: dict | None, project_dir: Path, fps: int, out: Path,
                   build: Path, log=None) -> Path:
    seconds = sg.frames / fps
    face_focus = creator.get("focus") or [0.5, 0.4]
    cw, ch = int(creator["width"]), int(creator["height"])
    inputs = ["-ss", f"{sg.start:.3f}", "-i", str(project_dir / creator["file"])]
    head = f"[0:v]fps={fps},setsar=1,tpad=stop_mode=clone:stop_duration=1"
    fy = float(face_focus[1])
    landscape = W > H
    if sg.layout == "broll" and screen is not None:
        # real-people b-roll full frame; the voice carries on underneath
        inputs = _screen_input(screen, project_dir, sg.screen_start, seconds)
        sx, sy, sw_, sh_ = cover(int(screen["width"]), int(screen["height"]), W / H, sg.focus, 1.0)
        tp = ",tpad=stop_mode=clone:stop_duration=1" if screen["type"] == "video" else ""
        graph = (f"[0:v]fps={fps},setsar=1{tp},crop={sw_}:{sh_}:{sx}:{sy},scale={W * 2}:{H * 2}:flags=bicubic,"
                 f"{_zp(sg.move, sg.frames, fps, W, H, float(sg.focus[1]), sg.strength)}[v]")
    elif sg.layout == "face" or screen is None:
        if cw / ch < (W / H) * 0.62:
            # a vertical selfie in a wide frame: sharp face over a blurred fill, like a news cut-in
            fh_ = H
            fw_ = _even(H * cw / ch)
            bw, bh = _even(W / 4), _even(H / 4)
            graph = (f"{head},split=2[a][b];"
                     f"[a]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},boxblur=16:2,"
                     f"scale={W}:{H},eq=brightness=-0.22:saturation=0.8[bg];"
                     f"[b]scale={fw_ * 2}:{fh_ * 2}:flags=bicubic,{_zp(sg.move, sg.frames, fps, fw_, fh_, fy, sg.strength)}[fg];"
                     f"[bg][fg]overlay=x=(W-w)/2:y=0:shortest=1[v]")
        else:
            x, y, w, h = cover(cw, ch, W / H, face_focus, sg.zoom)
            graph = (f"{head},crop={w}:{h}:{x}:{y},scale={W * 2}:{H * 2}:flags=bicubic,"
                     f"{_zp(sg.move, sg.frames, fps, W, H, fy, sg.strength)}[v]")
    elif sg.layout == "split":
        inputs += _screen_input(screen, project_dir, sg.screen_start, seconds)
        # vertical: app on top, face below; landscape: app left, face right
        pw, ph = (W // 2, H) if landscape else (W, H // 2)
        pw, ph = _even(pw), _even(ph)
        x, y, w, h = cover(cw, ch, pw / ph, face_focus, sg.zoom)
        sx, sy, sw_, sh_ = cover(int(screen["width"]), int(screen["height"]), pw / ph, sg.focus, 1.0)
        tp = ",tpad=stop_mode=clone:stop_duration=1" if screen["type"] == "video" else ""
        stack = (f"[top][bot]hstack=inputs=2,drawbox=x={pw - 3}:y=0:w=6:h={H}:color=white@0.9:t=fill[v]" if landscape
                 else f"[top][bot]vstack=inputs=2,drawbox=x=0:y={ph - 3}:w={W}:h=6:color=white@0.9:t=fill[v]")
        graph = (
            f"[1:v]fps={fps},setsar=1{tp},crop={sw_}:{sh_}:{sx}:{sy},scale={pw}:{ph}:flags=lanczos[top];"
            f"{head},crop={w}:{h}:{x}:{y},scale={pw * 2}:{ph * 2}:flags=bicubic,"
            f"{_zp(sg.move, sg.frames, fps, pw, ph, fy, sg.strength * 0.7)}[bot];" + stack
        )
    elif sg.layout == "bubble":
        inputs += _screen_input(screen, project_dir, sg.screen_start, seconds)
        bs = bubble_size()
        ring = _ring_png(build / f"ring_{bs + 16}.png", bs + 16)
        inputs += ["-loop", "1", "-i", str(ring)]
        x, y, w, h = cover(cw, ch, 1.0, face_focus, 1.25)
        r = bs / 2
        m = int(min(W, H) * 0.044)
        top = int(H * 0.09)
        graph = (
            _card(1, screen, sg.focus, fps, seconds, cy=int(H * 0.52), move=sg.move, strength=sg.strength * 0.6) + ";"
            f"{head},crop={w}:{h}:{x}:{y},scale={bs}:{bs}:flags=lanczos,format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(hypot(X-{r}+0.5,Y-{r}+0.5),{r - 1}),255,0)'[face];"
            f"[card1][2:v]overlay=x={W - bs - 16 - m}:y={top - 8}:shortest=1[c2];"
            f"[c2][face]overlay=x={W - bs - 8 - m}:y={top}:shortest=1[v]"
        )
    else:  # screen only, the voice carries on
        inputs += _screen_input(screen, project_dir, sg.screen_start, seconds)
        graph = _card(1, screen, sg.focus, fps, seconds, move=sg.move, strength=sg.strength) + ";[card1]null[v]"
    media.run([*inputs, "-filter_complex", graph, "-map", "[v]", "-frames:v", str(sg.frames), "-r", str(fps),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-an", str(out)],
              log=log)
    return out


def _audio(path: Path, cache: Path) -> np.ndarray:
    f = cache / (path.stem + ".f32")
    if f.exists():
        return np.fromfile(f, dtype=np.float32)
    data = whisper_align.decode(path, SR)
    data.tofile(f)
    return data


def build(proj: dict, beats: list[dict], project_dir: Path, build_dir: Path, fps: int, end_card_on: bool,
          end_card_seconds: float, log=None, progress=None, gap: float | None = GAP) -> Built:
    look = proj.get("style") or {}
    if not look.get("preset"):
        # nothing chosen yet: real people get the natural, realistic camera (a hand-held phone)
        look = {**look, "camera": "handheld", "camera_strength": 0.5}
    segs = plan(beats, fps, gap, look.get("camera") or "dynamic", float(look.get("camera_strength") or 1.0))
    if not segs:
        raise RuntimeError("Keep at least one sentence with speech in it.")
    by_id = {a["id"]: a for a in proj.get("assets", [])}
    # start screen recordings where they show something, not on a blank loading frame
    offsets = {}
    for sg in segs:
        a = by_id.get(sg.screen) if sg.screen else None
        if a and a["type"] == "video":
            if a["id"] not in offsets:
                offsets[a["id"]] = media.content_start(project_dir / a["file"], build_dir / "thumbs")
            sg.screen_start += offsets[a["id"]]
    seg_dir = build_dir / "ugc"
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)
    files = []
    for i, sg in enumerate(segs):
        if progress:
            progress(0.15 + 0.6 * i / len(segs), f"Cutting shot {i + 1} of {len(segs)}")
        creator = by_id[sg.asset]
        screen = by_id.get(sg.screen) if sg.screen else None
        files.append(render_segment(sg, creator, screen, project_dir, fps, seg_dir / f"u{i:03d}.mp4", build_dir, log))
    speech_end = segs[-1].out_start + segs[-1].frames / fps
    end_card_start = None
    if end_card_on:
        end_frames = round(end_card_seconds * fps)
        end = seg_dir / "end.mp4"
        media.run(["-f", "lavfi", "-i", f"color=c=0x0c0c0b:s={W}x{H}:r={fps}", "-frames:v", str(end_frames),
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", str(end)], log=log)
        files.append(end)
        end_card_start = speech_end
    total = speech_end + (round(end_card_seconds * fps) / fps if end_card_on else 0.0)
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    video = build_dir / "ugc_video.mp4"
    media.run(["-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", str(video)], cwd=seg_dir, log=log)

    # the creator's own voice, cut exactly like the picture (6 ms fades so cuts don't click)
    cache = build_dir / "transcripts"
    cache.mkdir(parents=True, exist_ok=True)
    pcm = np.zeros(int(round(total * SR)), dtype=np.float32)
    fade = int(0.006 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    srcs: dict[str, np.ndarray] = {}
    for sg in segs:
        src = srcs.setdefault(sg.asset, _audio(project_dir / by_id[sg.asset]["file"], cache))
        n = int(round(sg.frames / fps * SR))
        a0 = int(round(sg.start * SR))
        piece = np.zeros(n, dtype=np.float32)
        chunk = src[a0:a0 + n]
        piece[:len(chunk)] = chunk
        piece[:fade] *= ramp
        piece[-fade:] *= ramp[::-1]
        o0 = int(round(sg.out_start * SR))
        pcm[o0:o0 + n] += piece[: len(pcm) - o0]
    voice = build_dir / "ugc_voice.wav"
    with wave.open(str(voice), "wb") as wv:
        wv.setnchannels(1)
        wv.setsampwidth(2)
        wv.setframerate(SR)
        wv.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())

    # captions from what was actually said, retimed onto the edit
    beat_words = {b["id"]: corrected_words(b) for b in beats}
    words: list[tts.Word] = []
    beat_times: dict[str, dict] = {}
    shots = []
    for sg in segs:
        dur = sg.frames / fps
        for w in beat_words.get(sg.beat, []):
            if _w(w["text"]) in FILLERS or w["start"] < sg.start - 0.02 or w["end"] > sg.end + 0.08:
                continue
            words.append(tts.Word(w["text"], round(sg.out_start + w["start"] - sg.start, 3),
                                  round(min(sg.out_start + dur, sg.out_start + w["end"] - sg.start), 3), sg.beat))
        bt = beat_times.setdefault(sg.beat, {"id": sg.beat, "start": sg.out_start, "speech_start": sg.out_start})
        bt["speech_end"] = bt["end"] = sg.out_start + dur
        scr = by_id.get(sg.screen) if sg.screen else None
        if scr and scr.get("genuine") and sg.layout != "face":
            shots.append({"start": sg.out_start, "duration": dur, "genuine": True, "ai_presenter": False})
        if by_id[sg.asset].get("ai_generated") and sg.layout != "screen":
            shots.append({"start": sg.out_start, "duration": dur, "genuine": False, "ai_presenter": True})
    return Built(video=video, voice=voice, words=words, beat_times=list(beat_times.values()), total=total,
                 end_card_start=end_card_start, shots=shots, segments=segs)
