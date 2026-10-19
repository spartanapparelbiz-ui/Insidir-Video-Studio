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

from . import animate, compliance
from .ugc import MOVES

SCHEMA_EXAMPLE = {
    "title": "How to read an insider trade in 30 seconds",
    "facts_used": ["form4_deadline", "links_to_filing"],
    "beats": [
        {"id": "b1", "text": "Hook sentence spoken in the first 2 seconds.", "visual": {"kind": "screen", "shot": "what the viewer sees"}, "overlay": "3-5 word headline"},
        {"id": "b2", "text": "...", "visual": {"kind": "screen", "shot": "..."}, "overlay": ""},
    ],
}

UGC_EXAMPLE = {
    "title": "How I read an insider trade",
    "facts_used": ["form4_deadline"],
    "beats": [
        {"id": "b1", "text": "Hook line said straight to camera.", "visual": {"layout": "face", "shot": ""}, "overlay": ""},
        {"id": "b2", "text": "...", "visual": {"layout": "split", "asset": "a1b2c3d4", "shot": "the filing feed"}, "overlay": "3-5 word headline"},
    ],
}

PEOPLE_EXAMPLE = {
    "title": "What executives have to tell you",
    "facts_used": ["form4_deadline"],
    "beats": [
        {"id": "b1", "text": "Hook line.", "visual": {"layout": "broll", "search": "man checking stock app at night"}, "overlay": ""},
        {"id": "b2", "text": "...", "visual": {"layout": "screen", "asset": "a1b2c3d4", "shot": "the filing feed"}, "overlay": "Form 4"},
    ],
}

HOOKS = {
    "question": "Open with a sharp question that opens a curiosity gap the video pays off later.",
    "myth": "Open by correcting a common misconception about insider trades (truthfully).",
    "how-to": "Open by promising a concrete skill the video teaches.",
    "pov": "Open with a 'POV:' style relatable moment, without claiming personal results.",
}


VOICE_LINE = {
    "demo": "Narration is read by an AI voice",
    "animated": "Narration is read by an AI voice",
    "photo_avatar": "Narration is read by an AI voice and lip-synced by an AI-generated presenter, who is labelled as AI on screen",
    "ugc": "These are talking points the creator will say on camera in their own words and voice",
    "people": "Narration is read by an AI voice over licensed stock footage of real people (b-roll, never shown speaking or endorsing anything)",
}
RULE5_AI = ('5. No first-person testimonials or personal results ("I made", "I\'ve been using", "my portfolio"). '
            'The voice is AI, so these would be made up. Speak to the viewer ("you") or describe what is on screen.')
RULE5_REAL = ('5. A real person says these lines, so first person is fine for how they research ("I check the Form 4 first"), '
              'but never personal results or returns ("I made", "my portfolio grew"). Mark nothing as a testimonial the '
              'creator has not actually experienced.')


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
    mode = proj.get("mode") or "demo"
    return f"""You are writing a short vertical UGC-style video script for Insidir, a research tool for reading SEC insider-trading filings (Form 4).

VIDEO
- Topic: {brief.get('topic') or 'how to read insider trades with Insidir'}
- Angle: {brief.get('angle') or 'practical, curious, plain-spoken'}
- Audience: {brief.get('audience') or 'retail investors who do their own research'}
- Length: {secs} seconds of narration, so {words_lo}-{words_hi} words in total.
- Hook: {hook}
- Call to action: {brief.get('cta') or 'Try Insidir'}
- {VOICE_LINE.get(mode, VOICE_LINE['demo']) + ('; an AI-generated presenter may appear on screen and is labelled as AI' if has_presenter and mode == 'demo' else '')}. Write "Insidir" as spelled; it is pronounced "insider".

FOOTAGE AVAILABLE (refer to these ids in visual.asset when one fits; otherwise leave asset out):
{footage}

APPROVED FACTS (the only claims you may make; cite their ids in facts_used):
{fact_lines}

RULES (a script that breaks any of these is rejected automatically):
1. Every number you write must appear in an approved fact. No other figures, percentages, prices, dates or counts.
2. No promises or hints of returns, profits, beating the market, or getting rich. No "guaranteed", "risk-free", "insider tips", "secret", "before Wall Street".
3. Never tell the viewer to buy, sell or short anything, and never predict a price. Do not name a stock as a pick.
4. Form 4s are public filings. Never imply nonpublic or secret information.
{RULE5_REAL if mode == 'ugc' else RULE5_AI}
6. Do not claim real-time data. Prices are delayed; filings are imported on a schedule.
7. Do not write a disclaimer; the video adds "Research tool. Not investment advice." itself.
8. Sound like a real person talking to a friend: short sentences, contractions, one idea per beat. No hashtags, emojis or stage directions inside "text".

{structure_for(proj)}
"""


