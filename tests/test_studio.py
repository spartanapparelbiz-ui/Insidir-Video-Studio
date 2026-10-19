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

from insidir_studio import avatars, fonts  # noqa: E402
from insidir_studio import (animate, avatar, captions, sound, compliance, config, media, project, render,  # noqa: E402
                            script_writer, timeline, tts, ugc, whisper_align)

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
                                 3.0, "#FFFFFF", "Research tool. Not investment advice.", {"headline": "Insidir."}, 2.0)
        self.assertNotIn("AI voice", ass)  # off by default
        self.assertIn("AI-generated presenter", ass)  # always shown for AI presenters
        ass2 = captions.build_ass(ws, shots, [{"id": "b1", "overlay": "Hi"}], [{"id": "b1", "start": 0, "end": 2}],
                                  3.0, "#FFFFFF", "Research tool. Not investment advice.", None, None,
                                  ai_voice_label="AI voice")
        self.assertIn("AI voice", ass2)
        self.assertIn("Not investment advice", ass)


class VoiceTests(unittest.TestCase):
    def test_insidir_is_pronounced_insider(self):
        self.assertEqual(tts.speakable("Insidir shows it. Visit insidir.com or insidir dot com."),
                         "Insider shows it. Visit insider.com or insider dot com.")
        # one word in, one word out, so caption timing still lines up
        t = "Try Insidir today, at insidir.com."
        self.assertEqual(len(t.split()), len(tts.speakable(t).split()))

    def test_man_and_woman_voices(self):
        self.assertEqual(tts.gender_of(tts.DEFAULT_VOICE), "man")
        for g, v in tts.DEFAULT_BY_GENDER.items():
            self.assertEqual(tts.gender_of(v), g)
        genders = {tts.gender_of(v) for v in tts.VOICES}
        self.assertEqual(genders, {"man", "woman"})
        self.assertEqual(tts.gender_of("am_michael"), "man")
        self.assertEqual(tts.gender_of("bf_emma"), "woman")

    def test_unknown_voice_falls_back(self):
        self.assertEqual(tts.valid_voice("am_adam_removed"), tts.DEFAULT_VOICE)
        self.assertEqual(whisper_align._norm("Insidir"), "insider")


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


class SoundTests(unittest.TestCase):
    def test_sfx_and_bed_are_generated_and_bounded(self):
        import numpy as np
        for name, fn in sound.SFX.items():
            x = fn()
            self.assertGreater(len(x), 100, name)
            self.assertLessEqual(float(np.max(np.abs(x))), 1.0, name)
        bed = sound.music_bed(6.0)
        self.assertEqual(bed.shape, (6 * sound.SR, 2))
        self.assertLessEqual(float(np.max(np.abs(bed))), 0.51)
        track = sound.sfx_track([(0.0, "hit"), (1.0, "whoosh"), (5.0, "riser")], 6.0)
        self.assertEqual(len(track), 6 * sound.SR)

    def test_events_follow_the_edit(self):
        beats = [{"id": "b1", "visual": {}}, {"id": "b2", "visual": {"emphasis": "2 business days"}}]
        ev = sound.plan_events(beats, [(0, 2), (2, 4)], [], 4.0, "viral")
        kinds = [k for _, k in ev]
        self.assertIn("whoosh", kinds)
        self.assertEqual(kinds.count("hit"), 3)  # hook, big number, end card
        self.assertIn("riser", kinds)

    def test_audio_graph_variants(self):
        from insidir_studio import render as r
        self.assertTrue(r._audio_graph(1, False, 10, -20).endswith("[aout]"))
        g = r._audio_graph(1, True, 10, -6, has_sfx=True)
        self.assertIn("sidechaincompress", g)
        self.assertIn("[3:a]", g)  # sfx stem after voice and music
        self.assertIn("amix=inputs=3", g)


