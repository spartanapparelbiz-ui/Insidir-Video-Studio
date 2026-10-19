"""Open video-generation models the engine can run, with honest requirements.

Every entry is a real, published checkpoint in diffusers format. Nothing here is bundled:
weights download from Hugging Face on first use (free, no account needed for these repos).

licence:
  "apache-2.0"  free for commercial use
  "check"       a custom licence (often free below a revenue/user threshold, or with
                regional limits): read it before commercial use; the app shows the link
vram_gb: rough minimum with the engine's memory savers (CPU offload, VAE tiling) at the
         default resolution; more VRAM is faster. 0 means the tiny CPU test model.
"""

from __future__ import annotations

# tasks: t2v text-to-video, i2v image-to-video, flf2v first+last frame, v2v video-to-video (restyle),
#        r2v reference-to-video (characters/objects), control (pose/depth video), edit (masked inpaint),
#        extend (continue a clip from its last frames)
MODELS: dict[str, dict] = {
    "wan2.2-ti2v-5b": {
        "name": "Wan 2.2 TI2V 5B (720p, 24 fps)",
        "repo": "Wan-AI/Wan2.2-TI2V-5B-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["t2v", "i2v", "extend"], "vram_gb": 12, "disk_gb": 34,
        "default": {"width": 1280, "height": 704, "frames": 121, "fps": 24, "steps": 40, "guidance": 5.0},
        "note": "Best quality-per-VRAM open model: 720p 24 fps text- and image-to-video in one checkpoint.",
    },
    "wan2.2-t2v-a14b": {
        "name": "Wan 2.2 T2V A14B (MoE, cinematic)",
        "repo": "Wan-AI/Wan2.2-T2V-A14B-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["t2v"], "vram_gb": 24, "disk_gb": 126,
        "default": {"width": 1280, "height": 720, "frames": 81, "fps": 16, "steps": 40, "guidance": 4.0,
                    "guidance_2": 3.0},
        "note": "Highest-fidelity open text-to-video: film-grade lighting, composition and motion. Needs a big GPU.",
    },
    "wan2.2-i2v-a14b": {
        "name": "Wan 2.2 I2V A14B (MoE)",
        "repo": "Wan-AI/Wan2.2-I2V-A14B-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["i2v", "extend"], "vram_gb": 24, "disk_gb": 126,
        "default": {"width": 1280, "height": 720, "frames": 81, "fps": 16, "steps": 40, "guidance": 3.5,
                    "guidance_2": 3.5},
        "note": "Highest-fidelity open image-to-video.",
    },
    "wan2.1-t2v-1.3b": {
        "name": "Wan 2.1 T2V 1.3B (480p, fits 8 GB)",
        "repo": "Wan-AI/Wan2.1-T2V-1.3B-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["t2v"], "vram_gb": 8, "disk_gb": 29,
        "default": {"width": 832, "height": 480, "frames": 81, "fps": 16, "steps": 30, "guidance": 5.0},
        "note": "Runs on consumer cards. Good motion; softer detail than the 14B models.",
    },
    "wan2.1-t2v-14b": {
        "name": "Wan 2.1 T2V 14B (720p)",
        "repo": "Wan-AI/Wan2.1-T2V-14B-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["t2v"], "vram_gb": 24, "disk_gb": 70,
        "default": {"width": 1280, "height": 720, "frames": 81, "fps": 16, "steps": 40, "guidance": 5.0},
        "note": "Strong photorealism and physics; 24 GB+ recommended.",
    },
    "wan2.1-i2v-14b-720p": {
        "name": "Wan 2.1 I2V 14B (720p)",
        "repo": "Wan-AI/Wan2.1-I2V-14B-720P-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["i2v", "extend"], "vram_gb": 24, "disk_gb": 90,
        "default": {"width": 1280, "height": 720, "frames": 81, "fps": 16, "steps": 40, "guidance": 5.0},
        "note": "Turns any photo into a moving shot while keeping the subject's identity.",
    },
    "wan2.1-i2v-14b-480p": {
        "name": "Wan 2.1 I2V 14B (480p)",
        "repo": "Wan-AI/Wan2.1-I2V-14B-480P-Diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["i2v", "extend"], "vram_gb": 16, "disk_gb": 90,
        "default": {"width": 832, "height": 480, "frames": 81, "fps": 16, "steps": 40, "guidance": 5.0},
        "note": "Image-to-video at 480p for 16 GB cards.",
    },
    "wan2.1-flf2v-14b": {
        "name": "Wan 2.1 FLF2V 14B (start + end frame)",
        "repo": "Wan-AI/Wan2.1-FLF2V-14B-720P-diffusers", "family": "wan", "license": "apache-2.0",
        "tasks": ["flf2v", "i2v"], "vram_gb": 24, "disk_gb": 90,
        "default": {"width": 1280, "height": 720, "frames": 81, "fps": 16, "steps": 40, "guidance": 5.5},
        "note": "Give the first and last frame; the model generates the motion between them.",
    },
    "wan2.1-vace-1.3b": {
        "name": "Wan 2.1 VACE 1.3B (all-in-one: references, control, edits)",
        "repo": "Wan-AI/Wan2.1-VACE-1.3B-diffusers", "family": "wan-vace", "license": "apache-2.0",
        "tasks": ["t2v", "i2v", "r2v", "control", "edit", "extend", "flf2v"], "vram_gb": 8, "disk_gb": 19,
        "default": {"width": 832, "height": 480, "frames": 81, "fps": 16, "steps": 30, "guidance": 5.0},
        "note": "One model for character references, pose/depth motion transfer, object removal/replacement and "
                "extending clips. Runs on 8 GB cards.",
    },
    "wan2.1-vace-14b": {
        "name": "Wan 2.1 VACE 14B (all-in-one, 720p)",
        "repo": "Wan-AI/Wan2.1-VACE-14B-diffusers", "family": "wan-vace", "license": "apache-2.0",
        "tasks": ["t2v", "i2v", "r2v", "control", "edit", "extend", "flf2v"], "vram_gb": 24, "disk_gb": 75,
        "default": {"width": 1280, "height": 720, "frames": 81, "fps": 16, "steps": 40, "guidance": 5.0},
        "note": "The high-quality version of VACE: consistent characters, motion transfer and editing at 720p.",
    },
    "ltx-0.9.7-distilled": {
        "name": "LTX-Video 0.9.7 distilled (fast)",
        "repo": "Lightricks/LTX-Video-0.9.7-distilled", "family": "ltx", "license": "check",
        "license_url": "https://huggingface.co/Lightricks/LTX-Video-0.9.7-distilled",
        "tasks": ["t2v", "i2v", "flf2v", "extend", "v2v"], "vram_gb": 12, "disk_gb": 48,
        "default": {"width": 1216, "height": 704, "frames": 121, "fps": 24, "steps": 8, "guidance": 1.0},
        "note": "Very fast (8 steps), 24 fps, keyframe conditioning. Custom open-weights licence: free for "
                "smaller organisations; read it before commercial use.",
    },
    "skyreels-v2-df-1.3b": {
        "name": "SkyReels V2 DF 1.3B (long videos)",
        "repo": "Skywork/SkyReels-V2-DF-1.3B-540P-Diffusers", "family": "skyreels-df", "license": "check",
        "license_url": "https://huggingface.co/Skywork/SkyReels-V2-DF-1.3B-540P-Diffusers",
        "tasks": ["t2v", "extend"], "vram_gb": 10, "disk_gb": 30,
        "default": {"width": 960, "height": 544, "frames": 97, "fps": 24, "steps": 30, "guidance": 6.0},
        "note": "Diffusion forcing: keeps generating past the usual clip length without a visible seam.",
    },
    "hunyuanvideo": {
        "name": "HunyuanVideo 13B",
        "repo": "hunyuanvideo-community/HunyuanVideo", "family": "hunyuan", "license": "check",
        "license_url": "https://huggingface.co/tencent/HunyuanVideo/blob/main/LICENSE",
        "tasks": ["t2v"], "vram_gb": 24, "disk_gb": 40,
        "default": {"width": 1280, "height": 720, "frames": 61, "fps": 24, "steps": 30, "guidance": 6.0},
        "note": "Excellent human motion. Tencent licence excludes the EU, UK and South Korea and very large services.",
    },
    "cogvideox-2b": {
        "name": "CogVideoX 2B",
        "repo": "zai-org/CogVideoX-2b", "family": "cogvideox", "license": "apache-2.0",
        "tasks": ["t2v"], "vram_gb": 6, "disk_gb": 14,
        "default": {"width": 720, "height": 480, "frames": 49, "fps": 8, "steps": 40, "guidance": 6.0},
        "note": "Older and lower quality, but runs on 6 GB cards.",
    },
    # Not a real model: random weights at a tiny size, so the whole pipeline can be tested on any
    # CPU in seconds. Its output is noise by design and it is hidden unless tests or dev mode ask.
    "tiny-test": {
        "name": "Tiny test model (random weights, CPU, output is noise)",
        "repo": "", "family": "wan-tiny", "license": "apache-2.0", "test_only": True,
        "tasks": ["t2v", "i2v", "v2v", "r2v", "control", "edit", "extend", "flf2v"], "vram_gb": 0, "disk_gb": 0,
        "default": {"width": 64, "height": 64, "frames": 9, "fps": 8, "steps": 2, "guidance": 1.0},
        "note": "Plumbing test only.",
    },
}