def structure_for(proj: dict) -> str:
    mode = proj.get("mode") or "demo"
    if mode == "ugc":
        return """STRUCTURE
- These are lines for a teleprompter. 5 to 8 beats, each one or two short spoken sentences.
- Beat 1 is the hook (under 12 words), said straight to camera. The last beat is the call to action.
- Write how people actually talk: contractions, small pauses, no corporate words.
- "visual" may suggest a "layout": face (talking head), split (Insidir screen on top, face below), bubble (Insidir screen with the face in a circle) or screen (screen only), plus a "shot" of what the screen should show.

Reply with ONLY a JSON object in this shape, no prose before or after:
""" + json.dumps(UGC_EXAMPLE, indent=2)
    if mode == "people":
        return """STRUCTURE
- 6 to 9 short beats (1.5-3.5 seconds each). Beat 1 is the hook (under 12 words). The last beat is the call to action.
- Each beat is shown over footage of real people (stock b-roll) or the real Insidir product. "visual" has:
  "layout": broll (real people) or screen (the Insidir app, with an "asset" id from the footage list),
  "search": for broll, 2-5 plain words describing the shot to find on a stock site, e.g. "woman reading phone at night",
  "investor at laptop", "busy city crosswalk", "man taking notes coffee shop". Concrete, filmable, no logos or brands.
- The people are actors in stock footage: never write lines that put words in their mouths or imply they are customers.
- An optional "overlay" headline of 2-5 words on 2-3 beats.

Reply with ONLY a JSON object in this shape, no prose before or after:
""" + json.dumps(PEOPLE_EXAMPLE, indent=2)
    if mode == "photo_avatar":
        return """STRUCTURE
- 5 to 8 beats. Beat 1 is the hook (under 12 words), said to camera by the presenter. The last beat is the call to action.
- Each beat: "text" (spoken words) and "visual" with "layout" one of face | split | bubble | screen, an "asset" id from the footage list for every layout except face, a "shot" of what the screen shows, and an optional "overlay" headline of 2-5 words (use for 2-3 beats).
- Mix layouts: start on face, show the real product in the middle, end on face.

Reply with ONLY a JSON object in this shape, no prose before or after:
""" + json.dumps(UGC_EXAMPLE, indent=2)
    if mode != "animated":
        return f"""STRUCTURE
- 5 to 8 beats. Beat 1 is the hook (under 12 words). The last beat is the call to action.
- Each beat: "text" (spoken words), "visual" with "kind" one of screen | image | presenter | title, an optional "asset" id from the footage list, a short "shot" description, and an optional "overlay" headline of 2-5 words shown on screen (use for 2-4 beats, not all).

Reply with ONLY a JSON object in this shape, no prose before or after:
{json.dumps(SCHEMA_EXAMPLE, indent=2)}"""
    tid = proj.get("template") or "dot-explainer"
    t = animate.TEMPLATES.get(tid, animate.TEMPLATES["dot-explainer"])
    example = {
        "title": "How to read an insider trade",
        "facts_used": ["form4_deadline"],
        "beats": [
            {"id": "b1", "text": "Hook sentence.", "overlay": "Short headline",
             "visual": {"icon": "eye", "pose": "wave", "label": "", "emphasis": "", "asset": None, "shot": ""}},
            {"id": "b2", "text": "...", "overlay": "...",
             "visual": {"icon": "calendar", "pose": "point", "label": "", "emphasis": "2 business days", "asset": None, "shot": ""}},
        ],
    }
    return f"""ANIMATION TEMPLATE: {t['name']} ({tid})
{t['description']} The narrator is the Insidir dot figure, a cartoon made of the dots in Insidir's "i" logo, drawn in a hand-drawn chalk style.
{t['prompt']}

STRUCTURE
- 5 to 7 beats. Beat 1 is the hook (under 12 words). The last beat is the call to action.
- Every beat has "text" (spoken words) and "overlay": a 2-5 word headline drawn on screen.
- "visual" fields: "icon" one of {', '.join(animate.ICONS)}; "pose" for the dot figure, one of {', '.join(animate.POSES)}; "label" ({'MYTH or FACT' if tid == 'myth-fact' else 'leave empty'}); "emphasis" (an approved figure only, or empty); "asset" (a footage id, or null); "shot" (what to circle or show).
- On-screen words follow the same rules as the narration.

Reply with ONLY a JSON object in this shape, no prose before or after:
{json.dumps(example, indent=2)}"""


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
                       "zoom": vis.get("zoom") or 1.0,
                       "icon": vis.get("icon") if vis.get("icon") in animate.ICONS else "",
                       "pose": vis.get("pose") if vis.get("pose") in animate.POSES else "",
                       "label": str(vis.get("label") or "").strip().upper()[:12],
                       "emphasis": str(vis.get("emphasis") or "").strip()[:28],
                       "layout": vis.get("layout") if vis.get("layout") in ("face", "split", "bubble", "screen", "broll") else "",
                       "search": str(vis.get("search") or "").strip()[:60],
                       "move": vis.get("move") if vis.get("move") in MOVES else ""},
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


