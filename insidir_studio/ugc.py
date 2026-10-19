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
LAYOUTS = ["face", "split", "bubble", "screen"]
GAP = 0.30        # silences longer than this are cut out
PAD_IN = 0.06     # keep a breath before the first word
PAD_OUT = 0.10    # and a little after the last
BUBBLE = 456      # face-cam circle size (px)


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


def plan(beats: list[dict], fps: int, gap: float | None = GAP) -> list[Seg]:
    """gap: pauses longer than this become jump cuts (None keeps each sentence whole)."""
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
            segs.append(Seg(b["id"], src, s, e, layout, screen, vis.get("focus") or [0.5, 0.5]))
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


def _card(idx: int, a: dict, focus, fps: int, seconds: float, cy: int = 860, max_w: int = 1000, max_h: int = 1200) -> str:
    """Screen asset as a card on its own blurred backdrop, slowly pushing in toward the focus."""
    sw, sh = int(a["width"]), int(a["height"])
    k = min(max_w / sw, max_h / sh)
    fw, fh = _even(sw * k), _even(sh * k)
    n = max(1, int(seconds * fps))
    fx, fy = float(focus[0]), float(focus[1])
    tp = f",tpad=stop_mode=clone:stop_duration={seconds + 1:.2f}" if a["type"] == "video" else ""
    return (
        f"[{idx}:v]fps={fps},setsar=1{tp},split=2[sa{idx}][sb{idx}];"
        f"[sa{idx}]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=14:2,"
        f"scale={W}:{H},eq=brightness=-0.28:saturation=0.7[bg{idx}];"
        f"[sb{idx}]scale={fw * 2}:{fh * 2}:flags=lanczos,"
        f"zoompan=z='1+0.07*on/{n}':x='(iw-iw/zoom)*{fx}':y='(ih-ih/zoom)*{fy}':d=1:s={fw}x{fh}:fps={fps}[fg{idx}];"
        f"[bg{idx}][fg{idx}]overlay=x=(W-w)/2:y={cy}-h/2:shortest=1[card{idx}]"
    )


def render_segment(sg: Seg, creator: dict, screen: dict | None, project_dir: Path, fps: int, out: Path,
                   build: Path, log=None) -> Path:
    seconds = sg.frames / fps
    face_focus = creator.get("focus") or [0.5, 0.4]
    cw, ch = int(creator["width"]), int(creator["height"])
    inputs = ["-ss", f"{sg.start:.3f}", "-i", str(project_dir / creator["file"])]
    head = f"[0:v]fps={fps},setsar=1,tpad=stop_mode=clone:stop_duration=1"
    if sg.layout == "face" or screen is None:
        x, y, w, h = cover(cw, ch, W / H, face_focus, sg.zoom)
        graph = f"{head},crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos[v]"
    elif sg.layout == "split":
        inputs += _screen_input(screen, project_dir, sg.screen_start, seconds)
        x, y, w, h = cover(cw, ch, W / (H / 2), face_focus, sg.zoom)
        sx, sy, sw_, sh_ = cover(int(screen["width"]), int(screen["height"]), W / (H / 2), sg.focus, 1.0)
        tp = ",tpad=stop_mode=clone:stop_duration=1" if screen["type"] == "video" else ""
        graph = (
            f"[1:v]fps={fps},setsar=1{tp},crop={sw_}:{sh_}:{sx}:{sy},scale={W}:{H // 2}:flags=lanczos[top];"
            f"{head},crop={w}:{h}:{x}:{y},scale={W}:{H // 2}:flags=lanczos[bot];"
            f"[top][bot]vstack=inputs=2,drawbox=x=0:y={H // 2 - 3}:w={W}:h=6:color=white@0.9:t=fill[v]"
        )
    elif sg.layout == "bubble":
        inputs += _screen_input(screen, project_dir, sg.screen_start, seconds)
        ring = _ring_png(build / f"ring_{BUBBLE + 16}.png", BUBBLE + 16)
        inputs += ["-loop", "1", "-i", str(ring)]
        x, y, w, h = cover(cw, ch, 1.0, face_focus, 1.25)
        r = BUBBLE / 2
        graph = (
            _card(1, screen, sg.focus, fps, seconds, cy=1000) + ";"
            f"{head},crop={w}:{h}:{x}:{y},scale={BUBBLE}:{BUBBLE}:flags=lanczos,format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(hypot(X-{r}+0.5,Y-{r}+0.5),{r - 1}),255,0)'[face];"
            f"[card1][2:v]overlay=x={W - BUBBLE - 16 - 48}:y=170:shortest=1[c2];"
            f"[c2][face]overlay=x={W - BUBBLE - 8 - 48}:y=178:shortest=1[v]"
        )
    else:  # screen only, the voice carries on
        inputs += _screen_input(screen, project_dir, sg.screen_start, seconds)
        graph = _card(1, screen, sg.focus, fps, seconds) + ";[card1]null[v]"
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
    segs = plan(beats, fps, gap)
    if not segs:
        raise RuntimeError("Keep at least one sentence with speech in it.")
    by_id = {a["id"]: a for a in proj.get("assets", [])}
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
