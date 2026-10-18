"""Scripts with Claude.

Free path (default): the studio builds a complete prompt; you paste it into Claude
(claude.ai, free plan works) and paste the reply back. No API key, no billing.

Optional path: if you already have an Anthropic API key and turn it on in Settings,
the studio can send the same prompt for you. API use is billed by Anthropic, so it is
off by default and never required.

Offline path: a built-in writer that assembles a script from approved facts only.
"""

from __future__ import annotations

import json
import re

from . import compliance

SCHEMA_EXAMPLE = {
    "title": "How to read an insider trade in 30 seconds",
    "facts_used": ["form4_deadline", "links_to_filing"],
    "beats": [
        {"id": "b1", "text": "Hook sentence spoken in the first 2 seconds.", "visual": {"kind": "screen", "shot": "what the viewer sees"}, "overlay": "3-5 word headline"},
        {"id": "b2", "text": "...", "visual": {"kind": "screen", "shot": "..."}, "overlay": ""},
    ],
}

HOOKS = {
    "question": "Open with a direct question the viewer has asked themselves.",
    "myth": "Open by correcting a common misconception about insider trades (truthfully).",
    "how-to": "Open by promising a concrete skill the video teaches.",
    "pov": "Open with a 'POV:' style relatable moment, without claiming personal results.",
}


def build_prompt(proj: dict, facts: dict) -> str:
    brief = proj.get("brief", {})
    secs = int(brief.get("target_seconds") or 28)
    secs = min(33, max(21, secs))
    words_lo, words_hi = int(secs * 1.95), int(secs * 2.3)
    assets = proj.get("assets", [])
    footage = "\n".join(
        f"- {a['id']}: {a.get('label') or a['file']} ({a['role']}, {a['type']}"
        + (f", {a['duration']:.0f}s" if a.get("duration") else "")
        + (", genuine Insidir recording" if a.get("genuine") else "")
        + (", AI-generated presenter" if a.get("ai_generated") and a["role"] == "presenter" else "")
        + (f"; notes: {a['notes']}" if a.get("notes") else "") + ")"
        for a in assets if a["role"] != "music"
    ) or "- (no footage uploaded yet: suggest shots of the real Insidir product)"
    fact_lines = "\n".join(f'- {f["id"]}: {f["text"]}' for f in facts.get("facts", []))
    has_presenter = any(a["role"] == "presenter" for a in assets)
    hook = HOOKS.get(brief.get("hook_style") or "question", HOOKS["question"])
    return f"""You are writing a short vertical UGC-style video script for Insidir, a research tool for reading SEC insider-trading filings (Form 4).

VIDEO
- Topic: {brief.get('topic') or 'how to read insider trades with Insidir'}
- Angle: {brief.get('angle') or 'practical, curious, plain-spoken'}
- Audience: {brief.get('audience') or 'retail investors who do their own research'}
- Length: {secs} seconds of narration, so {words_lo}-{words_hi} words in total.
- Hook: {hook}
- Call to action: {brief.get('cta') or 'Try Insidir'}
- Narration is read by an AI voice{'; an AI-generated presenter may appear on screen' if has_presenter else ''}. Both are labelled as AI in the video.

FOOTAGE AVAILABLE (refer to these ids in visual.asset when one fits; otherwise leave asset out):
{footage}

APPROVED FACTS (the only claims you may make; cite their ids in facts_used):
{fact_lines}

RULES (a script that breaks any of these is rejected automatically):
1. Every number you write must appear in an approved fact. No other figures, percentages, prices, dates or counts.
2. No promises or hints of returns, profits, beating the market, or getting rich. No "guaranteed", "risk-free", "insider tips", "secret", "before Wall Street".
3. Never tell the viewer to buy, sell or short anything, and never predict a price. Do not name a stock as a pick.
4. Form 4s are public filings. Never imply nonpublic or secret information.
5. No first-person testimonials or personal results ("I made", "I've been using", "my portfolio"). The voice is AI, so these would be made up. Speak to the viewer ("you") or describe what is on screen.
6. Do not claim real-time data. Prices are delayed; filings are imported on a schedule.
7. Do not write a disclaimer; the video adds "Research tool. Not investment advice." itself.
8. Sound like a real person talking to a friend: short sentences, contractions, one idea per beat. No hashtags, emojis or stage directions inside "text".

STRUCTURE
- 5 to 8 beats. Beat 1 is the hook (under 12 words). The last beat is the call to action.
- Each beat: "text" (spoken words), "visual" with "kind" one of screen | image | presenter | title, an optional "asset" id from the footage list, a short "shot" description, and an optional "overlay" headline of 2-5 words shown on screen (use for 2-4 beats, not all).

Reply with ONLY a JSON object in this shape, no prose before or after:
{json.dumps(SCHEMA_EXAMPLE, indent=2)}
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in the reply. Ask Claude to reply with only the JSON.")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("The JSON in the reply is incomplete.")


def normalize(script: dict, assets: list[dict] | None = None) -> dict:
    ids = {a["id"] for a in assets or []}
    beats = []
    for i, b in enumerate(script.get("beats") or []):
        if isinstance(b, str):
            b = {"text": b}
        text = re.sub(r"\s+", " ", str(b.get("text") or b.get("narration") or "")).strip()
        text = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text).strip()  # drop stage directions
        if not text:
            continue
        vis = b.get("visual") if isinstance(b.get("visual"), dict) else {"shot": str(b.get("visual") or "")}
        kind = vis.get("kind") if vis.get("kind") in ("screen", "image", "presenter", "title") else "screen"
        asset = vis.get("asset") if vis.get("asset") in ids else None
        beats.append({
            "id": f"b{len(beats) + 1}",
            "text": text,
            "visual": {"kind": kind, "asset": asset, "shot": str(vis.get("shot") or "")[:200],
                       "start": vis.get("start"), "focus": vis.get("focus") or [0.5, 0.5],
                       "zoom": vis.get("zoom") or 1.0},
            "overlay": str(b.get("overlay") or "")[:40],
        })
    if not beats:
        raise ValueError("The script has no spoken beats.")
    facts_used = [str(f) for f in (script.get("facts_used") or []) if isinstance(f, (str, int))]
    return {"title": str(script.get("title") or "")[:120], "beats": beats, "facts_used": facts_used}


def parse_reply(text: str, assets: list[dict] | None = None) -> dict:
    return normalize(_extract_json(text), assets)


def call_api(prompt: str, model: str, api_key: str | None = None) -> str:
    """Optional, billed by Anthropic. Requires `pip install anthropic` and a key."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("The optional 'anthropic' package is not installed (pip install anthropic).") from e
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=model or "claude-opus-5-5",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise RuntimeError("Anthropic rejected the API key.") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("Anthropic rate limit reached; try again shortly or use the copy/paste path.") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("Could not reach the Anthropic API.") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Anthropic API error {e.status_code}.") from e
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request. Adjust the brief and try again.")
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------------ offline writer

