"""Sound for generated video, synthesised locally and timed to what happens on screen.

- Events: optical-flow motion energy per frame; sharp rises become whooshes, sudden jumps
  become hits, so sound lands on the visual action.
- Ambience: a bed matched to words in the prompt (rain, wind, city, forest, ocean, fire, crowd,
  room tone), built from filtered noise and modulation, so there is nothing to license.
- Dialogue: Kokoro voices (several speakers) via the film assembler; lip sync for photoreal
  faces uses the talking-avatar step (see Settings).
Open audio-generation models (e.g. MMAudio) can be added as backends later; their weights are
currently released for non-commercial use only, so they are not enabled by default.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .. import sound

SR = 48000
AMBIENCES = {
    "rain": r"\brain|storm|drizzle|downpour|wet street",
    "wind": r"\bwind|desert|mountain|cliff|snow|blizzard|arctic",
    "city": r"\bcity|street|traffic|downtown|new york|tokyo|subway|car\b|cars\b",
    "forest": r"\bforest|woods|jungle|garden|park|meadow|bird",
    "ocean": r"\bocean|sea\b|beach|waves|shore|harbou?r",
    "fire": r"\bfire|campfire|fireplace|burning|flames",
    "crowd": r"\bcrowd|stadium|concert|party|market|cafe|restaurant",
}


def _noise(n: int, rng) -> np.ndarray:
    return rng.standard_normal(n).astype(np.float32)


def _fast_lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    k = max(1, int(SR / max(1.0, cutoff_hz)))
    return np.convolve(x, np.ones(k, np.float32) / k, mode="same")


def ambience(kind: str, seconds: float, seed: int = 0) -> np.ndarray:
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / SR
    if kind == "rain":
        bed = _fast_lowpass(_noise(n, rng), 6000) - _fast_lowpass(_noise(n, rng), 300) * 0.5
        drops = np.zeros(n, np.float32)
        for p in rng.integers(0, max(1, n - 400), int(seconds * 120)):
            drops[p:p + 200] += np.exp(-np.arange(200) / 30) * rng.uniform(0.2, 0.8) * np.sign(rng.standard_normal())
        x = 0.25 * bed + 0.12 * _fast_lowpass(drops, 9000)
    elif kind == "wind":
        x = _fast_lowpass(_noise(n, rng), 500) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * t) * np.sin(2 * np.pi * 0.07 * t + 1))
        x *= 0.8
    elif kind == "city":
        hum = 0.05 * np.sin(2 * np.pi * 55 * t) + 0.03 * np.sin(2 * np.pi * 110 * t)
        x = 0.35 * _fast_lowpass(_noise(n, rng), 900) + hum
    elif kind == "forest":
        x = 0.12 * _fast_lowpass(_noise(n, rng), 1500)
        for s0 in rng.uniform(0, max(0.1, seconds - 0.5), int(seconds * 0.8)):
            i0 = int(s0 * SR)
            d = int(0.18 * SR)
            tt = np.arange(d) / SR
            f = 3500 + 1800 * np.sin(2 * np.pi * 9 * tt)
            chirp = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 14) * 0.08
            x[i0:i0 + d] += chirp[: max(0, min(d, n - i0))]
    elif kind == "ocean":
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t - np.pi / 2)
        x = 0.4 * _fast_lowpass(_noise(n, rng), 1200) * swell ** 1.5
    elif kind == "fire":
        x = 0.15 * _fast_lowpass(_noise(n, rng), 400)
        crackle = (rng.random(n) > 0.9993).astype(np.float32) * rng.uniform(-1, 1, n).astype(np.float32)
        x += 0.5 * _fast_lowpass(crackle, 5000)
    elif kind == "crowd":
        babble = sum(_fast_lowpass(_noise(n, rng), f) * 0.1 for f in (300, 700, 1400))
        x = babble * (0.8 + 0.2 * np.sin(2 * np.pi * 0.3 * t))
    else:   # room tone
        x = 0.06 * _fast_lowpass(_noise(n, rng), 250)
    fade = min(n // 2, int(0.6 * SR))
    if fade:
        x[:fade] *= np.linspace(0, 1, fade)
        x[-fade:] *= np.linspace(1, 0, fade)
    return np.asarray(x, np.float32)


def detect_ambience(prompt_text: str) -> str:
    t = prompt_text.lower()
    for kind, pat in AMBIENCES.items():
        if re.search(pat, t):
            return kind
    return "room"


def motion_events(video: Path) -> tuple[list[tuple[float, str]], float]:
    """Sound events from on-screen motion: whooshes on fast-motion onsets, hits on sudden jumps."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    prev, mags, jumps = None, [], []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(f, (160, int(160 * f.shape[0] / f.shape[1]) or 90)), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 2, 9, 2, 5, 1.1, 0)
            mags.append(float(np.mean(np.linalg.norm(flow, axis=2))))
            jumps.append(float(np.mean(np.abs(g.astype(np.float32) - prev.astype(np.float32)))))
        prev = g
    cap.release()
    seconds = (len(mags) + 1) / fps
    events = []
    if len(mags) > 4:
        m = np.convolve(mags, np.ones(3) / 3, mode="same")
        thr = np.median(m) + 1.5 * np.std(m)
        last = -1.0
        for i in range(1, len(m)):
            t = i / fps
            if m[i] > thr and m[i - 1] <= thr and t - last > 0.6:
                events.append((max(0.0, t - 0.12), "whoosh"))
                last = t
        j = np.array(jumps)
        for i in np.where(j > np.median(j) + 4 * np.std(j) + 1)[0]:
            events.append(((i + 1) / fps, "hit"))
    return events, seconds


def soundtrack(video: Path, prompt_text: str, out: Path, ambience_kind: str = "", sfx: bool = True) -> Path:
    events, seconds = motion_events(video)
    kind = ambience_kind or detect_ambience(prompt_text)
    bed = ambience(kind, seconds + 0.2)
    mix = 0.9 * bed[: int(seconds * SR)]
    if sfx and events:
        stem = np.asarray(sound.sfx_track(events, seconds), np.float32)
        k = min(len(mix), len(stem))
        mix[:k] += 0.8 * stem[:k]
    peak = float(np.max(np.abs(mix))) or 1.0
    sound.write_wav(out, mix / peak * 0.7)
    return out
