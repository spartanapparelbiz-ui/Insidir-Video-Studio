"""The generation engine: runs real open video models (via diffusers) for every task.

    generate(spec) -> candidates -> quality scores -> best -> post-processing -> final MP4

Long videos are made by continuation: each new chunk is conditioned on the last frames of the
previous one (VACE: those frames are kept and the model continues the motion; image-to-video
models: the last frame starts the next chunk), then chunks are joined with a short crossfade.
"""

from __future__ import annotations

import gc
import json
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from . import hardware, manager, post, prompt as prompts, quality
from .models import MODELS


class Cancelled(Exception):
    pass


# pipelines that can continue a clip from its last frames
CONTINUES = ("WanVACEPipeline", "WanImageToVideoPipeline", "LTXConditionPipeline",
             "SkyReelsV2DiffusionForcingVideoToVideoPipeline")


def continuation_model(model_id: str) -> str | None:
    """A model that can extend clips made by model_id: itself if it can, else an installed one,
    preferring the same family (Wan models share their text encoder, so the prompt is reused)."""
    m = MODELS[model_id]
    if m.get("test_only"):
        return model_id
    if "extend" in m["tasks"] and m["family"] in ("wan-vace", "ltx", "skyreels-df"):
        return model_id
    have = manager.installed_set()
    same = [k for k in MODELS if "extend" in MODELS[k]["tasks"] and k in have and not MODELS[k].get("test_only")
            and MODELS[k]["family"].split("-")[0] == m["family"].split("-")[0]]
    other = [k for k in MODELS if "extend" in MODELS[k]["tasks"] and k in have and not MODELS[k].get("test_only")]
    return (same or other or [None])[0]


@dataclass
class Spec:
    task: str = "t2v"
    model: str = ""
    prompt: str = ""
    negative: str = ""
    raw_prompt: bool = False           # send the prompt exactly as typed
    camera: list = field(default_factory=list)
    camera_speed: str = "medium"
    lens: str = ""
    lighting: str = ""
    style: str = "photoreal"
    motion: float = 0.5                # motion strength 0..1 (prompt + guidance hints)
    adherence: float = 0.5             # how literally to follow the prompt 0..1
    width: int = 0
    height: int = 0
    aspect: str = "16:9"
    seconds: float = 5.0
    fps: int = 0                       # 0 = the model's native rate
    steps: int = 0
    guidance: float = 0.0
    seed: int = -1
    variations: int = 1
    image: str = ""                    # start frame (i2v, flf2v)
    last_image: str = ""               # end frame (flf2v)
    video: str = ""                    # source video (v2v, control, edit, extend)
    mask: str = ""                     # edit mask (image or video; white = regenerate)
    references: list = field(default_factory=list)   # character / object reference images (r2v)
    characters: list = field(default_factory=list)   # [{name, description, images}]
    control: str = "none"              # none | pose | depth | edges | camera
    control_scale: float = 1.0
    strength: float = 0.7              # v2v: how much to change the source
    post: dict = field(default_factory=dict)
    quality: str = "standard"          # draft | standard | high | max (see QUALITY)
    refine: bool | None = None         # second detail pass at a higher resolution (None = by quality)


# What each quality level adds. Only fills in what the user didn't set explicitly.
QUALITY = {
    "draft": {"steps": 0.6, "variations": 1, "refine": False, "upscale": 1, "finish": False},
    "standard": {"steps": 1.0, "variations": 1, "refine": False, "upscale": 1, "finish": False},
    "high": {"steps": 1.25, "variations": 2, "refine": True, "upscale": 2, "finish": True},
    "max": {"steps": 1.5, "variations": 3, "refine": True, "upscale": 2, "finish": True},
}


def apply_quality(spec: "Spec", m: dict) -> tuple[int, int, bool, dict]:
    """(steps, variations, refine, post options) for the chosen quality level."""
    q = QUALITY.get(spec.quality, QUALITY["standard"])
    steps = spec.steps or max(4, int(round(m["default"]["steps"] * q["steps"])))
    variations = spec.variations if spec.variations > 1 else q["variations"]
    refine = q["refine"] if spec.refine is None else bool(spec.refine)
    opts = dict(spec.post)
    opts.setdefault("upscale", q["upscale"])
    opts.setdefault("film_finish", q["finish"])
    return steps, variations, refine, opts


