"""Command line: python -m insidir_studio [serve|doctor|render|new|download-models]"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from . import animate, avatar, compliance, config, project, render, script_writer, tts, whisper_align


def cmd_doctor(_args) -> int:
    ok = True
    print(f"{config.APP_NAME} {config.VERSION}")
    print(f"Home:    {config.studio_home()}")
    for tool in ("ffmpeg", "ffprobe"):
        path = config.find_tool(tool)
        print(f"{tool:8} {path or 'MISSING'}")
        ok &= bool(path)
    if config.find_tool("ffmpeg"):
        import subprocess
        out = subprocess.run([config.ffmpeg(), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for f in ("ass", "xfade", "zoompan", "loudnorm", "sidechaincompress"):
            has = f" {f} " in out
            print(f"  filter {f:18} {'ok' if has else 'MISSING (use a full FFmpeg build, e.g. gyan.dev essentials)'}")
            ok &= has
    ks = tts.kokoro_status()
    print(f"Kokoro:  package {'ok' if ks['installed'] else 'MISSING (pip install kokoro-onnx)'}; "
          f"model {ks['model'] or 'MISSING in ' + ks['models_dir']}")
    ok &= ks["ready"]
    ms = animate.status()
    print(f"Node:    {ms['node'] or 'MISSING (install.bat installs it)'} {ms['node_version'] or ''}")
    print(f"Motion:  {'Motion Canvas + Rough.js installed' if ms['motion_installed'] else 'MISSING (cd motion && npm ci)'}")
    ok &= ms["ready"]
    if ms["ready"]:
        b_ok, b_msg = animate.check_browser()
        print(f"Browser: {'ok ' + b_msg[3:] if b_ok else 'MISSING - ' + b_msg}")
        ok &= b_ok
    ws = whisper_align.status()
    print(f"Whisper: {'Faster Whisper installed' if ws['installed'] else 'not installed (optional; captions use estimated timing)'}"
          + (f", model {ws['model']} {'downloaded' if ws['downloaded'] else 'downloads on first use'}" if ws["installed"] else ""))
    print("Manim:   not needed (every template runs in Motion Canvas)")
    st = avatar.status(config.load_settings())
    gpus = ", ".join(f"{g['name']} ({g['vram_gb']} GB)" for g in st["gpus"]) or "none"
    print(f"GPU:     {gpus}")
    print(f"Avatar:  {'ready' if st['usable'] else 'off - ' + ' '.join(st['reasons'])}")
    facts = compliance.load_facts()
    print(f"Facts:   {len(facts.get('facts', []))} approved ({config.facts_path()})")
    print("All required parts are ready." if ok else "Some required parts are missing (see above).")
    return 0 if ok else 1


def _download(url: str, dest: Path) -> None:
    print(f"Downloading {dest.name} ...", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                print(f"\r  {got / total:5.1%} of {total / 1e6:.0f} MB", end="", flush=True)
    print()
    tmp.replace(dest)


def cmd_download_models(args) -> int:
    if args.whisper:
        if not whisper_align.available():
            print("Faster Whisper is not installed; skipping its model.")
            return 0
        print(f"Downloading the Faster Whisper '{whisper_align.MODEL}' model (about 140 MB) ...", flush=True)
        whisper_align.download()
        print(f"Whisper model is in {whisper_align.model_dir()}")
        return 0
    d = config.models_dir()
    names = ["voices-v1.0.bin", "kokoro-v1.0.int8.onnx" if args.small else "kokoro-v1.0.onnx"]
    for name in names:
        dest = d / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"{name} already present")
            continue
        _download(config.KOKORO_FILES[name], dest)
    print(f"Kokoro model files are in {d}")
    return 0


def cmd_new(args) -> int:
    """Create a project from files on disk with an offline script (handy for testing)."""
    brief = {"topic": args.topic or "", "mode": "animated" if args.template else "demo"}
    if args.template:
        brief["template"] = args.template
    proj = project.new(args.name, brief)
    d = project.project_dir(proj["id"])
    for f in args.files:
        src = Path(f)
        tmp = Path(tempfile.mkdtemp()) / src.name
        shutil.copyfile(src, tmp)
        a = project.add_asset(d, src.name, tmp)
        proj = project.load(d)
        for x in proj["assets"]:
            if x["id"] == a["id"]:
                x["rights_confirmed"] = True
                x["genuine"] = bool(args.genuine and x["role"] in ("screen", "image"))
                if x["role"] == "image" and args.genuine:
                    x["role"] = "screen"
        project.save(d, proj)
    proj = project.load(d)
    proj["script"] = script_writer.template_script(proj, compliance.load_facts(), args.variant)
    if args.voice:
        proj["voice"]["voice"] = args.voice
    project.save(d, proj)
    print(json.dumps({"id": proj["id"], "dir": str(d)}, indent=2))
    return 0


def cmd_render(args) -> int:
    d = Path(args.project)
    if not (d / "project.json").exists():
        d = project.project_dir(args.project)
    report = render.render(d, engine_name=args.engine)
    print(json.dumps({k: report[k] for k in ("file", "duration", "width", "height", "shots", "render_seconds")}, indent=2))
    return 0


def cmd_serve(args) -> int:
    from . import server
    server.serve(args.port, open_browser=not args.no_browser)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="insidir_studio", description=config.APP_NAME)
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="start the local app (default)")
    s.add_argument("--port", type=int, default=7860)
    s.add_argument("--no-browser", action="store_true")
    sub.add_parser("doctor", help="check FFmpeg, Kokoro, GPU")
    dm = sub.add_parser("download-models", help="download the Kokoro voice model")
    dm.add_argument("--small", action="store_true", help="int8 model (88 MB) instead of full (310 MB)")
    dm.add_argument("--whisper", action="store_true", help="download the Faster Whisper caption model instead")
    n = sub.add_parser("new", help="create a project from files with an offline script")
    n.add_argument("name")
    n.add_argument("files", nargs="*")
    n.add_argument("--topic")
    n.add_argument("--voice")
    n.add_argument("--variant", type=int, default=0)
    n.add_argument("--genuine", action="store_true", help="mark the files as genuine Insidir recordings")
    n.add_argument("--template", choices=list(animate.TEMPLATES), help="make an animated video with this template")
    r = sub.add_parser("render", help="render a project folder or id")
    r.add_argument("project")
    r.add_argument("--engine", choices=["kokoro", "test-tone"], default=None)
    args = p.parse_args(argv)
    if args.cmd is None:
        args = p.parse_args(["serve", *(argv or sys.argv[1:])])
    return {"serve": cmd_serve, "doctor": cmd_doctor, "download-models": cmd_download_models,
            "new": cmd_new, "render": cmd_render}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
