"""Control signals for motion transfer and editing (fed to Wan VACE).

  depth  Depth Anything V2 Small (Apache-2.0) through transformers: the shape and layout of a
         reference video, so the new video follows its motion and camera exactly
  pose   ViTPose (Apache-2.0) with an RT-DETR person detector (Apache-2.0) through transformers,
         drawn as an OpenPose-style skeleton: transfers body movement to a new character
  edges  Canny edges (OpenCV): keeps outlines, lets the model repaint everything else
Masks for editing: a still image (applied to every frame) or a mask video; white = regenerate.
"""

from __future__ import annotations

import numpy as np

_models: dict = {}


def load_masks(path: str, w: int, h: int, n: int) -> list:
    from PIL import Image, ImageOps
    if not path:
        raise ValueError("Editing needs a mask: paint the area to change in white.")
    if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        m = ImageOps.fit(Image.open(path).convert("L"), (w, h), Image.NEAREST)
        m = m.point(lambda v: 255 if v > 127 else 0)
        return [m] * n
    from .engine import load_video
    frames = load_video(path, w, h, n)
    return [f.convert("L").point(lambda v: 255 if v > 127 else 0) for f in frames]


def depth(frames: list, log=None) -> list:
    from PIL import Image
    from transformers import pipeline
    if "depth" not in _models:
        _models["depth"] = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")
        if log:
            log("loaded Depth Anything V2 Small")
    out = []
    for f in frames:
        d = np.asarray(_models["depth"](f)["depth"], dtype=np.float32)
        d = (d - d.min()) / max(1e-6, d.max() - d.min())
        im = Image.fromarray((d * 255).astype(np.uint8)).convert("RGB").resize(f.size)
        out.append(im)
    return out


def depth_map(image) -> np.ndarray:
    """Relative depth (0 far .. 1 near) of one image."""
    from transformers import pipeline
    if "depth" not in _models:
        _models["depth"] = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")
    d = np.asarray(_models["depth"](image)["depth"].resize(image.size), dtype=np.float32)
    return (d - d.min()) / max(1e-6, d.max() - d.min())


# COCO-17 limbs, OpenPose-like colours
LIMBS = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14),
         (14, 16), (0, 1), (0, 2), (1, 3), (2, 4), (0, 5), (0, 6)]
COLOURS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0),
           (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255),
           (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]


def pose(frames: list, log=None) -> list:
    import cv2
    import torch
    from PIL import Image
    from transformers import AutoProcessor, RTDetrForObjectDetection, VitPoseForPoseEstimation
    if "pose" not in _models:
        _models["det_p"] = AutoProcessor.from_pretrained("PekingU/rtdetr_r50vd_coco_o365")
        _models["det"] = RTDetrForObjectDetection.from_pretrained("PekingU/rtdetr_r50vd_coco_o365").eval()
        _models["pose_p"] = AutoProcessor.from_pretrained("usyd-community/vitpose-base-simple")
        _models["pose"] = VitPoseForPoseEstimation.from_pretrained("usyd-community/vitpose-base-simple").eval()
        if log:
            log("loaded RT-DETR person detector and ViTPose")
    out = []
    for f in frames:
        w, h = f.size
        canvas = np.zeros((h, w, 3), np.uint8)
        with torch.no_grad():
            inp = _models["det_p"](images=f, return_tensors="pt")
            det = _models["det"](**inp)
            res = _models["det_p"].post_process_object_detection(det, target_sizes=torch.tensor([(h, w)]), threshold=0.4)[0]
            boxes = res["boxes"][res["labels"] == 0].numpy()   # COCO label 0 = person
            if len(boxes):
                boxes[:, 2] -= boxes[:, 0]
                boxes[:, 3] -= boxes[:, 1]
                pin = _models["pose_p"](f, boxes=[boxes], return_tensors="pt")
                pout = _models["pose"](**pin)
                people = _models["pose_p"].post_process_pose_estimation(pout, boxes=[boxes])[0]
                for person in people:
                    kp = person["keypoints"].numpy()
                    sc = person["scores"].numpy()
                    th = max(2, int(min(w, h) / 120))
                    for i, (a, b) in enumerate(LIMBS):
                        if sc[a] > 0.3 and sc[b] > 0.3:
                            cv2.line(canvas, tuple(int(v) for v in kp[a]), tuple(int(v) for v in kp[b]), COLOURS[i], th * 2)
                    for j, p in enumerate(kp):
                        if sc[j] > 0.3:
                            cv2.circle(canvas, (int(p[0]), int(p[1])), th * 2, COLOURS[j % len(COLOURS)], -1)
        out.append(Image.fromarray(canvas))
    return out


def edges(frames: list, log=None) -> list:
    import cv2
    from PIL import Image
    out = []
    for f in frames:
        g = cv2.cvtColor(np.asarray(f), cv2.COLOR_RGB2GRAY)
        e = cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 60, 140)
        out.append(Image.fromarray(e).convert("RGB"))
    return out


def extract(kind: str, frames: list, log=None) -> list:
    if kind == "depth":
        return depth(frames, log)
    if kind == "pose":
        return pose(frames, log)
    if kind == "edges":
        return edges(frames, log)
    raise ValueError(f"Unknown control '{kind}'")