def tune_scheduler(pipe, family: str, w: int, h: int, log=None) -> None:
    """Wan's noise schedule: the authors use flow shift 3.0 at 480p and 5.0 at 720p. A shift
    matched to the resolution keeps fine detail at higher sizes instead of washing it out."""
    if not family.startswith("wan") or family == "wan-tiny":
        return
    cfg = dict(pipe.scheduler.config)
    key = "flow_shift" if "flow_shift" in cfg else ("shift" if "shift" in cfg else None)
    if not key:
        return
    want = 5.0 if w * h >= 0.8 * 1280 * 720 else 3.0
    if abs(float(cfg[key]) - want) > 1e-6:
        pipe.scheduler = type(pipe.scheduler).from_config(cfg, **{key: want})
        if log:
            log(f"noise schedule: flow shift {want} for {w}x{h}")


def refiner_model(model_id: str) -> str | None:
    """A plain Wan text-to-video model (its weights power video-to-video) for the detail pass."""
    m = MODELS[model_id]
    if m.get("test_only"):
        return model_id
    if not m["family"].startswith("wan"):
        return None
    if m["family"] == "wan" and "t2v" in m["tasks"]:
        return model_id
    have = manager.installed_set()
    for k in ("wan2.1-t2v-14b", "wan2.1-t2v-1.3b"):
        if k in have:
            return k
    return None


ASPECTS = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1), "4:5": (4, 5), "21:9": (21, 9), "4:3": (4, 3)}


def plan_size(spec: Spec, m: dict) -> tuple[int, int, int, int, int]:
    """(width, height, frames_per_chunk, total_frames, fps) snapped to what the model accepts."""
    d = m["default"]
    fam = m["family"]
    mult = 32 if fam == "ltx" else 16
    area = d["width"] * d["height"]
    if spec.width and spec.height:
        w, h = spec.width, spec.height
    else:
        a, b = ASPECTS.get(spec.aspect, (16, 9))
        h = math.sqrt(area * b / a)
        w = h * a / b
    w = max(mult, int(round(w / mult)) * mult)
    h = max(mult, int(round(h / mult)) * mult)
    fps = d["fps"]
    step = 8 if fam == "ltx" else 4
    chunk = d["frames"]
    if spec.seconds <= 0:            # a single frame: storyboard stills
        return w, h, 1, 1, fps
    total = max(step + 1, int(round(spec.seconds * fps)))
    total = (total - 1) // step * step + 1
    chunk = min(chunk, total)
    chunk = (chunk - 1) // step * step + 1
    return w, h, chunk, total, fps


# ------------------------------------------------------------------ media helpers

def load_image(path: str, w: int, h: int):
    from PIL import Image, ImageOps
    im = Image.open(path).convert("RGB")
    return ImageOps.fit(im, (w, h), Image.LANCZOS)


