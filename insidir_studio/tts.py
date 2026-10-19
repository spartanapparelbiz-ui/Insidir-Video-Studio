"""Local narration with Kokoro-82M (Apache-2.0) through kokoro-onnx, on CPU or GPU.

Each sentence is synthesized on its own so sentence and beat boundaries are exact.
Word times inside a sentence are aligned from the audio: speech onset/offset and
pauses found in the waveform anchor commas and clause breaks, and the words in
between are spread by phoneme length. That is accurate to a few frames, which is
what 1-3 word animated captions need.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from . import config

SENTENCE_PAUSE = 0.20
BEAT_PAUSE = 0.30
LEAD_IN = 0.12

# Best-sounding Kokoro voices first (Kokoro's own quality grades in brackets). The
# "studio" entries blend two voice styles, which smooths out each voice's quirks.
# Every English Kokoro voice, best first within each group. Grades are Kokoro's own
# published quality grades (A best). Blends mix voice styles for a fuller, more natural read.
VOICES = {
    # men
    "studio_male": "Studio Male (US): Michael + Fenrir blend [recommended]",
    "studio_male_deep": "Studio Male Deep (US): Michael + Puck blend, lower and calmer",
    "studio_male_narrator": "Studio Narrator (US): Fenrir + Michael + Echo, documentary",
    "studio_male_uk": "Studio Male (UK): George + Fable blend",
    "am_michael": "Michael (US, steady) [C+]",
    "am_fenrir": "Fenrir (US, clear) [C+]",
    "am_puck": "Puck (US, lively) [C+]",
    "am_echo": "Echo (US, airy) [D]",
    "am_eric": "Eric (US, upbeat) [D]",
    "am_liam": "Liam (US, young) [D]",
    "am_onyx": "Onyx (US, deep) [D]",
    "bm_george": "George (UK) [C]",
    "bm_fable": "Fable (UK, storyteller) [C]",
    "bm_lewis": "Lewis (UK, deep) [D+]",
    "bm_daniel": "Daniel (UK, crisp) [D]",
    # women
    "studio_warm": "Studio Warm (US): Heart + Bella blend [recommended]",
    "studio_bright": "Studio Bright (US): Bella + Nicole blend",
    "studio_calm": "Studio Calm (US): Heart + Sarah blend, measured",
    "studio_female_uk": "Studio Female (UK): Emma + Isabella blend",
    "af_heart": "Heart (US, warm) [A]",
    "af_bella": "Bella (US, bright) [A-]",
    "af_nicole": "Nicole (US, soft, close-mic) [B-]",
    "af_aoede": "Aoede (US, smooth) [C+]",
    "af_kore": "Kore (US, confident) [C+]",
    "af_sarah": "Sarah (US, calm) [C+]",
    "af_nova": "Nova (US, crisp) [C]",
    "af_alloy": "Alloy (US, neutral) [C]",
    "af_sky": "Sky (US, light) [C-]",
    "af_jessica": "Jessica (US, casual) [D]",
    "af_river": "River (US, relaxed) [D]",
    "bf_emma": "Emma (UK) [B-]",
    "bf_isabella": "Isabella (UK, polished) [C]",
    "bf_alice": "Alice (UK, clear) [D]",
    "bf_lily": "Lily (UK, soft) [D]",
}
BLENDS = {
    "studio_male": [("am_michael", 0.55), ("am_fenrir", 0.45)],
    "studio_male_deep": [("am_michael", 0.5), ("am_puck", 0.5)],
    "studio_male_narrator": [("am_fenrir", 0.45), ("am_michael", 0.4), ("am_echo", 0.15)],
    "studio_male_uk": [("bm_george", 0.6), ("bm_fable", 0.4)],
    "studio_warm": [("af_heart", 0.65), ("af_bella", 0.35)],
    "studio_bright": [("af_bella", 0.6), ("af_nicole", 0.4)],
    "studio_calm": [("af_heart", 0.55), ("af_sarah", 0.45)],
    "studio_female_uk": [("bf_emma", 0.6), ("bf_isabella", 0.4)],
}


def gender_of(voice: str) -> str:
    """'man' or 'woman' for every voice in VOICES (a blend takes its first voice's)."""
    base = BLENDS[voice][0][0] if voice in BLENDS else voice
    return "man" if base[1:2] == "m" else "woman"


# the best voice for each choice in the studio's Man / Woman switch
DEFAULT_BY_GENDER = {"man": "studio_male", "woman": "studio_warm"}
DEFAULT_VOICE = DEFAULT_BY_GENDER["man"]

# How words are *said* (captions still show the real spelling). Word counts must not
# change, so every replacement is one word for one word.
PRONOUNCE = [
    (re.compile(r"\binsidir\b", re.I), "insider"),
    (re.compile(r"\bEDGAR\b"), "Edgar"),
]


def _keep_case(src: str, rep: str) -> str:
    return rep[0].upper() + rep[1:] if src[:1].isupper() else rep


def speakable(text: str) -> str:
    for pat, rep in PRONOUNCE:
        text = pat.sub(lambda m: _keep_case(m.group(0), rep), text)
    return text


@dataclass
class Word:
    text: str
    start: float
    end: float
    beat: str


@dataclass
class Narration:
    wav: str
    duration: float
    speed: float
    voice: str
    engine: str
    beats: list[dict] = field(default_factory=list)  # {id, start, speech_start, speech_end, end}
    words: list[Word] = field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        return d


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9\"'$])", text)
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------- engines

