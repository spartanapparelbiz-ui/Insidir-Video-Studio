"""Measurable quality scores, used to pick the best of several generated candidates.

  consistency  1 - optical-flow warp error between neighbouring frames: objects that morph,
               melt or pop in and out can't be explained by motion, so they score low
  flicker      stability of overall brightness from frame to frame
  sharpness    variance of the Laplacian (fine detail vs mush)
  motion       how much things move (a frozen clip and chaotic jitter both lose points)
  spikes       sudden whole-frame jumps (glitches, scene breaks inside one shot)
  exposure     share of blown-out or crushed pixels
  prompt       optional: CLIP image-text similarity (adherence to the prompt)

All are computed on a downscaled copy, so scoring takes seconds, not minutes.
"""

from __future__ import annotations

import numpy as np

_clip = {}


def read_frames(path: str, short: int = 256, max_frames: int = 96) -> np.ndarray:
    import cv2
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, n // max_frames) if n else 1
    out, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            h, w = f.shape[:2]
            k = short / min(h, w)
            out.append(cv2.resize(f, (max(16, int(w * k)), max(16, int(h * k))), interpolation=cv2.INTER_AREA))
        i += 1
    cap.release()
    return np.asarray(out)


def _clip_score(frames_bgr: np.ndarray, text: str) -> float | None:
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
    except ImportError:
        return None
    if "m" not in _clip:
        try:
            _clip["m"] = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
            _clip["p"] = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        except Exception:
            return None
    from PIL import Image
    pick = frames_bgr[np.linspace(0, len(frames_bgr) - 1, min(4, len(frames_bgr))).astype(int)]
    ims = [Image.fromarray(f[:, :, ::-1]) for f in pick]
    with torch.no_grad():
        inp = _clip["p"](text=[text[:300]], images=ims, return_tensors="pt", padding=True, truncation=True)
        out = _clip["m"](**inp)
        sim = torch.nn.functional.cosine_similarity(out.image_embeds, out.text_embeds).mean().item()
    return float(np.clip((sim - 0.15) / 0.2, 0, 1))   # CLIP cosine ~0.15 unrelated .. 0.35 strong


def score(path: str, prompt_text: str = "", use_clip: bool = False) -> dict:
    import cv2
    f = read_frames(path)
    if len(f) < 2:
        return {"total": 0.0, "frames": len(f)}
    gray = [cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255 for x in f]
    h, w = gray[0].shape
    diag = (h * h + w * w) ** 0.5
    warp_err, mags, diffs = [], [], []
    grid = np.dstack(np.meshgrid(np.arange(w), np.arange(h))).astype(np.float32)
    for a, b in zip(gray[:-1], gray[1:]):
        flow = cv2.calcOpticalFlowFarneback((a * 255).astype(np.uint8), (b * 255).astype(np.uint8), None,
                                            0.5, 3, 15, 3, 5, 1.2, 0)
        warped = cv2.remap(b, grid + flow, None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        warp_err.append(float(np.mean(np.abs(warped - a))))
        mags.append(float(np.mean(np.linalg.norm(flow, axis=2))) / diag)
        diffs.append(float(np.mean(np.abs(b - a))))
    means = np.array([g.mean() for g in gray])
    lap = np.mean([cv2.Laplacian(g, cv2.CV_32F).var() for g in gray[:: max(1, len(gray) // 12)]])
    clipped = float(np.mean([(g < 0.01).mean() + (g > 0.99).mean() for g in gray[:: max(1, len(gray) // 12)]]))
    d = np.array(diffs)
    spikes = int(np.sum(d > max(0.02, 4 * np.median(d) + 1e-6)))
    s = {
        "consistency": float(np.clip(1 - np.mean(warp_err) / 0.08, 0, 1)),
        "flicker": float(np.clip(1 - np.std(np.diff(means)) / 0.02, 0, 1)),
        "sharpness": float(np.clip(lap / 0.004, 0, 1)),
        "motion": float(np.clip(min(np.mean(mags) / 0.003, 1) * np.clip(1 - (np.mean(mags) - 0.03) / 0.05, 0, 1), 0, 1)),
        "spikes": float(np.clip(1 - spikes / 3, 0, 1)),
        "exposure": float(np.clip(1 - clipped / 0.15, 0, 1)),
    }
    weights = {"consistency": 0.32, "flicker": 0.14, "sharpness": 0.14, "motion": 0.14, "spikes": 0.13, "exposure": 0.13}
    if use_clip and prompt_text:
        c = _clip_score(f, prompt_text)
        if c is not None:
            s["prompt"] = c
            weights = {k: v * 0.75 for k, v in weights.items()}
            weights["prompt"] = 0.25
    # Temporal consistency gates everything: a sharp, busy clip whose content can't be explained
    # by motion (morphing, boiling noise) must never beat a coherent one.
    s["total"] = float(sum(s[k] * wgt for k, wgt in weights.items()) * (0.35 + 0.65 * s["consistency"]))
    s["frames"] = len(f)
    return s
