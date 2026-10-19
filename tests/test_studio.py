"""Run with: python -m unittest discover -s tests

The render test uses the built-in test-tone voice and synthetic FFmpeg footage, so it
needs FFmpeg but not the Kokoro model.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="ivs-test-"))
os.environ["INSIDIR_STUDIO_HOME"] = str(TMP)

from insidir_studio import (animate, captions, compliance, config, media, project, render,  # noqa: E402
                            script_writer, timeline, tts, whisper_align)

FACTS = compliance.load_facts(config.DEFAULT_FACTS)


class ComplianceTests(unittest.TestCase):
    def lint(self, *texts, overlay=""):
        beats = [{"id": f"b{i}", "text": t, "overlay": overlay if i == 0 else ""} for i, t in enumerate(texts)]
        return compliance.lint({"beats": beats}, FACTS, [])

    def errors(self, *texts, **kw):
        return [i for i in self.lint(*texts, **kw) if i["level"] == "error"]

    def test_blocks_return_promises_and_directions(self):
        for bad in ["This is a guaranteed way to beat the market.", "Buy this stock now before it moons.",
                    "Get rich following insider tips.", "Prices will go up after a purchase.",
                    "You should buy when the CEO buys."]:
            self.assertTrue(self.errors(bad), bad)

    def test_blocks_testimonials(self):
        for bad in ["I made a lot with this app.", "I've been using Insidir for months.", "My portfolio grew fast."]:
            self.assertTrue(self.errors(bad), bad)

    def test_blocks_unapproved_numbers(self):
        errs = self.errors("Insiders bought 40% more this year.")
        self.assertTrue(any("40%" in e["message"] for e in errs))
        self.assertTrue(self.errors("Ten thousand trades a day."))
        self.assertTrue(self.errors("Clean text.", overlay="Up 300%"))

    def test_allows_approved_facts_and_document_names(self):
        ok = ("Insiders report trades on a Form 4 within two business days. Insidir imports them every 15 minutes. "
              "Try it for 3 days for $1, then $39 a month. Form 4s are public, not nonpublic information. "
              "It is not investment advice.")
        self.assertEqual(self.errors(ok), [])

    def test_rights_and_unknown_facts(self):
        script = {"beats": [{"id": "b1", "text": "Read the filing.", "visual": {"kind": "screen", "asset": "a1"}}],
                  "facts_used": ["made_up"]}
        errs = [i for i in compliance.lint(script, FACTS, [{"id": "a1", "rights_confirmed": False}]) if i["level"] == "error"]
        self.assertTrue(any("rights" in e["message"] for e in errs))
        self.assertTrue(any("made_up" in e["message"] for e in errs))

    def test_offline_templates_pass(self):
        for v in range(len(script_writer.TEMPLATES)):
            s = script_writer.template_script({"assets": []}, FACTS, v)
            self.assertEqual([i for i in compliance.lint(s, FACTS, []) if i["level"] == "error"], [], v)


    def test_myth_must_be_corrected(self):
        beat = lambda i, text, label: {"id": f"b{i}", "text": text, "visual": {"label": label}}
        ok = {"beats": [beat(1, "Myth: Form 4s are insider tips.", "MYTH"), beat(2, "False. They're public records.", "FACT")]}
        errs = [i for i in compliance.lint(ok, FACTS, []) if i["level"] == "error"]
        self.assertEqual(errs, [])
        bad = {"beats": [beat(1, "Myth: Form 4s are insider tips.", "MYTH"), beat(2, "Anyway.", "")]}
        errs = [i for i in compliance.lint(bad, FACTS, []) if i["level"] == "error"]
        self.assertTrue(any("FACT" in e["message"] for e in errs))

    def test_emphasis_numbers_are_checked(self):
        s = {"beats": [{"id": "b1", "text": "Fast.", "visual": {"emphasis": "90% faster"}}]}
        self.assertTrue([i for i in compliance.lint(s, FACTS, []) if i["level"] == "error"])

    def test_animated_drafts_pass(self):
        for tid in animate.TEMPLATES:
            s = script_writer.template_script({"mode": "animated", "template": tid, "assets": []}, FACTS)
            self.assertEqual([i for i in compliance.lint(s, FACTS, []) if i["level"] == "error"], [], tid)
            words = sum(len(b["text"].split()) for b in s["beats"])
            self.assertTrue(45 <= words <= 78, (tid, words))


class ScriptTests(unittest.TestCase):
    def test_parse_fenced_reply(self):
        reply = ('Here you go:\n```json\n{"title": "T", "facts_used": ["trial"], "beats": ['
                 '{"text": "Hook here? [smiles]", "visual": {"kind": "screen", "asset": "zz"}, "overlay": "Hi"},'
                 '{"text": "Second {brace} beat.", "visual": {"kind": "weird"}}]}\n```')
        s = script_writer.parse_reply(reply, [{"id": "a1"}])
        self.assertEqual([b["id"] for b in s["beats"]], ["b1", "b2"])
        self.assertEqual(s["beats"][0]["text"], "Hook here?")
        self.assertIsNone(s["beats"][0]["visual"]["asset"])  # unknown asset id dropped
        self.assertEqual(s["beats"][1]["visual"]["kind"], "screen")

    def test_bad_reply(self):
        with self.assertRaises(ValueError):
            script_writer.parse_reply("Sorry, I can't.")

    def test_prompt_contains_rules_and_facts(self):
        p = script_writer.build_prompt({"brief": {"topic": "x", "target_seconds": 28}, "assets": []}, FACTS)
        self.assertIn("form4_deadline", p)
        self.assertIn("No first-person testimonials", p)


class CaptionTests(unittest.TestCase):
    def test_grouping_keeps_numbers_with_words(self):
        ws = [tts.Word(t, i * 0.3, i * 0.3 + 0.25, "b1") for i, t in enumerate("on a Form 4 within two days.".split())]
        groups = [" ".join(w.text for w in g) for g in captions.group_words(ws)]
        self.assertTrue(any("Form 4" in g for g in groups), groups)

    def test_ass_has_disclosures(self):
        ws = [tts.Word("Hello", 0.1, 0.5, "b1"), tts.Word("there.", 0.5, 0.9, "b1")]
        shots = [{"start": 0, "duration": 2, "ai_presenter": True, "genuine": False}]
        ass = captions.build_ass(ws, shots, [{"id": "b1", "overlay": "Hi"}], [{"id": "b1", "start": 0, "end": 2}],
                                 3.0, "#FFD84D", "Research tool. Not investment advice.", {"headline": "Insidir."}, 2.0)
        self.assertIn("AI voice", ass)
        self.assertIn("AI-generated presenter", ass)
        self.assertIn("Not investment advice", ass)


class AlignTests(unittest.TestCase):
    def test_alignment_is_monotonic_and_inside_clip(self):
        e = tts.ToneEngine()
        text = "Insiders file, then you read the filing."
        audio = e.synth(text, "af_heart", 1.0)
        words = text.split()
        times = tts.align_words(audio, e.sample_rate, words, [e.weight(w, "") for w in words])
        dur = len(audio) / e.sample_rate
        last = 0.0
        for a, b in times:
            self.assertGreaterEqual(a, last - 1e-6)
            self.assertGreater(b, a)
            self.assertLessEqual(b, dur + 1e-6)
            last = b


class WhisperMatchTests(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(whisper_align._norm("Form,"), "form")
        self.assertEqual(whisper_align._norm("It's"), "its")


@unittest.skipUnless(config.find_tool("ffmpeg"), "FFmpeg not installed")
class RenderTests(unittest.TestCase):
    def test_full_render(self):
        src = TMP / "src"
        src.mkdir(exist_ok=True)
        vid, img = src / "insidir-screen.mp4", src / "insidir-shot.png"
        media.run(["-f", "lavfi", "-i", "testsrc2=s=1280x800:r=30:d=12", "-pix_fmt", "yuv420p", str(vid)])
        media.run(["-f", "lavfi", "-i", "testsrc=s=1600x1000:r=1:d=1", "-frames:v", "1", str(img)])
        proj = project.new("Test video", {"mode": "demo"})
        d = project.project_dir(proj["id"])
        for f in (vid, img):
            tmp = TMP / ("up_" + f.name)
            shutil.copyfile(f, tmp)
            project.add_asset(d, f.name, tmp)
        proj = project.load(d)
        for a in proj["assets"]:
            a.update(rights_confirmed=True, genuine=True, role="screen")
        proj["script"] = script_writer.template_script(proj, FACTS, 1)
        project.save(d, proj)
        report = render.render(d, log=lambda m: None, engine_name="test-tone")
        out = d / "out" / report["file"]
        info = media.probe(out)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertTrue(config.MIN_SECONDS <= info["duration"] <= config.MAX_SECONDS + 0.1, info["duration"])
        self.assertTrue(info["has_audio"])
        side = json.loads(out.with_suffix(".json").read_text())
        self.assertTrue(side["disclosure"]["ai_voice"])
        edl = json.loads((d / "build" / "edl.json").read_text())
        frames = [s["frame_start"] for s in edl["shots"]]
        self.assertEqual(frames, sorted(frames))
        for a, b in zip(edl["shots"], edl["shots"][1:]):
            self.assertEqual(a["frame_end"], b["frame_start"])  # no gaps or overlaps on the grid

    @unittest.skipUnless(animate.status()["ready"], "Node.js / Motion Canvas not installed")
    def test_animated_render(self):
        proj = project.new("Animated", {"mode": "animated", "template": "steps"})
        d = project.project_dir(proj["id"])
        proj = project.load(d)
        proj["style"]["captions"] = "estimate"
        proj["script"] = script_writer.template_script(proj, FACTS)
        project.save(d, proj)
        report = render.render(d, log=lambda m: None, engine_name="test-tone")
        info = media.probe(d / "out" / report["file"])
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertTrue(config.MIN_SECONDS <= info["duration"] <= config.MAX_SECONDS + 0.1, info["duration"])
        self.assertEqual(report["mode"], "animated")

    def test_guard_blocks_render(self):
        proj = project.new("Blocked")
        d = project.project_dir(proj["id"])
        proj = project.load(d)
        proj["script"] = {"title": "", "facts_used": [], "beats": [{"id": "b1", "text": "Guaranteed 50% returns."}]}
        project.save(d, proj)
        with self.assertRaises(render.RenderError):
            render.render(d, log=lambda m: None, engine_name="test-tone")


if __name__ == "__main__":
    unittest.main()
