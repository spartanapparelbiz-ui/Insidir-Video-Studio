"""Tests for the generation engine (insidir_studio.gen).

The engine runs the real diffusers pipelines; here they get tiny random-weight components
("tiny-test") so everything runs on a CPU in seconds. Their pixels are noise by design: these
tests check the plumbing (conditioning, continuation, scoring, post-processing, queue), not looks.
"""

import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="ivs-gen-test-"))
os.environ["INSIDIR_STUDIO_HOME"] = str(TMP)

import numpy as np  # noqa: E402

from insidir_studio import config, media  # noqa: E402
from insidir_studio.gen import camera, models, post, prompt, quality, story  # noqa: E402

try:
    import diffusers  # noqa: F401
    import torch  # noqa: F401
    HAVE_TORCH = True
except ImportError:
    HAVE_TORCH = False


def _video(path: Path, kind: str, n: int = 24, size=(96, 64)) -> Path:
    w, h = size
    frames = []
    for i in range(n):
        if kind == "smooth":   # a gradient sliding slowly: perfectly explainable motion
            x = np.linspace(0, 1, w)[None, :] + i * 0.01
            f = (np.sin(x * 6) * 0.5 + 0.5)[..., None].repeat(h, 0).repeat(3, 2)
        else:                  # independent noise every frame: nothing carries over
            f = np.random.default_rng(i).random((h, w, 3))
        frames.append((f * 255).astype(np.uint8))
    return post.write_video(np.asarray(frames), 12, path)


class PromptTests(unittest.TestCase):
    def test_enhance_adds_camera_lens_light_and_negatives(self):
        r = prompt.enhance("a fox in the snow", camera=["push_in", "orbit"], lens="85", lighting="dusk")
        self.assertIn("push-in", r["prompt"])
        self.assertIn("orbit", r["prompt"])
        self.assertIn("85mm", r["prompt"])
        self.assertIn("dusk", r["prompt"].lower())
        self.assertIn("flickering", r["negative"])
        self.assertIn("yellow", r["negative"])                       # brand rule: never yellow
        self.assertFalse(any("golden" in v or "candle" in v for v in prompt.LIGHTING.values()))
        self.assertTrue(r["prompt"].startswith("a fox in the snow."))

    def test_conflicts_and_adherence(self):
        self.assertTrue(prompt.conflicts("a city at night at noon"))
        self.assertTrue(prompt.conflicts("static tripod shot, orbit around her"))
        self.assertFalse(prompt.conflicts("a calm lake at dawn"))
        self.assertLess(prompt.guidance_for(0, 5), prompt.guidance_for(1, 5))

    def test_characters_go_into_every_prompt(self):
        r = prompt.enhance("she walks in", characters=[{"name": "Mara", "description": "short black hair, leather jacket"}])
        self.assertIn("Mara: short black hair, leather jacket", r["prompt"])


class PlanTests(unittest.TestCase):
    def test_sizes_and_frames_snap_to_what_models_accept(self):
        from insidir_studio.gen.engine import Spec, plan_size
        m = models.MODELS["wan2.1-t2v-1.3b"]
        w, h, chunk, total, fps = plan_size(Spec(aspect="9:16", seconds=10), m)
        self.assertEqual((w % 16, h % 16), (0, 0))
        self.assertGreater(h, w)
        self.assertEqual((total - 1) % 4, 0)
        self.assertEqual(chunk, 81)
        self.assertGreater(total, chunk)                     # 10 s needs continuation
        ltx = models.MODELS["ltx-0.9.7-distilled"]
        w, h, chunk, total, fps = plan_size(Spec(aspect="16:9", seconds=5), ltx)
        self.assertEqual((w % 32, h % 32, (total - 1) % 8), (0, 0, 0))
        self.assertEqual(plan_size(Spec(seconds=0), m)[2:4], (1, 1))   # storyboard still

    def test_every_model_entry_is_complete(self):
        for k, m in models.MODELS.items():
            for f in ("name", "repo", "family", "license", "tasks", "vram_gb", "default"):
                self.assertIn(f, m, k)
            self.assertTrue(set(m["tasks"]) <= set(models.TASKS), k)