# Offline drafts for the animated templates: (text, headline, icon, pose, label, emphasis, use_asset)
ANIMATED_DRAFTS = {
    "avatar-host": {
        "title": "What insiders have to tell you",
        "facts_used": ["form4_deadline", "form4_public", "purchases_apart", "links_to_filing"],
        "beats": [
            ("Want to know when executives buy their own stock?", "Insiders file too", "eye", "wave", "", "", False),
            ("They have to report it on a Form 4.", "Form 4", "form", "explain", "", "", False),
            ("Usually within two business days.", "The deadline", "clock", "point", "", "2 business days", False),
            ("And it's public. Anyone can read it.", "Public record", "", "point", "", "", True),
            ("Insidir keeps real buys apart from awards.", "Real buys only", "", "point", "", "", True),
            ("Every line links to the original filing.", "Check the source", "link", "think", "", "", False),
            ("Go read them yourself at insidir dot com.", "insidir.com", "magnifier", "cheer", "", "", False),
        ],
    },
    "chat": {
        "title": "Wait, insiders have to report that?",
        "facts_used": ["form4_deadline", "form4_public", "purchases_apart", "links_to_filing"],
        "beats": [
            ("Wait, do executives have to say when they buy their own stock?", "", "", "", "THEM", "", False),
            ("Yep. It's called a Form 4, and it's public.", "", "", "", "ME", "", False),
            ("How fast?", "", "", "", "THEM", "", False),
            ("Usually within two business days.", "Form 4 deadline", "", "", "ME", "2 business days", False),
            ("Where do I even find those?", "", "", "", "THEM", "", False),
            ("Insidir puts them in one feed, buys apart from awards.", "", "", "", "ME", "", True),
            ("And every line links to the real filing. Try insidir dot com.", "", "", "", "ME", "", False),
        ],
    },
    "viral": {
        "title": "The trades executives have to report",
        "facts_used": ["form4_deadline", "form4_public", "purchases_apart", "links_to_filing"],
        "beats": [
            ("When a CEO buys their own stock, they have to tell everyone.", "They have to tell you", "eye", "", "", "", False),
            ("It's called a Form 4.", "Form 4", "form", "", "", "", False),
            ("And it's due within two business days.", "The deadline", "clock", "", "", "2 business days", False),
            ("It's public. Anyone can read it.", "Public record", "", "", "", "", True),
            ("Insidir keeps real buys apart from awards and option exercises.", "Real buys only", "", "", "", "", True),
            ("Every line links to the original filing.", "Check the source", "link", "", "", "", False),
            ("Read them yourself at insidir dot com.", "insidir.com", "magnifier", "", "", "", False),
        ],
    },
    "dot-explainer": {
        "title": "Insiders file too",
        "facts_used": ["form4_deadline", "form4_public", "purchases_apart", "links_to_filing"],
        "beats": [
            ("Ever wonder what a company's own executives do with its stock?", "Insiders file too", "eye", "wave", "", "", False),
            ("When insiders trade their shares, they report it on a Form 4, usually within two business days.", "Form 4", "form", "point", "", "2 business days", False),
            ("Those filings are public. Anyone can read them on EDGAR.", "Public records", "building", "explain", "", "", False),
            ("Insidir puts them in one place, buys apart from awards.", "One place", "list", "point", "", "", False),
            ("Every line links to the original filing.", "Check the source", "link", "think", "", "", False),
            ("Do your own research at insidir dot com.", "Do your own research", "magnifier", "cheer", "", "", False),
        ],
    },
    "myth-fact": {
        "title": "Insider filing myths",
        "facts_used": ["form4_public", "form4_deadline", "purchases_apart"],
        "beats": [
            ("Let's clear up what insider filings really are.", "Insider filings", "question", "wave", "", "", False),
            ("Myth: insider filings are secret tips for a lucky few.", "Insider filings are secret", "lock", "think", "MYTH", "", False),
            ("False. Form 4s are public SEC records, and anyone can read them.", "They're public records", "building", "pointleft", "FACT", "", False),
            ("Myth: you only hear about a trade months later.", "You hear months later", "calendar", "think", "MYTH", "", False),
            ("Not true. Most trades must be reported within two business days.", "2 business days", "clock", "pointleft", "FACT", "", False),
            ("Insidir lays those filings out in plain words. Read them at insidir dot com.", "Read the filings", "magnifier", "cheer", "", "", False),
        ],
    },
    "steps": {
        "title": "Read an insider trade",
        "facts_used": ["company_reports", "purchases_apart", "personnel_files", "links_to_filing"],
        "beats": [
            ("Here's how to read an insider trade, step by step.", "Read an insider trade", "", "wave", "", "", False),
            ("First, open a company and go to insider activity.", "Open insider activity", "", "pointleft", "", "", False),
            ("Next, look for open-market buys and sales, not awards or option exercises.", "Find open-market trades", "", "pointleft", "", "", False),
            ("Then check who filed it. Every reporting person has their own file.", "Check who filed", "", "pointleft", "", "", False),
            ("Finally, open the original SEC filing and read it yourself.", "Open the filing", "", "pointleft", "", "", False),
            ("That's it. Try it at insidir dot com.", "Try Insidir", "", "cheer", "", "", False),
        ],
    },
    "big-number": {
        "title": "How fast insider trades show up",
        "facts_used": ["form4_deadline", "import_cadence", "links_to_filing", "trial"],
        "beats": [
            ("How fast do you find out when an insider trades?", "How fast?", "clock", "think", "", "", False),
            ("Insiders usually have two business days to report a trade on a Form 4.", "The deadline", "calendar", "pointup", "", "2 business days", False),
            ("Insidir imports new filings from EDGAR every 15 minutes.", "New filings", "cabinet", "pointup", "", "15 minutes", False),
            ("Each one is written in plain words, with a link to the source.", "Plain words", "link", "explain", "", "", False),
            ("Try it for 3 days for $1, then it's $39 a month. Cancel any time.", "Try it", "tag", "cheer", "", "$1 for 3 days", False),
        ],
    },
    "screen-sketch": {
        "title": "Insidir, up close",
        "facts_used": ["purchases_apart", "personnel_files", "links_to_filing"],
        "beats": [
            ("Here's what insider trading data looks like in Insidir.", "Insider activity", "laptop", "wave", "", "", True),
            ("Each row is one line from a Form 4: who traded, and when.", "One row, one filing", "form", "pointleft", "", "", True),
            ("Open-market buys and sales are kept apart from awards and option exercises.", "Buys vs. awards", "list", "pointleft", "", "", True),
            ("Tap a person and you get their file, built from public filings.", "Their file", "people", "pointleft", "", "", True),
            ("See it for yourself at insidir dot com.", "insidir.com", "laptop", "cheer", "", "", False),
        ],
    },
}


