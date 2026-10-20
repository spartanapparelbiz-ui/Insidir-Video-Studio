"""Wall Street Decoded #1 — natural narration with precise timings.

One non-company-specific financial education Reel: an earnings beat can be
followed by a lower share price when guidance disappoints.
Run: python examples/render_wallstreetdecoded_reel01.py --destination artifacts
"""
from __future__ import annotations
import argparse,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from insidir_studio import tts,compliance

STORYBOARD=[
 ("They beat earnings. The stock still dropped. Why?", "BEAT EARNINGS. STOCK DROPPED.", "shock"),
 ("Because an earnings beat only measures the past against expectations.", "YESTERDAY LOOKED GOOD.", "beat"),
 ("Investors are also betting on what happens next.", "STOCKS PRICE IN THE FUTURE.", "future"),
 ("Imagine the company warns next quarter could be slower.", "THEN THE FORECAST CHANGES.", "guidance"),
 ("Even after good earnings, that future outlook can shake confidence.", "EXPECTATIONS SHIFT.", "reaction"),
 ("That's why the stock can fall after a beat.", "THE STOCK CAN STILL FALL.", "drop"),
 ("Read the guidance, not just the headline. Wall Street, decoded.", "READ THE GUIDANCE.", "lesson"),
]

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--destination",type=Path,default=Path("artifacts"))
 a=p.parse_args()
 beats=[{"id":f"b{i}","text":line,"overlay":heading,"visual":{"kind":"doodle","icon":"chart"}}
         for i,(line,heading,scene) in enumerate(STORYBOARD,1)]
 script={"title":"EARNINGS UP. STOCK DOWN?", "facts_used":[], "beats":beats}
 errs=[e for e in compliance.lint(script,compliance.load_facts(),[]) if e.get("level")=="error"]
 if errs:raise RuntimeError("Script compliance issue: "+json.dumps(errs))
 build=Path("artifacts-build")
 build.mkdir(exist_ok=True)
 engine=tts.get_engine("kokoro")
 nar=tts.fit_narration(beats, "studio_male", 1.01, engine, build, extra_seconds=2)
 duration=round(nar.duration+2,3)
 if duration<20 or duration>36:raise RuntimeError(f"Unexpected duration: {duration}")
 a.destination.mkdir(parents=True,exist_ok=True)
 shutil.copy2(Path(nar.wav),a.destination/"wallstreetdecoded-voice.wav")
 data={"total":duration,"narration_seconds":nar.duration,
  "beats":[{"id":b["id"],"start":b["start"],"end":b["end"],
            "speech_start":b["speech_start"],"speech_end":b["speech_end"]}
           for b in nar.beats],
  "words":[{"text":w.text,"start":w.start,"end":w.end,"beat":w.beat} for w in nar.words],
  "storyboard":[{"spoken":a,"headline":b,"scene":c} for a,b,c in STORYBOARD]}
 (a.destination/"wallstreetdecoded-timing.json").write_text(json.dumps(data,indent=2),encoding="utf8")
 print("NARRATION OK",data["total"],len(data["words"]),flush=True)
if __name__=="__main__":main()
