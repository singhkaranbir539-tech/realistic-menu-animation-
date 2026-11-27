"""Assemble the final 30 s, 2160x3840, 30 fps documentary.

For every output frame: pick/blend rendered scene frames (transitions), grade (teal/blue with controlled
reds, bloom, light shafts, vignette) at render resolution, Lanczos-upscale 3x to 2160x3840, add film
grain, on-screen titles and word-by-word subtitles (Montserrat SemiBold, white + cyan highlight),
then pipe raw frames into FFmpeg (H.264 High, yuv420p, BT.709) and mux the final audio mix (AAC 48 kHz).
Also writes output/sleep_documentary_subtitles.srt.
usage: python3 assemble_video.py [--preview N]   (preview renders every Nth frame to PNG only)
"""
import os, sys, json, math, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "renders/scene_renders")
OUTW, OUTH = 2160, 3840
FPS = 30; NF = 900
FONT_SUB = os.path.join(ROOT, "assets/fonts/Montserrat_600SemiBold.ttf")
FONT_TITLE = os.path.join(ROOT, "assets/fonts/Montserrat_700Bold.ttf")
FONT_SMALL = os.path.join(ROOT, "assets/fonts/Montserrat_500Medium.ttf")

# ------------------------------------------------------------------ edit decision list
# (shot, first output frame, number of frames, first source frame)
SHOTS = [("scene_01a", 0, 64, 1), ("scene_01b", 56, 104, 1), ("scene_02", 150, 146, 1), ("shot2b", 286, 40, 1),
         ("shot3", 326, 186, 1), ("scene_04", 506, 186, 1), ("scene_05", 690, 210, 1)]
# transitions: (outgoing, incoming, start, end, kind)
TRANS = [("scene_01a", "scene_01b", 56, 64, "skin"), ("scene_01b", "scene_02", 150, 160, "zoom"),
         ("scene_02", "shot2b", 286, 296, "zoom"), ("shot2b", "shot3", 322, 334, "flash"),
         ("shot3", "scene_04", 506, 516, "vessel"), ("scene_04", "scene_05", 682, 692, "pull")]
TITLES = [("YOUR BODY NEVER\nTRULY SLEEPS", 0.7, 4.3), ("YOUR BRAIN\nSTAYS ACTIVE", 5.7, 9.7),
          ("MEMORIES PROCESSED.\nWASTE CLEARED.", 11.7, 15.9), ("REPAIR. RECOVERY.\nRESTORATION.", 17.6, 21.9),
          ("SLEEP IS ESSENTIAL\nMAINTENANCE.", 23.5, 26.9), ("PROTECT YOUR SLEEP.", 27.2, 29.3)]

_cache = {}


def src(shot, i):
    """source frame (float32 HxWx3, 0..1) for output frame i, or None."""
    for nm, o0, n, s0 in SHOTS:
        if nm == shot:
            k = min(max(i - o0, 0), n - 1) + s0
            d = os.path.join(R, nm + "_30") if os.path.isdir(os.path.join(R, nm + "_30")) else os.path.join(R, nm)
            p = os.path.join(d, f"f_{k:04d}.png")
            while not (os.path.exists(p) and os.path.getsize(p) > 0) and k > 1:
                k -= 1; p = os.path.join(d, f"f_{k:04d}.png")
            if p not in _cache:
                if len(_cache) > 12:
                    _cache.pop(next(iter(_cache)))
                im = Image.open(p)
                a = np.asarray(im).astype(np.float32)
                a = a / (65535.0 if a.max() > 255 else 255.0)
                _cache[p] = a[..., :3]
            return _cache[p]
    raise KeyError(shot)


def active(i):
    return [nm for nm, o0, n, s0 in SHOTS if o0 <= i < o0 + n]


def zoom(img, s, cx=0.5, cy=0.5):
    if abs(s - 1) < 1e-3:
        return img
    h, w = img.shape[:2]
    out = np.empty_like(img)
    for c in range(3):
        out[..., c] = ndi.affine_transform(img[..., c], [1 / s, 1 / s], offset=[cy * h * (1 - 1 / s), cx * w * (1 - 1 / s)], order=1, mode="nearest")
    return out