def animated_draft(proj: dict, facts: dict) -> dict:
    tid = proj.get("template") or "dot-explainer"
    d = ANIMATED_DRAFTS.get(tid, ANIMATED_DRAFTS["dot-explainer"])
    known = {f["id"] for f in facts.get("facts", [])}
    footage = sorted([a for a in proj.get("assets", []) if a.get("role") in ("screen", "image") and a.get("rights_confirmed")],
                     key=lambda a: (not a.get("genuine"), a["type"] != "image"))
    beats = []
    k = 0
    for text, headline, icon, pose, label, emph, use_asset in d["beats"]:
        asset = None
        if use_asset and footage:
            asset = footage[k % len(footage)]["id"]
            k += 1
        beats.append({"text": text, "overlay": headline,
                      "visual": {"kind": "screen", "asset": asset, "icon": icon, "pose": pose,
                                 "label": label, "emphasis": emph}})
    return normalize({"title": d["title"], "facts_used": [f for f in d["facts_used"] if f in known], "beats": beats},
                     proj.get("assets", []))


LAYOUT_CYCLE = ["face", "split", "face", "bubble", "screen", "split", "face", "face"]


def presenter_draft(proj: dict, script: dict) -> dict:
    """Give a demo draft talking-head layouts: face on the hook and the call to action,
    the real product in between."""
    screens = sorted([a for a in proj.get("assets", []) if a.get("role") in ("screen", "image") and a.get("rights_confirmed")],
                     key=lambda a: not a.get("genuine"))
    n = len(script["beats"])
    for i, b in enumerate(script["beats"]):
        layout = "face" if i in (0, n - 1) or not screens else LAYOUT_CYCLE[i % len(LAYOUT_CYCLE)]
        b["visual"].update({"kind": "ugc", "layout": layout,
                            "asset": screens[i % len(screens)]["id"] if layout != "face" else None})
    return script