def load_video(path: str, w: int, h: int, n: int | None = None, fps: float | None = None) -> list:
    """Frames of a video as PIL images, resized and cropped to w x h (resampled to fps if given)."""
    from PIL import Image, ImageOps
    import cv2
    cap = cv2.VideoCapture(str(path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames, i, t_next = [], 0, 0.0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        t = i / src_fps
        i += 1
        if fps and t + 1e-6 < t_next:
            continue
        t_next += 1 / fps if fps else 0
        im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        frames.append(ImageOps.fit(im, (w, h), Image.LANCZOS))
        if n and len(frames) >= n:
            break
    cap.release()
    return frames


def to_uint8(frames) -> np.ndarray:
    a = np.asarray(frames)
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    return a


# ------------------------------------------------------------------ conditioning (VACE)

def _gray(w, h):
    from PIL import Image
    return Image.new("RGB", (w, h), (127, 127, 127))


def _mask(w, h, on: bool):
    from PIL import Image
    return Image.new("L", (w, h), 255 if on else 0)


def vace_inputs(task: str, n: int, w: int, h: int, *, image=None, last=None, prior: list | None = None,
                control: list | None = None, source: list | None = None, masks: list | None = None):
    """(video, mask) for WanVACEPipeline. Mask white = generate, black = keep the given pixels."""
    if task == "t2v" or task == "r2v" and not control:
        return None, None
    if task == "control" or (task in ("r2v", "i2v") and control):
        video = list(control[:n]) + [_gray(w, h)] * max(0, n - len(control))
        mask = [_mask(w, h, True)] * n
        if image is not None:      # keep the start frame, steer the rest by the control signal
            video[0], mask[0] = image, _mask(w, h, False)
        return video, mask
    if task == "edit":
        return list(source[:n]), list(masks[:n])
    video = [_gray(w, h)] * n
    mask = [_mask(w, h, True)] * n
    if task in ("i2v", "flf2v") and image is not None:
        video[0], mask[0] = image, _mask(w, h, False)
    if task == "flf2v" and last is not None:
        video[-1], mask[-1] = last, _mask(w, h, False)
    if task == "extend" and prior:
        k = min(len(prior), max(1, n // 4))
        for i in range(k):
            video[i], mask[i] = prior[-k + i], _mask(w, h, False)
    return video, mask


# ------------------------------------------------------------------ run one chunk

def _encode_prompt(model_id: str, _unused, text: str, negative: str, cfg: bool, log=None):
    """Encode the prompt with the text encoder alone, then free it (halves peak memory)."""
    import torch
    from transformers import AutoTokenizer, UMT5EncoderModel
    hw = hardware.detect()
    path = manager.local_path(model_id)
    tok = AutoTokenizer.from_pretrained(path, subfolder="tokenizer")
    enc = UMT5EncoderModel.from_pretrained(path, subfolder="text_encoder", torch_dtype=torch.bfloat16)
    dev = "cuda" if hw["device"] == "cuda" else "cpu"
    enc.to(dev)

    def one(t):
        # Encode only the real tokens: the padding is masked out anyway, so the embeddings are
        # identical to Wan's padded encoding, at a fraction of the compute. Then zero-pad to 512.
        ids = tok([t], max_length=512, truncation=True, add_special_tokens=True, return_tensors="pt")
        with torch.no_grad():
            e = enc(ids.input_ids.to(dev), torch.ones_like(ids.input_ids).to(dev)).last_hidden_state
        n = e.size(1)
        return torch.cat([e, e.new_zeros(1, 512 - n, e.size(2))], dim=1)

    pe = one(text)
    ne = one(negative) if cfg else None
    del enc
    gc.collect()
    if log:
        log("prompt encoded; text encoder freed")
    return pe, ne


def run_chunk(pipe, model_id: str, task: str, spec: Spec, text: str, negative: str, w: int, h: int, n: int,
              seed: int, guidance: float, steps: int, *, image=None, last=None, prior=None, control=None,
              source=None, masks=None, refs=None, embeds=None, on_step=None):
    import torch
    m = MODELS[model_id]
    fam = m["family"]
    gen = torch.Generator(device="cpu").manual_seed(seed)
    kw = dict(height=h, width=w, num_inference_steps=steps, guidance_scale=guidance, generator=gen,
              output_type="np", callback_on_step_end=on_step)
    kw.update(prompt=text, negative_prompt=negative)
    if embeds is not None:
        # The text encoder isn't loaded: hand the pipeline the embeddings computed up front.
        # (Some Wan pipelines insist on a text prompt, so answer their encode step instead of
        # passing prompt_embeds.)
        pe, ne = embeds
        pipe.encode_prompt = lambda *a, **k: (pe, ne)
    name = type(pipe).__name__
    tune_scheduler(pipe, fam, w, h)
    if name == "WanVACEPipeline":
        video, mask = vace_inputs(task, n, w, h, image=image, last=last, prior=prior, control=control,
                                  source=source, masks=masks)
        kw.update(num_frames=n, video=video, mask=mask, conditioning_scale=spec.control_scale)
        if refs:
            kw["reference_images"] = refs
    elif name == "WanImageToVideoPipeline":
        kw.update(num_frames=n, image=image if image is not None else (prior[-1] if prior else None))
        if last is not None:
            kw["last_image"] = last
        if m["default"].get("guidance_2"):
            kw["guidance_scale_2"] = m["default"]["guidance_2"]
    elif name == "WanVideoToVideoPipeline":
        kw.update(video=source[:n], strength=spec.strength)
    elif name == "WanPipeline":
        kw["num_frames"] = n
        if m["default"].get("guidance_2"):
            kw["guidance_scale_2"] = m["default"]["guidance_2"]
    elif name == "LTXConditionPipeline":
        from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
        conds = []
        if image is not None:
            conds.append(LTXVideoCondition(image=image, frame_index=0))
        if last is not None:
            conds.append(LTXVideoCondition(image=last, frame_index=n - 1))
        if prior:
            conds.append(LTXVideoCondition(video=prior[-9:], frame_index=0))
        if source and task == "v2v":
            conds.append(LTXVideoCondition(video=source[:n], frame_index=0, strength=1 - spec.strength))
        kw.update(num_frames=n, frame_rate=m["default"]["fps"], decode_timestep=0.05, decode_noise_scale=0.025,
                  image_cond_noise_scale=0.0)
        if conds:
            kw["conditions"] = conds
    elif name.startswith("SkyReelsV2DiffusionForcing"):
        kw.update(num_frames=n)
        if prior and "VideoToVideo" in name:
            kw["video"] = prior
    else:   # Hunyuan, CogVideoX
        kw["num_frames"] = n
    out = pipe(**kw).frames
    frames = to_uint8(out[0] if isinstance(out, (list, tuple)) or getattr(out, "ndim", 0) == 5 else out)
    return frames


def frames_to_pil(frames: np.ndarray) -> list:
    from PIL import Image
    return [Image.fromarray(f) for f in frames]


def refine_pass(model_id: str, src: Path, built: dict, embeds, w: int, h: int, fps: int, steps: int, guidance: float,
                seed: int, out_dir: Path, on_step=None, log=None, cancel=None) -> Path:
    """Hi-res detail pass ("hires fix" for video): enlarge the chosen take 1.5x, then let a Wan
    text-to-video model re-denoise it lightly (strength 0.3). Composition and motion stay; the
    model paints real texture at the higher resolution instead of an upscaler guessing it."""
    import torch
    from PIL import Image
    m = MODELS[model_id]
    fam = m["family"]
    mult = 16
    rw = int(round(w * 1.5 / mult)) * mult
    rh = int(round(h * 1.5 / mult)) * mult
    # stay within what the model handles well (about 1.3x its native area)
    cap = m["default"]["width"] * m["default"]["height"] * 1.3 if not m.get("test_only") else rw * rh
    if rw * rh > cap:
        k = math.sqrt(cap / (rw * rh))
        rw, rh = int(rw * k / mult) * mult, int(rh * k / mult) * mult
    frames = load_video(str(src), rw, rh)
    frames = [f.resize((rw, rh), Image.LANCZOS) for f in frames]
    pipe = manager.load(model_id, "v2v", log=log, without_text_encoder=embeds is not None)
    tune_scheduler(pipe, fam, rw, rh, log)
    if embeds is not None:
        pe, ne = embeds
        pipe.encode_prompt = lambda *a, **k: (pe, ne)

    def stop(p, i, t, kw):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        return kw

    out = pipe(video=frames, prompt=built["prompt"], negative_prompt=built["negative"], height=rh, width=rw,
               num_inference_steps=max(8, int(steps * 0.6)), strength=0.3, guidance_scale=guidance,
               generator=torch.Generator(device="cpu").manual_seed(seed), output_type="np",
               callback_on_step_end=on_step or stop).frames
    arr = to_uint8(out[0] if getattr(out, "ndim", 0) == 5 or isinstance(out, (list, tuple)) else out)
    path = out_dir / "refined.mp4"
    post.write_video(arr, fps, path)
    if log:
        log(f"detail pass at {rw}x{rh} with {m['name']} (strength 0.3)")
    return path


# ------------------------------------------------------------------ public entry

def generate(spec: Spec, out_dir: Path, progress=None, cancel: threading.Event | None = None, log=None) -> dict:
    t0 = time.time()
    progress = progress or (lambda f, msg="": None)
    log = log or (lambda msg: None)
    if spec.model not in MODELS:
        raise ValueError("Pick a model")
    m = MODELS[spec.model]
    if spec.task not in m["tasks"]:
        raise ValueError(f"{m['name']} can't do '{spec.task}'. Pick a model that lists it.")
    out_dir.mkdir(parents=True, exist_ok=True)

    built = {"prompt": spec.prompt, "negative": spec.negative or "", "conflicts": prompts.conflicts(spec.prompt)}
    if not spec.raw_prompt:
        built = prompts.enhance(spec.prompt, camera=spec.camera, camera_speed=spec.camera_speed, lens=spec.lens,
                                lighting=spec.lighting, style=spec.style, motion=spec.motion,
                                characters=spec.characters, extra_negative=spec.negative)
    w, h, chunk, total, fps = plan_size(spec, m)
    d = m["default"]
    steps, n_variations, refine, post_opts = apply_quality(spec, m)
    guidance = spec.guidance or prompts.guidance_for(spec.adherence, d["guidance"])
    if w * h < 0.7 * d["width"] * d["height"] and spec.seconds > 0:
        log(f"note: {w}x{h} is below this model's native {d['width']}x{d['height']}; detail and anatomy suffer at "
            f"small sizes (use upscaling for a bigger file instead)")
    seed = spec.seed if spec.seed >= 0 else int(time.time() * 1000) % 2_147_483_647
    log(f"{m['name']}: {spec.task} {w}x{h}, {total} frames ({total / fps:.1f}s @ {fps} fps), {steps} steps, "
        f"guidance {guidance}, seed {seed}")
    (out_dir / "prompt.json").write_text(json.dumps({**built, "spec": asdict(spec), "size": [w, h],
                                                     "frames": total, "fps": fps, "steps": steps,
                                                     "guidance": guidance, "seed": seed}, indent=2))

    # inputs
    image = load_image(spec.image, w, h) if spec.image else None
    last = load_image(spec.last_image, w, h) if spec.last_image else None
    source = load_video(spec.video, w, h, total, fps) if spec.video else None
    if spec.task in ("v2v", "control", "edit", "extend") and not source:
        raise ValueError("This task needs a source video.")
    if spec.task in ("i2v", "flf2v") and image is None:
        raise ValueError("Add a start image.")
    masks = None
    if spec.task == "edit":
        from . import control as ctl
        masks = ctl.load_masks(spec.mask, w, h, len(source))
    refs = [load_image(r, w, h) for r in (spec.references or [])]
    for c in spec.characters or []:
        refs += [load_image(p, w, h) for p in c.get("images", [])[:2]]
    control_frames = None
    if spec.control != "none":
        from . import camera as cam, control as ctl
        progress(0.02, f"Preparing {spec.control} control")
        if spec.control == "camera":
            if image is None:
                raise ValueError("Camera control needs a start image (it builds a 3D-ish depth scene from it).")
            control_frames = cam.depth_camera_video(image, spec.camera, total, spec.camera_speed, log=log)
        else:
            if not source:
                raise ValueError("Motion transfer needs a reference video.")
            control_frames = ctl.extract(spec.control, source, log=log)
        if spec.task not in ("control", "r2v", "i2v"):
            spec.task = "control"

    hw = hardware.detect()
    # Wan's text encoder is 11 GB: on the CPU or a smaller GPU, encode the prompt first, free the
    # encoder, and only then load the video model, so both are never in memory together.
    split = m["family"] in ("wan", "wan-vace") and (hw["device"] == "cpu" or hw["vram_gb"] < 20)
    embeds = None
    if split:
        progress(0.03, "Reading the prompt")
        embeds = _encode_prompt(spec.model, None, built["prompt"], built["negative"], guidance > 1.0, log=log)
    progress(0.04, "Loading the model")
    # only the manager holds pipelines (one at a time), so switching models frees memory
    pipe_name = type(manager.load(spec.model, spec.task, log=log, without_text_encoder=split)).__name__

    n_chunks = 1 + max(0, math.ceil((total - chunk) / max(1, chunk - max(1, chunk // 4))))
    total_steps = steps * n_chunks * max(1, n_variations)
    done = {"n": 0}

    def on_step(p, i, t, kwargs):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        done["n"] += 1
        progress(0.05 + 0.75 * done["n"] / total_steps, f"Generating: step {done['n']} of {total_steps}")
        return kwargs

    candidates = []
    for v in range(max(1, n_variations)):
        s = seed + v
        frames_all: list = []
        prior = None
        produced = 0
        ci = 0
        while produced < total:
            n = chunk
            task = spec.task if ci == 0 else "extend"
            use_model, use_embeds = spec.model, embeds
            if ci == 0 or pipe_name in CONTINUES:
                use_pipe = manager.load(spec.model, spec.task, log=log, without_text_encoder=split)
            else:
                use_pipe = None
                cont = continuation_model(spec.model)
                if not cont:
                    log("no installed model can continue this clip; install Wan VACE to make longer videos")
                    break
                if cont != spec.model:
                    log(f"continuing with {MODELS[cont]['name']}")
                use_model = cont
                use_pipe = manager.load(cont, "extend", log=log, without_text_encoder=split and cont != "tiny-test")
                if MODELS[cont]["family"] != m["family"] and not (MODELS[cont]["family"].startswith("wan")
                                                                  and m["family"].startswith("wan")):
                    use_embeds = None
            ctrl = control_frames[produced:produced + n] if control_frames else None
            src = source[produced:produced + n] if source else None
            msk = masks[produced:produced + n] if masks else None
            fr = run_chunk(use_pipe, use_model, task, spec, built["prompt"], built["negative"], w, h, n, s, guidance,
                           steps, image=image if ci == 0 else None, last=last if produced + n >= total else None,
                           prior=prior, control=ctrl, source=src, masks=msk, refs=refs if ci == 0 else refs[:1],
                           embeds=use_embeds, on_step=on_step)
            if ci == 0:
                frames_all = list(fr)
            else:
                k = min(len(prior), max(1, n // 4))
                frames_all = post.crossfade_join(frames_all, list(fr), k)
            produced = len(frames_all)
            prior = frames_to_pil(np.asarray(frames_all[-max(1, chunk // 4):]))
            ci += 1
        frames = np.asarray(frames_all[:total])
        path = out_dir / f"candidate_{v + 1}.mp4"
        post.write_video(frames, fps, path)
        candidates.append({"path": str(path), "seed": s, "frames": len(frames)})
        log(f"candidate {v + 1}: {len(frames)} frames")

    progress(0.82, "Scoring candidates")
    for c in candidates:
        c["scores"] = quality.score(c["path"], built["prompt"], use_clip=spec.post.get("clip_score", False))
    best = max(candidates, key=lambda c: c["scores"]["total"])
    log(f"best: {Path(best['path']).name} (score {best['scores']['total']:.3f})")

    finish_src = Path(best["path"])
    if refine and spec.seconds > 0:
        rm = refiner_model(spec.model)
        if rm:
            progress(0.84, "Detail pass")
            finish_src = refine_pass(rm, finish_src, built, embeds if MODELS[rm]["family"].startswith("wan") else None,
                                     w, h, fps, steps, guidance, best["seed"], out_dir, on_step=None, log=log,
                                     cancel=cancel)
        else:
            log("detail pass skipped: it needs a Wan text-to-video model (e.g. Wan 2.1 T2V 1.3B) downloaded")
    progress(0.86, "Finishing")
    final = post.finish(finish_src, out_dir / "final.mp4", fps, {**post_opts, "prompt": built["prompt"]}, log=log,
                        progress=lambda f, msg="": progress(0.86 + 0.13 * f, msg))
    result = {"final": str(final), "candidates": candidates, "best": best["path"], "prompt": built,
              "quality": spec.quality, "refined": str(finish_src) != best["path"], "steps": steps,
              "size": [w, h], "fps": fps, "frames": best["frames"], "seed": best["seed"], "model": spec.model,
              "task": spec.task, "seconds": round(time.time() - t0, 1), "device": hw["name"]}
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    progress(1.0, "Done")
    return result