def blur(img, sig):
    return img if sig < 0.3 else ndi.gaussian_filter(img, (sig, sig, 0))


def radial_blur(img, amount, cx=0.5, cy=0.5, n=6):
    if amount < 0.002:
        return img
    acc = img.copy()
    for k in range(1, n):
        acc += zoom(img, 1 + amount * k / n, cx, cy)
    return acc / n


def smooth(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


def compose(i):
    names = active(i)
    tr = [t for t in TRANS if t[2] <= i < t[3]]
    if tr:
        a, b, t0, t1, kind = tr[0]
        u = smooth((i - t0) / (t1 - t0))
        A_, B_ = src(a, i), src(b, i)
        if kind == "skin":   # push into the skin: zoom + blur + warm subsurface glow, emerge inside
            A2 = blur(zoom(A_, 1 + 0.5 * u), 10 * u)
            glow = np.array([0.55, 0.12, 0.08], np.float32) * math.sin(math.pi * u) * 0.9
            B2 = blur(zoom(B_, 1.25 - 0.25 * u), 10 * (1 - u))
            return A2 * (1 - u) + B2 * u + glow
        if kind == "zoom":
            A2 = radial_blur(zoom(A_, 1 + 0.35 * u), 0.15 * u)
            B2 = radial_blur(zoom(B_, 0.8 + 0.2 * u), 0.15 * (1 - u))
            return A2 * (1 - u) + B2 * u
        if kind == "flash":  # neural impulse expands into a bright transition
            f = math.sin(math.pi * u)
            mix = A_ * (1 - u) + B_ * u
            yy, xx = np.mgrid[0:mix.shape[0], 0:mix.shape[1]]
            r = np.hypot((xx - mix.shape[1] * 0.5) / mix.shape[1], (yy - mix.shape[0] * 0.5) / mix.shape[1])
            ring = np.exp(-r ** 2 / (0.02 + 0.5 * u) ** 2)[..., None]
            return mix + f * 1.4 * ring * np.array([0.6, 0.85, 1.0], np.float32)
        if kind == "vessel":
            A2 = zoom(A_, 1 + 0.6 * u); B2 = zoom(B_, 1.3 - 0.3 * u)
            tint = np.array([0.35, 0.02, 0.03], np.float32) * math.sin(math.pi * u)
            return blur(A2, 6 * u) * (1 - u) + blur(B2, 6 * (1 - u)) * u + tint
        if kind == "pull":
            A2 = blur(zoom(A_, 1 - 0.15 * u), 8 * u); B2 = blur(zoom(B_, 1.15 - 0.15 * u), 8 * (1 - u))
            return A2 * (1 - u) + B2 * u
    nm = names[-1] if names else SHOTS[-1][0]
    return src(nm, i).copy()


# ------------------------------------------------------------------ grading (render resolution)
H0, W0 = 1280, 720
yy, xx = np.mgrid[0:H0, 0:W0]
VIG = (1 - 0.42 * (np.hypot((xx - W0 / 2) / (W0 / 2), (yy - H0 / 2) / (H0 / 2)) / 1.25) ** 2.2)[..., None].astype(np.float32)


def grade(img, i):
    t = i / FPS
    x = np.clip(img, 0, 4)
    # bloom (restrained)
    lum = x.mean(2, keepdims=True)
    hi = np.clip(x - 0.72, 0, None)
    bl = ndi.gaussian_filter(hi, (6, 6, 0)) * 0.5 + ndi.gaussian_filter(hi, (22, 22, 0)) * 0.35
    x = x + bl
    # moonlight shafts in the bedroom shot: directional smear of highlights from the window side
    if t < 2.2:
        k = (1 - smooth((t - 1.6) / 0.5)) * 0.22
        src_ = np.clip(x - 0.35, 0, None) * (lum > 0.3)
        sh = np.zeros_like(x)
        for s_ in range(1, 9):
            sh += np.roll(np.roll(src_, int(s_ * 9), axis=1), int(s_ * 7), axis=0) * (1 - s_ / 9)
        x = x + ndi.gaussian_filter(sh, (5, 5, 0)) * k / 4
    # split-tone: teal/blue shadows, keep reds controlled
    l = x.mean(2, keepdims=True)
    shadow = np.clip(1 - l * 2.2, 0, 1)
    x = x + shadow * np.array([-0.010, 0.006, 0.022], np.float32)
    sat = 1.06
    x = l + (x - l) * sat
    r_excess = np.clip(x[..., :1] - np.maximum(x[..., 1:2], x[..., 2:3]) - 0.35, 0, None)
    x[..., :1] -= r_excess * 0.3
    # gentle S-curve
    x = np.clip(x, 0, None)
    x = x / (1 + 0.18 * x)
    x = np.clip((x - 0.012) * 1.08, 0, 1)
    x = x ** 1.02
    x *= VIG
    # final fade to black over the last 0.5 s
    if t > 29.5:
        x *= max(0.0, 1 - (t - 29.5) / 0.5)
    return np.clip(x, 0, 1)


# ------------------------------------------------------------------ text
timing = json.load(open(os.path.join(ROOT, "audio/voiceover/timing.json")))
chunks = []   # list of dicts: words [(word,start,end)], start, end
for ln in timing["lines"]:
    ws = ln["words"]; cur = []
    for j, w in enumerate(ws):
        cur.append(w)
        nchar = sum(len(x["word"]) + 1 for x in cur)
        brk = w["word"].endswith((".", ",")) and nchar > 14
        if nchar > 30 or brk or j == len(ws) - 1:
            chunks.append(cur); cur = []
CH = []
for k, c in enumerate(chunks):
    st = c[0]["start"] - 0.05
    nxt = chunks[k + 1][0]["start"] - 0.05 if k + 1 < len(chunks) else 99
    en = min(c[-1]["end"] + 0.45, nxt)
    CH.append({"words": c, "start": st, "end": en})


def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s_, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s_:02d},{ms:03d}"