class KokoroOnnxEngine:
    name = "kokoro"
    sample_rate = 24000
    _lock = threading.Lock()
    _cache: dict = {}

    def __init__(self, model_path: Path, voices_path: Path):
        from kokoro_onnx import Kokoro  # imported lazily so the UI starts without it

        key = (str(model_path), str(voices_path))
        with self._lock:
            if key not in self._cache:
                self._cache[key] = Kokoro(str(model_path), str(voices_path))
        self.kokoro = self._cache[key]
        self.model_id = Path(model_path).name

    def voices(self) -> list[str]:
        return sorted(self.kokoro.get_voices())

    def _style(self, voice: str):
        if voice in BLENDS:
            return sum(w * self.kokoro.get_voice_style(v) for v, w in BLENDS[voice])
        return voice

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        with self._lock:
            audio, sr = self.kokoro.create(speakable(text), voice=self._style(voice), speed=float(speed),
                                           lang=_lang_for(voice), trim=True)
        if sr != self.sample_rate:
            raise RuntimeError(f"Unexpected Kokoro sample rate {sr}")
        return np.asarray(audio, dtype=np.float32)

    def weight(self, word: str, voice: str) -> float:
        clean = re.sub(r"[^\w$%'-]", "", word)
        if not clean:
            return 0.5
        try:
            with self._lock:
                ph = self.kokoro.tokenizer.phonemize(speakable(clean), _lang_for(voice))
            n = len(re.sub(r"\s", "", ph))
            return max(1.0, float(n))
        except Exception:
            return _letter_weight(clean)


class ToneEngine:
    """Stand-in voice for tests and for checking edits before Kokoro is installed.

    It produces a soft hum per word, not speech, and is labelled as such in the UI.
    """

    name = "test-tone"
    sample_rate = 24000
    model_id = "test-tone"

    def voices(self) -> list[str]:
        return list(VOICES)

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        sr = self.sample_rate
        chunks = []
        rng = np.random.default_rng(len(text))
        for w in text.split():
            dur = max(0.12, 0.062 * len(re.sub(r"\W", "", w)) + 0.05) / speed
            t = np.arange(int(dur * sr)) / sr
            env = np.sin(np.pi * t / dur) ** 0.6
            tone = 0.25 * np.sin(2 * np.pi * (150 + 40 * rng.random()) * t) * env
            chunks.append(tone.astype(np.float32))
            pause = 0.18 if w[-1] in ",;:" else 0.05
            chunks.append(np.zeros(int(pause * sr / speed), dtype=np.float32))
        return np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)

    def weight(self, word: str, voice: str) -> float:
        return _letter_weight(word)


def _letter_weight(word: str) -> float:
    return max(1.0, len(re.sub(r"[^\w]", "", word)) * 0.9)


def _lang_for(voice: str) -> str:
    return "en-gb" if voice.startswith("b") else "en-us"


