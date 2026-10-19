"""Local web app. Binds to 127.0.0.1 only; nothing is exposed to the network."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import animate, avatar, avatars, captions, compliance, config, fonts, look, stock, media, project, render, script_writer, tts, ugc, whisper_align

JOBS: dict[str, dict] = {}
RENDER_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _public_settings(s: dict) -> dict:
    out = json.loads(json.dumps(s))
    key = out.get("claude", {}).get("api_key")
    if key:
        out["claude"]["api_key"] = "••••" + key[-4:]
        out["claude"]["has_key"] = True
    for k in ("pexels_key", "pixabay_key"):
        v = (out.get("stock") or {}).get(k)
        if v:
            out["stock"][k] = "••••" + v[-4:]
    return out


def status_payload() -> dict:
    settings = config.load_settings()
    return {
        "app": config.APP_NAME,
        "version": config.VERSION,
        "home": str(config.studio_home()),
        "ffmpeg": config.find_tool("ffmpeg"),
        "ffprobe": config.find_tool("ffprobe"),
        "kokoro": tts.kokoro_status(),
        "avatar": avatar.status(settings),
        "motion": animate.status(),
        "whisper": whisper_align.status(),
        "fonts": fonts.catalogue(),
        "look": {**look.catalogue(), "captions": {k: v["name"] for k, v in captions.CAPTION_STYLES.items()},
                 "camera": ugc.CAMERA_STYLES, "moves": ugc.MOVES},
        "limits": {"min": config.MIN_SECONDS, "max": config.MAX_SECONDS, "width": config.WIDTH,
                   "height": config.HEIGHT, "fps": config.FPS},
    }


def _job_runner(job_id: str, pdir: Path, engine: str | None) -> None:
    job = JOBS[job_id]

    def log(msg: str) -> None:
        job["log"].append(msg)
        del job["log"][:-400]

    def progress(p: float, msg: str = "") -> None:
        job["progress"] = round(p, 3)
        if msg:
            job["message"] = msg

    with RENDER_LOCK:
        job["status"] = "running"
        try:
            job["result"] = render.render(pdir, log=log, progress=progress, engine_name=engine)
            job["status"] = "done"
        except Exception as e:  # report every failure to the UI
            job["status"] = "error"
            job["error"] = str(e)
            log(traceback.format_exc())


class Handler(BaseHTTPRequestHandler):
    server_version = "InsidirStudio/" + config.VERSION

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    # ------------------------------------------------------------ plumbing
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def _body_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20_000_000:
            raise ApiError(413, "Request too large")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            raise ApiError(400, "Invalid JSON")

    def _check_origin(self) -> None:
        # refuse cross-site requests from other pages open in the browser
        origin = self.headers.get("Origin")
        if origin and not re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
            raise ApiError(403, "Cross-origin request refused")

    def _serve_file(self, path: Path, ctype: str | None = None) -> None:
        if not path.is_file():
            raise ApiError(404, "Not found")
        ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        status = 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                status = 206
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def _dispatch(self, method: str) -> None:
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.split("/") if p]
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            # DNS-rebinding guard: only answer requests addressed to this machine
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                raise ApiError(403, "Requests must be addressed to 127.0.0.1")
            if method != "GET":
                self._check_origin()
            if not parts or parts[0] != "api":
                return self._static(parts)
            return self._api(method, parts[1:], q)
        except ApiError as e:
            self._json({"error": str(e)}, e.status)
        except (ValueError, RuntimeError, media.FFmpegError) as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": f"Unexpected error: {e}"}, 500)

    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # ------------------------------------------------------------ static
    def _static(self, parts: list[str]) -> None:
        if not parts:
            return self._serve_file(config.WEB_DIR / "index.html", "text/html; charset=utf-8")
        if parts[0] == "fonts" and len(parts) == 2 and parts[1].endswith((".otf", ".ttf")):
            return self._serve_file(config.FONTS_DIR / Path(parts[1]).name,
                                    "font/ttf" if parts[1].endswith(".ttf") else "font/otf")
        rel = Path(*parts)
        target = (config.WEB_DIR / rel).resolve()
        if config.WEB_DIR.resolve() not in target.parents:
            raise ApiError(404, "Not found")
        self._serve_file(target)

    # ------------------------------------------------------------ api
    def _project(self, pid: str) -> Path:
        d = project.project_dir(pid)
        if not (d / "project.json").exists():
            raise ApiError(404, "Project not found")
        return d

    def _put_project(self, d: Path) -> None:
        body = self._body_json()
        cur = project.load(d)
        # assets are managed by upload/delete; keep their paths authoritative
        # (an upload finishing during an edit must not be dropped, so PUT never removes assets)
        edits = {a.get("id"): a for a in body.get("assets", []) if isinstance(a, dict)}
        assets = []
        for keep in cur["assets"]:
            a = edits.get(keep["id"], {})
            merged = {**keep, **{k: a[k] for k in ("label", "role", "genuine", "ai_generated",
                                                   "rights_confirmed", "notes") if k in a}}
            if merged["role"] not in project.ROLES:
                merged["role"] = keep["role"]
            f = a.get("focus")
            if isinstance(f, list) and len(f) == 2 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in f):
                merged["focus"] = [float(f[0]), float(f[1])]
            assets.append(merged)
        body["assets"] = assets
        body["id"] = cur["id"]
        body["created"] = cur.get("created")
        return self._json(project.save(d, body))

    def _receive_upload(self, into: Path) -> Path:
        """Stream the request body to a temp file inside `into` (the caller moves or deletes it)."""
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            raise ApiError(400, "Empty upload")
        if n > 4 * 1024 ** 3:
            raise ApiError(413, "Files up to 4 GB")
        into.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=into)) / "upload"
        with open(tmp, "wb") as f:
            left = n
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        return tmp

    def _avatars(self, method: str, sub: list[str], q: dict) -> None:
        """The saved-avatar library, shared by every project."""
        if method == "GET" and not sub:
            return self._json({"avatars": avatars.list_avatars(), "characters": animate.CHARACTERS})
        if method == "POST" and not sub:
            kind = q.get("kind") or "photo"
            tmp = self._receive_upload(avatars.avatars_dir() / "_incoming") if kind == "photo" else None
            try:
                av = avatars.create(q.get("name") or "", kind, tmp, q.get("filename") or "", q.get("character") or "dot",
                                    q.get("voice"))
            except ValueError as e:
                raise ApiError(400, str(e))
            finally:
                if tmp:
                    shutil.rmtree(tmp.parent, ignore_errors=True)
            return self._json(av)
        try:
            av = avatars.load(sub[0])
        except (OSError, ValueError):
            raise ApiError(404, "No such avatar")
        if method == "PUT" and len(sub) == 1:
            return self._json(avatars.update(av["id"], self._body_json()))
        if method == "DELETE" and len(sub) == 1:
            avatars.delete(av["id"])
            return self._json({"deleted": av["id"]})
        if method == "GET" and sub[1:] == ["photo"] and av.get("photo"):
            return self._serve_file(avatars.photo_path(av))
        if method == "POST" and sub[1:] == ["voice-preview"]:
            body = self._body_json()
            text = (body.get("text") or f"Hi, I'm {av['name']}. This is how I'll sound in your videos.").strip()[:400]
            out = avatars.avatar_dir(av["id"]) / "previews" / f"{av['voice']}-{uuid.uuid4().hex[:6]}.wav"
            old = sorted((out.parent).glob("*.wav")) if out.parent.exists() else []
            for f in old[:-4]:
                f.unlink(missing_ok=True)
            tts.preview(text, av["voice"], float(av.get("speed") or 1.0), out)
            return self._json({"url": f"/api/avatars/{av['id']}/preview/{out.name}"})
        if method == "GET" and len(sub) == 3 and sub[1] == "preview":
            f = avatars.avatar_dir(av["id"]) / "previews" / Path(sub[2]).name
            if not f.exists():
                raise ApiError(404, "Not found")
            return self._serve_file(f, "audio/wav")
        raise ApiError(404, "Unknown avatar endpoint")

    def _api(self, method: str, p: list[str], q: dict) -> None:
        route = (method, *p[:1])

        if route == ("GET", "status"):
            return self._json(status_payload())
        if route == ("GET", "settings"):
            return self._json(_public_settings(config.load_settings()))
        if route == ("PUT", "settings"):
            body = self._body_json()
            cur = config.load_settings()
            key = (body.get("claude") or {}).get("api_key")
            if key is not None and key.startswith("••••"):
                body["claude"]["api_key"] = cur.get("claude", {}).get("api_key", "")
            for k in ("pexels_key", "pixabay_key"):
                v = (body.get("stock") or {}).get(k)
                if v is not None and v.startswith("••••"):
                    body["stock"][k] = (cur.get("stock") or {}).get(k, "")
            return self._json(_public_settings(config.save_settings(body)))
        if route == ("GET", "facts"):
            return self._json(compliance.load_facts())
        if route == ("PUT", "facts"):
            compliance.save_facts(self._body_json())
            return self._json(compliance.load_facts())
        if route == ("GET", "voices"):
            return self._json({"voices": tts.VOICES, "gender": {v: tts.gender_of(v) for v in tts.VOICES},
                               "defaults": tts.DEFAULT_BY_GENDER})
        if p[:1] == ["gen"]:
            from .gen import api as gen_api   # imported lazily: the generate stack is optional
            return gen_api.handle(self, method, p[1:], q)
        if p[:1] == ["avatars"]:
            return self._avatars(method, p[1:], q)
        if method == "GET" and p[:1] == ["jobs"] and len(p) == 2:
            job = JOBS.get(p[1])
            if not job:
                raise ApiError(404, "No such job")
            return self._json({k: v for k, v in job.items() if k != "thread"})
        if route == ("GET", "projects") and len(p) == 1:
            return self._json({"projects": project.list_projects()})
        if route == ("POST", "projects") and len(p) == 1:
            body = self._body_json()
            name = (body.get("name") or "").strip() or "Insidir video"
            return self._json(project.new(name, body.get("brief")))
        if p[:1] != ["projects"] or len(p) < 2:
            raise ApiError(404, "Unknown endpoint")

        d = self._project(p[1])
        sub = p[2:]
        if method == "GET" and not sub:
            return self._json(project.load(d))
        if method == "PUT" and not sub:
            with project.LOCK:
                return self._put_project(d)
        if method == "DELETE" and not sub:
            shutil.rmtree(d)
            return self._json({"deleted": p[1]})

        what = sub[0] if sub else ""
        if what == "assets" and method == "POST":
            filename = q.get("filename") or "upload.bin"
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                raise ApiError(400, "Empty upload")
            if n > 4 * 1024 ** 3:
                raise ApiError(413, "Files up to 4 GB")
            tmpdir = Path(tempfile.mkdtemp(dir=d))
            tmp = tmpdir / "upload"
            with open(tmp, "wb") as f:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            try:
                asset = project.add_asset(d, filename, tmp, q.get("role"))
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
            return self._json(asset)
        if what == "assets" and method == "DELETE" and len(sub) == 2:
            return self._json(project.remove_asset(d, sub[1]))
        if what == "thumb" and method == "GET" and len(sub) == 2:
            proj = project.load(d)
            a = next((x for x in proj["assets"] if x["id"] == sub[1]), None)
            if not a or a["type"] == "audio":
                raise ApiError(404, "No thumbnail")
            t = float(q.get("t") or 0)
            out = d / "build" / "thumbs" / f"{a['id']}_{int(t * 10)}.jpg"
            if not out.exists():
                media.thumbnail(d / a["file"], out, t)
            return self._serve_file(out, "image/jpeg")
        if what == "file" and method == "GET" and len(sub) >= 2:
            target = (d / Path(*sub[1:])).resolve()
            if d.resolve() not in target.parents or not any(
                    (d / s).resolve() in target.parents for s in ("assets", "out", "build")):
                raise ApiError(404, "Not found")
            extra_type = "text/plain; charset=utf-8" if target.suffix == ".txt" else None
            return self._serve_file(target, extra_type)
        if what == "prompt" and method == "GET":
            proj = project.load(d)
            return self._json({"prompt": script_writer.build_prompt(proj, compliance.load_facts())})
        if what == "script" and method == "POST" and len(sub) == 2:
            proj = project.load(d)
            body = self._body_json()
            if sub[1] == "parse":
                script = script_writer.parse_reply(body.get("reply") or "", proj["assets"])
            elif sub[1] == "template":
                script = script_writer.template_script(proj, compliance.load_facts(), int(body.get("variant") or 0))
            elif sub[1] == "api":
                s = config.load_settings()
                if not s["claude"].get("api_enabled"):
                    raise ApiError(400, "The optional Claude API path is off. Use copy and paste, or turn it on in Settings.")
                prompt = script_writer.build_prompt(proj, compliance.load_facts())
                reply = script_writer.call_api(prompt, s["claude"].get("model"), s["claude"].get("api_key") or None)
                script = script_writer.parse_reply(reply, proj["assets"])
            elif sub[1] == "transcribe":
                try:
                    script = ugc.transcribe(proj, d, log=print)
                except RuntimeError as e:
                    raise ApiError(400, str(e))
            else:
                raise ApiError(404, "Unknown script action")
            return self._json({"script": script, "issues": script_writer.lint_reply(script, proj)})
        if what == "lint" and method == "POST":
            proj = project.load(d)
            body = self._body_json()
            script = body.get("script") or proj.get("script") or {}
            return self._json({"issues": script_writer.lint_reply(script, proj)})
        if what == "stock" and method == "POST" and sub[1:] == ["search"]:
            body = self._body_json()
            try:
                return self._json({"results": stock.search(body.get("query") or "", body.get("aspect") or "9:16")})
            except stock.StockError as e:
                raise ApiError(400, str(e))
        if what == "stock" and method == "POST" and sub[1:] == ["add"]:
            try:
                return self._json(stock.download(d, self._body_json()))
            except stock.StockError as e:
                raise ApiError(400, str(e))
        if what == "look-preview" and method == "GET":
            # a graded still of this project's footage (or the built-in sample) for the Style tab
            proj = project.load(d)
            grade = q.get("grade") or "none"
            fx = [e for e in (q.get("effects") or "").split(",") if e in look.EFFECTS]
            src_a = next((a for a in proj["assets"] if a["type"] in ("video", "image") and a.get("role") != "music"), None)
            if src_a:
                src = d / "build" / "thumbs" / f"{src_a['id']}_look.jpg"
                if not src.exists():
                    media.thumbnail(d / src_a["file"], src, min(1.0, (src_a.get("duration") or 0) / 2), width=540)
            else:
                src = config.WEB_DIR / "templates" / "viral.jpg"
            out = d / "build" / "looks" / f"{grade}-{'-'.join(sorted(fx)) or 'plain'}-{src_a['id'] if src_a else 'sample'}.jpg"
            if not out.exists():
                look.preview(src, out, {"grade": grade, "effects": fx})
            return self._serve_file(out, "image/jpeg")
        if what == "voice-preview" and method == "POST":
            body = self._body_json()
            text = (body.get("text") or "This is how your narration will sound.").strip()[:400]
            voice = body.get("voice") or tts.DEFAULT_VOICE
            if voice not in tts.VOICES:
                raise ApiError(400, "Unknown voice")
            out = d / "build" / "previews" / f"{voice}-{uuid.uuid4().hex[:6]}.wav"
            tts.preview(text, voice, float(body.get("speed") or 1.0), out)
            return self._json({"url": f"/api/projects/{p[1]}/file/build/previews/{out.name}"})
        if what == "render" and method == "POST":
            body = self._body_json()
            engine = body.get("engine") if body.get("engine") in ("kokoro", "test-tone") else None
            job_id = uuid.uuid4().hex[:10]
            JOBS[job_id] = {"id": job_id, "project": p[1], "status": "queued", "progress": 0.0,
                            "message": "Waiting for the previous render" if RENDER_LOCK.locked() else "Starting",
                            "log": [], "result": None, "error": None, "started": time.time()}
            threading.Thread(target=_job_runner, args=(job_id, d, engine), daemon=True).start()
            return self._json(JOBS[job_id])
        if what == "open-folder" and method == "POST":
            folder = d / "out"
            folder.mkdir(exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)  # noqa: S606 (local desktop convenience)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            return self._json({"opened": str(folder)})
        raise ApiError(404, "Unknown endpoint")


def make_server(port: int) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    return httpd


def serve(port: int = 7860, open_browser: bool = True) -> None:
    for attempt in range(10):
        try:
            httpd = make_server(port + attempt)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"Ports {port}-{port + 9} are busy.")
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print()
    print("   o  .")
    print("  ooo   Insidir Video Studio " + config.VERSION)
    print("   o    Free, local, claim-checked short videos")
    print("   o")
    print("  ooo")
    print()
    print(f"{config.APP_NAME} is running at {url}")
    print("Keep this window open while you work. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
