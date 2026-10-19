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
# 8 distinct scenes; Dot the Insidir dot-figure follows the evidence.
STORYBOARD = [
    ("A headline says an insider traded. But what actually happened?", "HEADLINES MISS CONTEXT", "document"),
    ("Meet Dot. Dot checks the public Form 4 instead.", "OPEN THE SOURCE", "form"),
    ("One filing can show a purchase, sale, award, or option exercise.", "DIFFERENT TRANSACTIONS", "list"),
    ("Those aren't the same thing. Transaction codes tell them apart.", "READ THE CODE", "tag"),
    ("That's where context starts, not with a headline.", "CONTEXT MATTERS", "eye"),
    ("Insidir separates the activity into plain language.", "LESS NOISE. MORE CLARITY.", "people"),
    ("And links each transaction back to the original SEC filing.", "BACK TO THE SOURCE", "link"),
    ("Follow the source. Understand the story. That's Insidir.", "THE RECORD COMES FIRST", "document"),
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
