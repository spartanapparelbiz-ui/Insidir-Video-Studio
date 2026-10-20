"""Narration/timing source for @insidirfinance Reel #2: REVENUE IS NOT PROFIT.

All dollar amounts are illustrative, NOT a claim about any real company.
Renders using the project's existing free Kokoro and FFmpeg stack, then exports
clean voice WAV and exact per-beat timing for the original 2D animation master.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insidir_studio import project,tts,compliance

STORYBOARD=[
 ("How can a company sell a hundred million dollars of products, and still lose money?", "ONE HUNDRED MILLION IN.", "question"),
 ("Imagine this. One hundred million dollars comes in from sales.", "SALES: $100 MILLION", "cash"),
 ("But payroll, shipping, and other costs add up to one hundred and twenty million.", "COSTS: $120 MILLION", "chart"),
 ("That's a twenty million dollar loss.", "LOSS: $20 MILLION", "alert"),
 ("More sales don't automatically mean the company earns more.", "MORE SALES IS NOT MORE EARNINGS.", "chart"),
 ("Before trusting a headline, check the income statement in the public filings.", "LOOK AT THE NUMBERS.", "document"),
 ("Insidir helps you research what's behind the headline. Know the numbers, not just the story.", "INSIDIR. GO DEEPER.", "link"),
]

def main():
 a=argparse.ArgumentParser()
 a.add_argument("--destination",type=Path,default=Path("artifacts"))
 args=a.parse_args()
 p=project.new("Insidirfinance Reel 02 - Revenue is not profit",{
  "mode":"animated","template":"editorial-story","topic":"A company with $100M in illustrative revenue and $120M expenses loses $20M",
  "target_seconds":32,"audience":"Beginners researching businesses and public filings",
  "angle":"One clear numerical lesson, with a 100/120/20 animation and fictional example",
  "cta":"Understand the numbers at insidir.com"
 })
 d=project.project_dir(p["id"])
 p["voice"]["voice"]="studio_male"
 p["voice"]["speed"]=0.98
 p["style"].update({"quality":"standard","captions":"auto","end_card":True,
 "sfx":False,"music_bed":False,"logo_overlay":False,"caption_words":3,
 "caption_highlight":"#FFFFFF","caption_size":0.8})
 p["script"]={
  "title":"REVENUE IS NOT WHAT IS LEFT",
  "facts_used":[],
  "beats":[{"id":f"b{i}","text":speech,"overlay":title,
            "visual":{"kind":"doodle","icon":ico,"pose":"explain"}}
          for i,(speech,title,ico) in enumerate(STORYBOARD,1)]
 }
 facts=compliance.load_facts()
 # Fictional arithmetic example, NOT a claim about any real public company.
 facts.setdefault("facts",[]).append({
     "id":"fictional_revenue_illustration",
     "text":"Fictional illustration: 100 million in sales minus 120 million in expenses is a 20 million loss.",
     "numbers":["hundred","million","twenty","100","120","20"],
     "source":"Synthetic example prepared for this educational video. Not actual company financials."
 })
 compliance.save_facts(facts)
 errors=[e for e in compliance.lint(p["script"],facts,[]) if e.get("level")=="error"]
 if errors: raise RuntimeError("Factual guard: "+json.dumps(errors))
 project.save(d,p)
 # Generate only natural narration and frame-accurate beat/word timings here.
 # The final 2D animated Reel is rendered and quality-checked separately.
 build=d/"build"
 build.mkdir(parents=True,exist_ok=True)
 voice=tts.valid_voice(p["voice"]["voice"])
 engine=tts.get_engine("kokoro")
 nar=tts.fit_narration(p["script"]["beats"],voice,p["voice"]["speed"],engine,build,extra_seconds=1.4)
 duration=round(nar.duration+1.4,3)
 if duration>35.05 or duration<20: raise RuntimeError(f"Narration duration out of range: {duration}")
 beats=[{"id":b["id"],"start":b["start"],"end":b["end"]} for b in nar.beats]
 words=[{"text":w.text,"start":w.start,"end":w.end,"beat":w.beat} for w in nar.words]
 timing={"beats":beats,"words":words,"total":duration,"end_card_start":round(nar.duration,3)}
 args.destination.mkdir(parents=True,exist_ok=True)
 shutil.copy2(Path(nar.wav),args.destination/"reel02-voice.wav")
 (args.destination/"reel02-timing.json").write_text(json.dumps(timing,indent=2),encoding="utf8")
 (args.destination/"render-report.json").write_text(json.dumps({
  "duration":duration,"narration_seconds":nar.duration,
  "voice":voice,"source":"Illustrative arithmetic only, not company data",
  "beats":len(beats),"words":len(words)},indent=2),encoding="utf8")
 print("Voice, timing, and report ready",timing["total"],"seconds",flush=True)

if __name__=="__main__":main()