TEMPLATES = [
    {
        "title": "How to read an insider trade",
        "facts_used": ["form4_deadline", "purchases_apart", "links_to_filing", "personnel_files"],
        "beats": [
            ("Ever wonder what a company's own executives do with its stock?", "screen", "", "Insiders file too"),
            ("When insiders trade, they report it on a Form 4, usually within two business days.", "screen", "", "Form 4 · 2 business days"),
            ("Insidir puts those filings in one place: who bought, who sold, and when.", "screen", "", ""),
            ("Real purchases are kept apart from awards and option exercises.", "screen", "", "Buys vs. awards"),
            ("Tap a name for their file, with every filing linked.", "screen", "", ""),
            ("Read the filings yourself at insidir dot com.", "screen", "", ""),
        ],
    },
    {
        "title": "Follow the people who file",
        "facts_used": ["form4_public", "follow_people", "import_cadence", "links_to_filing"],
        "beats": [
            ("What if a company's directors' trades showed up on your home screen?", "screen", "", ""),
            ("Form 4 filings are public records. Anyone can read them.", "screen", "", "Public SEC filings"),
            ("Insidir imports new ones from EDGAR every 15 minutes, in plain words.", "screen", "", "Every 15 minutes"),
            ("Follow the insiders you care about, and their trades show up first.", "screen", "", ""),
            ("Every line links to the original filing, so you can check it.", "screen", "", ""),
            ("Do your own research with Insidir.", "screen", "", "insidir.com"),
        ],
    },
    {
        "title": "Try it for a dollar",
        "facts_used": ["company_reports", "purchases_apart", "trial"],
        "beats": [
            ("Stop guessing what the people running a company do with its stock.", "screen", "", ""),
            ("Insidir has a report for every company in the SEC's ticker list.", "screen", "", "Every listed company"),
            ("Open insider activity: open-market buys and sales, apart from awards.", "screen", "", ""),
            ("Each code comes with the SEC's own meaning, in plain words.", "screen", "", ""),
            ("Try it for 3 days for $1, then it's $39 a month. Cancel any time.", "title", "", "3 days for $1"),
        ],
    },
]


def template_script(proj: dict, facts: dict, variant: int = 0) -> dict:
    known = {f["id"] for f in facts.get("facts", [])}
    usable = [t for t in TEMPLATES if set(t["facts_used"]) <= known] or TEMPLATES[:1]
    t = usable[variant % len(usable)]
    script = {
        "title": t["title"],
        "facts_used": [f for f in t["facts_used"] if f in known],
        "beats": [{"text": text, "visual": {"kind": kind, "asset": asset or None}, "overlay": ov}
                  for text, kind, asset, ov in t["beats"]],
    }
    return normalize(script, proj.get("assets", []))


def lint_reply(script: dict, proj: dict) -> list[dict]:
    return compliance.lint(script, compliance.load_facts(), proj.get("assets", []))
