"""Turns a voiced script into an edit decision list of shots on a 30 fps grid.

Editing rules (the "cinematic cuts"):
- every beat cuts in ~80 ms before its first word (a J-cut), so pictures lead the voice;
- beats longer than ~3 s are cut into 2-4 shots on word starts: wide -> tight -> tighter,
  alternating push-in and pull-out, over continuous demo playback (the footage keeps
  running across the cut, so the product is shown as it really behaves);
- the hook opens tight and goes wide;
- quick transitions only where the subject changes; hard cuts everywhere else.
"""

from __future__ import annotations

import math

from . import config

J_CUT = 0.08
END_CARD_SECONDS = 1.8
MIN_SHOT = 0.9


def _frames(t: float) -> int:
    return int(round(t * config.FPS))


def choose_asset(beat: dict, index: int, assets: list[dict], cursors: dict) -> dict | None:
    vis = beat.get("visual") or {}
    by_id = {a["id"]: a for a in assets}
    if vis.get("asset") in by_id:
        return by_id[vis["asset"]]
    kind = vis.get("kind") or "screen"
    usable = [a for a in assets if a.get("rights_confirmed") and a.get("role") != "music"]
    if kind == "title":
        return None
    pools = {
        "screen": [a for a in usable if a.get("role") == "screen"],
        "presenter": [a for a in usable if a.get("role") == "presenter"],
        "image": [a for a in usable if a.get("role") == "image"],
    }
    pool = pools.get(kind) or pools["screen"] or pools["image"] or pools["presenter"]
    if not pool:
        return None
    # prefer genuine product footage, videos before stills
    pool = sorted(pool, key=lambda a: (not a.get("genuine"), a.get("type") != "video"))
    n = cursors.setdefault(("pick", kind), 0)
    cursors[("pick", kind)] = n + 1
    return pool[n % len(pool)]


def _cut_points(span_start: float, span_end: float, words: list, max_shot: float) -> list[float]:
    length = span_end - span_start
    if length <= max_shot + 0.4:
        return []
    n = min(4, max(2, math.ceil(length / max_shot)))
    starts = [w.start for w in words if span_start + MIN_SHOT < w.start < span_end - MIN_SHOT]
    cuts = []
    for k in range(1, n):
        ideal = span_start + length * k / n
        cand = min(starts, key=lambda s: abs(s - ideal), default=ideal) if starts else ideal
        if abs(cand - ideal) > 0.6:
            cand = ideal
        cand -= 0.04  # land the cut just before the word
        if (not cuts or cand - cuts[-1] >= MIN_SHOT) and span_end - cand >= MIN_SHOT and cand - span_start >= MIN_SHOT:
            cuts.append(cand)
    return cuts


def _framings(role: str, asset: dict | None, beat_index: int) -> list[str]:
    if asset is None:
        return ["card"]
    portrait = asset.get("height", 0) > asset.get("width", 0) * 1.2
    if role == "presenter" or portrait:
        return ["full", "full_tight", "full", "full_tight"]
    if beat_index == 0:
        return ["tight", "wide", "tighter", "wide"]
    return ["wide", "tight", "tighter", "tight"]


def beat_spans(beat_times: list[dict], narration_seconds: float) -> list[tuple[float, float]]:
    """On-screen span of each beat: from just before its first word to the next beat's cut."""
    starts = [0.0 if i == 0 else max(bt["start"], bt["speech_start"] - J_CUT) for i, bt in enumerate(beat_times)]
    ends = starts[1:] + [narration_seconds]
    return list(zip(starts, ends))


def plan(beats: list[dict], beat_times: list[dict], words: list, narration_seconds: float,
         assets: list[dict], transitions: str = "cinematic", end_card: bool = True,
         avatar_videos: dict | None = None) -> dict:
    avatar_videos = avatar_videos or {}
    cursors: dict = {}
    spans = beat_spans(beat_times, narration_seconds)
    total = narration_seconds + (END_CARD_SECONDS if end_card else 0.0)

    shots: list[dict] = []
    prev_key = None
    for i, (beat, (s0, s1)) in enumerate(zip(beats, spans)):
        vis = beat.get("visual") or {}
        asset = choose_asset(beat, i, assets, cursors)
        role = (asset or {}).get("role") or "title"
        kind = "title" if asset is None else role
        bwords = [w for w in words if w.beat == beat.get("id")]
        max_shot = 2.6 if kind in ("screen", "image") else 3.4
        if kind == "title":
            cuts = []
        else:
            cuts = _cut_points(s0, s1, bwords, max_shot)
        bounds = [s0, *cuts, s1]
        framings = _framings(role, asset, i)
        focus = vis.get("focus") or [0.5, 0.5]
        zoom = float(vis.get("zoom") or 1.0)

        # source time for video: continue where this asset was last used unless set
        src_base = 0.0
        if asset is not None and asset.get("type") == "video":
            length = s1 - s0
            if vis.get("start") is not None:
                src_base = float(vis["start"])
            else:
                src_base = cursors.get(("src", asset["id"]), 0.0)
            dur = float(asset.get("duration") or 0)
            if dur and src_base + length > dur:
                src_base = max(0.0, dur - length) if length < dur else 0.0
            cursors[("src", asset["id"])] = src_base + length

        key = (kind, (asset or {}).get("id"))
        trans_in = None
        if i > 0:
            if transitions == "cinematic" and key != prev_key:
                trans_in = {"type": "zoomin" if i == 1 else "smoothleft", "duration": 0.22}
        prev_key = key

        for k, (a, b) in enumerate(zip(bounds, bounds[1:])):
            avatar = avatar_videos.get(beat.get("id")) if role == "presenter" else None
            shots.append({
                "beat": beat.get("id"),
                "kind": kind,
                "asset": asset,
                "avatar_video": avatar,
                "src_start": round(src_base + (a - s0), 3) if not avatar else round(a - s0, 3),
                "framing": framings[k % len(framings)],
                "focus": focus,
                "zoom": zoom,
                "motion": "in" if (k + i) % 2 == 0 else "out",
                "start": a,
                "end": b,
                "genuine": bool(asset and asset.get("genuine") and role == "screen"),
                "ai_presenter": bool(asset and role == "presenter" and asset.get("ai_generated")),
                "transition_in": trans_in if k == 0 else None,
            })

    if end_card:
        shots.append({
            "beat": "end", "kind": "endcard", "asset": None, "avatar_video": None, "src_start": 0.0,
            "framing": "card", "focus": [0.5, 0.5], "zoom": 1.0, "motion": "in",
            "start": narration_seconds, "end": total, "genuine": False, "ai_presenter": False,
            "transition_in": {"type": "fadeblack", "duration": 0.3},
        })

    # snap to the frame grid so audio and video stay locked
    for sh in shots:
        sh["frame_start"] = _frames(sh["start"])
        sh["frame_end"] = _frames(sh["end"])
    shots = [s for s in shots if s["frame_end"] > s["frame_start"]]
    for sh in shots:
        sh["frames"] = sh["frame_end"] - sh["frame_start"]
        sh["start"] = sh["frame_start"] / config.FPS
        sh["duration"] = sh["frames"] / config.FPS
    return {"shots": shots, "total": _frames(total) / config.FPS, "end_card_start": narration_seconds if end_card else None}
