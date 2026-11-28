"""Contact sheets of keyframes: python3 scripts/contact_sheet.py <dir> <prefix> [cols rows]"""
import sys, glob, os
from PIL import Image, ImageDraw, ImageFont
d, pre = sys.argv[1], sys.argv[2]; cols = int(sys.argv[3]) if len(sys.argv) > 3 else 3; rows = int(sys.argv[4]) if len(sys.argv) > 4 else 2
files = sorted(glob.glob(f"{d}/{pre}_*.png")); n = cols * rows
f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Bold.otf", 22)
os.makedirs(f"{d}/sheets", exist_ok=True)
for k in range(0, len(files), n):
    ims = [Image.open(x) for x in files[k:k + n]]; w, h = ims[0].size; tw = 640; th = int(h * tw / w)
    sheet = Image.new("RGB", (tw * cols, th * rows), (40, 40, 40))
    for i, im in enumerate(ims):
        im = im.convert("RGB").resize((tw, th), Image.LANCZOS); x, y = (i % cols) * tw, (i // cols) * th; sheet.paste(im, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + 6), os.path.basename(files[k + i])[2:-4].lstrip('0'), fill=(255, 255, 0), font=f)
    sheet.save(f"{d}/sheets/{pre}_{k // n:02d}.jpg", quality=88)
print(len(files), "frames")
