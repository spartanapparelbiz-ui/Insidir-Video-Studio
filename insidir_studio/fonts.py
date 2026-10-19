"""Font catalogue: the typefaces a video's captions and headlines can use.

The first three are the fonts of insidir.com itself (web/assets/fonts in the Insidir repo):
Inter for the interface, Source Serif 4 for headlines and JetBrains Mono for data. The rest
are display faces that suit short-form video. All are SIL Open Font License 1.1 (commercial
use allowed); the licences are in insidir_studio/fonts/licenses.

The .ttf files are the published static weights converted from WOFF2 to TTF (a format change
only; the font data and names are untouched, as the OFL's Reserved Font Names require).

Two places draw text, and each needs the font found differently:
- libass (captions burned in by FFmpeg) matches the font's internal family name, so every
  entry names the exact internal family + bold flag of the file to use ("ass").
- Motion Canvas (the animated templates) runs in a browser, which gets @font-face rules for
  two aliases, "IVS Head" and "IVS Caption", one per weight, each pointing at the nearest file.
"""

from __future__ import annotations

from . import config

FONTS: dict[str, dict] = {
    # --- the fonts on insidir.com
    "inter": {"name": "Inter", "group": "insidir", "note": "Insidir's interface font",
              "files": {600: "Inter-SemiBold.otf", 700: "Inter-Bold.otf", 800: "Inter-ExtraBold.otf"},
              "ass": ("Inter", True)},
    "source-serif-4": {"name": "Source Serif 4", "group": "insidir", "note": "Insidir's headline serif",
                       "files": {600: "SourceSerif4-SemiBold.ttf", 700: "SourceSerif4-Bold.ttf", 900: "SourceSerif4-Black.ttf"},
                       "ass": ("Source Serif 4", True)},
    "jetbrains-mono": {"name": "JetBrains Mono", "group": "insidir", "note": "Insidir's data and filing font",
                       "files": {500: "JetBrainsMono-Medium.ttf", 700: "JetBrainsMono-Bold.ttf", 800: "JetBrainsMono-ExtraBold.ttf"},
                       "ass": ("JetBrains Mono ExtraBold", False), "scale": 0.86},
    # --- display faces for short-form video
    "montserrat": {"name": "Montserrat", "group": "display", "note": "Geometric, heavy: the classic caption look",
                   "files": {700: "Montserrat-Bold.ttf", 800: "Montserrat-ExtraBold.ttf", 900: "Montserrat-Black.ttf"},
                   "ass": ("Montserrat Thin Black", False), "scale": 0.94},
    "poppins": {"name": "Poppins", "group": "display", "note": "Round and friendly",
                "files": {600: "Poppins-SemiBold.ttf", 700: "Poppins-Bold.ttf", 800: "Poppins-ExtraBold.ttf"},
                "ass": ("Poppins ExtraBold", False), "scale": 0.94},
    "anton": {"name": "Anton", "group": "display", "note": "Tall condensed impact headlines",
              "files": {400: "Anton-Regular.ttf"}, "ass": ("Anton", False), "scale": 1.12},
    "bebas-neue": {"name": "Bebas Neue", "group": "display", "note": "All-caps condensed, cinematic",
                   "files": {400: "BebasNeue-Regular.ttf"}, "ass": ("Bebas Neue", False), "scale": 1.22},
    "archivo-black": {"name": "Archivo Black", "group": "display", "note": "Wide and punchy",
                      "files": {400: "ArchivoBlack-Regular.ttf"}, "ass": ("Archivo Black", False), "scale": 0.9},
    "space-grotesk": {"name": "Space Grotesk", "group": "display", "note": "Techy grotesk",
                      "files": {500: "SpaceGrotesk-Medium.ttf", 700: "SpaceGrotesk-Bold.ttf"},
                      "ass": ("Space Grotesk Light", True)},
    "permanent-marker": {"name": "Permanent Marker", "group": "display", "note": "Hand-written marker",
                         "files": {400: "PermanentMarker-Regular.ttf"}, "ass": ("Permanent Marker", False), "scale": 0.95},
    "patrick-hand": {"name": "Patrick Hand", "group": "display", "note": "Hand-drawn (the sketch templates' default)",
                     "files": {400: "PatrickHand-Regular.ttf"}, "ass": ("Patrick Hand", False), "scale": 1.1},
}

DEFAULT_CAPTION = "inter"
WEIGHTS = (400, 500, 600, 700, 800, 900)


def get(fid: str | None, default: str | None = DEFAULT_CAPTION) -> dict | None:
    if fid in FONTS:
        return {"id": fid, **FONTS[fid]}
    return get(default, None) if default else None


def nearest(f: dict, weight: int) -> str:
    """The file for a requested weight: the closest one, heavier on a tie (never faux bold)."""
    return f["files"][min(f["files"], key=lambda w: (abs(w - weight), -w))]


def web_faces(f: dict) -> dict[str, str]:
    """weight -> file name, for @font-face rules in the browser."""
    return {str(w): nearest(f, w) for w in WEIGHTS}


def preview_file(f: dict) -> str:
    return f["files"][max(f["files"])]


def catalogue() -> dict:
    return {fid: {"name": f["name"], "group": f["group"], "note": f["note"], "preview": preview_file(f)}
            for fid, f in FONTS.items()}


def files_exist() -> list[str]:
    return [n for f in FONTS.values() for n in f["files"].values() if not (config.FONTS_DIR / n).exists()]