os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
with open(os.path.join(ROOT, "output/sleep_documentary_subtitles.srt"), "w") as f:
    for k, c in enumerate(CH):
        txt = " ".join(w["word"] for w in c["words"])
        f.write(f"{k+1}\n{srt_time(c['start'])} --> {srt_time(min(c['end'], 30.0))}\n{txt}\n\n")

fsub = ImageFont.truetype(FONT_SUB, 104)
ftitle = ImageFont.truetype(FONT_TITLE, 118)
fsmall = ImageFont.truetype(FONT_SMALL, 46)
WHITE = (255, 255, 255); CYAN = (64, 214, 255)


def layout_words(words, font, maxw):
    lines = [[]]; wsp = font.getlength(" ")
    for w in words:
        test = lines[-1] + [w]
        width = sum(font.getlength(x["word"]) for x in test) + wsp * (len(test) - 1)
        if width > maxw and lines[-1]:
            lines.append([w])
        else:
            lines[-1] = test
    return lines[:2]


def draw_spaced(d, xy, text, font, fill, spacing):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + spacing


def spaced_width(text, font, spacing):
    return sum(font.getlength(c) for c in text) + spacing * (len(text) - 1)


def text_layer(i):
    """RGBA overlay at 4K for frame i (titles + subtitles) or None."""
    t = i / FPS
    lay = Image.new("RGBA", (OUTW, OUTH), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    used = False
    # ---- titles (upper third), letter-spacing ease, fade
    for txt, t0, t1 in TITLES:
        if t0 - 0.1 <= t <= t1 + 0.1:
            a = smooth((t - t0) / 0.45) * (1 - smooth((t - (t1 - 0.4)) / 0.4))
            if a <= 0.01:
                continue
            used = True
            sp = 22 + 14 * (1 - smooth((t - t0) / 1.2))
            lines = txt.split("\n")
            y = 560
            for ln in lines:
                wdt = spaced_width(ln, ftitle, sp)
                draw_spaced(d, ((OUTW - wdt) / 2, y), ln, ftitle, (255, 255, 255, int(255 * a)), sp)
                y += 150
            # thin cyan rule under the title
            rw = int(260 * smooth((t - t0) / 0.8))
            d.rectangle([(OUTW - rw) / 2, y + 30, (OUTW + rw) / 2, y + 36], fill=(64, 214, 255, int(220 * a)))
    # ---- subtitles (lower-centre safe area), word-by-word, current word cyan
    for c in CH:
        if c["start"] <= t < c["end"]:
            vis = [w for w in c["words"] if w["start"] <= t + 0.02]
            if not vis:
                continue
            used = True
            fade_out = 1 - smooth((t - (c["end"] - 0.15)) / 0.15)
            lines = layout_words(c["words"], fsub, 1720)
            y = 2860 - (len(lines) - 1) * 70
            for ln in lines:
                full_w = sum(fsub.getlength(w["word"]) for w in ln) + fsub.getlength(" ") * (len(ln) - 1)
                x = (OUTW - full_w) / 2
                for w in ln:
                    if w["start"] <= t + 0.02:
                        age = t - w["start"]
                        a = smooth(age / 0.12) * fade_out
                        cur = w["start"] <= t < w["end"]
                        col = CYAN if cur else WHITE
                        dy = 10 * (1 - smooth(age / 0.15))
                        d.text((x, y + dy), w["word"], font=fsub, fill=(*col, int(255 * a)))
                    x += fsub.getlength(w["word"]) + fsub.getlength(" ")
                y += 140
    if not used:
        return None
    # soft shadow for legibility
    alpha = np.asarray(lay)[..., 3].astype(np.float32) / 255
    sh = ndi.gaussian_filter(alpha[::4, ::4], 5) * 0.85
    sh = np.asarray(Image.fromarray((np.clip(sh, 0, 1) * 255).astype(np.uint8)).resize((OUTW, OUTH), Image.BILINEAR)).astype(np.float32) / 255
    return np.asarray(lay).astype(np.float32) / 255, sh


rng = np.random.default_rng(1)
GRAIN = [ndi.gaussian_filter(rng.standard_normal((OUTH // 2, OUTW // 2)).astype(np.float32), 0.6) for _ in range(6)]


def finish(img_small, i):
    im = Image.fromarray((img_small * 255 + 0.5).astype(np.uint8)).resize((OUTW, OUTH), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=3, percent=45, threshold=2))
    x = np.asarray(im).astype(np.float32) / 255
    g = GRAIN[i % len(GRAIN)]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    l = x.mean(2, keepdims=True)
    x = x + g * 0.022 * (0.35 + 0.65 * np.sqrt(np.clip(l, 0, 1))) * (1 - l)
    tl = text_layer(i)
    if tl is not None:
        rgba, sh = tl
        x = x * (1 - sh[..., None] * 0.75)
        a = rgba[..., 3:4]
        x = x * (1 - a) + rgba[..., :3] * a
    return (np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    preview = None
    if "--preview" in sys.argv:
        preview = int(sys.argv[sys.argv.index("--preview") + 1])
    if preview:
        od = os.path.join(ROOT, "renders/final_video/preview"); os.makedirs(od, exist_ok=True)
        for i in range(0, NF, preview):
            fr = finish(grade(compose(i), i), i)
            Image.fromarray(fr).resize((540, 960), Image.LANCZOS).save(f"{od}/p_{i:03d}.jpg", quality=90)
            print("preview", i, flush=True)
        return
    out = os.path.join(ROOT, "output/sleep_documentary_30s.mp4")
    audio = os.path.join(ROOT, "audio/final_mix.wav")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUTW}x{OUTH}", "-r", str(FPS),
           "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-profile:v", "high", "-level", "5.2", "-pix_fmt", "yuv420p",
           "-x264-params", "aq-mode=3:deblock=-1,-1",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
           "-frames:v", str(NF), "-t", "30", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time; t0 = time.time()
    for i in range(NF):
        p.stdin.write(finish(grade(compose(i), i), i).tobytes())
        if i % 30 == 0:
            print(f"frame {i}/{NF}  {time.time()-t0:.0f}s", flush=True)
    p.stdin.close(); p.wait()
    print("wrote", out, "exit", p.returncode)


if __name__ == "__main__":
    main()
