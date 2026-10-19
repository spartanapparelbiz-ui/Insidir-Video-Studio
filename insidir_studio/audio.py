"""Voice mastering: makes the Kokoro narration sound like a produced voice-over.

Chain (all FFmpeg, all local):
  soxr resample to 48 kHz -> rumble cut -> de-mud -> warmth -> presence -> de-ess ->
  gentle compression -> limiter, then a two-pass EBU R128 loudness match to -14 LUFS
  (the level TikTok, Reels and Shorts play at) with -1 dBTP headroom.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import config, media

TARGET_LUFS = -14.0
TARGET_TP = -1.0
TARGET_LRA = 7.0

VOICE_CHAIN = ",".join([
    "aresample=48000:resampler=soxr:precision=28",
    "highpass=f=75:poles=2",
    "equalizer=f=280:t=q:w=1.1:g=-2.5",    # less boxy/muddy
    "equalizer=f=140:t=q:w=0.9:g=1.5",     # warmth / chest
    "equalizer=f=3200:t=q:w=1.3:g=2.2",    # presence and clarity
    "highshelf=f=7500:g=1.5",              # a little air
    "deesser=i=0.35:m=0.5:f=0.5",
    "acompressor=threshold=0.09:ratio=2.6:attack=6:release=140:knee=4:makeup=1.5",
    "alimiter=limit=0.94:attack=3:release=40:level=disabled",
])


def _measure(src: Path, chain: str) -> dict:
    import subprocess
    import sys

    cmd = [config.ffmpeg(), "-hide_banner", "-nostats", "-i", str(src), "-af",
           f"{chain},loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
           "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=0x08000000 if sys.platform == "win32" else 0)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if proc.returncode != 0 or not m:
        raise media.FFmpegError("Loudness measurement failed: " + proc.stderr[-500:])
    return json.loads(m.group(0))


def master_voice(src: Path, out: Path, log=None, denoise: bool = False) -> Path:
    """Write a mastered 48 kHz stereo 24-bit WAV of the narration.

    denoise: for real microphone recordings (UGC), remove steady room/fan noise first."""
    chain = ("afftdn=nf=-28:tn=1," if denoise else "") + VOICE_CHAIN
    meas = _measure(src, chain)
    norm = (f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}"
            f":measured_I={meas['input_i']}:measured_TP={meas['input_tp']}"
            f":measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}"
            f":offset={meas['target_offset']}:linear=true")
    if log:
        log(f"voice mastering: {float(meas['input_i']):.1f} LUFS -> {TARGET_LUFS:.0f} LUFS")
    media.run(["-i", str(src), "-af", f"{chain},{norm},aresample=48000:resampler=soxr",
               "-ac", "2", "-c:a", "pcm_s24le", str(out)], log=log)
    return out
