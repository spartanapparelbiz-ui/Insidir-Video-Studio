# Insidir Video Studio

A local, free app for Windows 11 that makes 20–35 second vertical (1080×1920) videos for Insidir, in one browser interface:

- **Claude writes the script.** It's free with copy and paste: the studio builds the full prompt (your brief, your template, your footage and the approved facts). You paste it into claude.ai and paste the reply back. An Anthropic API key is optional and off by default.
- **Every kind of short video, in one place.** Pick a format on the Brief tab: animated explainers, a cartoon **avatar host** with real lip sync, a **text-chat** story, an **AI photo avatar**, **UGC** made from footage of you, or a cinematic **screen demo**. See [Video formats](#video-formats).
- **Motion Canvas animates it.** The animated templates are drawn in a hand-drawn chalkboard style with **Rough.js**. The narrator is the **Insidir dot figure**: the dotted "i" of the Insidir favicon, read as a little person that waves, points, thinks, shrugs and cheers. Frames render headlessly in Microsoft Edge (built into Windows 11) and stream straight into FFmpeg.
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
  - uses a first-person testimonial in an AI voice. (In UGC, where a real person speaks, first person is allowed, but personal results are still blocked and you are reminded to disclose payment with #ad.)

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

## Video formats

| Category | Format | What you give it | What you get |
|---|---|---|---|
| Animated | **Viral cinematic**, **Text chat**, **Dot explainer**, **Myth vs fact**, **Step by step**, **Big number**, **Screen sketch** | A script (Claude or an offline draft); optional Insidir recordings | Motion Canvas animation, Kokoro voice, captions, sound design |
| Avatars | **Avatar host** | A script | A cartoon presenter (Dot, Maya, Leo or Sam) talking to camera, lip-synced to the voice frame by frame, blinking, nodding and gesturing, and pointing up at your real Insidir screens. Runs on any PC with no GPU. |
| Avatars | **AI photo avatar** | A presenter photo you have the rights to, plus a local talking-avatar model (see below) | The photo lip-synced to the Kokoro narration, cut like UGC (face, split, bubble, screen), always labelled "AI-generated presenter" |
| UGC | **Talking head** | Clips of you talking (record them in the studio or upload them) | Your own voice and face, cut into tight jump cuts with captions from what you actually said |
| Screen demo | **Screen-recording demo** | Your Insidir screen recordings and screenshots | Cinematic cuts with a Kokoro voice-over |

### Saved avatars

Click **Avatars** in the top bar.

- **Import a photo:** a sharp, front-facing head-and-shoulders photo works best, 1024 px or larger.
- **Add a cartoon host:** Dot, Maya, Leo or Sam.
- Give each avatar a name and a voice. Use **Hear voice** to preview it.
- For a photo, click the middle of the face. Then confirm either:
  - that it's you or the person gave written consent, or
  - that the face is AI-generated.

Avatars are saved in `%USERPROFILE%\InsidirStudio\avatars` and stay there for every future project. On the Brief tab of an **AI photo avatar** or **Avatar host** video, pick one. Its voice comes with it.

**How realistic a photo avatar looks depends on the talking-avatar model you install** (see [Optional: talking avatar](#optional-talking-avatar)). With **InfiniteTalk** on a 24 GB+ NVIDIA GPU you get natural head and body motion and lip sync from a single photo. That is the closest open, local equivalent to paid avatar services. On a PC without a suitable GPU, photo avatars can't be animated realistically, and the studio won't fake it. Use the cartoon **Avatar host** or **UGC** instead.

### Voices

There are 34 Kokoro voices, all running on your PC:

- **Men (15):** US and UK voices, plus studio blends:
  - **Studio Male** (the default),
  - **Studio Male Deep**,
  - **Studio Narrator**,
  - **Studio Male (UK)**.
- **Women (19):** US and UK voices, plus studio blends:
  - **Studio Warm** (the default),
  - **Studio Bright**,
  - **Studio Calm**,
  - **Studio Female (UK)**.

Each voice shows Kokoro's own quality grade. Blends mix voices for a fuller, more natural read.

### Smoothness

In **High** quality, these formats render at 60 fps:

- animated templates,
- UGC,
- AI photo avatar.

Every UGC/avatar face shot gets a slow, eased push-in, computed at 2× resolution so it moves in half-pixel steps instead of jittering. The screen-demo cut stays at 30 fps.

### UGC: videos of you

1. Choose **Talking head (UGC)** on the Brief tab.
2. On the **Footage** tab, press **Start camera** and **Record**. A teleprompter scrolls your lines over the preview, and each take is saved straight into the project. You can also drop in clips filmed on your phone and set them to **Me on camera**. Click your face on the clip so the crops follow it.
3. Optional: on the **Script** tab, have Claude write talking points (or use an offline draft). They go to the teleprompter, not into the video.
4. Press **Transcribe my footage**. Faster Whisper splits what you said into sentences, on your PC. For each sentence:
   - untick it to cut it,
   - pick a layout:
     - **Face**: full screen,
     - **Split**: the Insidir app on top, your face below,
     - **Face bubble over app**: your face in a circle on the screen recording,
     - **App only**: your voice continues over the screen,
   - optionally add a headline,
   - fix spellings in the caption text, as long as the number of words stays the same.
5. Render. The studio cuts every pause longer than 0.3 s and every "um"/"uh" into a jump cut, alternating the framing so each cut lands as a punch-in. Screen recordings keep playing across cuts. Your voice is denoised and mastered to −14 LUFS. Captions, sound design and the end card are added as usual.

The claim guard still checks every kept sentence: numbers must be approved facts, and you can't promise returns. Your real voice is never called an AI voice. If you're paid or get free access, say so in the video and add #ad.

## The animated templates

| Template | What happens on screen | Use it for |
|---|---|---|
| **Text chat** | The script plays out as a phone conversation. Typing dots, message bubbles that pop in and light up word by word as they're read, approved figures as stat cards, and your real Insidir screens sent as photos. Set each beat to ME or THEM. | Relatable hooks: a friend asks, someone answers. |
| **Avatar host** | A cartoon presenter talks to camera. The mouth is driven by the voice (loudness for openness, brightness for lip width), with blinks, head nods and gestures per beat. Beats with footage or a figure go split-screen with the host pointing up at it; the rest are close-ups. Choose the host under **Voice & look**. | A face for the channel without filming. |
| **Viral cinematic** (default) | Huge kinetic captions that light up word by word, camera punch-ins, whip transitions with motion blur, cinematic light, approved figures that count up, and your real Insidir screens in a floating device with a spotlight. A progress bar runs along the top. | Reach on TikTok, Reels and Shorts. |
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

1. **Brief.** Pick a **video format**: an animated template, an avatar (cartoon host or AI photo avatar), UGC of you, or the screen-recording demo. Then set the topic, angle, audience, hook style, target length and call to action.
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

### Fonts

**Voice & look** has a **Caption font** and a **Headline font**. Each shows a live preview as you pick.

- **From insidir.com:** the fonts of the Insidir site itself:
  - **Insidir logo**, the wordmark face (Source Serif 4 Medium with the logo's tight spacing; the end-card wordmark and the studio header use it too). The "i" icon is drawn from dots, not a font.
  - **Inter**, the interface font and the default,
  - **Source Serif 4**, the site's headline serif,
  - **JetBrains Mono**, its data font.
- **Display fonts:** Montserrat, Poppins, Anton, Bebas Neue, Archivo Black, Space Grotesk, Permanent Marker and Patrick Hand.

The caption font is used for the spoken-word captions, in every format, including the kinetic captions and chat bubbles of the animated templates. The headline font is used for headlines, big numbers and titles. Leave the headline font on **Template default** to keep each template's own face. The disclosure labels, disclaimer and end card always stay in Inter, the brand face. Every font is SIL Open Font License, so commercial use is allowed.

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

## Generate: AI video from text, images and video

**Generate** (top bar, or `/generate.html`) runs open-source video generation models on your own GPU. Nothing is uploaded, and nothing is paid for. Weights download once from Hugging Face; no account is needed for these.

### What it takes, honestly

These models need an **NVIDIA GPU**. Rough guide to what each size of card runs:

| GPU memory | What runs well | Typical result |
|---|---|---|
| 8 GB | Wan 2.1 T2V 1.3B, Wan 2.1 VACE 1.3B | 832×480, 5 s at 16 fps, several minutes per clip |
| 12–16 GB | + Wan 2.2 TI2V 5B, LTX-Video, Wan I2V 480p | 1280×704 at 24 fps (Wan 2.2 5B) |
| 24 GB+ | + Wan 2.1/2.2 14B and A14B, VACE 14B, FLF2V | 720p; the most realistic open results |

- **Smaller cards:** the engine offloads layers to system RAM automatically, which is slower but works.
- **No NVIDIA GPU:** the models still run on the CPU, but expect hours per few seconds of video. On CPU, use small sizes and few steps.
- **Resolution:** 4K is reached by upscaling, not native generation. No open model generates native 4K video today.
- **Comparison with paid services:** the best open models, Wan 2.2 A14B and Wan 2.1 14B, are among the strongest available, open or closed. They don't win every shot against Kling, Runway or Higgsfield; the gap shows most on long, complex human action. The engine's job is to get the most out of them.

### Models

On the **Models** tab, each model shows its size, VRAM, licence and how it will fit your GPU, with a download button.

| Model | Licence | Best at |
|---|---|---|
| Wan 2.2 TI2V 5B | Apache-2.0 | 720p 24 fps text- and image-to-video on 12 GB+ |
| Wan 2.2 T2V / I2V A14B | Apache-2.0 | Highest-fidelity open video (24 GB+) |
| Wan 2.1 T2V 1.3B / 14B, I2V 480p / 720p, FLF2V | Apache-2.0 | Text-to-video, photo-to-video, start + end frame |
| Wan 2.1 VACE 1.3B / 14B | Apache-2.0 | One model for character references, motion transfer, masked edits, extending clips |
| LTX-Video 0.9.7 distilled | custom (read it) | Very fast, 24 fps, keyframes |
| SkyReels V2 DF | custom (read it) | Long videos without seams |
| HunyuanVideo | custom (regional limits) | Human motion |
| CogVideoX 2B | Apache-2.0 | Runs on 6 GB |

### What you can do

- **Text to video, image to video, start + end frame, restyle a video**: each with a choice of model.
- **Characters** (Characters tab): give a name, a fixed description and 2–4 reference photos. Consistency comes from two mechanisms:
  - the description goes into every prompt;
  - with VACE models, the photos go to the model itself (reference-to-video).

  Characters are saved for reuse in any video.
- **Motion transfer**: upload a reference video. Pose (ViTPose), depth (Depth Anything V2) or edges are extracted from it, and VACE moves your character the same way.
- **Precise camera moves from an image**: Depth Anything builds a depth scene from your start image, and the camera path is applied to it with real parallax. Supported moves include dolly zoom, orbit, crane, push and pull, FPV and crash zoom. VACE then renders the move. A full 360° orbit or bullet time needs views the image doesn't contain, so those moves are limited.
- **Editing**: paint a mask (white = change) and describe what should be there instead, to remove or replace objects or backgrounds.
- **Extend and long videos**: past a model's clip length (about 5 s), the engine continues from the last frames, using VACE or image-to-video. The overlapping frames are blended, so a 60 s shot is many seamless chunks.
- **Prompt engine**: your idea becomes the long, literal description these models follow best: camera, lens, lighting, motion and look. It also:
  - flags contradictions (night vs noon, static vs orbit),
  - maps "prompt adherence" onto guidance strength,
  - always shows the exact final prompt and negative prompt. You can switch enhancement off.
- **Automatic quality pass**:
  1. Generate several variations (different seeds).
  2. Score each one with measurable signals:
     - optical-flow warp error for temporal consistency (morphing scores low),
     - flicker,
     - sharpness,
     - motion,
     - glitch spikes,
     - exposure,
     - optionally, CLIP prompt adherence.
  3. Keep the best.
  4. Optionally:
     - stabilise (vid.stab),
     - de-flicker,
     - enhance faces (GFPGAN, if installed),
     - interpolate to 24/30/60 fps (RIFE if installed, else FFmpeg motion-compensated interpolation),
     - upscale 2×/4× (Real-ESRGAN if installed, else Lanczos),
     - add sound,
     - encode to H.264, H.265, ProRes or WebM.
- **Sound**: ambience matched to the prompt (rain, wind, city, forest, ocean, fire, crowd) and effects placed on the video's own motion peaks. Everything is synthesised locally, so there's nothing to license.
- **Film**: a description or script becomes scenes and shots with varied coverage and camera moves. You can also copy a prompt for Claude and paste back its JSON shot list. Then:
  - storyboard stills (one frame per shot),
  - edit any shot,
  - generate,
  - regenerate a single shot without redoing the rest,
  - assemble with cuts, crossfades, dip-to-black, whip or flash transitions, slow motion and speed per shot, Kokoro dialogue per character, and your music with optional cuts on the beat.
- **Queue and history**: jobs run one at a time on the GPU, with live progress and cancel. History survives restarts. Every result keeps its prompt, seed and scores.

### Not built in (yet)

- **Lip sync for photoreal generated faces** uses the talking-avatar step (Settings), not the Generate engine.
- **Generated audio from video models** (such as MMAudio) isn't enabled, because those weights are currently non-commercial.

## Optional: talking avatar

This powers the **AI photo avatar** format and animated presenter beats in the screen demo. The **Avatar host** cartoon doesn't need it. Turn it on in **Settings → Talking avatar**. The studio doesn't download or bundle any avatar model. You install one, then give the command line it should run. These placeholders are available: `{image}`, `{audio}`, `{output}` and `{outdir}`.

| Engine | Status (check the current licences yourself) |
|---|---|
| InfiniteTalk | Most realistic: photo → talking video with head/body motion, built on Wan2.1. Code and Wan2.1 weights published under Apache-2.0; check the audio encoder and every other bundled model. Needs a 24 GB+ GPU for good speed |
| EchoMimic | Portrait animation with head motion; code Apache-2.0, check the weights; 12–16 GB GPU |
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
| `insidir_studio/gen/` | Generate engine: model registry (`models.py`), loading and memory strategy (`manager.py`, `hardware.py`), generation, continuation and conditioning (`engine.py`), prompt engine, depth-based camera paths, pose/depth/edge control, quality scoring, post-processing, sound, characters, film planning and assembly, job queue, API |
| `insidir_studio/ugc.py` | UGC and AI photo avatar: transcription into sentences, jump-cut planning, face/split/bubble/screen layouts, the cut voice track |
| `insidir_studio/captions.py` | Animated ASS captions, headlines, disclosure labels, end card |
| `insidir_studio/avatar.py` | GPU detection, licence gate, external avatar command |
| `insidir_studio/animate.py` | Template catalogue, Motion Canvas job folder (data.json + media), lip-sync mouth track, Node bridge |
| `insidir_studio/whisper_align.py` | Faster Whisper word timestamps matched back to the script |
| `motion/scripts/render.mjs` | Headless render: Vite + Motion Canvas in Edge/Chromium, frames piped into FFmpeg |
| `motion/src/lib/figure.tsx` | The Insidir dot figure and its poses |
| `motion/src/lib/rough.tsx`, `icons.ts` | Rough.js strokes as Motion Canvas paths that draw on; doodle icons |
| `motion/src/templates/` | The animated and avatar templates (and `lib/presenter.tsx`, the cartoon hosts) |
| `insidir_studio/server.py`, `web/` | Local web app (127.0.0.1 only) |

The app is bound to `127.0.0.1`, checks the `Host` header against DNS rebinding, and refuses cross-origin writes.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the licences of the tools it uses.
