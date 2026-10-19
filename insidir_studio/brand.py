"""Brand rules applied to every video the studio makes.

1. The Insidir logo is on every video: the dotted "i" mark from insidir.com's favicon
   (web/assets/icons/favicon.svg in the Insidir repo) next to the "insidir." wordmark, set in
   the site's logo face (Source Serif 4 Medium, letter-spacing -0.035em, as in base.css .logo).
   Paper-white (#e9e4da, the favicon's ink) with a soft shadow so it reads on any footage.
2. No yellow, ever. Every finished video passes through a hue-keyed 3D LUT that desaturates
   yellows and ambers (hue ~43-72 degrees, easing out to 35 and 80) and leaves everything else alone: skin, orange, red and
   gold-brown fur keep their colour, white stays white. (A generic "desaturate yellows" filter
   also greys out orange and skin; the LUT is exact.)
"""

from __future__ import annotations

import colorsys
from pathlib import Path

import numpy as np

from . import config, media

PAPER = (233, 228, 218)
# the favicon's dots, in its 64x64 viewBox: three across the top of the stem, the stem, three
# across the foot, and the tittle above
DOTS = [(27, 27), (33, 27), (39, 27), (33, 33), (33, 39), (33, 45), (27, 51), (33, 51), (39, 51)]
TITTLE = (33, 15, 4.2)
DOT_R = 3.1
CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")


def _font(px: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(config.FONTS_DIR / "SourceSerif4-Medium.ttf"), px)


