"""Prompt engine: turns a short idea into the detailed, structured prompt open video models
follow best, and shows the user exactly what will be sent.

Open models (Wan, LTX, Hunyuan) are trained on long, literal captions: subject and appearance,
then action, then setting, lighting, camera and lens, then style. Short prompts leave all of
that to chance; this fills the gaps without inventing story content, flags contradictions, and
maps "how closely to follow the prompt" onto guidance scale.

Deterministic and local (no model needed). The optional Claude path in the UI can rewrite the
prompt further; whatever is used is shown in full and is editable.
"""

from __future__ import annotations

import re

from .models import WAN_NEGATIVE

CAMERA = {
    "static": "locked-off static camera on a tripod",
    "push_in": "slow cinematic push-in, the camera dollies smoothly toward the subject",
    "pull_out": "slow pull-back, the camera dollies away to reveal the scene",
    "dolly_zoom": "dolly zoom (vertigo effect): the camera moves back while zooming in, the background stretches behind the subject",
    "orbit": "smooth orbit shot, the camera circles around the subject at a steady height",
    "orbit_360": "full 360-degree orbit around the subject, steady speed",
    "drone": "aerial drone flythrough, gliding forward high above the scene",
    "fpv": "FPV drone shot, fast agile flight close to the ground, banking through gaps",
    "crash_zoom": "sudden crash zoom into the subject",
    "tracking": "tracking shot, the camera follows alongside the subject at the same speed",
    "handheld": "handheld camera with subtle natural shake, documentary feel",
    "crane": "crane shot rising up and over the scene",
    "jib_down": "jib shot descending from above to eye level",
    "bullet_time": "bullet time: the action freezes while the camera sweeps around it",
    "hyperlapse": "hyperlapse, the camera travels quickly through the scene while time speeds up",
    "gimbal": "smooth gimbal shot gliding forward, perfectly stable",
    "rack_focus": "rack focus from the foreground to the subject",
    "macro": "extreme macro close-up, very shallow depth of field",
    "high_speed": "high-speed action shot, fast whip pans, motion blur, slow-motion moments",
    "pan_left": "slow pan to the left", "pan_right": "slow pan to the right",
    "tilt_up": "slow tilt up", "tilt_down": "slow tilt down",
}
SPEED = {"slow": "slow, smooth", "medium": "steady", "fast": "fast, energetic"}
LENSES = {
    "14": "14mm ultra-wide lens", "24": "24mm wide-angle lens", "35": "35mm lens, natural perspective",
    "50": "50mm lens", "85": "85mm portrait lens, compressed background", "135": "135mm telephoto lens",
    "anamorphic": "anamorphic lens, oval bokeh, horizontal lens flares, 2.39:1 cinematic framing",
}
LIGHTING = {
    # (no golden hour / candlelight: Insidir videos never go yellow)
    "dusk": "dusk after sunset, rose-pink sky, soft low light, long soft shadows",
    "blue_hour": "blue hour, cool ambient light, city lights coming on",
    "overcast": "soft overcast daylight, even diffuse light",
    "noon": "hard midday sun, crisp shadows",
    "night_neon": "night, neon signs reflecting on wet streets",
    "studio": "three-point studio lighting, soft key light, rim light",
    "low_key": "low-key dramatic lighting, deep shadows, single hard key light",
    "practical": "practical lights in frame, neutral white lamps",
}
STYLES = {
    "photoreal": "photorealistic, shot on a cinema camera, natural skin texture, realistic materials, true-to-life colour",
    "film": "35mm film look, fine grain, rich colour, organic highlights",
    "documentary": "documentary realism, natural light, candid",
    "commercial": "high-end commercial, clean, polished, glossy",
    "music_video": "music video aesthetic, bold colour, dramatic light",
    "noir": "black and white film noir, high contrast",
    "anime": "anime style, cel shading", "3d": "3D animated film style, stylised characters",
}
QUALITY = ("high detail, sharp focus, natural motion, consistent anatomy, temporally stable, no flicker")

# words that pull in opposite directions in one prompt
CONFLICTS = [
    (r"\bnight\b|\bmidnight\b", r"\b(noon|midday|sunny day|daylight|dusk)\b", "night vs daytime lighting"),
    (r"\bstatic\b|\blocked[- ]off\b|\btripod\b", r"\b(orbit|dolly|tracking|drone|pan|crash zoom|handheld)\b", "a static camera and a moving camera"),
    (r"\bslow[- ]motion\b|\bslow motion\b", r"\b(hyperlapse|time-?lapse|sped up)\b", "slow motion and time-lapse"),
    (r"\bblack and white\b|\bmonochrome\b", r"\b(vibrant|colorful|colourful|neon)\b", "black and white and vivid colour"),
    (r"\bclose[- ]up\b|\bmacro\b", r"\b(wide shot|aerial|establishing shot)\b", "a close-up and a wide shot in one shot"),
    (r"\bphotorealistic\b|\brealistic\b", r"\b(anime|cartoon|cel[- ]shad)", "photorealism and a cartoon style"),
]


def conflicts(text: str) -> list[str]:
    t = text.lower()
    out = [why for a, b, why in CONFLICTS if re.search(a, t) and re.search(b, t)]
    if re.search(r"\b(yellow|golden|gold|amber|mustard|lemon)\b", t):
        out.append("No yellow in Insidir videos: anything yellow comes out neutral in the final video")
    return out


def guidance_for(adherence: float, base: float) -> float:
    """adherence 0..1 (loose..strict) mapped around the model's recommended guidance."""
    a = min(1.0, max(0.0, adherence))
    return round(base * (0.7 + 0.6 * a), 2)


def enhance(prompt: str, *, camera: list[str] | None = None, camera_speed: str = "medium", lens: str = "",
            lighting: str = "", style: str = "photoreal", motion: float = 0.5, characters: list[dict] | None = None,
            shot: str = "", extra_negative: str = "", enhance_text: bool = True) -> dict:
    """Build the final prompt. Returns {prompt, negative, conflicts, parts} - all shown to the user."""
    base = re.sub(r"\s+", " ", (prompt or "").strip())
    parts: list[str] = []
    if characters:
        # describe each persistent character the same way in every shot: identity drift starts in the text
        for c in characters:
            if c.get("description"):
                parts.append(f"{c['name']}: {c['description']}")
    parts.append(base.rstrip(".") + ".")
    if enhance_text:
        if shot:
            parts.append(shot.rstrip(".") + ".")
        cams = [CAMERA[c] for c in (camera or []) if c in CAMERA]
        if cams:
            parts.append(f"Camera: {SPEED.get(camera_speed, 'steady')} " + ", then ".join(cams) + ".")
        if lens in LENSES:
            parts.append(LENSES[lens].capitalize() + ".")
        if lighting in LIGHTING:
            parts.append(LIGHTING[lighting].capitalize() + ".")
        mv = ("subtle, gentle movement" if motion < 0.35 else "dynamic, energetic movement" if motion > 0.7
              else "natural, fluid movement")
        parts.append(f"Motion: {mv}, physically plausible, correct gravity and momentum.")
        if style in STYLES:
            parts.append(STYLES[style].capitalize() + ".")
        if style in ("photoreal", "film", "documentary", "commercial"):
            parts.append(QUALITY.capitalize() + ".")
    final = " ".join(parts)
    neg = WAN_NEGATIVE + (", " + extra_negative.strip() if extra_negative.strip() else "")
    if style in ("anime", "3d"):
        neg = neg.replace("style, artwork, painting, ", "")
    return {"prompt": final, "negative": neg, "conflicts": conflicts(final), "parts": parts}