def valid_voice(voice: str | None) -> str:
    return voice if voice in VOICES else DEFAULT_VOICE


def find_model_files() -> tuple[Path, Path] | None:
    d = config.models_dir()
    voices = d / "voices-v1.0.bin"
    for name in ("kokoro-v1.0.onnx", "kokoro-v1.0.fp16.onnx", "kokoro-v1.0.int8.onnx"):
        if (d / name).exists() and voices.exists():
            return d / name, voices
    return None


def kokoro_status() -> dict:
    try:
        import kokoro_onnx  # noqa: F401
        installed = True
    except Exception:
        installed = False
    files = find_model_files()
    return {
        "installed": installed,
        "model": str(files[0]) if files else None,
        "ready": bool(installed and files),
        "models_dir": str(config.models_dir()),
    }


def get_engine(name: str | None = None):
    if name == "test-tone":
        return ToneEngine()
    files = find_model_files()
    if files is None:
        raise RuntimeError(
            f"Kokoro model files were not found in {config.models_dir()}. Run install.bat "
            "(or: python -m insidir_studio download-models)."
        )
    return KokoroOnnxEngine(*files)


# ------------------------------------------------------------------- alignment

def _frames_rms(samples: np.ndarray, sr: int, hop: float = 0.01) -> np.ndarray:
    h = max(1, int(sr * hop))
    n = len(samples) // h
    if n == 0:
        return np.zeros(1)
    x = samples[: n * h].reshape(n, h)
    return np.sqrt((x.astype(np.float64) ** 2).mean(axis=1))


def align_words(samples: np.ndarray, sr: int, words: list[str], weights: list[float]) -> list[tuple[float, float]]:
    """Return (start, end) seconds for each word, relative to the clip."""
    if not words:
        return []
    hop = 0.01
    rms = _frames_rms(samples, sr, hop)
    peak = float(np.percentile(rms, 98)) if rms.size else 0.0
    thr = max(peak * 0.07, 1e-4)
    voiced = rms > thr
    idx = np.flatnonzero(voiced)
    total = len(samples) / sr
    if idx.size == 0:
        s0, s1 = 0.0, total
    else:
        s0, s1 = idx[0] * hop, min(total, (idx[-1] + 1) * hop)

    # silent runs of 80 ms or more inside the speech region
    gaps = []
    run_start = None
    for i in range(int(s0 / hop), int(s1 / hop)):
        if i < len(voiced) and not voiced[i]:
            run_start = i if run_start is None else run_start
        else:
            if run_start is not None and (i - run_start) * hop >= 0.08:
                gaps.append((run_start * hop, i * hop))
            run_start = None

    speech = s1 - s0
    cum = np.cumsum([0.0] + list(weights))
    tot_w = cum[-1] or 1.0

    # anchor clause punctuation to the nearest real pause
    anchors = []  # (word boundary index k: words[:k] before, gap)
    used = -1
    for k in range(1, len(words)):
        if words[k - 1][-1:] in ",;:—–-" or words[k - 1].endswith("..."):
            expected = s0 + speech * cum[k] / tot_w
            best, best_d = None, 0.22 * speech
            for gi, g in enumerate(gaps):
                if gi <= used:
                    continue
                d = abs((g[0] + g[1]) / 2 - expected)
                if d < best_d:
                    best, best_d = gi, d
            if best is not None:
                anchors.append((k, gaps[best]))
                used = best

    # spread words between anchors
    times: list[tuple[float, float]] = [(0.0, 0.0)] * len(words)
    bounds = [(0, s0)] + [(k, g) for k, g in anchors] + [(len(words), s1)]
    for (k0, a), (k1, b) in zip(bounds, bounds[1:]):
        t0 = a[1] if isinstance(a, tuple) else a
        t1 = b[0] if isinstance(b, tuple) else b
        seg_w = cum[k1] - cum[k0] or 1.0
        for i in range(k0, k1):
            ws = t0 + (t1 - t0) * (cum[i] - cum[k0]) / seg_w
            we = t0 + (t1 - t0) * (cum[i + 1] - cum[k0]) / seg_w
            times[i] = (round(ws, 3), round(we, 3))
    return times


