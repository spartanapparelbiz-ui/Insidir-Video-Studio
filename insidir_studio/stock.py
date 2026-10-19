"""Real people: free stock video of real humans from Pexels and Pixabay.

Both services are free: make an account, copy the API key (no card, no plan), paste it in
Settings. Their licences allow commercial use without attribution, but not implying that the
people shown endorse anything, so the studio uses stock people only as b-roll under the
narration, never as a speaking customer, and says "stock footage" in the post disclosure.

The search runs from this PC straight to the provider; the chosen clip is downloaded into the
project like any other footage, with its source, author and licence recorded on the asset.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config, project

UA = "InsidirVideoStudio/1.0 (local desktop app)"
LICENSES = {
    "pexels": ("Pexels License", "https://www.pexels.com/license/"),
    "pixabay": ("Pixabay Content License", "https://pixabay.com/service/license-summary/"),
}


class StockError(RuntimeError):
    pass


def keys(settings: dict | None = None) -> dict:
    st = (settings or config.load_settings()).get("stock") or {}
    return {"pexels": (st.get("pexels_key") or "").strip(), "pixabay": (st.get("pixabay_key") or "").strip()}


def _get(url: str, headers: dict | None = None, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise StockError("The stock API key was refused. Check it in Settings.")
        if e.code == 429:
            raise StockError("The stock site's free hourly limit was reached. Try again in a while.")
        raise StockError(f"Stock search failed ({e.code}).")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise StockError(f"Couldn't reach the stock site: {e}")


def _orientation(aspect: str) -> str:
    return {"9:16": "portrait", "4:5": "portrait", "1:1": "square", "16:9": "landscape"}.get(aspect, "portrait")


def _best_file(files: list[dict], want_short: int = 1080) -> dict | None:
    """The smallest MP4 at least `want_short` px on its short side (or the biggest available)."""
    mp4 = [f for f in files if (f.get("file_type") or "video/mp4") == "video/mp4" and f.get("width") and f.get("link")]
    if not mp4:
        return None
    ok = sorted([f for f in mp4 if min(f["width"], f["height"]) >= want_short], key=lambda f: f["width"] * f["height"])
    return ok[0] if ok else max(mp4, key=lambda f: f["width"] * f["height"])


def parse_pexels(data: dict) -> list[dict]:
    out = []
    for v in data.get("videos") or []:
        best = _best_file(v.get("video_files") or [])
        if not best:
            continue
        out.append({"provider": "pexels", "id": str(v["id"]), "thumb": v.get("image") or "",
                    "duration": v.get("duration") or 0, "width": best["width"], "height": best["height"],
                    "download": best["link"], "page": v.get("url") or "", "author": (v.get("user") or {}).get("name") or "",
                    "author_url": (v.get("user") or {}).get("url") or ""})
    return out


def parse_pixabay(data: dict) -> list[dict]:
    out = []
    for h in data.get("hits") or []:
        vids = h.get("videos") or {}
        cands = [dict(vids[k], quality=k) for k in ("large", "medium", "small") if vids.get(k, {}).get("url")]
        files = [{"file_type": "video/mp4", "width": c.get("width") or 0, "height": c.get("height") or 0,
                  "link": c["url"]} for c in cands]
        best = _best_file(files)
        if not best:
            continue
        thumb = next((c.get("thumbnail") for c in cands if c.get("thumbnail")), "")
        out.append({"provider": "pixabay", "id": str(h["id"]), "thumb": thumb, "duration": h.get("duration") or 0,
                    "width": best["width"], "height": best["height"], "download": best["link"],
                    "page": h.get("pageURL") or "", "author": h.get("user") or "", "author_url": ""})
    return out


def search(query: str, aspect: str = "9:16", settings: dict | None = None, per_page: int = 18) -> list[dict]:
    query = (query or "").strip()[:100]
    if not query:
        raise StockError("Type what the people should be doing, e.g. \"woman reading phone at night\".")
    k = keys(settings)
    if not (k["pexels"] or k["pixabay"]):
        raise StockError("Add a free Pexels or Pixabay API key in Settings to search real-people footage.")
    results: list[dict] = []
    errors = []
    if k["pexels"]:
        q = urllib.parse.urlencode({"query": query, "orientation": _orientation(aspect), "per_page": per_page,
                                    "size": "medium"})
        try:
            results += parse_pexels(_get(f"https://api.pexels.com/videos/search?{q}", {"Authorization": k["pexels"]}))
        except StockError as e:
            errors.append(f"Pexels: {e}")
    if k["pixabay"]:
        q = urllib.parse.urlencode({"key": k["pixabay"], "q": query, "per_page": per_page, "safesearch": "true",
                                    "video_type": "film"})
        try:
            results += parse_pixabay(_get(f"https://pixabay.com/api/videos/?{q}"))
        except StockError as e:
            errors.append(f"Pixabay: {e}")
    if not results and errors:
        raise StockError(" ".join(errors))
    return results


def download(d: Path, item: dict, max_bytes: int = 400 * 1024 ** 2) -> dict:
    """Download a search result into the project as a real-people b-roll asset."""
    if item.get("provider") not in LICENSES or not str(item.get("download", "")).startswith("https://"):
        raise StockError("Not a stock result from Pexels or Pixabay.")
    host = urllib.parse.urlparse(item["download"]).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in ("pexels.com", "pixabay.com")):
        raise StockError("Stock downloads only come from Pexels or Pixabay.")
    tmpdir = Path(tempfile.mkdtemp(dir=d))
    tmp = tmpdir / "stock.mp4"
    try:
        req = urllib.request.Request(item["download"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            got = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                got += len(chunk)
                if got > max_bytes:
                    raise StockError("That clip is too large.")
                f.write(chunk)
        name = f"{item['provider']}-{item['id']}.mp4"
        asset = project.add_asset(d, name, tmp, "broll")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise StockError(f"Download failed: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    lic, lic_url = LICENSES[item["provider"]]
    with project.LOCK:
        proj = project.load(d)
        for a in proj["assets"]:
            if a["id"] == asset["id"]:
                a.update({
                    "label": f"{item['provider'].title()} {item['id']}" + (f" by {item['author']}" if item.get("author") else ""),
                    "rights_confirmed": True,  # the stock licence allows commercial use
                    "genuine": False,
                    "stock": {"provider": item["provider"], "id": item["id"], "page": item.get("page", ""),
                              "author": item.get("author", ""), "author_url": item.get("author_url", ""),
                              "license": lic, "license_url": lic_url},
                    "notes": "Real people, licensed stock b-roll. Not a customer; never shown endorsing anything.",
                })
                asset = a
        project.save(d, proj)
    return asset
