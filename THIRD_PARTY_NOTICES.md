# Third-party software and models

All required components are free and allow commercial use. Check the current terms before you rely on them; this list reflects October 2026.

| Component | Use | Licence | Notes |
|---|---|---|---|
| Kokoro-82M (hexgrad) | Narration voices | Apache-2.0 | Weights fetched from the kokoro-onnx release page on first setup |
| kokoro-onnx | Runs Kokoro with ONNX Runtime | MIT | |
| ONNX Runtime | Inference | MIT | |
| espeak-ng (through espeakng-loader / phonemizer) | Phonemes for Kokoro | GPL-3.0 | Used as a separate library for pronunciation; it doesn't affect your videos |
| NumPy | Audio arrays | BSD-3-Clause | |
| FFmpeg (gyan.dev essentials build) | Editing, encoding, captions (libass) | GPL-3.0 | Run as a separate program. Rendered videos aren't covered by the GPL |
| Motion Canvas (`@motion-canvas/*`) | Animation engine for the templates | MIT | |
| Rough.js | Hand-drawn strokes and doodles | MIT | |
| Vite | Serves the templates to the headless browser | MIT | |
| Playwright (`playwright-core`) | Drives Edge / Chromium headlessly | Apache-2.0 | Chromium itself is BSD-licensed |
| Node.js | Runs Motion Canvas | MIT | Portable copy in `tools\node` |
| Faster Whisper + CTranslate2 | Caption timing | MIT | |
| Whisper `base.en` model (Systran conversion of OpenAI Whisper) | Caption timing | MIT | Downloaded from Hugging Face on first setup |
| Patrick Hand typeface (`@fontsource/patrick-hand`) | Hand-written labels in templates | SIL OFL 1.1 | |
| Inter typeface (`insidir_studio/fonts`) | Captions and UI | SIL OFL 1.1 | Licence in `insidir_studio/fonts/OFL.txt` |
| Source Serif 4, JetBrains Mono (the insidir.com fonts), Montserrat, Poppins, Anton, Bebas Neue, Archivo Black, Space Grotesk, Permanent Marker, Patrick Hand (`insidir_studio/fonts`) | Selectable caption and headline fonts | SIL OFL 1.1 | Published static weights from Fontsource, converted from WOFF2 to TTF with no other change (names kept, as Reserved Font Names require). Licences in `insidir_studio/fonts/licenses/` |
| Anthropic Python SDK (optional) | Claude API path | MIT | Only if you install it; API use is billed by Anthropic |
| Claude (claude.ai) | Script writing by copy and paste | Anthropic terms | Review Anthropic's terms for commercial use of outputs |

The studio bundles no talking-avatar model. If you add one, you're responsible for its licence and the licence of every checkpoint it loads. The studio blocks engines it knows are non-commercial (for example Wav2Lip) when a project is marked commercial.

Music you add must be licensed for commercial use. The studio ships none.

## Generate workspace (downloaded on demand, not bundled)

| Component | Use | Licence |
|---|---|---|
| PyTorch | Inference | BSD-3-Clause |
| diffusers, transformers, accelerate (Hugging Face) | Model pipelines | Apache-2.0 |
| Wan 2.1 / 2.2 models (Wan-AI) | Video generation | Apache-2.0 |
| LTX-Video (Lightricks), SkyReels V2 (Skywork), HunyuanVideo (Tencent), CogVideoX 5B (Zhipu) | Optional video models | Custom licences: read each before commercial use (shown in the app) |
| CogVideoX 2B | Optional video model | Apache-2.0 |
| Depth Anything V2 Small | Depth for camera paths and motion transfer | Apache-2.0 |
| ViTPose, RT-DETR | Pose for motion transfer | Apache-2.0 |
| OpenCV | Optical flow, scoring, edges | Apache-2.0 |
| CLIP ViT-B/32 (optional) | Prompt adherence score | MIT |
| RIFE (rife-ncnn-vulkan), Real-ESRGAN (realesrgan-ncnn-vulkan), GFPGAN | Optional if you install them | MIT, BSD-3-Clause, Apache-2.0 (check model weights) |
