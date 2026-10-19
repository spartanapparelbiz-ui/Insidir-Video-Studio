"""AI upscaling with Real-ESRGAN (x4plus), in plain PyTorch.

The RRDBNet below is the published Real-ESRGAN generator (BasicSR, BSD-3-Clause); the official
RealESRGAN_x4plus weights (BSD-3-Clause) download once (64 MB) on first use. Unlike Lanczos,
it reconstructs texture (hair, fabric, foliage, skin pores) instead of only enlarging pixels.

Runs on an NVIDIA GPU when available (fast), otherwise on the CPU (slow but works). Frames are
processed in overlapping tiles so 4K output fits in modest memory, then the result is
resampled to the requested factor. A light temporal blend afterwards keeps per-frame
detail from shimmering.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np

from .. import config

WEIGHTS_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
_model: dict = {}


def weights_path() -> Path:
    return config.studio_home() / "models" / "RealESRGAN_x4plus.pth"


def ensure_weights(log=None) -> Path:
    p = weights_path()
    if not p.exists() or p.stat().st_size < 60_000_000:
        p.parent.mkdir(parents=True, exist_ok=True)
        if log:
            log("downloading Real-ESRGAN x4plus weights (64 MB, once)")
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(WEIGHTS_URL, tmp)
        tmp.replace(p)
    return p


def _net():
    import torch
    from torch import nn
    from torch.nn import functional as F

    class RDB(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, inplace=True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            return self.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.rdb1, self.rdb2, self.rdb3 = RDB(nf, gc), RDB(nf, gc), RDB(nf, gc)

        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, nf=64, nb=23, gc=32):
            super().__init__()
            self.conv_first = nn.Conv2d(3, nf, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB(nf, gc) for _ in range(nb)])
            self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, inplace=True)

        def forward(self, x):
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
            return self.conv_last(self.lrelu(self.conv_hr(feat)))

    return RRDBNet()


def load(log=None):
    import torch
    if "net" not in _model:
        net = _net()
        state = torch.load(ensure_weights(log), map_location="cpu", weights_only=True)
        net.load_state_dict(state.get("params_ema") or state.get("params") or state, strict=True)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        net.eval().to(dev)
        if dev == "cuda":
            net.half()
        _model.update(net=net, dev=dev)
    return _model["net"], _model["dev"]


def upscale_frame(img: np.ndarray, tile: int = 192, pad: int = 12, log=None) -> np.ndarray:
    """One RGB uint8 frame -> 4x larger, tile by tile with overlap (seamless)."""
    import torch
    net, dev = load(log)
    h, w, _ = img.shape
    x = torch.from_numpy(img).permute(2, 0, 1).float().div(255).unsqueeze(0)
    out = torch.zeros(1, 3, h * 4, w * 4)
    dtype = torch.float16 if dev == "cuda" else torch.float32
    with torch.no_grad():
        for y0 in range(0, h, tile):
            for x0 in range(0, w, tile):
                y1, x1 = min(h, y0 + tile), min(w, x0 + tile)
                py0, px0 = max(0, y0 - pad), max(0, x0 - pad)
                py1, px1 = min(h, y1 + pad), min(w, x1 + pad)
                t = x[:, :, py0:py1, px0:px1].to(dev, dtype)
                o = net(t).float().cpu()
                oy, ox = (y0 - py0) * 4, (x0 - px0) * 4
                out[:, :, y0 * 4:y1 * 4, x0 * 4:x1 * 4] = o[:, :, oy:oy + (y1 - y0) * 4, ox:ox + (x1 - x0) * 4]
    return (out.clamp(0, 1).mul(255).round().byte()[0].permute(1, 2, 0).numpy())


def upscale_video(src: Path, out: Path, factor: int, log=None, progress=None) -> Path:
    """Real-ESRGAN every frame, resample to `factor`, blend a touch of the previous frame's
    detail so per-frame hallucinated texture doesn't shimmer, encode near-lossless."""
    import cv2
    from . import post
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames, prev, i = [], None, 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        up = upscale_frame(rgb, log=log)
        h, w = rgb.shape[:2]
        if factor != 4:
            up = cv2.resize(up, (w * factor, h * factor), interpolation=cv2.INTER_AREA)
        if prev is not None:
            # temporal stabilisation of fine detail, only where the picture is nearly static
            # (blending moving areas would ghost)
            still = (np.abs(up.astype(np.int16) - prev.astype(np.int16)).mean(axis=2, keepdims=True) < 10)
            up = np.where(still, (up * 0.85 + prev * 0.15).astype(np.uint8), up)
        frames.append(up)
        prev = up
        i += 1
        if progress and n:
            progress(i / n, f"AI upscaling frame {i} of {n}")
    cap.release()
    post.write_video(np.asarray(frames), int(round(fps)), out, crf=12)
    if log:
        log(f"upscaled x{factor} with Real-ESRGAN ({_model.get('dev')})")
    return out
