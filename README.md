# Insidir Video Studio

A local, free app for Windows 11 that makes 20–35 second vertical (1080×1920) videos for Insidir, in one browser interface:

- **Claude writes the script.** It's free with copy and paste: the studio builds the full prompt (your brief, your template, your footage and the approved facts). You paste it into claude.ai and paste the reply back. An Anthropic API key is optional and off by default.
- **Motion Canvas animates it.** Five reusable templates are drawn in a hand-drawn chalkboard style with **Rough.js**. The narrator is the **Insidir dot figure**: the dotted "i" of the Insidir favicon, read as a little person that waves, points, thinks, shrugs and cheers. Frames render headlessly in Microsoft Edge (built into Windows 11) and stream straight into FFmpeg.
- **Kokoro speaks it, mastered like a real voice-over.** Kokoro-82M (Apache-2.0) runs on your CPU using the full-precision model. Pick **Man** or **Woman** in **Voice & look**. The default man's voice is **Studio Male** (a Michael + Fenrir blend, the clearest male voice in testing), with Studio Male Deep and single voices as options. The woman's default is **Studio Warm**, a blend of Kokoro's two top-rated voices (Heart and Bella). Every narration is upsampled to 48 kHz with soxr and run through EQ (less mud, more warmth and presence), de-essing, gentle compression and a two-pass loudness match to −14 LUFS. "Insidir" is always pronounced "insider", while captions keep the real spelling.
- **Faster Whisper times the captions.** It listens to the finished narration and lines every caption word up with the voice, on your computer. It matched 94–96% of words in testing; if it's missing, timing is estimated from the audio.
- **Sound design and music, made on your PC.** Whooshes land on every cut, hits on the hook and big numbers, and a riser leads into the end card. An original dark, minimal music bed sits under the voice and ducks while it speaks. Every sound is synthesized from oscillators and noise when you render, so there is no sample library and nothing to license. Your own licensed track replaces the bed if you add one. Both can be switched off in **Voice & look**.
- **High quality by default.** Animated templates render at 60 fps from a near-lossless intermediate. The final encode is H.264 High (slow preset, CRF 16, tuned for animation), BT.709 colour, 48 kHz / 256 kbps AAC. Switch to **Standard** (30 fps) in **Voice & look** for faster renders.
- **FFmpeg edits and exports it.** It burns in captions that pop and highlight each word as it's spoken, the AI labels and the end card, mixes the voice (and optional licensed music) to −14 LUFS, and exports H.264 MP4.
- **The screen-recording demo style is still here.** It makes cinematic cuts of your real Insidir recordings: J-cuts, wide → tight → tighter framing, slow push-ins.
- **It stays honest.** A claim guard blocks the render if the script or anything drawn on screen:
  - states a number that isn't an approved fact,
  - promises returns or tells anyone to buy or sell,
  - implies nonpublic information,
  - uses a first-person testimonial.

  A MYTH card must be followed straight away by the FACT card that corrects it. Genuine footage is labelled "Real Insidir screen recording", an AI-generated presenter is always labelled, and the last beat carries "Research tool. Not investment advice." An on-screen "AI voice" label is off by default; you can switch it on in **Voice & look**. Each render's post-caption text and file metadata still say the narration is an AI voice, and some platforms ask you to tick their AI-content label for synthetic voices.

There are no paid APIs, subscriptions, credits, credit cards or watermarks. Nothing leaves your computer except the free downloads on first setup and anything you choose to paste into Claude. **Manim isn't used:** every template runs in Motion Canvas, so it was never needed.

## Install and launch on Windows 11

1. On GitHub, open **spartanapparelbiz-ui/Insidir-Video-Studio** (branch **`main`**), then click **Code → Download ZIP**. You can also clone it:
   `git clone https://github.com/spartanapparelbiz-ui/Insidir-Video-Studio.git C:\InsidirVideoStudio`
