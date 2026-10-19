"""Cinematic finishing: colour grades and film effects for every format.

Applied in the final FFmpeg pass, after the picture is cut and before captions and labels are
burned in (so text stays clean and readable). Everything is plain FFmpeg filters: free, local,
fast, and the same on every PC.

Presets bundle a grade, effects, caption style and camera style, like the looks on paid AI
video sites; every part can still be changed on its own in the Style tab.
"""

from __future__ import annotations

from pathlib import Path

from . import brand, config, media

GRADES = {
    "none": ("Natural", ""),
    # brand rule: no grade pushes toward yellow (highlights go rose/red, never amber)
    "cinematic": ("Teal & rose blockbuster",
                  "colorbalance=rs=-0.05:gs=-0.01:bs=0.07:rm=0.02:bm=-0.01:rh=0.06:gh=-0.02:bh=-0.01,"
                  "eq=contrast=1.08:saturation=1.1:gamma=0.98"),
    "film": ("Film stock, soft lifted blacks",
             "curves=r='0/0.05 0.25/0.24 0.5/0.52 0.75/0.77 1/0.96':g='0/0.04 0.5/0.49 1/0.94':"
             "b='0/0.07 0.5/0.5 1/0.95',eq=saturation=0.93"),
    "moody": ("Moody: dark, desaturated, cool shadows",
              "eq=brightness=-0.035:contrast=1.14:saturation=0.82,colorbalance=bs=0.06:bm=0.02:rh=0.03"),
    "noir": ("Noir black and white", "hue=s=0,eq=contrast=1.28:brightness=-0.02,curves=preset=strong_contrast"),
    "bleach": ("Bleach bypass: gritty, silvery", "eq=saturation=0.55:contrast=1.22:gamma=0.96"),
    "vivid": ("Vivid: punchy social colour", "eq=saturation=1.3:contrast=1.06,unsharp=5:5:0.35"),
    "cool": ("Cool steel blue", "colorbalance=rs=-0.04:bs=0.08:bm=0.05:bh=0.03,eq=saturation=0.95"),
    "rose": ("Rose dusk: soft red-magenta warmth, no yellow", "colorbalance=rs=0.05:rm=0.04:gm=-0.03:bm=0.01:gh=-0.02,eq=saturation=1.04"),
    "vintage": ("Faded vintage", "curves=preset=vintage,eq=saturation=0.85:contrast=0.96"),
    "matrix": ("Green-tinted tech", "colorbalance=rs=-0.05:gs=0.05:bs=-0.03:gm=0.04:gh=0.02,eq=contrast=1.1:saturation=0.9"),
}

EFFECTS = {
    "letterbox": "Cinema bars (2.39:1 feel)",
    "vignette": "Vignette",
    "bloom": "Bloom: highlights glow",
    "halation": "Halation: red glow around highlights, like film",
    "grain": "Film grain (light; bigger files)",
    "chroma": "Lens fringing (chromatic aberration)",
    "leaks": "Light leaks on cuts",
    "sharpen": "Crisp sharpen",
}

PRESETS = {
    # the default for real people: footage looks like it came off a real camera, nothing stylised
    "natural": {"name": "Natural (realistic)", "grade": "none", "effects": [], "caption_style": "outline",
                "camera": "handheld", "camera_strength": 0.5, "transitions": "cuts"},
    "cinematic": {"name": "Cinematic", "grade": "cinematic", "effects": ["letterbox", "vignette", "bloom", "chroma"],
                  "caption_style": "minimal", "camera": "calm", "transitions": "cinematic"},
    "viral": {"name": "Viral", "grade": "vivid", "effects": ["vignette", "sharpen"],
              "caption_style": "pop", "camera": "energetic", "transitions": "cinematic"},
    "documentary": {"name": "Documentary", "grade": "film", "effects": ["vignette", "grain"],
                    "caption_style": "boxed", "camera": "handheld", "transitions": "cuts"},
    "noir": {"name": "Noir", "grade": "noir", "effects": ["letterbox", "vignette", "grain"],
             "caption_style": "outline", "camera": "calm", "transitions": "cinematic"},
    "moody": {"name": "Moody", "grade": "moody", "effects": ["vignette", "halation", "leaks"],
              "caption_style": "neon", "camera": "dynamic", "transitions": "cinematic"},
    "dusk": {"name": "Rose dusk", "grade": "rose", "effects": ["bloom", "leaks", "vignette"],
               "caption_style": "karaoke", "camera": "handheld", "transitions": "cinematic"},
    "clean": {"name": "Clean", "grade": "none", "effects": [], "caption_style": "outline", "camera": "dynamic",
              "transitions": "cuts"},
}

# looks that were retired under the no-yellow rule, for projects saved before
LEGACY = {"warm": "rose", "golden": "dusk"}

STRENGTH = {"subtle": 0.6, "normal": 1.0, "strong": 1.5}


