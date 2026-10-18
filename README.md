# Insidir Video Studio

A local, free app for Windows 11 that makes 20–35 second vertical (1080×1920) UGC-style videos for Insidir:

- **Claude writes the script.** It's free with copy and paste: the studio builds the full prompt (your brief, your footage and the approved facts). You paste it into claude.ai and paste the reply back. An Anthropic API key is optional and off by default.
- **Kokoro speaks it.** Kokoro-82M (Apache-2.0) runs on your CPU, with 15 natural English voices. Captions are timed from the audio.
- **FFmpeg edits it.** Your real Insidir screen recordings and screenshots are cut on the spoken words: J-cuts, wide → tight → tighter framing, slow push-ins, quick transitions only where the subject changes. Captions pop in and highlight each word as it's spoken. Headlines, an end card, loudness at −14 LUFS, and optional licensed music that ducks under the voice.
- **It stays honest.** A claim guard blocks the render if the script states a number that isn't an approved fact, promises returns, tells anyone to buy or sell, implies nonpublic information, or uses a first-person testimonial. Every video is labelled "AI voice". An AI-generated presenter is labelled "AI-generated presenter", genuine product footage is labelled "Real Insidir screen recording", and the last beat carries "Research tool. Not investment advice."
- **The talking avatar is optional.** It is used only if you install a local model yourself, an NVIDIA GPU with enough memory is present, the model is not known to forbid commercial use, and you confirm you've checked its licence.

There are no paid APIs, subscriptions, credit cards or watermarks. Nothing leaves your computer except the model download on first setup and anything you choose to paste into Claude.

## Install (Windows 10/11)

1. Download this repository (Code → Download ZIP) and unzip it, for example to `C:\InsidirVideoStudio`.
2. Double-click **`install.bat`**. It:
   - finds Python 3.10–3.13, or installs Python 3.12 with `winget`,
   - creates `.venv` and installs `kokoro-onnx`,
   - downloads FFmpeg (the gyan.dev essentials build, which includes libass) to `tools\ffmpeg` if FFmpeg isn't already installed,
   - downloads the Kokoro model (310 MB) and voices (28 MB) to `%USERPROFILE%\InsidirStudio\models`,
   - runs a self-check and adds a desktop shortcut.
3. Double-click **`start.bat`**. The studio opens in your browser at `http://127.0.0.1:7860`. Keep the window open while you work.

To use the smaller 88 MB voice model on a slow machine, run `.venv\Scripts\python -m insidir_studio download-models --small`.

## Making a video

1. **Brief.** Set the topic, angle, audience, hook style, target length and call to action.
2. **Footage.** Drop in screen recordings of the real product (Win+Alt+R with Xbox Game Bar, or OBS) and screenshots. On each file, tick:
   - *I have the rights to use it commercially.* This is required for every file you use.
   - *Genuine recording of the real Insidir product*, for demo footage.
   - *AI-generated person*, for any synthetic presenter or image. It is labelled on screen.

   Add a short note on what each clip shows; Claude uses these notes to choose shots.
3. **Script.** Click **Copy prompt**, open claude.ai, paste it, then paste Claude's whole reply back and click **Use this reply**. You can also start from an offline draft. Edit any beat. For each beat you can:
   - choose the footage,
   - set the start second in a recording,
   - click the thumbnail to set where close-ups aim,
   - set the close-up zoom,
   - add an on-screen headline.

   The claim guard panel updates as you type.
4. **Voice & look.** Pick a Kokoro voice and preview it. You can also set:
   - the speaking rate,
   - the caption highlight colour,
   - hard cuts or cinematic transitions,
   - the end card,
   - music level,
   - the presenter avatar.
5. **Render.** A checklist confirms everything is ready. The MP4 is saved in the project's `out` folder with:
   - a `.json` report: facts used, assets, AI disclosures and warnings,
   - a `.txt` disclosure you can paste into the post caption.

   Also switch on the platform's own "AI-generated" label when you post.

Rendering a 30-second video takes about 1 minute on a typical laptop CPU.

### How the length is kept to 20–35 s

The studio voices the script and measures it. If it runs slightly over or under, it re-voices once at a speaking rate between 0.85× and 1.2×. If it's still outside 20–35 s, the render stops and tells you to cut or add a line. About 50–75 words is right.