class WhisperMatchTests(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(whisper_align._norm("Form,"), "form")
        self.assertEqual(whisper_align._norm("It's"), "its")


def _words(text, start, gap_after=None):
    """Fake word timings: 0.3 s per word, with an optional pause after word index -> seconds."""
    out, t = [], start
    for i, w in enumerate(text.split()):
        out.append({"text": w, "start": round(t, 3), "end": round(t + 0.26, 3)})
        t += 0.3 + (gap_after or {}).get(i, 0.0)
    return out


class UgcTests(unittest.TestCase):
    def test_sentences_split_on_punctuation_and_pauses(self):
        ws = _words("Hi there. This is long", 0.0, {2: 1.2}) + _words("and done.", 3.0)
        groups = ugc.sentences(ws)
        self.assertEqual([" ".join(w["text"] for w in g) for g in groups], ["Hi there.", "This", "is long and done."])

    def test_plan_cuts_pauses_and_fillers_into_jump_cuts(self):
        ws = _words("So um the filing is public", 1.0, {2: 0.9})
        beats = [{"id": "b1", "keep": True, "words": ws, "source": {"asset": "c1"},
                  "visual": {"layout": "face"}},
                 {"id": "b2", "keep": False, "words": _words("cut me", 5.0), "source": {"asset": "c1"}, "visual": {}}]
        segs = ugc.plan(beats, 30)
        # "um" is dropped (its gap becomes a cut), the long pause is a cut, b2 is left out
        self.assertEqual([" ".join(w["text"] for w in ws if sg.start <= w["start"] < sg.end) for sg in segs],
                         ["So", "the", "filing is public"])
        self.assertEqual([s.zoom for s in segs], [1.0, 1.16, 1.0])  # alternate framing on every cut
        t = 0.0
        for sg in segs:
            self.assertAlmostEqual(sg.out_start, t)
            self.assertEqual(sg.frames, int((sg.end - sg.start) * 30 + 1e-6))
            t += sg.frames / 30
        self.assertEqual(len(ugc.plan(beats, 30, gap=None)), 1)  # photo avatar: sentences stay whole

    def test_layout_without_screen_falls_back_to_face(self):
        beats = [{"id": "b1", "words": _words("hello there", 0.2), "source": {"asset": "c1"},
                  "visual": {"layout": "split", "asset": None}}]
        self.assertEqual(ugc.plan(beats, 30)[0].layout, "face")

    def test_caption_fixes_keep_timing(self):
        b = {"text": "Insidir shows filings", "words": _words("Insider shows filings", 0.0)}
        self.assertEqual([w["text"] for w in ugc.corrected_words(b)], ["Insidir", "shows", "filings"])
        b["text"] = "Insidir shows every filing"   # word count changed: keep what was said
        self.assertEqual(ugc.corrected_words(b)[0]["text"], "Insider")
        self.assertEqual(ugc.tidy("every form four is on edgar"), "every Form 4 is on EDGAR")

    def test_real_person_may_speak_in_first_person(self):
        script = {"title": "", "facts_used": [], "beats": [
            {"id": "b1", "text": "I use Insidir to read the Form 4 before I research a company, and I check the source filing every time."},
            {"id": "b2", "text": "Each line links to the original filing on EDGAR so you can read it yourself too, which is how I like it."}]}
        ai = compliance.lint(script, FACTS)
        real = compliance.lint(script, FACTS, real_person=True)
        self.assertTrue(any("testimonial" in i["message"] for i in ai if i["level"] == "error"))
        self.assertFalse(any("testimonial" in i["message"] for i in real if i["level"] == "error"))
        self.assertTrue(any("#ad" in i["message"] for i in real))
        # results are still blocked for real people
        script["beats"][0]["text"] = "I made huge returns with this."
        self.assertTrue(compliance.has_errors(compliance.lint(script, FACTS, real_person=True)))

    def test_presenter_drafts_mix_layouts(self):
        proj = {"mode": "photo_avatar", "assets": [{"id": "s1", "role": "screen", "type": "video", "rights_confirmed": True,
                                                     "genuine": True, "label": "feed", "file": "x"}]}
        sc = script_writer.template_script(proj, FACTS, 0)
        layouts = [b["visual"]["layout"] for b in sc["beats"]]
        self.assertEqual(layouts[0], "face")
        self.assertEqual(layouts[-1], "face")
        self.assertTrue({"split", "bubble", "screen"} & set(layouts))
        self.assertFalse(compliance.has_errors(compliance.lint(sc, FACTS, proj["assets"])))

    def test_new_formats_have_prompts_and_clean_drafts(self):
        for mode, tpl in (("ugc", None), ("photo_avatar", None), ("animated", "avatar-host"), ("animated", "chat")):
            proj = {"mode": mode, "template": tpl, "brief": {}, "assets": []}
            prompt = script_writer.build_prompt(proj, FACTS)
            self.assertIn("APPROVED FACTS", prompt)
            sc = script_writer.template_script(proj, FACTS, 0)
            self.assertFalse(compliance.has_errors(compliance.lint(sc, FACTS)), (mode, tpl))
        self.assertIn("first person is fine", script_writer.build_prompt({"mode": "ugc", "brief": {}, "assets": []}, FACTS))


class AvatarLibraryTests(unittest.TestCase):
    def test_cartoon_avatar_and_edits(self):
        av = avatars.create("Host", "cartoon", character="maya", voice="studio_female_uk")
        self.assertEqual((av["kind"], av["character"], av["voice"]), ("cartoon", "maya", "studio_female_uk"))
        av = avatars.update(av["id"], {"voice": "nope", "speed": 3, "character": "leo", "focus": [2, 0]})
        self.assertEqual((av["voice"], av["speed"], av["character"], av["focus"]), (tts.DEFAULT_VOICE, 1.2, "leo", [0.5, 0.4]))
        self.assertEqual(avatars.usable_photo(av), ["This avatar has no photo."])
        avatars.delete(av["id"])
        self.assertNotIn(av["id"], [a["id"] for a in avatars.list_avatars()])
        with self.assertRaises(ValueError):
            avatars.avatar_dir("../etc")

    def test_every_voice_has_a_gender(self):
        self.assertGreaterEqual(len(tts.VOICES), 30)
        for v in tts.VOICES:
            self.assertIn(tts.gender_of(v), ("man", "woman"))
        self.assertEqual(tts.gender_of("studio_male_uk"), "man")
        self.assertEqual(tts.gender_of("studio_calm"), "woman")


class FontTests(unittest.TestCase):
    def test_catalogue_files_exist_and_include_insidir_fonts(self):
        self.assertEqual(fonts.files_exist(), [])
        insidir = {f["name"] for f in fonts.FONTS.values() if f["group"] == "insidir"}
        self.assertEqual(insidir, {"Insidir logo", "Inter", "Source Serif 4", "JetBrains Mono"})
        for f in fonts.FONTS.values():
            self.assertTrue((config.FONTS_DIR / fonts.preview_file(f)).exists())

    def test_nearest_weight_never_fakes_bold(self):
        f = fonts.get("source-serif-4")
        self.assertEqual(fonts.nearest(f, 800), "SourceSerif4-Black.ttf")   # tie -> heavier
        self.assertEqual(fonts.nearest(f, 400), "SourceSerif4-Medium.ttf")
        self.assertEqual(set(fonts.web_faces(fonts.get("anton")).values()), {"Anton-Regular.ttf"})
        self.assertEqual(fonts.get("nope")["id"], "inter")
        self.assertIsNone(fonts.get("", None))

    def test_ass_uses_the_chosen_fonts(self):
        w = [tts.Word("Hello", 0.0, 0.4, "b1")]
        bt = [{"id": "b1", "start": 0, "speech_start": 0, "speech_end": 0.5, "end": 0.6}]
        ass = captions.build_ass(w, [], [{"id": "b1", "text": "Hello", "overlay": "Hi"}], bt, 1.0, "#FFFFFF", "x", None, None,
                                 caption_font="anton", headline_font="source-serif-4")
        self.assertIn("Style: Caption,Anton,", ass)
        self.assertIn("Style: Overlay,Source Serif 4,", ass)
        self.assertIn("Style: Label,Inter,", ass)   # disclosure labels stay in the brand face
        self.assertIn("Style: EndHead,Source Serif 4 Medium,", ass)   # the wordmark uses the logo face


@unittest.skipUnless(config.find_tool("ffmpeg"), "FFmpeg not installed")
class LipSyncTests(unittest.TestCase):
    def test_mouth_follows_the_voice(self):
        wav = TMP / "lips.wav"
        # 1 s of silence, 1 s of a buzzy "voice", 1 s of silence
        media.run(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=1", "-f", "lavfi", "-i", "sine=f=180:r=24000:d=1",
                   "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=1",
                   "-filter_complex", "[1]volume=0.5[v];[0][v][2]concat=n=3:v=0:a=1", str(wav)])
        mouth, width = animate.mouth_track(wav, 30, 3.0)
        self.assertEqual(len(mouth), 90)
        self.assertEqual(len(width), 90)
        self.assertLess(max(mouth[:25]), 0.05)
        self.assertGreater(sum(mouth[35:55]) / 20, 0.6)
        self.assertLess(mouth[-1], 0.1)
        self.assertTrue(all(0 <= v <= 1 for v in mouth + width))


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

    def _creator_clip(self):
        """A 'talking head' test clip: speech-like tone bursts with pauses between them."""
        src = TMP / "src"
        src.mkdir(exist_ok=True)
        clip = src / "creator-selfie.mp4"
        if not clip.exists():
            media.run(["-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=30",
                       "-f", "lavfi", "-i", "sine=f=220:r=48000:d=30",
                       "-filter_complex", "[1]volume='if(lt(mod(t,4),3),0.4,0)':eval=frame[a]",
                       "-map", "0:v", "-map", "[a]", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)])
        return clip

    def _screen(self, d):
        vid = TMP / "src" / "insidir-screen.mp4"
        if not vid.exists():
            media.run(["-f", "lavfi", "-i", "testsrc2=s=1280x800:r=30:d=12", "-pix_fmt", "yuv420p", str(vid)])
        tmp = TMP / "up_screen.mp4"
        shutil.copyfile(vid, tmp)
        return project.add_asset(d, vid.name, tmp, "screen")

    def test_ugc_render(self):
        proj = project.new("UGC", {"mode": "ugc"})
        d = project.project_dir(proj["id"])
        tmp = TMP / "up_creator.mp4"
        shutil.copyfile(self._creator_clip(), tmp)
        c = project.add_asset(d, "creator-selfie.mp4", tmp)
        self.assertEqual(c["role"], "creator")
        s = self._screen(d)
        proj = project.load(d)
        for a in proj["assets"]:
            a.update(rights_confirmed=True, genuine=a["role"] == "screen")
        lines = ["Okay so here is how I read an insider filing every single morning.",
                 "Every Form 4 is a public SEC filing that anyone can read.",
                 "Insidir puts all of them in one clean feed for you to read.",
                 "You see the real buys kept apart from the awards and exercises.",
                 "And every line links straight to the original filing on EDGAR.", "Uh this part gets cut.",
                 "Go and look for yourself at insidir dot com right now."]
        layouts = ["face", "split", "bubble", "screen", "face", "face", "face"]
        beats = []
        for i, (text, layout) in enumerate(zip(lines, layouts)):
            ws = _words(text, i * 4.0 + 0.2, {3: 0.6})
            beats.append({"id": f"b{i + 1}", "text": text, "keep": i != 5, "overlay": "",
                          "source": {"asset": c["id"], "start": ws[0]["start"], "end": ws[-1]["end"]}, "words": ws,
                          "visual": {"kind": "ugc", "layout": layout, "asset": s["id"] if layout != "face" else None}})
        proj["script"] = {"title": "UGC", "facts_used": [], "beats": beats}
        project.save(d, proj)
        report = render.render(d, log=lambda m: None)
        info = media.probe(d / "out" / report["file"])
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertTrue(config.MIN_SECONDS <= info["duration"] <= config.MAX_SECONDS + 0.1, info["duration"])
        self.assertTrue(info["has_audio"])
        self.assertEqual(report["mode"], "ugc")
        self.assertGreaterEqual(report["jump_cuts"], 12)       # one per pause, cut sentence left out
        self.assertFalse(report["disclosure"]["ai_voice"])     # a real voice is not called AI
        ass = (d / "build" / "captions.ass").read_text(encoding="utf-8")
        self.assertIn("Real Insidir screen recording", ass)
        self.assertNotIn("gets", ass.lower())               # the unticked sentence has no captions

    def test_photo_avatar_render(self):
        fake = TMP / "fake_avatar.py"
        fake.write_text(
            "import sys, subprocess\n"
            "a = dict(zip(sys.argv[1::2], sys.argv[2::2]))\n"
            "subprocess.run([sys.argv[-1], '-loglevel', 'error', '-y', '-loop', '1', '-framerate', '25', '-i', a['--image'],\n"
            "                '-i', a['--audio'], '-vf', 'scale=720:1280,format=yuv420p', '-shortest', a['--out']], check=True)\n")
        settings = config.load_settings()
        settings["avatar"] = {"enabled": True, "engine": "custom", "license_confirmed": True,
                              "command": f'"{sys.executable}" "{fake}" --image "{{image}}" --audio "{{audio}}" --out "{{output}}" --ff "{config.ffmpeg()}"'}
        old = avatar.detect_gpus
        avatar.detect_gpus = lambda: [{"name": "Test GPU", "vram_gb": 24.0}]
        try:
            # a saved avatar from the library, imported once
            img = TMP / "src" / "presenter.png"
            img.parent.mkdir(exist_ok=True)
            media.run(["-f", "lavfi", "-i", "testsrc=s=800x1000:r=1:d=1", "-frames:v", "1", str(img)])
            tmp = TMP / "up_presenter.png"
            shutil.copyfile(img, tmp)
            av = avatars.create("Jordan", "photo", tmp, "presenter.png", voice="studio_calm")
            self.assertEqual((av["width"], av["height"], av["voice"]), (800, 1000, "studio_calm"))
            proj = project.new("Photo avatar", {"mode": "photo_avatar"})
            d = project.project_dir(proj["id"])
            self._screen(d)
            proj = project.load(d)
            for a in proj["assets"]:
                a.update(rights_confirmed=True, genuine=True)
            proj["avatar"] = {"id": av["id"]}
            proj["style"]["captions"] = "estimate"
            proj["style"]["quality"] = "standard"
            proj["script"] = script_writer.template_script(proj, FACTS, 0)
            project.save(d, proj)
            with self.assertRaises(render.RenderError):   # no consent yet
                render.render(d, settings=settings, log=lambda m: None, engine_name="test-tone")
            avatars.update(av["id"], {"consent_confirmed": True})
            report = render.render(d, settings=settings, log=lambda m: None, engine_name="test-tone")
        finally:
            avatar.detect_gpus = old
        info = media.probe(d / "out" / report["file"])
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertTrue(report["disclosure"]["ai_presenter"])
        self.assertTrue(report["disclosure"]["ai_voice"])
        self.assertIn("AI-generated presenter", (d / "build" / "captions.ass").read_text(encoding="utf-8"))

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
