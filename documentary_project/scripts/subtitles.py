"""Word-synchronised ASS subtitles (landscape + vertical) from transcript/transcript.json.

Each cue shows at most two lines. Words fill from 60% to full white exactly when
spoken (karaoke \\k timing, no motion). Key scientific terms are set in a warm
accent. Exports subtitles/*.ass plus the SRT copies already made by tts.py.
"""
import json, os, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
T = json.load(open(f"{ROOT}/transcript/transcript.json"))
KEY = set("""glucose dextrose dextrin karbolyn carbohydrate carbohydrates glycogen insulin anabolic amino acids metabolism energy
eccentric overload lengthening lowering stimulus protocol negatives hypertrophy strength deload recovery nutrition consistency
eight seconds adaptation signals muscle growth rest-pause cluster ma30 twelfth""".split())

def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def cues(maxchars):
    out = []
    for sec in T["sections"]:
        for cl in sec["clauses"]:
            cur = []
            for w in cl["words"]:
                if cur and len(" ".join(x["word"] for x in cur + [w])) > maxchars * 2:
                    out.append(cur); cur = []
                cur.append(w)
            if cur: out.append(cur)
    # merge tiny cues (single-word list items) with the following cue when close in time
    merged = []
    for c in out:
        if merged and len(" ".join(x["word"] for x in merged[-1] + c)) <= maxchars * 2 and c[0]["start"] - merged[-1][-1]["end"] < 0.4 \
                and len(merged[-1]) <= 3:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return merged

def split2(words, maxchars):
    """balanced split into <=2 lines"""
    s = " ".join(w["word"] for w in words)
    if len(s) <= maxchars: return [words]
    best, bi = 1e9, 1
    for i in range(1, len(words)):
        a = len(" ".join(w["word"] for w in words[:i])); b = len(" ".join(w["word"] for w in words[i:]))
        if max(a, b) < best: best, bi = max(a, b), i
    return [words[:bi], words[bi:]]

def build(name, W, H, font, margin_v, maxchars, outline):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter Medium,{font},&H00FFFFFF,&H66FFFFFF,&H64000000,&H8C000000,0,0,0,0,100,100,0.5,0,1,{outline},{outline * 1.6:.1f},2,{int(W*0.08)},{int(W*0.08)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    cs = cues(maxchars)
    for i, c in enumerate(cs):
        start = c[0]["start"] - 0.08
        end = c[-1]["end"] + 0.35
        if i + 1 < len(cs): end = min(end, cs[i + 1][0]["start"] - 0.1)
        parts = []
        for li, ln in enumerate(split2(c, maxchars)):
            seg = []
            for w in ln:
                prev_end = start if (w is c[0]) else None
                seg.append(w)
            parts.append(ln)
        text, tcur = "", start
        for li, ln in enumerate(parts):
            for wi, w in enumerate(ln):
                gap = max(0, w["start"] - tcur); dur = max(0.01, w["end"] - w["start"])
                k1 = int(round(gap * 100)); k2 = int(round(dur * 100))
                word = w["word"]
                bare = re.sub(r"[^\w\-]", "", word).lower()
                styled = "{\\1c&H9AC4FF&}" + word + "{\\1c&HFFFFFF&}" if bare in KEY else word
                text += (f"{{\\k{k1}}}" if k1 else "") + f"{{\\kf{k2}}}" + styled + (" " if wi < len(ln) - 1 else "")
                tcur = w["end"]
            if li < len(parts) - 1: text += "\\N"
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Sub,,0,0,0,,{{\\fad(120,120)}}{text}")
    os.makedirs(f"{ROOT}/subtitles", exist_ok=True)
    open(f"{ROOT}/subtitles/{name}.ass", "w").write(head + "\n".join(lines) + "\n")
    return len(lines)

n1 = build("landscape_1080p", 1920, 1080, 50, 70, 42, 2.2)
n2 = build("vertical_1080x1920", 1080, 1920, 58, 330, 24, 2.6)
# exact-wording check: concatenated subtitle words == transcript words
words = [w["word"] for s in T["sections"] for c in s["clauses"] for w in c["words"]]
for f in ("landscape_1080p", "vertical_1080x1920"):
    txt = open(f"{ROOT}/subtitles/{f}.ass").read().split("[Events]")[1]
    got = re.sub(r"\{[^}]*\}", "", "\n".join(l.split(",", 9)[9] for l in txt.splitlines() if l.startswith("Dialogue")))
    got = got.replace("\\N", " ").split()
    assert got == words, f
for f in ("transcript.srt", "words.srt"):
    os.system(f"cp {ROOT}/transcript/{f} {ROOT}/subtitles/")
print("cues", n1, n2, "words", len(words), "exact match OK")