# ------------------------------------------------------------------ narration

def _cache_dir(build: Path) -> Path:
    d = build / "tts_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _synth_cached(engine, build: Path, text: str, voice: str, speed: float) -> np.ndarray:
    key = hashlib.sha1(json.dumps([engine.model_id, text, voice, round(speed, 3)]).encode()).hexdigest()[:20]
    p = _cache_dir(build) / f"{key}.npy"
    if p.exists():
        return np.load(p)
    audio = engine.synth(text, voice, speed)
    np.save(p, audio)
    return audio


def _write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def synthesize(beats: list[dict], voice: str, speed: float, engine, build: Path, log=None) -> Narration:
    sr = engine.sample_rate
    pieces: list[np.ndarray] = [np.zeros(int(LEAD_IN * sr), dtype=np.float32)]
    t = LEAD_IN
    words: list[Word] = []
    beat_times = []
    for bi, beat in enumerate(beats):
        b_start = t if bi else 0.0
        speech_start = None
        sentences = split_sentences(beat.get("text", ""))
        for si, sent in enumerate(sentences):
            if log:
                log(f"voice: {sent[:70]}")
            audio = _synth_cached(engine, build, sent, voice, speed)
            ws = sent.split()
            weights = [engine.weight(w, voice) for w in ws]
            for w, (a, b) in zip(ws, align_words(audio, sr, ws, weights)):
                words.append(Word(w, round(t + a, 3), round(t + b, 3), beat.get("id", f"b{bi + 1}")))
            if speech_start is None:
                speech_start = t
            pieces.append(audio)
            t += len(audio) / sr
            if si < len(sentences) - 1:
                pieces.append(np.zeros(int(SENTENCE_PAUSE * sr), dtype=np.float32))
                t += SENTENCE_PAUSE
        speech_end = t
        pause = BEAT_PAUSE if bi < len(beats) - 1 else 0.35
        pieces.append(np.zeros(int(pause * sr), dtype=np.float32))
        t += pause
        beat_times.append({
            "id": beat.get("id", f"b{bi + 1}"),
            "start": round(b_start, 3),
            "speech_start": round(speech_start if speech_start is not None else b_start, 3),
            "speech_end": round(speech_end, 3),
            "end": round(t, 3),
        })
    samples = np.concatenate(pieces)
    # gentle peak normalisation; loudness is set in the final mix
    peak = float(np.max(np.abs(samples))) or 1.0
    samples = samples * (0.89 / peak)
    out = build / "narration.wav"
    _write_wav(out, samples, sr)
    return Narration(wav=str(out), duration=round(len(samples) / sr, 3), speed=speed, voice=voice,
                     engine=engine.name, beats=beat_times, words=words)


def fit_narration(beats: list[dict], voice: str, speed: float, engine, build: Path,
                  extra_seconds: float = 0.0, log=None) -> Narration:
    """Synthesize, then adjust speaking rate once (0.92-1.12) to land within 20-35 s.

    Kokoro sounds most natural close to 1.0, so the range is narrow; a script that
    still doesn't fit is reported to the user instead of being rushed."""
    nar = synthesize(beats, voice, speed, engine, build, log)
    total = nar.duration + extra_seconds
    target = None
    if total > config.MAX_SECONDS - 0.3:
        target = config.MAX_SECONDS - 1.0
    elif total < config.MIN_SECONDS + 0.3:
        target = config.MIN_SECONDS + 1.0
    if target is not None:
        speech = max(1.0, nar.duration - LEAD_IN)
        new_speed = speed * speech / max(1.0, target - extra_seconds - LEAD_IN)
        new_speed = float(min(1.12, max(0.92, new_speed)))
        if abs(new_speed - speed) > 0.01:
            if log:
                log(f"narration ran {total:.1f}s; re-voicing at speed {new_speed:.2f}")
            nar = synthesize(beats, voice, new_speed, engine, build, log)
    return nar


def preview(text: str, voice: str, speed: float, out: Path, engine=None) -> Path:
    engine = engine or get_engine()
    audio = engine.synth(text, voice, speed)
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_wav(out, audio, engine.sample_rate)
    return out
