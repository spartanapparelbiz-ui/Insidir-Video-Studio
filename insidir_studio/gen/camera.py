"""Precise camera control from a single image.

1. Depth Anything V2 estimates the scene's depth from the start image.
2. The chosen camera moves become a path (dolly, truck, pedestal, zoom, roll, orbit) over time.
3. The depth map is re-projected along that path with real parallax (near things move more
   than far things), giving a moving depth video of the shot the camera would see.
4. Wan VACE renders the shot: the start image is kept as frame 1 and the moving depth steers
   the camera, while the model fills in newly revealed areas.

Within reach of a single image: push/pull, dolly zoom, partial orbit, crane, pan/tilt, roll,
crash zoom, handheld, drone/FPV forward flight. A full 360 orbit or bullet time needs views the
image doesn't contain, so for those the depth path is limited and the prompt describes the move.
"""

from __future__ import annotations

import math

import numpy as np

SPEED = {"slow": 0.6, "medium": 1.0, "fast": 1.6}


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def path(moves: list[str], t: float, k: float = 1.0) -> dict:
    """Camera parameters at time t (0..1). All moves add up, so they can be combined."""
    e = _ease(t)
    p = {"tx": 0.0, "ty": 0.0, "tz": 0.0, "zoom": 1.0, "roll": 0.0, "yaw": 0.0, "shake": 0.0}
    for mv in moves or []:
        if mv == "push_in" or mv == "gimbal":
            p["tz"] += 0.32 * k * e
        elif mv == "pull_out":
            p["tz"] -= 0.28 * k * e
        elif mv == "dolly_zoom":
            p["tz"] += 0.45 * k * e
            p["zoom"] /= 1 + 0.45 * k * e * 0.85     # zoom out as the camera moves in: subject holds size
        elif mv in ("orbit", "orbit_360", "bullet_time"):
            p["yaw"] += (0.22 if mv == "orbit" else 0.3) * k * e
        elif mv in ("drone", "hyperlapse"):
            p["tz"] += 0.45 * k * e
            p["ty"] -= 0.04 * k * e
        elif mv == "fpv":
            p["tz"] += 0.7 * k * e
            p["roll"] += 6 * k * math.sin(t * math.pi * 1.5)
        elif mv == "crash_zoom":
            p["zoom"] *= 1 + 0.6 * k * (1 - (1 - min(1.0, t / 0.18)) ** 3)
        elif mv == "tracking":
            p["tx"] += 0.18 * k * e
        elif mv == "crane":
            p["ty"] -= 0.2 * k * e
        elif mv == "jib_down":
            p["ty"] += 0.2 * k * e
        elif mv == "pan_left":
            p["tx"] -= 0.2 * k * e
        elif mv == "pan_right":
            p["tx"] += 0.2 * k * e
        elif mv == "tilt_up":
            p["ty"] -= 0.16 * k * e
        elif mv == "tilt_down":
            p["ty"] += 0.16 * k * e
        elif mv == "handheld":
            p["shake"] += 0.006 * k
        elif mv in ("macro", "rack_focus"):
            p["zoom"] *= 1 + 0.12 * k * e
        elif mv == "high_speed":
            p["tz"] += 0.5 * k * e
    return p


def warp(img: np.ndarray, depth: np.ndarray, p: dict, t: float, pivot: float) -> np.ndarray:
    """Re-project an image (or depth map) for camera parameters p, with depth parallax."""
    import cv2
    h, w = depth.shape
    cx, cy = w / 2, h / 2
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    near = 0.15 + depth                    # 0.15 (far) .. 1.15 (near)
    # dolly: things grow by 1/(1 - tz*near); orbit: parallax around the pivot depth
    s = p["zoom"] / np.maximum(0.2, 1 - p["tz"] * near)
    dx = p["tx"] * w * near + p["yaw"] * w * (near - (0.15 + pivot))
    dy = p["ty"] * h * near
    if p["shake"]:
        dx += p["shake"] * w * (math.sin(t * 37) + 0.5 * math.sin(t * 91))
        dy += p["shake"] * h * (math.cos(t * 29) + 0.5 * math.sin(t * 73))
    a = math.radians(p["roll"])
    ux, uy = (xs - cx) - dx, (ys - cy) - dy
    rx = (ux * math.cos(a) + uy * math.sin(a)) / s + cx
    ry = (-ux * math.sin(a) + uy * math.cos(a)) / s + cy
    return cv2.remap(img, rx.astype(np.float32), ry.astype(np.float32), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REPLICATE)


def depth_camera_video(image, moves: list[str], n: int, speed: str = "medium", log=None) -> list:
    """A moving depth video for VACE: what the camera path would see, frame by frame."""
    from PIL import Image
    from . import control
    d = control.depth_map(image)
    pivot = float(np.median(d[d.shape[0] // 3: 2 * d.shape[0] // 3, d.shape[1] // 3: 2 * d.shape[1] // 3]))
    k = SPEED.get(speed, 1.0)
    out = []
    d8 = (d * 255).astype(np.uint8)
    for i in range(n):
        t = i / max(1, n - 1)
        fr = warp(d8, d, path(moves, t, k), t, pivot)
        out.append(Image.fromarray(fr).convert("RGB"))
    if log:
        log(f"camera path from depth: {', '.join(moves) or 'static'} ({speed})")
    return out
