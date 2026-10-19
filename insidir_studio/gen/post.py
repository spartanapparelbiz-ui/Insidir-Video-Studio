"""After generation: join, stabilise, de-flicker, interpolate, upscale, enhance faces, encode.

Each stage is a real algorithm; the best tool found on this PC is used and named in the log:
  frame interpolation  RIFE (rife-ncnn-vulkan, MIT) if installed, else FFmpeg's motion-compensated
                       interpolation (minterpolate, bidirectional motion estimation + OBMC)
  upscaling            Real-ESRGAN (realesrgan-ncnn-vulkan, BSD-3) if installed, else Lanczos + light
                       unsharp (classic resampling: sharper, but adds no new detail)
  stabilisation        FFmpeg vid.stab two-pass if available, else deshake
  de-flicker           FFmpeg deflicker (temporal brightness smoothing)
  faces                GFPGAN if its Python package and weights are installed (check its licence)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from .. import config, media

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def write_video(frames: np.ndarray, fps: int, path: Path, crf: int = 10) -> Path:
    """Frames (N, H, W, 3 uint8) -> near-lossless H.264 intermediate."""
    n, h, w, _ = frames.shape
    cmd = [config.ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_NO_WINDOW)
    _, err = proc.communicate(np.ascontiguousarray(frames).tobytes())
    if proc.returncode != 0:
        raise media.FFmpegError(err.decode(errors="replace")[-800:])
    return path


def crossfade_join(a: list, b: list, k: int) -> list:
    """Join chunk b onto a, where b's first k frames re-create a's last k: blend them, no seam."""
    k = max(0, min(k, len(a), len(b)))
    if not k:
        return list(a) + list(b)
    out = list(a[:-k])
    for i in range(k):
        t = (i + 1) / (k + 1)
        out.append((np.asarray(a[len(a) - k + i], np.float32) * (1 - t) + np.asarray(b[i], np.float32) * t)
                   .round().astype(np.uint8))
    return out + list(b[k:])


def tools() -> dict:
    """Which optional accelerated tools are installed."""
    filters = ""
    try:
        filters = subprocess.run([config.ffmpeg(), "-hide_banner", "-filters"], capture_output=True, text=True,
                                 creationflags=_NO_WINDOW).stdout
    except (OSError, media.FFmpegError):
        pass
    gfpgan = False
    try:
        import gfpgan as _g  # noqa: F401
        gfpgan = True
    except ImportError:
        pass
    return {"rife": shutil.which("rife-ncnn-vulkan"), "realesrgan": shutil.which("realesrgan-ncnn-vulkan"),
            "vidstab": "vidstabdetect" in filters, "minterpolate": "minterpolate" in filters, "gfpgan": gfpgan}


def _fps(path: Path) -> float:
    import cv2
    cap = cv2.VideoCapture(str(path))
    f = cap.get(cv2.CAP_PROP_FPS) or 24
    cap.release()
    return f


def _run(args: list[str], log=None):
    media.run(args, log=log)


def interpolate(src: Path, out: Path, fps_in: int, fps_out: int, log=None) -> Path:
    t = tools()
    if t["rife"] and fps_out % fps_in == 0:
        # RIFE on frames: extract, interpolate x(fps_out/fps_in), re-encode
        work = out.parent / "rife"
        shutil.rmtree(work, ignore_errors=True)
        (work / "in").mkdir(parents=True)
        (work / "out").mkdir()
        _run(["-i", str(src), str(work / "in" / "%06d.png")], log)
        n_in = len(list((work / "in").glob("*.png")))
        subprocess.run([t["rife"], "-i", str(work / "in"), "-o", str(work / "out"),
                        "-n", str(n_in * (fps_out // fps_in))], check=True, creationflags=_NO_WINDOW)
        _run(["-framerate", str(fps_out), "-i", str(work / "out" / "%08d.png"), "-c:v", "libx264", "-crf", "10",
              "-pix_fmt", "yuv420p", str(out)], log)
        if log:
            log(f"interpolated {fps_in}->{fps_out} fps with RIFE")
        return out
    _run(["-i", str(src), "-vf", f"minterpolate=fps={fps_out}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
          "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(out)], log)
    if log:
        log(f"interpolated {fps_in}->{fps_out} fps with motion-compensated interpolation (FFmpeg)")
    return out


def upscale(src: Path, out: Path, factor: int, log=None, ai: bool = True) -> Path:
    """ai=False forces the fast Lanczos path (seconds instead of minutes on a CPU)."""
    t = tools()
    info = media.probe(src)
    if ai and t["realesrgan"]:
        work = out.parent / "esrgan"
        shutil.rmtree(work, ignore_errors=True)
        (work / "in").mkdir(parents=True)
        (work / "out").mkdir()
        _run(["-i", str(src), str(work / "in" / "%06d.png")], log)
        # the photographic model is 4x only: run it at 4x, then resample to the requested factor
        subprocess.run([t["realesrgan"], "-i", str(work / "in"), "-o", str(work / "out"), "-s", "4",
                        "-n", "realesrgan-x4plus"], check=True, creationflags=_NO_WINDOW)
        fps = _fps(src)
        w, h = info["width"] * factor, info["height"] * factor
        _run(["-framerate", str(fps), "-i", str(work / "out" / "%06d.png"), "-vf", f"scale={w}:{h}:flags=lanczos",
              "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(out)], log)
        if log:
            log(f"upscaled x{factor} with Real-ESRGAN")
        return out
    if ai:
        try:
            import torch  # noqa: F401  (Real-ESRGAN in PyTorch: GPU if present, else CPU)
            from . import upscale as esrgan
            return esrgan.upscale_video(src, out, factor, log=log)
        except ImportError:
            pass
        except Exception as e:  # weights couldn't download, out of memory, ...: still deliver a video
            if log:
                log(f"AI upscaling failed ({e}); using Lanczos instead")
    w, h = info["width"] * factor, info["height"] * factor
    _run(["-i", str(src), "-vf", f"scale={w}:{h}:flags=lanczos,unsharp=5:5:0.5", "-c:v", "libx264", "-crf", "12",
          "-pix_fmt", "yuv420p", str(out)], log)
    if log:
        log(f"upscaled x{factor} with Lanczos (AI upscaling needs PyTorch)")
    return out


def stabilize(src: Path, out: Path, log=None) -> Path:
    if tools()["vidstab"]:
        trf = out.parent / "transforms.trf"
        _run(["-i", str(src), "-vf", f"vidstabdetect=shakiness=5:accuracy=15:result={trf.as_posix()}", "-f", "null", "-"], log)
        _run(["-i", str(src), "-vf", f"vidstabtransform=input={trf.as_posix()}:smoothing=20:zoom=1,unsharp=5:5:0.3",
              "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(out)], log)
    else:
        _run(["-i", str(src), "-vf", "deshake", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(out)], log)
    return out


def film_finish(src: Path, out: Path, log=None) -> Path:
    """The last 5%: a gentle sharpen to crisp edges and a whisper of moving film grain, which
    breaks up the waxy smoothness of generated (and upscaled) surfaces so skin, fabric and
    foliage read as photographed."""
    _run(["-i", str(src), "-vf", "unsharp=5:5:0.35:3:3:0.0,noise=alls=3:allf=t+u", "-c:v", "libx264", "-crf", "10",
          "-pix_fmt", "yuv420p", str(out)], log)
    if log:
        log("film finish: fine sharpen + subtle grain")
    return out


def deflicker(src: Path, out: Path, log=None) -> Path:
    _run(["-i", str(src), "-vf", "deflicker=mode=pm:size=5", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
          str(out)], log)
    return out


def enhance_faces(src: Path, out: Path, log=None) -> Path:
    """GFPGAN face restoration per frame (only when installed; its weights have their own licence)."""
    import cv2
    from gfpgan import GFPGANer
    model = config.studio_home() / "models" / "GFPGANv1.4.pth"
    if not model.exists():
        raise RuntimeError(f"Put GFPGANv1.4.pth in {model.parent} to enhance faces.")
    restorer = GFPGANer(model_path=str(model), upscale=1, arch="clean", channel_multiplier=2)
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        _, _, restored = restorer.enhance(f, has_aligned=False, only_center_face=False, paste_back=True)
        frames.append(cv2.cvtColor(restored, cv2.COLOR_BGR2RGB))
    cap.release()
    write_video(np.asarray(frames), int(round(fps)), out)
    if log:
        log("faces enhanced with GFPGAN")
    return out


CODECS = {
    "h264": ["-c:v", "libx264", "-preset", "slow", "-pix_fmt", "yuv420p"],
    "h265": ["-c:v", "libx265", "-preset", "medium", "-pix_fmt", "yuv420p", "-tag:v", "hvc1"],
    "prores": ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
    "webm": ["-c:v", "libvpx-vp9", "-b:v", "0", "-pix_fmt", "yuv420p"],
}
QUALITY_CRF = {"max": 12, "high": 16, "balanced": 20, "small": 26}


def finish(src: Path, out: Path, fps: int, opts: dict, log=None, progress=None) -> Path:
    """Apply the requested improvements in a sensible order, then encode the final file.

    opts: stabilize, deflicker, faces, upscale (1|2|4), upscaler (ai|fast), film_finish, fps (target), codec,
    quality, audio (path)."""
    progress = progress or (lambda f, msg="": None)
    work = out.parent
    work.mkdir(parents=True, exist_ok=True)
    cur, cur_fps = src, fps
    steps = [k for k in ("stabilize", "deflicker", "faces") if opts.get(k)]
    # upscale before interpolating: the AI upscaler then runs on fewer frames
    if int(opts.get("upscale") or 1) > 1:
        steps.append("upscale")
    if opts.get("fps") and int(opts["fps"]) > fps:
        steps.append("interpolate")
    if opts.get("film_finish"):
        steps.append("film_finish")
    for i, step in enumerate(steps):
        progress(i / max(1, len(steps)), step.capitalize())
        nxt = work / f"post_{i}_{step}.mp4"
        if step == "stabilize":
            cur = stabilize(cur, nxt, log)
        elif step == "deflicker":
            cur = deflicker(cur, nxt, log)
        elif step == "faces":
            cur = enhance_faces(cur, nxt, log)
        elif step == "interpolate":
            cur_fps = int(opts["fps"])
            cur = interpolate(cur, nxt, fps, cur_fps, log)
        elif step == "upscale":
            cur = upscale(cur, nxt, int(opts["upscale"]), log, ai=opts.get("upscaler", "ai") != "fast")
        elif step == "film_finish":
            cur = film_finish(cur, nxt, log)
    if opts.get("sound") and not opts.get("audio"):
        # synthesised ambience + effects timed to the on-screen motion
        from . import audio
        progress(0.95, "Sound design")
        opts = {**opts, "audio": str(audio.soundtrack(cur, opts.get("prompt", ""), work / "soundtrack.wav",
                                                      opts.get("ambience", "")))}
    codec = opts.get("codec") or "h264"
    ext = {"prores": ".mov", "webm": ".webm"}.get(codec, ".mp4")
    out = out.with_suffix(ext)
    crf = QUALITY_CRF.get(opts.get("quality") or "high", 16)
    args = ["-i", str(cur)]
    if opts.get("audio"):
        args += ["-i", str(opts["audio"]), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-shortest"]
    args += CODECS[codec] + (["-crf", str(crf)] if codec in ("h264", "h265", "webm") else [])
    if codec in ("h264", "h265"):
        args += ["-movflags", "+faststart"]
    _run(args + ["-r", str(cur_fps), str(out)], log)
    progress(1.0, "Encoded")
    return out
