"""Generation job queue: one worker (one GPU), persistent history, progress and cancellation."""

from __future__ import annotations

import json
import queue
import threading
import time
import traceback
import uuid
from dataclasses import asdict
from pathlib import Path

from .. import config


def gen_dir() -> Path:
    d = config.studio_home() / "generate"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Queue:
    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self.cancels: dict[str, threading.Event] = {}
        self.q: queue.Queue = queue.Queue()
        self.lock = threading.RLock()
        self._load()
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    # ------------------------------------------------------------ persistence
    def _hist(self) -> Path:
        return gen_dir() / "history.json"

    def _load(self):
        try:
            for j in json.loads(self._hist().read_text(encoding="utf-8")):
                if j["status"] in ("queued", "running"):
                    j.update(status="error", error="The app was closed while this was running. Run it again.")
                self.jobs[j["id"]] = j
        except (OSError, ValueError):
            pass

    def _save(self):
        with self.lock:
            items = sorted(self.jobs.values(), key=lambda j: j["created"], reverse=True)[:500]
            tmp = self._hist().with_suffix(".tmp")
            tmp.write_text(json.dumps([{k: v for k, v in j.items() if k != "log_full"} for j in items], indent=1),
                           encoding="utf-8")
            tmp.replace(self._hist())

    # ------------------------------------------------------------ api
    def submit(self, kind: str, payload: dict, title: str = "") -> dict:
        jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:5]
        job = {"id": jid, "kind": kind, "title": title or payload.get("prompt", "")[:80] or kind, "payload": payload,
               "status": "queued", "progress": 0.0, "message": "Waiting for the GPU", "log": [], "result": None,
               "error": None, "created": time.time(), "started": None, "finished": None,
               "dir": str(gen_dir() / jid)}
        with self.lock:
            self.jobs[jid] = job
            self.cancels[jid] = threading.Event()
            self._save()
        self.q.put(jid)
        return job

    def cancel(self, jid: str) -> dict:
        with self.lock:
            job = self.jobs[jid]
            if job["status"] == "queued":
                job.update(status="cancelled", message="Cancelled", finished=time.time())
            ev = self.cancels.get(jid)
            if ev:
                ev.set()
            self._save()
            return job

    def delete(self, jid: str) -> None:
        import shutil
        with self.lock:
            job = self.jobs.pop(jid, None)
            self._save()
        if job:
            shutil.rmtree(job["dir"], ignore_errors=True)

    def get(self, jid: str) -> dict:
        return self.jobs[jid]

    def list(self) -> list[dict]:
        return sorted(self.jobs.values(), key=lambda j: j["created"], reverse=True)

    # ------------------------------------------------------------ worker
    def _run(self):
        while True:
            jid = self.q.get()
            job = self.jobs.get(jid)
            if not job or job["status"] != "queued":
                continue
            ev = self.cancels[jid]
            job.update(status="running", started=time.time(), message="Starting")
            self._save()

            def log(msg, job=job):
                job["log"] = (job["log"] + [str(msg)])[-400:]

            def progress(f, msg="", job=job):
                job["progress"] = round(float(f), 4)
                if msg:
                    job["message"] = msg

            try:
                job["result"] = HANDLERS[job["kind"]](job["payload"], Path(job["dir"]), progress, ev, log)
                job.update(status="done", progress=1.0, message="Done")
            except Exception as e:  # noqa: BLE001 - every failure is reported on the job
                from .engine import Cancelled
                if isinstance(e, (Cancelled, InterruptedError)) or ev.is_set():
                    job.update(status="cancelled", message="Cancelled")
                else:
                    job.update(status="error", error=_friendly(e), message="Failed")
                    log(traceback.format_exc()[-3000:])
            finally:
                job["finished"] = time.time()
                self._save()


def _friendly(e: Exception) -> str:
    s = str(e)
    if "out of memory" in s.lower() or "CUDA out of memory" in s:
        return ("The GPU ran out of memory. Try a smaller size, fewer frames, or a smaller model; the engine already "
                "offloads layers to system RAM when it has to.")
    return s or type(e).__name__


# ------------------------------------------------------------------ handlers

def _generate(payload, out_dir, progress, cancel, log):
    from .engine import Spec, generate
    fields = Spec.__dataclass_fields__
    spec = Spec(**{k: v for k, v in payload.items() if k in fields})
    return generate(spec, out_dir, progress, cancel, log)


def _download(payload, out_dir, progress, cancel, log):
    from . import manager
    path = manager.download(payload["model"], progress, cancel)
    log(f"downloaded to {path}")
    return {"model": payload["model"], "path": path}


def _film(payload, out_dir, progress, cancel, log):
    from . import story
    return story.render_film(payload, out_dir, progress, cancel, log)


HANDLERS = {"generate": _generate, "download": _download, "film": _film}

_queue: Queue | None = None


def queue_() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue()
    return _queue


def spec_dict(spec) -> dict:
    return asdict(spec)
