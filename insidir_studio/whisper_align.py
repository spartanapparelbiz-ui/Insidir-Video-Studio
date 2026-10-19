"""Accurate caption timing with Faster Whisper (MIT, runs locally on CPU).

The script text is already known, so Whisper is only used for *timing*: it
transcribes the narration with word timestamps and those times are matched back to
the script's words. Words Whisper missed are placed between their matched neighbours.
"""

from __future__ import annotations

import difflib
import re
import subprocess
import sys
import threading

import numpy as np

from . import config

MODEL = "base.en"
_lock = threading.Lock()
_model = None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def model_dir():
    d = config.models_dir() / "whisper"
    d.mkdir(parents=True, exist_ok=True)
    return d


def status() -> dict:
    cached = any(model_dir().glob(f"*{MODEL}*"))
    return {"installed": available(), "model": MODEL, "downloaded": cached, "dir": str(model_dir())}


def _load():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel(MODEL, device="cpu", compute_type="int8", download_root=str(model_dir()))
        return _model


def download() -> None:
    _load()


def _norm(w: str) -> str:
    w = w.lower().replace("’", "'")
    w = {"$1": "one", "$39": "thirtynine"}.get(w, w)
    return re.sub(r"[^a-z0-9]", "", w)


def align(wav_path: str, words: list, log=None) -> tuple[list, float]:
    """Return (words with Whisper timing, share of words matched)."""
    model = _load()
    # decode with FFmpeg (16 kHz mono float) so no PyAV version issues can get in the way
    proc = subprocess.run([config.ffmpeg(), "-v", "error", "-i", str(wav_path), "-ac", "1", "-ar", "16000",
                           "-f", "f32le", "-"], capture_output=True,
                          creationflags=0x08000000 if sys.platform == "win32" else 0)
    if proc.returncode != 0:
        raise RuntimeError("Could not decode the narration for Whisper.")
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    segments, _info = model.transcribe(audio, language="en", word_timestamps=True, beam_size=1,
                                       vad_filter=False, condition_on_previous_text=False)
    heard = [(w.word.strip(), float(w.start), float(w.end)) for seg in segments for w in (seg.words or [])]
    if not heard or not words:
        return words, 0.0
    a = [_norm(w.text) for w in words]
    b = [_norm(h[0]) for h in heard]
    times: list[tuple[float, float] | None] = [None] * len(words)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for block in sm.get_matching_blocks():
        for k in range(block.size):
            _, s, e = heard[block.b + k]
            times[block.a + k] = (s, e)
    matched = sum(t is not None for t in times) / len(words)

    # fill gaps by spreading unmatched words between matched neighbours (estimate as fallback)
    out = []
    i = 0
    while i < len(words):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and times[j] is None:
            j += 1
        left = times[i - 1][1] if i > 0 and times[i - 1] else words[i].start
        right = times[j][0] if j < len(words) and times[j] else words[j - 1].end
        if right <= left:
            for k in range(i, j):
                times[k] = (words[k].start, words[k].end)
        else:
            n = j - i
            for k in range(i, j):
                s = left + (right - left) * (k - i) / n
                times[k] = (s, left + (right - left) * (k - i + 1) / n)
        i = j
    for w, t in zip(words, times):
        out.append(type(w)(w.text, round(t[0], 3), round(max(t[1], t[0] + 0.05), 3), w.beat))
    if log:
        log(f"whisper: matched {matched:.0%} of {len(words)} words")
    return out, matched