def _leak_png(path: Path, w: int, h: int) -> Path:
    """A light leak: a red-to-magenta radial glow from one edge (never orange/yellow)."""
    if not path.exists():
        r = max(w, h) * 0.75
        media.run(["-f", "lavfi", "-i", f"color=c=black:s={w // 4}x{h // 4}", "-frames:v", "1", "-vf",
                   f"format=rgba,geq=r='255':g='30':b='90+90*Y/{h / 4}':"
                   f"a='255*max(0,1-hypot(X-{w // 16},Y-{h // 10})/{r / 4})^1.6',scale={w}:{h}", str(path)])
    return path


def chain(style: dict, w: int, h: int, total: float, cuts: list[float], build: Path, first_input: int,
          src: str, out: str) -> tuple[list[str], list[str]]:
    """Filter graph parts that turn [src] into the graded, finished [out].

    Returns (extra FFmpeg input args, filter parts). cuts: times of the major cuts (for light leaks)."""
    grade = GRADES.get(LEGACY.get(style.get("grade"), style.get("grade")) or "none", GRADES["none"])[1]
    fx = set(style.get("effects") or [])
    k = STRENGTH.get(style.get("look_strength") or "normal", 1.0)
    parts: list[str] = []
    inputs: list[str] = []
    cur = src
    n = 0

    def step(f: str) -> None:
        nonlocal cur, n
        n += 1
        nxt = f"lk{n}"
        parts.append(f"[{cur}]{f}[{nxt}]")
        cur = nxt

    if grade:
        step(grade)
    if "bloom" in fx or "halation" in fx:
        n += 1
        a, g, base = f"lka{n}", f"lkg{n}", f"lkb{n}"
        tint = ",colorchannelmixer=rr=1:gg=0.18:bb=0.3" if "halation" in fx else ""
        glow = min(0.6, 0.28 * k + (0.08 if "halation" in fx else 0))
        # blend in RGB: a screen blend on YUV planes shifts every colour toward magenta
        parts.append(f"[{cur}]format=gbrp,split[{a}][{base}]")
        parts.append(f"[{a}]curves=all='0/0 0.62/0 1/1',gblur=sigma={int(min(w, h) * 0.02)}{tint}[{g}]")
        nxt = f"lk{n}x"
        parts.append(f"[{base}][{g}]blend=all_mode=screen:all_opacity={glow:.2f}[{nxt}]")
        cur = nxt
    if "chroma" in fx:
        px = max(1, round(2 * k))
        step(f"rgbashift=rh=-{px}:bh={px}")
    if "sharpen" in fx:
        step(f"unsharp=5:5:{0.45 * k:.2f}")
    if "leaks" in fx and cuts:
        leak = _leak_png(build / f"leak_{w}x{h}.png", w, h)
        idx = first_input
        inputs += ["-loop", "1", "-framerate", "30", "-t", f"{total:.3f}", "-i", str(leak.relative_to(build))]
        use = cuts[:8]
        parts.append(f"[{idx}:v]format=rgba,split={len(use)}" + "".join(f"[lkl{i}]" for i in range(len(use))))
        for i, t in enumerate(use):
            a0 = max(0.0, t - 0.12)
            peak = min(0.55, 0.38 * k)
            parts.append(f"[lkl{i}]colorchannelmixer=aa={peak:.2f},fade=t=in:st={a0:.2f}:d=0.12:alpha=1,"
                         f"fade=t=out:st={a0 + 0.14:.2f}:d=0.45:alpha=1[lkf{i}]")
            nxt = f"lko{i}"
            parts.append(f"[{cur}][lkf{i}]overlay=0:0:shortest=1:format=auto[{nxt}]")
            cur = nxt
    if "vignette" in fx:
        step(f"vignette=angle=PI/{max(3.2, 5.2 - 1.2 * k):.2f}")
    if "grain" in fx:
        step(f"noise=alls={max(2, round(5 * k))}:allf=t")
    if "letterbox" in fx:
        # bars that make any frame feel 2.39:1 wide, without cropping the important middle
        bar = int((h - w / 2.39) / 2) if w > h else int(h * (0.075 if h > w else 0.06))
        step(f"drawbox=x=0:y=0:w={w}:h={bar}:color=black:t=fill,drawbox=x=0:y={h - bar}:w={w}:h={bar}:color=black:t=fill")
    # brand rule, last so no grade or effect can bring it back: no yellow
    step(brand.lut_step())
    parts.append(f"[{cur}]format=yuv420p[{out}]")
    return inputs, parts


def preview(src_image: Path, out: Path, style: dict) -> Path:
    """A graded still for the Style tab swatches."""
    w, h = 270, 480
    build = out.parent
    build.mkdir(parents=True, exist_ok=True)
    s = {**style, "effects": [e for e in style.get("effects") or [] if e != "leaks"]}
    _, parts = chain(s, w, h, 1.0, [], build, 1, "p0", "pout")
    graph = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuv420p[p0];" + ";".join(parts)
    media.run(["-i", str(src_image), "-filter_complex", graph, "-map", "[pout]", "-frames:v", "1", "-q:v", "4", str(out)])
    return out


def catalogue() -> dict:
    return {"grades": {k: v[0] for k, v in GRADES.items()}, "effects": EFFECTS, "presets": PRESETS,
            "aspects": config.ASPECT_NAMES}