2. If you downloaded the ZIP, right-click it → **Extract All…** → `C:\InsidirVideoStudio`. Use a short path with no special characters.
3. Open the folder and double-click **`install.bat`**. If Windows SmartScreen asks, click **More info → Run anyway**. The first run takes 5–15 minutes and downloads about 1 GB. It installs into the folder (no admin rights needed):
   1. Python 3.12 (with `winget`) if you don't have Python 3.10–3.13,
   2. Python packages in `.venv`: **kokoro-onnx** and **faster-whisper**,
   3. **FFmpeg** in `tools\ffmpeg` (the gyan.dev build, with libass and libvpx),
   4. **Node.js 22 LTS** in `tools\node` (portable; checksum verified),
   5. **Motion Canvas 3.17, Rough.js 4.6 and Vite** in `motion\node_modules` (exact versions from the lockfile),
   6. a render browser: Microsoft Edge, or Playwright's Chromium if Edge can't be used,
   7. the Kokoro voice model, to `%USERPROFILE%\InsidirStudio\models`,
   8. the Faster Whisper `base.en` caption model (about 140 MB).

   It ends with a self-check, where every line should say ok or ready, and adds a desktop shortcut.
4. Double-click **`start.bat`** (or the **Insidir Video Studio** desktop shortcut). A console window opens and your browser goes to **http://127.0.0.1:7860**. Keep the console window open while you work; close it (or press Ctrl+C) to stop the studio.
5. To check the setup at any time, open a terminal in the folder and run `.venv\Scripts\python -m insidir_studio doctor`.

To update later, download the new ZIP (or `git pull`) into the same folder and run `install.bat` again. Your projects live in `%USERPROFILE%\InsidirStudio` and are kept.

To use the smaller 88 MB voice model on a slow machine, run `.venv\Scripts\python -m insidir_studio download-models --small`.

## The animated templates

| Template | What happens on screen | Use it for |
|---|---|---|
| **Viral cinematic** (default) | Huge kinetic captions that light up word by word, camera punch-ins, whip transitions with motion blur, cinematic light and film grain, approved figures that count up, and your real Insidir screens in a floating device with a spotlight. A progress bar runs along the top. | Reach on TikTok, Reels and Shorts. |
| **Dot explainer** | The dot figure explains one idea per beat. A doodle (form, calendar, magnifier…) is drawn on beside it and the headline is written in with an underline. | Any topic. The default. |
| **Myth vs fact** | Cards whip in. MYTH cards get scribbled out in red while the figure shrugs; FACT cards get a green tick. | Correcting misconceptions. |
| **Step by step** | Numbered hand-drawn boxes joined by arrows, each ticked off as the next one starts. | How-tos. |
| **Big number** | An approved figure ("2 business days", "15 minutes") written huge and circled. | Facts with a number. |
| **Screen sketch** | A real Insidir screenshot or recording in a hand-drawn window, slowly zooming. The spot you click is circled, and the figure points at it with an arrow. | Showing the real product. |

Every template:

- keeps the top-left corner clear for the AI labels and the lower third for captions,
- times every beat to the narration to the frame,
- makes the figure's head nod on each spoken word.

There are 23 doodle icons and 11 poses. Pick them per beat on the Script tab, or let Claude choose them.

The templates live in `motion/src/templates/*.tsx`; the drawing helpers are in `motion/src/lib/`. Edit a template, then render a project to see the change.

The style is a dark, chalk-on-ink hand-drawn explainer look. The palette is Insidir's paper and ink, with bright white for emphasis (red and green only on MYTH/FACT cards), set in `insidir_studio/animate.py` (`PALETTE`).

## Making a video

1. **Brief.** Pick a **video style**: one of the five animated templates or the screen-recording demo. Then set the topic, angle, audience, hook style, target length and call to action.
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
| `insidir_studio/animate.py` | Template catalogue, Motion Canvas job folder (data.json + media), Node bridge |
| `insidir_studio/whisper_align.py` | Faster Whisper word timestamps matched back to the script |
| `motion/scripts/render.mjs` | Headless render: Vite + Motion Canvas in Edge/Chromium, frames piped into FFmpeg |
| `motion/src/lib/figure.tsx` | The Insidir dot figure and its poses |
| `motion/src/lib/rough.tsx`, `icons.ts` | Rough.js strokes as Motion Canvas paths that draw on; doodle icons |
| `motion/src/templates/` | The five templates |
| `insidir_studio/server.py`, `web/` | Local web app (127.0.0.1 only) |

The app is bound to `127.0.0.1`, checks the `Host` header against DNS rebinding, and refuses cross-origin writes.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the licences of the tools it uses.