class VaceInputTests(unittest.TestCase):
    def test_masks_keep_the_given_frames(self):
        from PIL import Image
        from insidir_studio.gen.engine import vace_inputs
        img = Image.new("RGB", (32, 32), (255, 0, 0))
        v, m = vace_inputs("flf2v", 9, 32, 32, image=img, last=img)
        self.assertEqual(len(v), 9)
        self.assertEqual([np.asarray(x).max() for x in m], [0] + [255] * 7 + [0])
        prior = [img] * 8
        v, m = vace_inputs("extend", 9, 32, 32, prior=prior)
        self.assertEqual(sum(np.asarray(x).max() == 0 for x in m), 2)   # last quarter of the previous chunk kept
        self.assertEqual(vace_inputs("t2v", 9, 32, 32), (None, None))


class CameraTests(unittest.TestCase):
    def test_push_in_moves_near_things_more_than_far_things(self):
        h, w = 64, 64
        depth = np.zeros((h, w), np.float32)
        depth[:, w // 2:] = 1.0                         # right half near, left half far
        img = np.tile(np.arange(w, dtype=np.uint8)[None, :] * 4, (h, 1))
        p = camera.path(["push_in"], 1.0)
        out = camera.warp(img, depth, p, 1.0, 0.5)
        far_shift = np.abs(out[:, 8].astype(int) - img[:, 8].astype(int)).mean()
        near_shift = np.abs(out[:, 56].astype(int) - img[:, 56].astype(int)).mean()
        self.assertGreater(near_shift, far_shift)
        self.assertEqual(camera.path([], 0.5)["tz"], 0.0)
        dz = camera.path(["dolly_zoom"], 1.0)
        self.assertGreater(dz["tz"], 0)
        self.assertLess(dz["zoom"], 1)                   # zooms out while dollying in


@unittest.skipUnless(config.find_tool("ffmpeg"), "FFmpeg not installed")
class QualityAndPostTests(unittest.TestCase):
    def test_scores_prefer_coherent_video(self):
        good = quality.score(str(_video(TMP / "smooth.mp4", "smooth")))
        bad = quality.score(str(_video(TMP / "noise.mp4", "noise")))
        self.assertGreater(good["consistency"], bad["consistency"])
        self.assertGreater(good["total"], bad["total"])

    def test_post_interpolates_upscales_stabilises(self):
        src = _video(TMP / "post_src.mp4", "smooth")
        out = post.finish(src, TMP / "post" / "final.mp4", 12, {"fps": 24, "upscale": 2, "upscaler": "fast",
                                                              "stabilize": True, "deflicker": True,
                                                              "film_finish": True}, log=lambda m: None)
        info = media.probe(out)
        self.assertEqual((info["width"], info["height"]), (192, 128))
        self.assertAlmostEqual(post._fps(out), 24, delta=0.5)

    @unittest.skipUnless(HAVE_TORCH, "PyTorch not installed")
    def test_ai_upscaler_is_4x_and_writes_video(self):
        from insidir_studio.gen import upscale
        upscale._model.update(net=upscale._net().eval(), dev="cpu")   # random weights: shapes only, no download
        try:
            f = upscale.upscale_frame(np.zeros((20, 30, 3), np.uint8), tile=16, pad=4)
            self.assertEqual(f.shape, (80, 120, 3))
            out = upscale.upscale_video(_video(TMP / "up_src.mp4", "smooth", n=3, size=(32, 16)), TMP / "up.mp4", 2)
            info = media.probe(out)
            self.assertEqual((info["width"], info["height"]), (64, 32))
        finally:
            upscale._model.clear()

    def test_every_video_gets_the_logo_and_no_yellow(self):
        from PIL import Image
        from insidir_studio import brand
        src = TMP / "brand_src.mp4"
        frame = np.zeros((128, 224, 3), np.uint8)
        frame[:, :56] = (235, 210, 40)    # yellow
        frame[:, 56:112] = (200, 90, 30)  # red-orange fox fur
        frame[:, 112:168] = (232, 190, 160)  # skin
        frame[:, 168:] = (30, 60, 120)    # blue
        post.write_video(np.stack([frame] * 6), 12, src)
        out = post.finish(src, TMP / "brand" / "final.mp4", 12, {}, log=lambda m: None)
        f = TMP / "brand" / "f.png"
        media.run(["-i", str(out), "-frames:v", "1", str(f)])
        o = np.asarray(Image.open(f).convert("RGB")).astype(int)
        y = o[100, 28]
        self.assertLess(y.max() - y.min(), 20)                         # yellow came out grey
        self.assertGreater(o[100, 84][0] - o[100, 84][2], 120)         # orange untouched
        self.assertGreater(o[100, 140][0] - o[100, 140][2], 50)        # skin untouched
        logo = np.asarray(brand.logo_image(20))
        self.assertGreater(logo[..., 3].max(), 200)
        # the paper-white logo sits in the top-left corner, over the yellow column
        corner = o[4:30, 4:56]
        self.assertGreater(corner.min(axis=2).max(), 200)

    def test_crossfade_join_has_no_seam(self):
        a = [np.full((4, 4, 3), 0, np.uint8)] * 6
        b = [np.full((4, 4, 3), 200, np.uint8)] * 6
        j = post.crossfade_join(a, b, 2)
        self.assertEqual(len(j), 10)
        means = [int(f.mean()) for f in j]
        self.assertEqual(means, sorted(means))           # ramps up, never jumps back


class StoryTests(unittest.TestCase):
    def test_script_becomes_scenes_and_shots(self):
        f = story.plan('EXT. ROOFTOP - NIGHT\nMara looks over the city. Rain starts to fall. "We\'re late," she says.\n\n'
                       "INT. TRAIN\nThe carriage rocks. Lights flicker.",
                       [{"id": "chabcdef01", "name": "Mara"}])
        self.assertEqual([s["heading"] for s in f["scenes"]], ["EXT. ROOFTOP - NIGHT", "INT. TRAIN"])
        shots = f["scenes"][0]["shots"]
        self.assertEqual(len(shots), 2)                  # the dialogue line joins the shot before it
        self.assertEqual(shots[0]["shot"], "Wide establishing shot")
        self.assertIn("chabcdef01", shots[0]["characters"])
        self.assertEqual(shots[1]["dialogue"], "We're late,")
        p = story.parse_claude('Sure! {"scenes":[{"heading":"A","shots":[{"prompt":"x"}]}]}')
        self.assertEqual(p["scenes"][0]["shots"][0]["id"], "s1_1")

    @unittest.skipUnless(config.find_tool("ffmpeg"), "FFmpeg not installed")
    def test_beat_detection_finds_the_tempo(self):
        from insidir_studio import sound
        sr = sound.SR
        x = np.zeros(sr * 8, np.float32)
        for k in range(16):                              # 120 BPM click track
            i = int(k * 0.5 * sr)
            x[i:i + 800] = np.hanning(800) * 0.9
        wav = sound.write_wav(TMP / "clicks.wav", x)
        b = story.beats(wav)
        gaps = np.diff(b)
        self.assertTrue(len(b) >= 10)
        self.assertAlmostEqual(float(np.median(gaps)), 0.5, delta=0.05)


@unittest.skipUnless(HAVE_TORCH and config.find_tool("ffmpeg"), "PyTorch/diffusers not installed")
class EngineTests(unittest.TestCase):
    def gen(self, **kw):
        from insidir_studio.gen.engine import Spec, generate
        out = TMP / f"run_{kw.get('task', 't2v')}_{time.time_ns()}"
        return generate(Spec(model="tiny-test", prompt="a lighthouse at dusk", seed=1, **kw), out, log=lambda m: None)

    def img(self, color=(200, 80, 40)):
        from PIL import Image
        p = TMP / f"img_{color[0]}.png"
        Image.new("RGB", (80, 48), color).save(p)
        return str(p)

    def test_text_to_video_with_variations_and_continuation(self):
        r = self.gen(task="t2v", seconds=2.5, variations=2)
        self.assertEqual(len(r["candidates"]), 2)
        self.assertGreater(r["frames"], models.MODELS["tiny-test"]["default"]["frames"])   # continued past one chunk
        self.assertTrue(Path(r["final"]).exists())
        self.assertIn(r["best"], [c["path"] for c in r["candidates"]])

    def test_image_and_first_last_frame(self):
        r = self.gen(task="i2v", image=self.img(), seconds=1)
        self.assertTrue(Path(r["final"]).exists())
        r = self.gen(task="flf2v", image=self.img(), last_image=self.img((20, 20, 200)), seconds=1)
        self.assertTrue(Path(r["final"]).exists())

    def test_references_edit_and_restyle(self):
        src = str(_video(TMP / "src.mp4", "smooth", n=16, size=(80, 48)))
        r = self.gen(task="r2v", references=[self.img()], seconds=1)
        self.assertTrue(Path(r["final"]).exists())
        mask = TMP / "mask.png"
        from PIL import Image
        m = Image.new("L", (80, 48), 0)
        m.paste(255, (20, 10, 60, 40))
        m.save(mask)
        r = self.gen(task="edit", video=src, mask=str(mask), seconds=1)
        self.assertTrue(Path(r["final"]).exists())
        r = self.gen(task="v2v", video=src, strength=0.6, seconds=1)
        self.assertTrue(Path(r["final"]).exists())
        r = self.gen(task="control", video=src, control="edges", seconds=1)
        self.assertTrue(Path(r["final"]).exists())

    def test_film_renders_shots_and_assembles(self):
        from insidir_studio import sound
        x = np.zeros(sound.SR * 6, np.float32)
        for k in range(12):
            i = int(k * 0.5 * sound.SR)
            x[i:i + 800] = np.hanning(800) * 0.9
        music = sound.write_wav(TMP / "music.wav", x)
        film = story.plan("A lighthouse on a cliff. Waves hit the rocks.\n\nA boat drifts in fog.", [], seconds_per_shot=1.5)
        shots = [sh for sc in film["scenes"] for sh in sc["shots"]]
        shots[1]["transition"], shots[2]["transition"], shots[2]["speed"] = "crossfade", "dip", 0.5
        events = []
        r = story.render_film({"film": film, "model": "tiny-test", "settings": {"fps": 12, "music": str(music),
                                                                           "beat_sync": True, "seed": 2}},
                              TMP / "film", lambda f, m="": events.append(f), threading.Event(), lambda m: None)
        info = media.probe(Path(r["final"]))
        self.assertTrue(info["has_audio"] and info["has_video"])
        self.assertEqual(r["shots"], 3)
        self.assertTrue(all(sh["take"] for sh in shots))  # each shot keeps its take for single-shot regeneration

    def test_quality_presets_add_steps_takes_and_a_detail_pass(self):
        from insidir_studio.gen.engine import Spec, apply_quality
        m = models.MODELS["wan2.1-t2v-1.3b"]
        self.assertEqual(apply_quality(Spec(quality="draft"), m)[:3], (int(round(m["default"]["steps"] * 0.6)), 1, False))
        steps, var, refine, opts = apply_quality(Spec(quality="max", post={"upscale": 1}), m)
        self.assertEqual((var, refine, opts["upscale"], opts["film_finish"]), (3, True, 1, True))   # user's choice wins
        self.assertGreater(steps, m["default"]["steps"])
        r = self.gen(task="t2v", seconds=1, quality="high", post={"upscaler": "fast"})
        self.assertTrue(r["refined"])
        self.assertEqual(len(r["candidates"]), 2)
        self.assertTrue((Path(r["final"]).parent / "refined.mp4").exists())
        info = media.probe(r["final"])
        self.assertGreater(info["width"], r["size"][0] * 2)        # ~1.5x detail pass (snapped to 16), then 2x upscale

    def test_cancel_stops_generation(self):
        from insidir_studio.gen.engine import Cancelled, Spec, generate
        ev = threading.Event()
        ev.set()
        with self.assertRaises(Cancelled):
            generate(Spec(model="tiny-test", prompt="x", seconds=1), TMP / "cancel", cancel=ev, log=lambda m: None)

    def test_queue_runs_and_records_history(self):
        from insidir_studio.gen import jobs
        q = jobs.Queue()
        j = q.submit("generate", {"task": "t2v", "model": "tiny-test", "prompt": "a boat", "seconds": 1, "seed": 3})
        for _ in range(600):
            if q.get(j["id"])["status"] in ("done", "error", "cancelled"):
                break
            time.sleep(0.1)
        self.assertEqual(q.get(j["id"])["status"], "done", q.get(j["id"]).get("error"))
        self.assertTrue((jobs.gen_dir() / "history.json").exists())
        self.assertIn(j["id"], [x["id"] for x in jobs.Queue().list()])   # survives a restart


class ApiSafetyTests(unittest.TestCase):
    def test_uploads_only_by_id(self):
        from insidir_studio.gen import api
        for bad in ("../../etc/passwd", "/etc/passwd", "up_xyz.png", "up_0123456789.exe"):
            with self.assertRaises(ValueError):
                api.resolve(bad)
        self.assertEqual(api.resolve(""), "")


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