# What each task needs from the user
TASKS = {
    "t2v": "Text to video",
    "i2v": "Image to video",
    "flf2v": "Start + end frame",
    "v2v": "Restyle a video (keep its motion)",
    "r2v": "Characters / objects from reference images",
    "control": "Motion transfer (pose or depth from a reference video)",
    "edit": "Edit a region (remove / replace with a mask)",
    "extend": "Extend a clip",
}

# Standard negative prompt published with Wan (translated); suppresses the usual artifacts.
WAN_NEGATIVE = ("bright colors, overexposed, static, blurred details, subtitles, style, artwork, painting, picture, "
                "still, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, "
                "extra fingers, poorly drawn hands, poorly drawn face, deformed, disfigured, misshapen limbs, "
                "fused fingers, still picture, messy background, three legs, many people in the background, "
                "walking backwards, flickering, morphing, warping, distorted face")


def public(include_test: bool = False) -> dict:
    return {k: v for k, v in MODELS.items() if include_test or not v.get("test_only")}


def best_for(task: str, vram_gb: float, installed: set[str], include_test: bool = False) -> str | None:
    """The model to suggest for a task: the best installed one that fits this GPU; on a CPU-only
    machine (vram 0) the smallest installed one, since everything runs there, only slowly."""
    cands = [k for k, m in MODELS.items() if task in m["tasks"] and (include_test or not m.get("test_only"))]
    if vram_gb <= 0:
        have = sorted((k for k in cands if k in installed), key=lambda k: MODELS[k]["vram_gb"])
        return have[0] if have else None
    fits = [k for k in cands if MODELS[k]["vram_gb"] <= vram_gb * 1.05]
    for k in fits:
        if k in installed:
            return k
    return fits[0] if fits else None
