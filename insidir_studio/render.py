"""FFmpeg render pipeline: shots -> runs -> transitions + captions + audio -> 1080x1920 MP4."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import animate, audio, avatars, sound, ugc, avatar, captions, compliance, config, media, project, timeline, tts, whisper_align

W, H, FPS = config.WIDTH, config.HEIGHT, config.FPS
INK = "0x111111"
SEG_ARGS = ["-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
            "-pix_fmt", "yuv420p", "-g", str(FPS), "-an"]


class RenderError(RuntimeError):
    pass


def _highlight(color: str | None) -> str:
    # the old yellow default is retired; projects that saved it get white
    return "#FFFFFF" if not color or color.upper() == "#FFD84D" else color


# ----------------------------------------------------------------- geometry

def _even(x: float) -> int:
    return max(2, int(round(x / 2.0)) * 2)


def _region(src_w: int, src_h: int, framing: str, focus, zoom: float) -> tuple[int, int, int, int]:
    """Crop rectangle (x, y, w, h) in source pixels for a framing."""
    fx = min(1.0, max(0.0, float(focus[0])))
    fy = min(1.0, max(0.0, float(focus[1])))
    if framing in ("wide", "card"):
        return 0, 0, src_w, src_h
    if framing in ("full", "full_tight"):
        z = zoom * (1.18 if framing == "full_tight" else 1.0)
        target = W / H
        if src_w / src_h > target:
            rh = src_h / z
            rw = rh * target
        else:
            rw = src_w / z
            rh = rw / target
    else:  # tight / tighter: a 4:5 window into a landscape screen
        z = zoom * (1.45 if framing == "tighter" else 1.0)
        rh = src_h / z
        rw = rh * 0.8
        if rw > src_w:
            rw = src_w
            rh = rw / 0.8
    rw, rh = min(rw, src_w), min(rh, src_h)
    x = min(max(0.0, fx * src_w - rw / 2), src_w - rw)
    y = min(max(0.0, fy * src_h - rh / 2), src_h - rh)
    return _even(x) if x >= 2 else 0, _even(y) if y >= 2 else 0, _even(rw), _even(rh)


def _fit(rw: int, rh: int, framing: str) -> tuple[int, int, int]:
    """Foreground size on the 1080x1920 canvas and its centre y."""
    if framing in ("full", "full_tight"):
        return W, H, H // 2
    max_w = 1000 if framing in ("wide", "card") else 920
    max_h = 1240
    s = min(max_w / rw, max_h / rh)
    return _even(rw * s), _even(rh * s), 880


def _zoom_expr(frames: int, motion: str, amount: float) -> str:
    n = max(1, frames - 1)
    if motion == "in":
        return f"1+{amount}*on/{n}"
    return f"{1 + amount}-{amount}*on/{n}"


# ----------------------------------------------------------------- segments

def _segment_inputs(shot: dict, project_dir: Path, seconds: float) -> tuple[list[str], dict]:
    """FFmpeg input args and source info for a shot."""
    if shot.get("avatar_video"):
        path = Path(shot["avatar_video"])
        info = media.probe(path)
        return ["-ss", f"{shot['src_start']:.3f}", "-i", str(path)], {**info, "type": "video"}
    asset = shot["asset"]
    path = project_dir / asset["file"]
    if asset["type"] == "video":
        return ["-ss", f"{max(0.0, shot['src_start']):.3f}", "-i", str(path)], asset
    return ["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds + 0.5:.3f}", "-i", str(path)], asset


def render_segment(shot: dict, frames: int, project_dir: Path, out: Path, log=None) -> Path:
    seconds = frames / FPS
    if shot["kind"] in ("title", "endcard") or shot.get("asset") is None and not shot.get("avatar_video"):
        media.run(["-f", "lavfi", "-i", f"color=c={INK}:s={W}x{H}:r={FPS}",
                   "-frames:v", str(frames), *SEG_ARGS, str(out)], log=log)
        return out

    inputs, info = _segment_inputs(shot, project_dir, seconds)
    sw, sh = int(info.get("width") or 0), int(info.get("height") or 0)
    if not sw or not sh:
        raise RenderError(f"Cannot read the size of {shot['asset'].get('file')}")
    framing = "full" if shot.get("avatar_video") else shot["framing"]
    rx, ry, rw, rh = _region(sw, sh, framing, shot["focus"], shot["zoom"])
    fw, fh, cy = _fit(rw, rh, framing)
    is_video = info.get("type") == "video"
    ss = 2 if (fw * fh) <= 1100 * 1300 else 1.5  # supersample so slow zooms stay smooth
    zw, zh = _even(fw * ss), _even(fh * ss)
    amount = 0.035 if framing in ("wide", "card") else 0.06
    z = _zoom_expr(frames, shot["motion"], amount)
    fx, fy = 0.5, 0.5
    head = f"[0:v]fps={FPS},setsar=1"
    if is_video:
        head += f",tpad=stop_mode=clone:stop_duration={seconds + 1:.2f}"
    zoom = (f"zoompan=z='{z}':x='(iw-iw/zoom)*{fx}':y='(ih-ih/zoom)*{fy}':d=1:"
            f"s={fw}x{fh}:fps={FPS}")
    crop = f"crop={rw}:{rh}:{rx}:{ry}"
    if framing in ("full", "full_tight"):
        graph = f"{head},{crop},scale={zw}:{zh}:flags=lanczos,{zoom},setsar=1[v]"
    else:
        graph = (
            f"{head},split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=12:2,"
            f"scale={W}:{H}:flags=bicubic,eq=brightness=-0.20:saturation=0.75[bg];"
            f"[b]{crop},scale={zw}:{zh}:flags=lanczos,{zoom},setsar=1[fg];"
            f"[bg][fg]overlay=x=(W-w)/2:y={cy}-h/2:shortest=1[v]"
        )
    media.run([*inputs, "-filter_complex", graph, "-map", "[v]", "-frames:v", str(frames),
               *SEG_ARGS, str(out)], log=log)
    return out


# ----------------------------------------------------------------- assembly

def _runs(shots: list[dict]) -> list[list[int]]:
    runs: list[list[int]] = []
    for i, sh in enumerate(shots):
        if not runs or sh.get("transition_in"):
            runs.append([i])
        else:
            runs[-1].append(i)
    return runs


def _concat(files: list[Path], out: Path, log=None) -> Path:
    if len(files) == 1:
        shutil.copyfile(files[0], out)
        return out
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    media.run(["-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", out.name], cwd=out.parent, log=log)
    return out


def _audio_graph(n_video: int, has_music: bool, total: float, music_db: float, has_sfx: bool = False) -> str:
    """Voice (pre-mastered) + optional music ducked under it + optional SFX stem."""
    a = n_video
    fade_out = max(0.0, total - 1.2)
    fmt = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    voice = f"[{a}:a]{fmt},apad,atrim=0:{total:.3f}"
    sfx_in = a + 1 + (1 if has_music else 0)
    if not has_music and not has_sfx:
        return voice + "[aout]"
    parts = []
    mix = ["[voice]"]
    if has_music:
        parts.append(voice + ",asplit=2[voice][sc]")
        parts.append(f"[{a + 1}:a]aresample=48000,{fmt},atrim=0:{total:.3f},"
                     f"volume={music_db}dB,afade=t=in:d=0.6,afade=t=out:st={fade_out:.2f}:d=1.2[music]")
        parts.append("[music][sc]sidechaincompress=threshold=0.04:ratio=10:attack=15:release=350[duck]")
        mix.append("[duck]")
    else:
        parts.append(voice + "[voice]")
    if has_sfx:
        parts.append(f"[{sfx_in}:a]{fmt},apad,atrim=0:{total:.3f}[sfx]")
        mix.append("[sfx]")
    parts.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,"
                 "alimiter=limit=0.89:level=disabled[aout]")
    return ";".join(parts)


# ----------------------------------------------------------------- main entry

def _demo_video(proj, beats, nar, words, assets, settings, end_card_on, project_dir, build, seg_dir, log, progress):
    """Screen-recording demo: avatar step (optional), edit decision list, shot segments."""
    # optional avatar clips for presenter beats
    avatar_videos = {}
    presenter_beats = [(b, bt) for b, bt in zip(beats, nar.beats) if (b.get("visual") or {}).get("kind") == "presenter"]
    if presenter_beats and proj.get("presenter", {}).get("use_avatar"):
        st = avatar.status(settings)
        if st["usable"]:
            spans = dict(zip([b["id"] for b in beats], timeline.beat_spans(nar.beats, nar.duration)))
            pres = next((a for a in proj.get("assets", []) if a.get("role") == "presenter" and a["type"] == "image"), None)
            if pres:
                for b, bt in presenter_beats:
                    s0, s1 = spans[b["id"]]
                    clip = build / "avatar" / f"{b['id']}.wav"
                    clip.parent.mkdir(parents=True, exist_ok=True)
                    media.run(["-i", nar.wav, "-ss", f"{s0:.3f}", "-to", f"{s1:.3f}", str(clip)], log=log)
                    progress(0.15, f"Animating presenter for {b['id']}")
                    out = avatar.generate(settings, project_dir / pres["file"], clip, build / "avatar" / f"{b['id']}.mp4", log)
                    avatar_videos[b["id"]] = str(out)
                    # an avatar is always AI-generated
                    pres = {**pres, "ai_generated": True}
        else:
            log("avatar skipped: " + " ".join(st["reasons"]))

    # 3. edit decision list
    if avatar_videos:
        assets = [{**a, "ai_generated": True} if a.get("role") == "presenter" else a for a in assets]
    edl = timeline.plan(beats, nar.beats, words, nar.duration, assets,
                        transitions=proj.get("style", {}).get("transitions") or settings.get("transitions", "cinematic"),
                        end_card=end_card_on, avatar_videos=avatar_videos)
    shots, total = edl["shots"], edl["total"]
    (build / "edl.json").write_text(json.dumps(
        {"total": total, "shots": [{k: v for k, v in s.items() if k != "asset"} | {"asset": (s["asset"] or {}).get("id")}
                                   for s in shots]}, indent=2), encoding="utf-8")

    # 4. shots (each extended under the next transition so the cut lands on time)
    runs = _runs(shots)
    run_files = []
    run_trans = []
    done = 0
    for ri, run in enumerate(runs):
        files = []
        nxt = runs[ri + 1][0] if ri + 1 < len(runs) else None
        ext = int(round(shots[nxt]["transition_in"]["duration"] * FPS)) if nxt is not None else 0
        for j, si in enumerate(run):
            sh = shots[si]
            frames = sh["frames"] + (ext if j == len(run) - 1 else 0)
            out = seg_dir / f"s{si:03d}.mp4"
            progress(0.2 + 0.6 * done / len(shots), f"Shot {si + 1} of {len(shots)}")
            render_segment(sh, frames, project_dir, out, log)
            files.append(out)
            done += 1
        run_files.append(_concat(files, seg_dir / f"run{ri:02d}.mp4", log))
        run_trans.append(shots[run[0]].get("transition_in"))

    run_durs = [sum(shots[si]["duration"] for si in run) for run in runs]
    return avatar_videos, shots, total, edl["end_card_start"], run_files, run_trans, run_durs


def render(project_dir: Path, settings: dict | None = None, log=print, progress=None,
           engine_name: str | None = None) -> dict:
    t0 = time.time()
    settings = settings or config.load_settings()
    proj = project.load(project_dir)
    progress = progress or (lambda p, msg="": None)
    facts = compliance.load_facts()
    script = proj.get("script") or {}
    beats = [b for b in script.get("beats", []) if (b.get("text") or "").strip()]
    if not beats:
        raise RenderError("The script is empty.")
    for i, b in enumerate(beats):
        b.setdefault("id", f"b{i + 1}")

    mode = proj.get("mode") or "demo"
    if mode == "ugc":
        beats = [b for b in beats if b.get("keep", True)]
        if not beats:
            raise RenderError("Keep at least one sentence.")
    if mode == "ugc":
        for a in ugc.creator_assets(proj):
            if not a.get("rights_confirmed"):
                raise RenderError(f'Confirm you have the rights to use "{a.get("label") or a.get("file")}" (Footage tab).')
    real_person = ugc.real_person(proj)
    issues = compliance.lint(script, facts, proj.get("assets", []), real_person=real_person)
    if compliance.has_errors(issues):
        msgs = "; ".join(f"[{i['where']}] {i['message']}" for i in issues if i["level"] == "error")
        raise RenderError("The claim guard blocked this render: " + msgs)

    build = project_dir / "build"
    seg_dir = build / "segments"
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True, exist_ok=True)
    fonts = build / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in [*config.FONTS_DIR.glob("*.otf"), *config.FONTS_DIR.glob("*.ttf")]:
        shutil.copyfile(f, fonts / f.name)

    # animated, UGC and avatar videos render at 60 fps in High quality (smoother motion and push-ins);
    # the screen-demo cut stays on its 30 fps grid
    high = proj.get("style", {}).get("quality", "high") == "high"
    out_fps = 60 if (mode in ("animated", "ugc", "photo_avatar") and high) else FPS
    assets = proj.get("assets", [])
    avatar_videos: dict = {}
    end_card_on = proj.get("style", {}).get("end_card", True)
    extra = timeline.END_CARD_SECONDS if end_card_on else 0.0
    if mode == "ugc":
        progress(0.05, "Cutting your footage")
        u = ugc.build(proj, beats, project_dir, build, out_fps, end_card_on, timeline.END_CARD_SECONDS, log, progress)
        if not (config.MIN_SECONDS - 0.05 <= u.total <= config.MAX_SECONDS + 0.05):
            raise RenderError(
                f"The edit runs {u.total:.1f}s; it must be {config.MIN_SECONDS:.0f}-{config.MAX_SECONDS:.0f}s. "
                + ("Untick a sentence or two on the Script tab." if u.total > config.MAX_SECONDS else "Keep more sentences.")
            )
        nar = tts.Narration(wav=str(u.voice), duration=u.end_card_start or u.total, speed=1.0, voice="creator",
                            engine="recorded", beats=u.beat_times, words=u.words)
        words = tts_words = u.words
        total, end_card_start = u.total, u.end_card_start
        run_files, run_trans, run_durs = [u.video], [None], [total]
        shots = u.shots
        caption_beats = beats
    else:
        # 1. voice
        progress(0.05, "Voicing the script")
        engine = tts.get_engine(engine_name)
        voice = tts.valid_voice(proj.get("voice", {}).get("voice") or settings.get("voice"))
        speed = float(proj.get("voice", {}).get("speed") or settings.get("speed", 1.0))
        nar = tts.fit_narration(beats, voice, speed, engine, build, extra_seconds=extra, log=log)
        tts_words = nar.words
        total_est = nar.duration + extra
        if not (config.MIN_SECONDS - 0.05 <= total_est <= config.MAX_SECONDS + 0.05):
            raise RenderError(
                f"The voiced video runs {total_est:.1f}s; it must be {config.MIN_SECONDS:.0f}-{config.MAX_SECONDS:.0f}s. "
                + ("Shorten the script." if total_est > config.MAX_SECONDS else "Add a sentence or two.")
            )

        # 1b. caption timing: Faster Whisper when available (or asked for), else the estimate
        cap_mode = proj.get("style", {}).get("captions") or "auto"
        words = nar.words
        if cap_mode == "whisper" or (cap_mode == "auto" and whisper_align.available()):
            if not whisper_align.available():
                raise RenderError("Faster Whisper is not installed. Run install.bat or pick estimated caption timing.")
            progress(0.12, "Timing captions with Faster Whisper")
            aligned, matched = whisper_align.align(nar.wav, nar.words, log=log)
            if matched >= 0.6:
                words = aligned
            else:
                log(f"whisper matched only {matched:.0%}; keeping the estimated timing")
    if mode == "ugc":
        pass
    elif mode == "photo_avatar":
        # 2 (photo avatar). The local avatar model lip-syncs the photo to the narration; the
        # result is then cut exactly like UGC footage (layouts, punch-ins, captions).
        u = _photo_avatar(proj, beats, nar, words, settings, project_dir, build, end_card_on, log, progress, out_fps)
        avatar_videos = {"_avatar": u.video}
        if u.total < config.MIN_SECONDS - 0.05:
            raise RenderError(f"With the pauses trimmed the video runs {u.total:.1f}s. Add a sentence or two.")
        words = u.words
        total, end_card_start = u.total, u.end_card_start
        run_files, run_trans, run_durs = [u.video], [None], [total]
        shots = u.shots
        caption_beats = beats
        nar = tts.Narration(wav=str(u.voice), duration=u.end_card_start or u.total, speed=nar.speed, voice=nar.voice,
                            engine=nar.engine, beats=u.beat_times, words=u.words)
    elif mode == "animated":
        # 2-4 (animated). Motion Canvas draws the picture; FFmpeg adds the rest below.
        st = animate.status()
        if not st["ready"]:
            raise RenderError("Animated templates need Node.js and the Motion Canvas packages. Run install.bat.")
        spans = timeline.beat_spans(nar.beats, nar.duration)
        total = round((nar.duration + extra) * out_fps) / out_fps
        end_card_start = nar.duration if end_card_on else None
        job = animate.build_job(proj, beats, spans, nar.beats, words, total, end_card_start, project_dir, build, log,
                                fps=out_fps, voice_wav=Path(nar.wav))
        progress(0.2, f"Animating ({animate.TEMPLATES.get(proj.get('template'), {}).get('name', 'template')})")
        motion_out = build / "motion.mp4"
        animate.render_job(job, motion_out, log=log, progress=lambda f: progress(0.2 + 0.6 * f, "Animating"))
        run_files = [motion_out]
        run_trans = [None]
        run_durs = [total]
        by_id = {a["id"]: a for a in assets}
        shots = []
        for b, (s0, s1) in zip(beats, spans):
            a = by_id.get((b.get("visual") or {}).get("asset"))
            if a and a.get("genuine") and a.get("rights_confirmed"):
                shots.append({"start": s0, "duration": s1 - s0, "genuine": True, "ai_presenter": False})
        caption_beats = [{**b, "overlay": ""} for b in beats]  # the template draws its own headlines
    else:
        avatar_videos, shots, total, end_card_start, run_files, run_trans, run_durs = _demo_video(
            proj, beats, nar, words, assets, settings, end_card_on, project_dir, build, seg_dir, log, progress)
        if avatar_videos:
            assets = [{**a, "ai_generated": True} if a.get("role") == "presenter" else a for a in assets]
        caption_beats = beats

    # 5. captions
    progress(0.82, "Captions")
    end_card = (facts.get("end_card") or {}) if end_card_on else None
    ass = captions.build_ass(
        words, shots, caption_beats, nar.beats, total,
        highlight=_highlight(proj.get("style", {}).get("caption_highlight") or settings.get("caption_highlight")),
        disclaimer=facts.get("disclaimer") or compliance.AUTO_DISCLAIMER,
        end_card=end_card, end_card_start=end_card_start,
        ai_voice_label="AI voice" if proj.get("style", {}).get("ai_voice_label") else "",
        show_captions=not (mode == "animated" and animate.TEMPLATES.get(proj.get("template"), {}).get("own_captions")),
        caption_font=proj.get("style", {}).get("caption_font"),
        headline_font=proj.get("style", {}).get("headline_font") or proj.get("style", {}).get("caption_font"),
    )
    (build / "captions.ass").write_text(ass, encoding="utf-8")

    # 6. final: transitions + captions + mixed audio
    progress(0.84, "Mastering the voice")
    voice_wav = audio.master_voice(Path(nar.wav), build / "voice_master.wav", log=log, denoise=mode == "ugc")
    progress(0.87, "Final mix and encode")
    inputs: list[str] = []
    for rf in run_files:
        inputs += ["-i", str(rf.relative_to(build))]
    inputs += ["-i", str(voice_wav.relative_to(build))]
    style = proj.get("style", {})
    tpl = animate.TEMPLATES.get(proj.get("template"), {}) if mode == "animated" else {}
    music = next((a for a in assets if a.get("role") == "music" and a.get("rights_confirmed")), None)
    use_music = False
    music_db = float(proj.get("music", {}).get("volume_db", -20))
    if music and proj.get("music", {}).get("enabled", True):
        inputs += ["-stream_loop", "-1", "-i", str(project_dir / music["file"])]
        use_music = True
    elif style.get("music_bed", True):
        # an original bed synthesized for this video (nothing to license)
        bed = sound.write_wav(build / "music_bed.wav", sound.music_bed(total + 0.5))
        inputs += ["-i", str(bed.relative_to(build))]
        use_music = True
        music_db = float(proj.get("music", {}).get("bed_db", -6))
    use_sfx = bool(style.get("sfx", True))
    if use_sfx:
        spans = timeline.beat_spans(nar.beats, nar.duration)
        events = sound.plan_events(beats, spans, words, end_card_start, proj.get("template") if mode == "animated" else mode)
        sfx_wav = sound.write_wav(build / "sfx.wav", sound.sfx_track(events, total + 0.1))
        inputs += ["-i", str(sfx_wav.relative_to(build))]
    parts = [f"[{i}:v]settb=AVTB,fps={out_fps},format=yuv420p[r{i}]" for i in range(len(run_files))]
    cur = "r0"
    offset = run_durs[0]
    for i in range(1, len(run_files)):
        tr = run_trans[i]
        parts.append(f"[{cur}][r{i}]xfade=transition={tr['type']}:duration={tr['duration']}:offset={offset:.4f}[x{i}]")
        cur = f"x{i}"
        offset += run_durs[i]
    # (no film grain: per-frame noise made files ~30x larger and platforms recompress it into mush)
    parts.append(f"[{cur}]format=yuv420p,ass=captions.ass:fontsdir=fonts,format=yuv420p[vout]")
    parts.append(_audio_graph(len(run_files), use_music, total, music_db, has_sfx=use_sfx))
    out_dir = project_dir / "out"
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = project.slug(proj.get("name") or "insidir") + f"-{stamp}.mp4"
    out_path = out_dir / name
    disclosure = disclosure_text(proj, nar, settings, avatar_videos)
    media.run([
        *inputs, "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
        "-t", f"{total:.3f}", "-r", str(out_fps),
        "-c:v", "libx264", "-preset", "slow", "-crf", "16" if high else "19",
        *(["-tune", "animation"] if mode == "animated" else []),
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-g", str(out_fps * 2),
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart",
        "-metadata", f"title={proj.get('script', {}).get('title') or proj.get('name', '')}",
        "-metadata", f"comment={disclosure['short']}",
        str(out_path),
    ], cwd=build, log=log)

    info = media.probe(out_path)
    side = out_path.with_suffix(".json")
    report = {
        "file": out_path.name,
        "duration": info["duration"],
        "width": info["width"],
        "height": info["height"],
        "voice": nar.voice,
        "speed": nar.speed,
        "engine": nar.engine,
        "mode": mode,
        "template": proj.get("template") if mode == "animated" else None,
        "jump_cuts": len(u.segments) if mode in ("ugc", "photo_avatar") else None,
        "caption_timing": "whisper" if (mode == "ugc" or words is not tts_words) else "estimated",
        "fps": out_fps,
        "shots": len(shots),
        "facts_used": script.get("facts_used", []),
        "facts": [f for f in facts.get("facts", []) if f["id"] in (script.get("facts_used") or [])],
        "assets": [{"label": a.get("label"), "file": a.get("file"), "genuine": a.get("genuine"),
                    "ai_generated": a.get("ai_generated")} for a in assets],
        "disclosure": disclosure,
        "warnings": [i for i in issues if i["level"] == "warning"],
        "render_seconds": round(time.time() - t0, 1),
    }
    side.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_path.with_suffix(".txt").write_text(disclosure["post"] + "\n", encoding="utf-8")
    try:  # poster frame for the studio's render list
        media.thumbnail(out_path, out_path.with_suffix(".jpg"), t=min(9.0, total * 0.4), width=540)
    except media.FFmpegError:
        pass
    progress(1.0, "Done")
    log(f"wrote {out_path} ({info['duration']:.1f}s, {info['width']}x{info['height']}) in {report['render_seconds']}s")
    return report


def _photo_avatar(proj, beats, nar, words, settings, project_dir, build, end_card_on, log, progress, fps=FPS):
    saved = (proj.get("avatar") or {}).get("id")
    if saved:
        # a saved avatar from the library (imported once, reused in every project)
        try:
            av = avatars.load(saved)
        except (OSError, ValueError):
            raise RenderError("The chosen avatar no longer exists. Pick another on the Brief tab.")
        why = avatars.usable_photo(av)
        if why:
            raise RenderError(" ".join(why))
        photo_file = avatars.photo_path(av)
        photo = {"focus": av.get("focus")}
    else:
        photo = next((a for a in proj.get("assets", []) if a.get("role") == "presenter" and a["type"] == "image"
                      and a.get("rights_confirmed")), None)
        if not photo:
            raise RenderError("Pick a saved avatar on the Brief tab, or upload a presenter photo on the Footage tab "
                              "(set it to Presenter and confirm the rights).")
        photo_file = project_dir / photo["file"]
    st = avatar.status(settings)
    if not st["usable"]:
        raise RenderError("The AI photo avatar needs the local talking-avatar model: " + " ".join(st["reasons"]))
    progress(0.15, "Animating the presenter (local avatar model)")
    raw = avatar.generate(settings, photo_file, Path(nar.wav), build / "avatar" / "presenter_raw.mp4", log)
    # use the narration itself as the clip's audio so the cut voice is exactly the mastered TTS
    clip = build / "avatar" / "presenter.mp4"
    media.run(["-i", str(raw), "-i", str(nar.wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
               "-b:a", "256k", "-shortest", str(clip)], log=log)
    info = media.probe(clip)
    cre = {"id": "_avatar", "file": str(clip), "type": "video", "role": "creator", "label": "AI presenter",
           "width": info["width"], "height": info["height"], "duration": info["duration"],
           "ai_generated": True, "rights_confirmed": True, "focus": photo.get("focus") or [0.5, 0.4]}
    p2 = {**proj, "assets": [*proj.get("assets", []), cre]}
    times = {bt["id"]: bt for bt in nar.beats}
    ubeats = []
    for b in beats:
        bt = times.get(b["id"])
        if not bt:
            continue
        ws = [{"text": w.text, "start": w.start, "end": w.end} for w in words if w.beat == b["id"]]
        vis = b.get("visual") or {}
        ubeats.append({**b, "words": ws, "source": {"asset": "_avatar", "start": bt["speech_start"], "end": bt["speech_end"]},
                       "visual": {**vis, "layout": vis.get("layout") or "face"}})
    return ugc.build(p2, ubeats, project_dir, build, fps, end_card_on, timeline.END_CARD_SECONDS, log, progress,
                     gap=None)


def disclosure_text(proj: dict, nar, settings: dict, avatar_videos: dict) -> dict:
    ai_presenter = bool(avatar_videos) or any(
        a.get("role") in ("presenter", "creator") and a.get("ai_generated") for a in proj.get("assets", []))
    ugc_real = (proj.get("mode") == "ugc") and nar.engine == "recorded" and not ai_presenter
    bits = [] if ugc_real else [f"Narration is an AI voice (Kokoro, voice {nar.voice})."]
    if ugc_real:
        bits.append("If you were paid, got free access or earn a referral fee, add #ad and say so in the video.")
    if ai_presenter:
        bits.append("The on-screen presenter is AI-generated.")
    if any(a.get("genuine") for a in proj.get("assets", [])):
        bits.append("Product footage is a real screen recording of Insidir.")
    bits.append("Research tool. Not investment advice.")
    short = " ".join(bits)
    post = (
        "Suggested post disclosure (paste into your caption"
        + ("):\n\n" if ugc_real else ", and switch on the platform's AI-generated content label):\n\n")
        + short
    )
    return {"short": short, "post": post, "ai_voice": not ugc_real, "ai_presenter": ai_presenter}