def logo_image(height: int):
    """RGBA logo, `height` px tall (the mark's height; the wordmark sits on its baseline)."""
    from PIL import Image, ImageDraw, ImageFilter
    s = 4                                                    # draw 4x, downsample: smooth dots
    H = height * s
    k = H / 46.0                                             # the mark spans y 10.8..54.1 (~44 units)
    pad = int(H * 0.35)
    font = _font(int(H * 0.98))
    text = "insidir."
    # letter-spacing -0.035em: draw glyph by glyph
    em = font.size
    xs, x = [], 0.0
    for ch in text:
        xs.append(x)
        x += font.getlength(ch) - 0.035 * em
    mark_w = 22 * k
    gap = H * 0.22
    W = int(pad * 2 + mark_w + gap + x)
    img = Image.new("RGBA", (W, H + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = pad - 23.5 * k, pad - 10.5 * k
    for cx, cy in DOTS:
        r = DOT_R * k
        d.ellipse((ox + cx * k - r, oy + cy * k - r, ox + cx * k + r, oy + cy * k + r), fill=PAPER + (255,))
    cx, cy, r = TITTLE
    d.ellipse((ox + cx * k - r * k, oy + cy * k - r * k, ox + cx * k + r * k, oy + cy * k + r * k), fill=PAPER + (255,))
    # wordmark: baseline on the foot dots' bottom edge
    base = oy + (51 + DOT_R) * k
    tx = pad + mark_w + gap
    for ch, cx0 in zip(text, xs):
        d.text((tx + cx0, base), ch, font=font, fill=PAPER + (255,), anchor="ls")
    # soft shadow underneath so it reads on white skies and snow
    alpha = img.getchannel("A")
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(H * 0.06)).point(lambda v: int(v * 0.55)))
    out = Image.alpha_composite(shadow, img)
    return out.resize((max(1, W // s), max(1, (H + pad * 2) // s)), Image.LANCZOS)


def logo_png(path: Path, frame_w: int, frame_h: int) -> Path:
    """The logo sized for a frame: the mark is ~4.2% of the frame's short side."""
    h = max(14, int(round(min(frame_w, frame_h) * 0.042)))
    path.parent.mkdir(parents=True, exist_ok=True)
    logo_image(h).save(path)
    return path


def is_yellow(hex_color: str) -> bool:
    """True for any colour a viewer would call yellow, gold or mustard."""
    try:
        h = hex_color.strip().lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, AttributeError, IndexError):
        return False
    hue, sat, val = colorsys.rgb_to_hsv(r, g, b)
    return 38 <= hue * 360 <= 80 and sat > 0.18 and val > 0.25


def safe_color(hex_color: str | None, fallback: str = "#FFFFFF") -> str:
    return fallback if not hex_color or is_yellow(hex_color) else hex_color


def _desat_weight(h_deg: np.ndarray) -> np.ndarray:
    """1 inside the yellow band, easing to 0 at its edges (orange <= 35, green >= 80 untouched)."""
    w = np.zeros_like(h_deg)
    core = (h_deg >= 43) & (h_deg <= 72)
    w[core] = 1.0
    lo = (h_deg > 35) & (h_deg < 43)
    w[lo] = (h_deg[lo] - 35) / 8
    hi = (h_deg > 72) & (h_deg < 80)
    w[hi] = (80 - h_deg[hi]) / 8
    return 0.5 - 0.5 * np.cos(np.pi * w)                      # smooth ease, no banding


def noyellow_cube(path: Path, n: int = 33) -> Path:
    """A .cube 3D LUT that turns yellows grey (luma kept) and touches nothing else."""
    if path.exists():
        return path
    g = np.linspace(0, 1, n)
    b, gr, r = np.meshgrid(g, g, g, indexing="ij")           # .cube order: red changes fastest
    rgb = np.stack([r, gr, b], -1).reshape(-1, 3)
    mx, mn = rgb.max(1), rgb.min(1)
    hue = np.array([colorsys.rgb_to_hsv(*p)[0] for p in rgb]) * 360
    chroma = mx - mn
    wt = _desat_weight(hue) * np.clip(chroma / 0.06, 0, 1)   # near-greys stay exactly as they are
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722])
    out = rgb + (luma[:, None] - rgb) * wt[:, None]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(f'TITLE "Insidir no yellow"\nLUT_3D_SIZE {n}\n')
        f.writelines(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n" for p in np.clip(out, 0, 1))
    return path


def cube_path() -> Path:
    return noyellow_cube(config.studio_home() / "cache" / "noyellow-v2.cube")


def lut_filter(cube: Path) -> str:
    """lut3d with the path escaped for FFmpeg's filter syntax (Windows drive colons included)."""
    p = cube.resolve().as_posix().replace("'", r"\'").replace(":", r"\:")
    return f"lut3d=file='{p}':interp=tetrahedral"


def overlay_position(w: int, h: int, corner: str = "top-left") -> str:
    """Inside the platform-safe area: clear of the status bar and the side buttons on phones."""
    mx = int(w * 0.045)
    my = int(h * (0.045 if h > w else 0.05))
    x = str(mx) if "left" in corner else f"W-w-{mx}"
    y = str(my) if "top" in corner else f"H-h-{my}"
    return f"x={x}:y={y}"


def lut_step() -> str:
    return f"format=gbrp,{lut_filter(cube_path())}"


def logo_parts(src: str, logo_idx: int, out: str, w: int, h: int, corner: str = "top-left",
               until: float | None = None) -> list[str]:
    """Filter parts that put the logo over [src]. `until` hides it from that time on (e.g. under
    an end card that already shows the full wordmark)."""
    enable = f":enable='lt(t,{until:.3f})'" if until else ""
    return [f"[{logo_idx}:v]format=rgba[lg_{out}]",
            f"[{src}][lg_{out}]overlay={overlay_position(w, h, corner)}:format=auto{enable},format=yuv420p[{out}]"]


def chain(src: str, logo_idx: int, out: str, w: int, h: int, corner: str = "top-left",
          until: float | None = None) -> list[str]:
    """No-yellow LUT, then the logo over it."""
    return [f"[{src}]{lut_step()}[ny_{out}]"] + logo_parts(f"ny_{out}", logo_idx, out, w, h, corner, until)


def apply(src: Path, out: Path, log=None, corner: str = "top-left", crf: int = 10) -> Path:
    """Stand-alone pass: logo + no-yellow on an existing video (audio copied)."""
    info = media.probe(src)
    w, h = info["width"], info["height"]
    logo = logo_png(out.parent / f"logo_{w}x{h}.png", w, h)
    parts = chain("0:v", 1, "v", w, h, corner)
    media.run(["-i", str(src), "-i", str(logo), "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)], log=log)
    if log:
        log("Insidir logo + no-yellow guard applied")
    return out
