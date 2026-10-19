"""Animated captions and on-screen labels as an ASS subtitle file, burned in by FFmpeg/libass.

- Captions: 1-3 word groups that pop in, with the spoken word highlighted.
- Overlays: a short headline per beat, slid in at the top.
- Disclosures: "AI voice" for the whole video (optional, off by default), "AI-generated presenter" while an AI
  presenter is on screen, "Real Insidir screen recording" over genuine demo footage.
- End card text and the research-only disclaimer.
"""

from __future__ import annotations

import re

from . import config, fonts

FONT = "Inter"


def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def group_words(words: list, max_words: int = 3, max_chars: int = 18) -> list[list]:
    """Split word timings into caption groups at punctuation, pauses and beat changes."""
    groups: list[list] = []
    cur: list = []
    for i, w in enumerate(words):
        if cur:
            prev = cur[-1]
            chars = sum(len(x.text) + 1 for x in cur) + len(w.text)
            # keep "Form 4", "$39 a month"-style pairs together
            glued = re.match(r"[\d$]", w.text) and not re.search(r"[.!?,;:]$", prev.text) and len(cur) <= max_words and w.beat == prev.beat
            if not glued and (len(cur) >= max_words or chars > max_chars or w.beat != prev.beat
                    or w.start - prev.end > 0.35 or re.search(r"[.!?,;:]$", prev.text)):
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def _clean(word: str) -> str:
    return word.strip().strip('"').rstrip(",;:")


def build_ass(words: list, shots: list[dict], beats: list[dict], beat_times: list[dict],
              total: float, highlight: str, disclaimer: str, end_card: dict | None,
              end_card_start: float | None, ai_voice_label: str = "", show_captions: bool = True,
              caption_font: str | None = None, headline_font: str | None = None) -> str:
    """caption_font / headline_font: ids from fonts.FONTS. Labels, the disclaimer and the end
    card stay in Inter, the Insidir brand face."""
    W, H = config.WIDTH, config.HEIGHT
    cf = fonts.get(caption_font)
    hf = fonts.get(headline_font)
    cap_name, cap_bold = cf["ass"]
    head_name, head_bold = hf["ass"]
    cap_size = round(84 * cf.get("scale", 1.0))
    head_size = round(54 * hf.get("scale", 1.0))
    b = lambda on: -1 if on else 0
    hl = _ass_color(highlight)
    header = f"""[Script Info]
Title: Insidir Video Studio captions
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{cap_name},{cap_size},&H00A9AFB6,&H00A9AFB6,&H00101010,&H80000000,{b(cap_bold)},0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Overlay,{head_name},{head_size},&H00F4F1EA,&H00F4F1EA,&H00111111,&H00111111,{b(head_bold)},0,0,0,100,100,0,0,3,18,0,8,80,80,0,1
Style: Label,{FONT},30,&H00F4F1EA,&H00F4F1EA,&H33111111,&H33111111,-1,0,0,0,100,100,1,0,3,10,0,7,40,40,0,1
Style: EndHead,{FONT},150,&H00F4F1EA,&H00F4F1EA,&H00111111,&H00111111,-1,0,0,0,100,100,-2,0,1,0,0,5,60,60,0,1
Style: EndLine,{FONT},52,&H00F4F1EA,&H00F4F1EA,&H00111111,&H00111111,-1,0,0,0,100,100,0,0,1,0,0,5,80,80,0,1
Style: EndUrl,{FONT},46,&H00111111,&H00111111,&H00F4F1EA,&H00F4F1EA,-1,0,0,0,100,100,1,0,3,16,0,5,80,80,0,1
Style: Disclaimer,{FONT},34,&H00D8D4CC,&H00D8D4CC,&H00111111,&H80000000,0,0,0,0,100,100,0,0,1,3,0,2,80,80,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev: list[str] = []

    def add(layer, start, end, style, text):
        if end - start >= 0.04:
            ev.append(f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    caption_end = end_card_start if end_card_start is not None else total

    # -- captions: each group gets one event per word so the spoken word lights up
    cap_y = int(H * 0.705)
    groups = group_words(words) if show_captions else []
    for gi, g in enumerate(groups):
        g_start = g[0].start - 0.05
        nxt = groups[gi + 1][0].start - 0.05 if gi + 1 < len(groups) else caption_end
        g_end = min(nxt, g[-1].end + 0.45, caption_end)
        texts = [_esc(_clean(w.text)).upper() for w in g]
        for wi, w in enumerate(g):
            s = g_start if wi == 0 else w.start
            e = g[wi + 1].start if wi + 1 < len(g) else g_end
            parts = []
            for j, t in enumerate(texts):
                parts.append(f"{{\\c{hl}}}{t}{{\\c&H00A9AFB6&}}" if j == wi else t)
            pop = "{\\fscx78\\fscy78\\t(0,110,\\fscx104\\fscy104)\\t(110,170,\\fscx100\\fscy100)}" if wi == 0 else ""
            add(2, s, e, "Caption", f"{{\\an5\\pos({W // 2},{cap_y})}}{pop}{' '.join(parts)}")

    # -- per-beat headline overlays
    by_id = {b["id"]: b for b in beat_times}
    for beat in beats:
        text = (beat.get("overlay") or "").strip()
        bt = by_id.get(beat.get("id"))
        if not text or not bt:
            continue
        s, e = bt["start"] + 0.1, min(bt["end"], caption_end)
        add(1, s, e, "Overlay",
            f"{{\\an8\\move({W // 2},250,{W // 2},280,0,220)\\fad(140,120)}}{_esc(text)}")

    # -- disclosure labels (top left), stacked
    label_y = 60
    if ai_voice_label:
        add(3, 0, total, "Label", "{\\an7\\pos(40,60)}" + _esc(ai_voice_label))
        label_y = 118
    for sh in shots:
        # an AI-generated presenter is always labelled, whatever the voice setting
        if sh.get("ai_presenter"):
            add(3, sh["start"], sh["start"] + sh["duration"], "Label", "{\\an7\\pos(40,%d)}AI-generated presenter" % label_y)
        if sh.get("genuine"):
            # stack under an AI-presenter label shown at the same time (e.g. split or bubble layouts)
            y = label_y + 58 if any(o.get("ai_presenter") and o["start"] < sh["start"] + sh["duration"]
                                    and sh["start"] < o["start"] + o["duration"] for o in shots) else label_y
            add(3, sh["start"], sh["start"] + sh["duration"], "Label", "{\\an7\\pos(40,%d)}Real Insidir screen recording" % y)

    # -- disclaimer over the last beat, and the end card
    if beat_times:
        last_start = beat_times[-1]["start"]
        add(3, last_start, total, "Disclaimer", "{\\an2\\pos(%d,%d)}%s" % (W // 2, H - 70, _esc(disclaimer)))
    if end_card and end_card_start is not None:
        s = end_card_start
        add(4, s + 0.05, total, "EndHead",
            f"{{\\an5\\pos({W // 2},{H // 2 - 170})\\fad(200,0)\\fscx92\\fscy92\\t(0,260,\\fscx100\\fscy100)}}{_esc(end_card.get('headline', 'Insidir.'))}")
        if end_card.get("line"):
            add(4, s + 0.2, total, "EndLine",
                f"{{\\an5\\pos({W // 2},{H // 2})\\fad(220,0)}}{_esc(end_card['line'])}")
        if end_card.get("url"):
            add(4, s + 0.35, total, "EndUrl",
                f"{{\\an5\\pos({W // 2},{H // 2 + 150})\\fad(220,0)}}{_esc(end_card['url'])}")

    return header + "\n".join(ev) + "\n"
