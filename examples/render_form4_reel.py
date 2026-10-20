"""Render a real, original Insidir Form 4 animated Reel for review.

This is a reproducible production smoke test, not sample stock footage.
Run from the repository root:
    python examples/render_form4_reel.py --engine kokoro
Set INSIDIR_STUDIO_HOME to move generated projects.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from insidir_studio import compliance, project, render

# A single slower narrative, not ten disconnected headline cards.
# 7 deliberate scenes: viewers, executives, analysts, and the actual meaning of SEC transaction codes.
STORYBOARD = [
    ("A headline says an executive bought shares. But did they really?", "DID THEY REALLY BUY?", "news"),
    ("The answer is in a public SEC Form 4. Look at the transaction code.", "CHECK THE FILING.", "filing"),
    ("P is an open-market purchase. A can mean a stock award.", "P IS NOT A.", "cash"),
    ("Same company, different transaction. The code tells you which.", "ONE LETTER CHANGES CONTEXT.", "search"),
    ("M can mark an option exercise. That's not an open-market purchase.", "AND THEN THERE'S M.", "option"),
    ("Executives, analysts, and investors can all check the same public filing.", "THREE READERS. ONE RECORD.", "people"),
    ("Insidir organizes the transactions and links to the original SEC record.", "DON'T GUESS. CHECK THE SOURCE.", "link"),
]


def build_project():
    p = project.new(
        "Form 4 - the headline is not the filing",
        {
            "mode": "animated",
            "template": "editorial-story",
            "topic": "What a public Form 4 filing actually shows",
            "target_seconds": 33,
            "audience": "Everyday people trying to understand financial filings",
            "angle": "Considered, personal, source-first financial research",
            "cta": "Read the public records at insidir.com",
        },
    )
    d = project.project_dir(p["id"])
    p["voice"]["voice"] = "studio_male"
    p["voice"]["speed"] = 0.93
    p["style"].update({"quality": "standard", "captions": "auto", "end_card": True,
                       "sfx": True, "music_bed": True, "caption_highlight": "#FFFFFF", "caption_size": 0.80, "caption_words": 3, "logo_overlay": False})
    p["script"] = {
        "title": "THE HEADLINE IS NOT THE FILING",
        "facts_used": ["form4_public", "purchases_apart", "links_to_filing"],
        "beats": [
            {
                "id": f"b{i}",
                "text": spoken,
                "overlay": headline,
                "visual": {"kind": "doodle", "icon": picture,
                           "pose": ["think", "point", "explain"][i % 3]},
            }
            for i, (spoken, headline, picture) in enumerate(STORYBOARD, 1)
        ],
    }
    errors = [x for x in compliance.lint(p["script"], compliance.load_facts(), [])
              if x.get("level") == "error"]
    if errors:
        raise RuntimeError("Storyboard failed factual checks:\n" + json.dumps(errors, indent=2))
    project.save(d, p)
    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["kokoro", "test-tone"], default="kokoro")
    parser.add_argument("--destination", type=Path, default=ROOT / "artifacts")
    a = parser.parse_args()
    d = build_project()
    print(f"Rendering {d / 'project.json'}", flush=True)
    result = render.render(d, engine_name=a.engine)
    outputs = sorted((d / "out").glob("*.mp4"), key=lambda x: x.stat().st_mtime)
    if not outputs:
        raise RuntimeError("Renderer reported success but did not create an MP4")
    a.destination.mkdir(parents=True, exist_ok=True)
    out = a.destination / "insidir-form4-first-reel.mp4"
    shutil.copy2(outputs[-1], out)
    (a.destination / "render-report.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print("Rendered output:", out.resolve(), flush=True)
    print("Report:", json.dumps({k: result.get(k) for k in ("duration", "width", "height", "render_seconds")}), flush=True)


if __name__ == "__main__":
    main()
