"""Sound design and an original music bed, synthesized on this PC with NumPy.

Everything here is generated from oscillators and noise at render time, so there is
no sample library and nothing to license: the studio owns every sound it makes.

- SFX: whoosh (transitions), hit (hook / big numbers), pop (headline slams),
  tick (caption groups, very quiet), riser (into the end card).
- Music: a dark, minimal ~92 BPM bed (sub bass, soft kick, hats, filtered pad)
  in A minor, four-bar loop, levelled to sit under the voice.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
_rng = np.random.default_rng(7)


def _t(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def _env(n: int, attack: float, release: float, curve: float = 3.0) -> np.ndarray:
    a = max(1, int(attack * SR))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    r = np.linspace(0, 1, n - a) if n > a else np.zeros(0)
    e[a:] = (1 - r) ** curve
    if release:
        pass
    return e


def _lowpass(x: np.ndarray, cutoff: np.ndarray | float) -> np.ndarray:
    """One-pole low-pass with an optional time-varying cutoff (Hz)."""
    cut = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    alpha = 1 - np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # short buffers only (SFX), so a loop is fine
        acc += alpha[i] * (x[i] - acc)
        y[i] = acc
    return y


def _lp_fast(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Fixed-cutoff low-pass via FFT for long buffers (music)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(spec, len(x))


def _hp_fast(x: np.ndarray, cutoff: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / np.sqrt(1 + (cutoff / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(spec, len(x))


# ------------------------------------------------------------------ SFX

def whoosh(dur: float = 0.45) -> np.ndarray:
    n = int(dur * SR)
    noise = _rng.standard_normal(n)
    t = np.linspace(0, 1, n)
    cutoff = 300 + 5200 * np.sin(np.pi * t) ** 1.5
    x = _lowpass(noise, cutoff) - _lowpass(noise, cutoff * 0.25)
    x *= np.sin(np.pi * t) ** 1.8
    return x / (np.max(np.abs(x)) + 1e-9) * 0.8


def hit(dur: float = 0.9) -> np.ndarray:
    t = _t(dur)
    f = 38 + 85 * np.exp(-t * 18)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.2)
    click = _rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.35
    x = np.tanh(1.6 * (body + click))
    return x / np.max(np.abs(x)) * 0.9


def pop(dur: float = 0.12) -> np.ndarray:
    t = _t(dur)
    f = 900 * np.exp(-t * 30) + 260
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38)
    return x / np.max(np.abs(x)) * 0.7


def tick(dur: float = 0.04) -> np.ndarray:
    t = _t(dur)
    x = _rng.standard_normal(len(t)) * np.exp(-t * 220)
    x = x - _lowpass(x, 2500.0)
    return x / (np.max(np.abs(x)) + 1e-9) * 0.5


def riser(dur: float = 1.6) -> np.ndarray:
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    noise = _rng.standard_normal(n)
    x = _lowpass(noise, 400 + 7000 * t ** 2) * t ** 2
    tone = np.sin(2 * np.pi * np.cumsum(220 + 660 * t ** 2) / SR) * 0.25 * t ** 3
    x = x / (np.max(np.abs(x)) + 1e-9) + tone
    x[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return x / np.max(np.abs(x)) * 0.7


SFX = {"whoosh": whoosh, "hit": hit, "pop": pop, "tick": tick, "riser": riser}
LEVEL_DB = {"whoosh": -15, "hit": -11, "pop": -19, "tick": -30, "riser": -17}


def sfx_track(events: list[tuple[float, str]], total: float) -> np.ndarray:
    """Mono SFX stem: events are (time in seconds, kind)."""
    out = np.zeros(int(total * SR) + SR)
    cache: dict[str, np.ndarray] = {}
    for at, kind in events:
        if kind not in SFX:
            continue
        snd = cache.setdefault(kind, SFX[kind]())
        start = int(max(0.0, at) * SR)
        if kind == "riser":
            start = max(0, start - len(snd))  # a riser ends on its time
        end = min(len(out), start + len(snd))
        out[start:end] += snd[: end - start] * 10 ** (LEVEL_DB[kind] / 20)
    return out[: int(total * SR)]


# ------------------------------------------------------------------ music bed

def music_bed(total: float, bpm: float = 92.0) -> np.ndarray:
    """Stereo (n, 2) original bed, about -20 LUFS before ducking."""
    n = int(total * SR) + SR
    beat = 60.0 / bpm
    bar = beat * 4
    # Am - F - C - G (roots and pad triads, Hz)
    roots = [55.0, 43.65, 65.41, 49.0]
    triads = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    t = np.arange(n) / SR
    bass = np.zeros(n)
    pad = np.zeros(n)
    drums = np.zeros(n)
    kick = hit(0.5) * 0.9
    hat = tick(0.05)
    nbars = int(np.ceil(total / bar)) + 1
    for b in range(nbars):
        chord = b % 4
        s0, s1 = int(b * bar * SR), min(n, int((b + 1) * bar * SR))
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        # sub bass with a slow swell, slightly saturated
        env = np.minimum(1, seg / 0.05) * np.exp(-seg * 0.35)
        bass[s0:s1] += np.tanh(1.4 * np.sin(2 * np.pi * roots[chord] * seg)) * env * 0.55
        # pad: detuned saws, filtered later
        for f in triads[chord]:
            for d in (-0.35, 0.35):
                ph = (f + d) * seg
                pad[s0:s1] += (2 * (ph - np.floor(ph + 0.5))) * 0.12
        # drums: kick on 1 and the "and" of 3, hats on eighths
        for k_at in (0.0, beat * 2.5):
            k0 = s0 + int(k_at * SR)
            k1 = min(n, k0 + len(kick))
            if k0 < n:
                drums[k0:k1] += kick[: k1 - k0]
        for e in range(8):
            h0 = s0 + int(e * beat / 2 * SR)
            h1 = min(n, h0 + len(hat))
            if h0 < n:
                drums[h0:h1] += hat[: h1 - h0] * (0.55 if e % 2 else 0.3)
    pad = _lp_fast(pad, 1400.0) * (0.55 + 0.45 * np.sin(2 * np.pi * t / (bar * 2)) ** 2)
    drums = _hp_fast(drums, 35.0)
    mono = bass * 0.9 + drums * 0.55
    left = mono + pad * 0.9
    right = mono + np.roll(pad, int(0.012 * SR)) * 0.9  # a little width
    stereo = np.stack([left, right], axis=1)[: int(total * SR)]
    fade = int(min(1.5, total / 4) * SR)
    stereo[:fade] *= np.linspace(0, 1, fade)[:, None]
    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]
    peak = np.max(np.abs(stereo)) + 1e-9
    return stereo / peak * 0.5


def write_wav(path: Path, data: np.ndarray) -> Path:
    data = np.asarray(data, dtype=np.float64)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def plan_events(beats: list[dict], spans: list[tuple[float, float]], words: list, end_card_start: float | None,
                template: str) -> list[tuple[float, str]]:
    """Where the sound effects go, from the edit itself."""
    ev: list[tuple[float, str]] = []
    if spans:
        ev.append((0.02, "hit"))
    for i, (b, (s0, _)) in enumerate(zip(beats, spans)):
        vis = b.get("visual") or {}
        if i > 0:
            ev.append((max(0.0, s0 - 0.12), "whoosh"))
        if vis.get("emphasis"):
            ev.append((s0 + 0.35, "hit"))
        elif b.get("overlay"):
            ev.append((s0 + 0.1, "pop"))
    if template == "viral":
        last = -1.0
        for w in words:
            if w.start - last > 0.55:  # a soft tick when a new caption group lands
                ev.append((w.start, "tick"))
                last = w.start
    if end_card_start is not None:
        ev.append((end_card_start, "riser"))
        ev.append((end_card_start + 0.02, "hit"))
    return ev
