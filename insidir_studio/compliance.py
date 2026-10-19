"""Claim guard: blocks fabricated or non-compliant financial claims before render.

Errors block rendering. Warnings are shown but do not block.

The rules are deliberately strict:
- every number spoken or shown must come from an approved fact (facts.json),
- no promises of returns, no buy/sell directions, no "insider tips",
- no first-person testimonials (the narration is an AI voice, so "I made..." is fabricated),
- no claim that Form 4 data is secret or nonpublic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import config

BANNED = [
    (r"\bguarantee[ds]?\b", "Promises a guaranteed outcome."),
    (r"\brisk[- ]?free\b", "Claims something is risk-free."),
    (r"\bcan'?t lose\b|\bcannot lose\b|\bno[- ]lose\b", "Claims you can't lose."),
    (r"\bget rich\b|\bgetting rich\b", "Get-rich claim."),
    (r"\bbeat(s|ing)? the market\b|\boutperform", "Performance claim versus the market."),
    (r"\bdouble (your|my) money\b|\b\d+x (your|my|returns)\b", "Return multiple claim."),
    (r"\b(huge|massive|guaranteed|easy|quick|fast) (returns|gains|profits?|money)\b", "Promises returns."),
    (r"\bpassive income\b|\bfinancial freedom\b|\bquit your job\b", "Income/lifestyle promise."),
    (r"\binsider tips?\b|\bhot tips?\b|\bstock tips?\b", "Implies tips or nonpublic information."),
    (r"(?<!not )(?<!aren't )(?<!isn't )\bnon-?public\b|\bsecret (trades?|data|info)", "Implies secret or nonpublic data. Form 4s are public filings."),
    (r"\bbefore (anyone|everyone) else\b|\bbefore wall street\b", "Implies an information edge over the public."),
    (r"\b(you should|you must|go|time to) (buy|sell|short)\b", "Tells the viewer to trade."),
    (r"\b(buy|sell|short) (this|these|it) (stock|now|today)\b", "Tells the viewer to trade."),
    (r"\bwill (go up|go down|rise|fall|moon|explode|skyrocket|crash)\b", "Predicts a price move."),
    (r"\bto the moon\b|\bmoon(ing)?\b|\b10x\b|\b100x\b", "Hype price language."),
    (r"\bsure thing\b|\bno[- ]brainer\b|\bcan'?t miss\b", "Certainty claim."),
    (r"\bprofit(s|able)?\b", "Mentions profits. Don't tie the product to making money."),
    (r"\bfollow the (smart|big) money\b.*\b(win|profit|returns)\b", "Implies following insiders makes money."),
    (r"\b(legal|legally) insider trading\b.*\b(profit|money|rich)\b", "Implies insider data makes money."),
    (r"(?<!not )(?<!no )\b(financial|investment) advice\b", "Mentions advice. The disclaimer is added automatically; don't say the product gives advice."),
    (r"\breal[- ]time\b|\blive (prices|data|trades)\b", "Prices are delayed and filings arrive on a schedule; don't claim real-time."),
    (r"\bevery single trade\b|\ball (insider )?trades\b", "Overclaims coverage. Say what a fact supports."),
]

TESTIMONIAL = [
    r"\bI('ve| have)? (made|earned|gained|banked|pocketed|returned)\b",
    r"\bI('ve| have)? been (using|trading|following|investing)\b",
    r"\bI (use|used|tried|found|switched to|love)\b",
    r"\bmy (portfolio|returns|gains|profits?|trades?|account) (is|are|was|were|went|grew|jumped|doubled)\b",
    r"\bmade me\b",
    r"\bchanged my (life|trading|investing)\b",
]

COMMON_ACRONYMS = {
    "SEC", "CEO", "CFO", "COO", "CTO", "AI", "US", "USA", "EDGAR", "OK", "TV", "PDF", "FAQ", "ETF", "IPO",
    "NYSE", "TTM", "EPS", "XBRL", "API", "UI", "FTC", "I", "A", "TL", "DR", "TLDR", "MYTH", "FACT", "SEC'S",
}

NUMBER_WORDS = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "million", "billion", "trillion", "percent", "half", "double", "triple", "dozen",
}

# Document names are not claims: "Form 4", "8-K", "10-Q", "Rule 16a-3".
DOC_NAMES = re.compile(r"\bForm\s+\d+(/A)?s?\b|\b\d+-[KQ]\b|\bRule\s+\d+\w*(-\d+)?\b|\bSection\s+\d+\w*(\(\w\))?", re.I)
NUM_TOKEN = re.compile(r"[$€£]?\d[\d,]*(\.\d+)?\s?%?|\b[a-z]+\b", re.I)

AUTO_DISCLAIMER = "Research tool. Not investment advice."


def load_facts(path: Path | None = None) -> dict:
    p = path or config.facts_path()
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"facts": [], "disclaimer": AUTO_DISCLAIMER}


def save_facts(data: dict, path: Path | None = None) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("facts"), list):
        raise ValueError("facts.json must be an object with a 'facts' list")
    for f in data["facts"]:
        if not f.get("id") or not f.get("text") or not f.get("source"):
            raise ValueError("Every fact needs an id, text and source")
        f.setdefault("numbers", [])
    p = path or config.facts_path()
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _norm_num(tok: str) -> str:
    return tok.lower().replace(",", "").replace(" ", "").strip()


def approved_numbers(facts: dict) -> set[str]:
    out: set[str] = set()
    for f in facts.get("facts", []):
        for n in f.get("numbers", []):
            out.add(_norm_num(str(n)))
            out.add(_norm_num(str(n)).lstrip("$€£"))
    return out


def find_numbers(text: str) -> list[str]:
    cleaned = DOC_NAMES.sub(" ", text)
    found = []
    for m in NUM_TOKEN.finditer(cleaned):
        tok = m.group(0).strip()
        if tok[0].isalpha():
            if tok.lower() in NUMBER_WORDS:
                found.append(tok)
        else:
            found.append(tok)
    return found


def find_tickers(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"\$[A-Z]{1,5}\b|\b[A-Z]{2,5}\b", text):
        tok = m.group(0)
        if tok.lstrip("$") in COMMON_ACRONYMS:
            continue
        out.append(tok)
    return out


def script_texts(script: dict) -> list[tuple[str, str]]:
    """(beat id, text) pairs for everything spoken or shown on screen."""
    pairs = []
    if script.get("title"):
        pairs.append(("title", script["title"]))
    for b in script.get("beats", []):
        if b.get("text"):
            pairs.append((b.get("id", "?"), b["text"]))
        if b.get("overlay"):
            pairs.append((b.get("id", "?") + " overlay", b["overlay"]))
        vis = b.get("visual") or {}
        for key in ("emphasis", "label"):
            if vis.get(key):
                pairs.append((f"{b.get('id', '?')} {key}", str(vis[key])))
    return pairs


def _is_myth(where: str, script: dict) -> bool:
    bid = where.split(" ")[0]
    for b in script.get("beats", []):
        if b.get("id") == bid:
            return str((b.get("visual") or {}).get("label") or "").upper() == "MYTH"
    return False


def lint(script: dict, facts: dict | None = None, assets: list[dict] | None = None) -> list[dict]:
    facts = facts if facts is not None else load_facts()
    allowed = approved_numbers(facts)
    known_fact_ids = {f["id"] for f in facts.get("facts", [])}
    issues: list[dict] = []

    def add(level, where, msg):
        issues.append({"level": level, "where": where, "message": msg})

    beats = script.get("beats", [])
    if not beats:
        add("error", "script", "The script has no beats.")
        return issues

    for where, text in script_texts(script):
        myth = _is_myth(where, script)
        for pat, why in BANNED:
            m = re.search(pat, text, re.I)
            if m:
                if myth:
                    # a myth is shown in order to be crossed out and corrected
                    add("warning", where, f'"{m.group(0)}" appears in a MYTH beat. It is crossed out on screen; make sure the narration says it is false and the next beat corrects it.')
                else:
                    add("error", where, f'"{m.group(0)}": {why}')
        for pat in TESTIMONIAL:
            m = re.search(pat, text, re.I)
            if m:
                add("error", where, f'"{m.group(0)}": first-person testimonial. The narration is an AI voice, so personal experience would be fabricated. Use "you" or describe the product.')
        for num in find_numbers(text):
            n = _norm_num(num)
            if n not in allowed and n.lstrip("$€£") not in allowed:
                add("error", where, f'"{num}" is not an approved figure. Add it to Facts with a source, or remove it.')
        for t in find_tickers(text):
            add("warning", where, f'"{t}" looks like a ticker or company. Only name it if your footage shows its real filing, and never as a pick.')

    for k, b in enumerate(beats):
        if str((b.get("visual") or {}).get("label") or "").upper() == "MYTH":
            nxt = beats[k + 1] if k + 1 < len(beats) else {}
            if str((nxt.get("visual") or {}).get("label") or "").upper() != "FACT":
                add("error", b.get("id", "?"), "A MYTH beat must be followed straight away by a FACT beat that corrects it.")

    for fid in script.get("facts_used", []) or []:
        if fid not in known_fact_ids:
            add("error", "facts_used", f'Unknown fact "{fid}". Claude may only cite facts from the list.')

    words = sum(len(b.get("text", "").split()) for b in beats)
    if words < 40:
        add("warning", "script", f"{words} words is likely under 20 seconds of narration. Aim for 50-75.")
    if words > 92:
        add("error", "script", f"{words} words will run past 35 seconds. Cut to 75 or fewer.")
    elif words > 78:
        add("warning", "script", f"{words} words may run past 35 seconds; the voice will be sped up to fit.")

    asset_by_id = {a["id"]: a for a in (assets or [])}
    for b in beats:
        vis = b.get("visual") or {}
        a = asset_by_id.get(vis.get("asset"))
        if vis.get("kind") == "screen" and a is not None and not a.get("genuine"):
            add("warning", b.get("id", "?"), f'Asset "{a.get("label") or a.get("file")}" is not marked as a genuine Insidir recording.')
        if a is not None and not a.get("rights_confirmed"):
            add("error", b.get("id", "?"), f'Confirm you have the rights to use "{a.get("label") or a.get("file")}".')
    return issues


def has_errors(issues: list[dict]) -> bool:
    return any(i["level"] == "error" for i in issues)