STOCK_SEARCHES = ["man checking stock app at night", "woman reading news on phone", "investor working on laptop",
                  "business people walking city", "person taking notes at desk", "woman smiling at phone",
                  "office worker thinking", "friends talking coffee shop", "man scrolling phone on train"]


def people_draft(proj: dict, script: dict) -> dict:
    """Real-people b-roll on most beats, the real product on one or two."""
    screens = [a for a in proj.get("assets", []) if a.get("role") in ("screen", "image") and a.get("rights_confirmed")
               and a.get("genuine")]
    for i, b in enumerate(script["beats"]):
        use_screen = screens and i in (2, 4)
        b["visual"].update({"kind": "people", "layout": "screen" if use_screen else "broll",
                            "asset": screens[i % len(screens)]["id"] if use_screen else None,
                            "search": "" if use_screen else STOCK_SEARCHES[i % len(STOCK_SEARCHES)]})
    return script


def template_script(proj: dict, facts: dict, variant: int = 0) -> dict:
    if (proj.get("mode") or "demo") == "animated":
        return animated_draft(proj, facts)
    known = {f["id"] for f in facts.get("facts", [])}
    usable = [t for t in TEMPLATES if set(t["facts_used"]) <= known] or TEMPLATES[:1]
    t = usable[variant % len(usable)]
    script = {
        "title": t["title"],
        "facts_used": [f for f in t["facts_used"] if f in known],
        "beats": [{"text": text, "visual": {"kind": kind, "asset": asset or None}, "overlay": ov}
                  for text, kind, asset, ov in t["beats"]],
    }
    script = normalize(script, proj.get("assets", []))
    if proj.get("mode") in ("ugc", "photo_avatar"):
        script = presenter_draft(proj, script)
    elif proj.get("mode") == "people":
        script = people_draft(proj, script)
    return script


def lint_reply(script: dict, proj: dict) -> list[dict]:
    from . import ugc
    return compliance.lint(script, compliance.load_facts(), proj.get("assets", []), real_person=ugc.real_person(proj))