## Facts and the claim guard

`facts/insidir_facts.json` is copied to `%USERPROFILE%\InsidirStudio\facts.json` on first run, and you can edit it in the app (**Facts**). Each fact has:

- the claim text,
- a source you can show,
- the numbers it allows.

The guard only lets a script use numbers listed there. Document names like "Form 4", "10-K" and "Rule 16a-3" are exempt. Before each campaign, check that pricing and features are still current. The shipped facts were taken from the Insidir site and docs as of 18 October 2026.

The guard blocks:

- figures that aren't approved,
- return or profit claims, "beat the market", "guaranteed", "risk-free",
- buy/sell/short directions and price predictions,
- "insider tips", "secret", "nonpublic", "before Wall Street",
- first-person testimonials ("I made…", "I've been using…", "my portfolio…"), because the narrator is an AI voice,
- "real-time" claims,
- files used without confirmed rights.

It warns on anything that looks like a ticker.

## Optional: talking avatar

Turn it on in **Settings → Talking avatar**. The studio doesn't download or bundle any avatar model. You install one, then give the command line it should run. These placeholders are available: `{image}`, `{audio}`, `{output}` and `{outdir}`.

| Engine | Status (check the current licences yourself) |
|---|---|
| SadTalker | Repository Apache-2.0 in recent versions; downloaded weights have their own terms |
| MuseTalk | Code MIT; loads third-party weights with their own licences; call it through a small wrapper script |
| Wav2Lip | Research / non-commercial only, so it is **blocked** for commercial projects |
| Custom | Any command that turns an image and a WAV into a video |

The step runs only when all of these are true:

- an NVIDIA GPU is detected with at least the memory you set (default 8 GB),
- the engine isn't marked non-commercial,
- you tick the licence confirmation.

Otherwise presenter beats use the still photo with slow camera motion. Avatar shots are always labelled "AI-generated presenter". Only use a real person's photo with their written consent.

## Optional: Claude API

If you already have an Anthropic API key, **Settings → Claude** can send the prompt for you with "Ask Claude API". It defaults to the `claude-opus-5-5` model with adaptive thinking. Anthropic bills API calls, so this is off by default and never required. The key is stored only in `%USERPROFILE%\InsidirStudio\settings.json`. Install the SDK first with `.venv\Scripts\pip install anthropic`.

## Command line

```
.venv\Scripts\python -m insidir_studio doctor            # check FFmpeg, Kokoro, GPU, avatar
.venv\Scripts\python -m insidir_studio serve             # the app (what start.bat runs)
.venv\Scripts\python -m insidir_studio new "Name" clip.mp4 shot.png --genuine   # project + offline script
.venv\Scripts\python -m insidir_studio render <project-id-or-folder>
.venv\Scripts\python -m unittest discover -s tests       # tests (needs FFmpeg, not the model)
```

You can set these environment variables:

- `INSIDIR_STUDIO_HOME` moves projects and settings,
- `INSIDIR_MODELS_DIR` moves the model,
- `INSIDIR_FFMPEG` and `INSIDIR_FFPROBE` point at specific binaries.

## How it's built

| File | Job |
|---|---|
| `insidir_studio/script_writer.py` | Claude prompt, reply parser, optional API call, offline drafts |
| `insidir_studio/compliance.py` | Claim guard |
| `insidir_studio/tts.py` | Kokoro narration, per-sentence synthesis, word alignment from the waveform, fit to 20–35 s |
| `insidir_studio/timeline.py` | Edit decision list: J-cuts, shot splits on word starts, framings, transitions, 30 fps grid |
| `insidir_studio/render.py` | FFmpeg: per-shot segments (blurred backdrop, focus crop, supersampled zoom), runs, xfades, ASS captions, voice/music mix, loudness |
| `insidir_studio/captions.py` | Animated ASS captions, headlines, disclosure labels, end card |
| `insidir_studio/avatar.py` | GPU detection, licence gate, external avatar command |
| `insidir_studio/server.py`, `web/` | Local web app (127.0.0.1 only) |

The app is bound to `127.0.0.1`, checks the `Host` header against DNS rebinding, and refuses cross-origin writes.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the licences of the tools it uses.
