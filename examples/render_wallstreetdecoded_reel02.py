"""Wall Street Decoded Reel 2: a hypothetical 10-for-1 split.
No real company or stock performance is portrayed.
"""
from __future__ import annotations
import sys,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from insidir_studio import tts
VOICE=[
"Your stock went from a thousand dollars to a hundred. Did you lose ninety percent?",
"Not if it was a ten for one stock split.",
"Before: one share worth a thousand dollars.",
"After: ten shares worth a hundred dollars each.",
"Ten times a hundred is still a thousand. Same total value, more shares.",
"It's like cutting one pizza into ten pieces. Nothing disappears.",
"A stock split doesn't shrink your investment by itself. Wall Street, decoded.",
]
def main():
    out=Path("artifacts");out.mkdir(exist_ok=True)
    beats=[{"id":f"b{i+1}","text":txt} for i,txt in enumerate(VOICE)]
    eng=tts.get_engine("kokoro")
    nar=tts.fit_narration(beats,"studio_male",1.01,eng,out,extra_seconds=1.9)
    total=round(nar.duration+1.9,3)
    if not 20<=total<=35: raise ValueError(f"Video duration {total} outside 20-35 sec")
    shutil.copyfile(nar.wav,out/"narration.wav")
    data={"total":total,"narration_duration":nar.duration,
        "beats":nar.beats,
        "words":[{"text":w.text,"start":w.start,"end":w.end,"beat":w.beat} for w in nar.words],
        "script":VOICE}
    (out/"timing.json").write_text(json.dumps(data,indent=2),encoding="utf8")
    print("SPLIT REEL VOICE READY",total,"seconds",flush=True)
if __name__=="__main__":main()
