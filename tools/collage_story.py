#!/usr/bin/env python3
"""Build a 2x2 photo collage story (1080x1920) with an optional caption bar.

Usage:
  python3 collage_story.py --photos a.jpg b.jpg c.jpg d.jpg \
      [--caption "line one\nline two"] [--top 150] --out out.png

Each photo is cover-cropped into its cell so nothing is squashed. The caption
bar sits on the horizontal seam, translucent dark with white text, matching the
venue's usual story collage.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]


def load_font(size):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def cover(img, cw, ch):
    scale = max(cw / img.width, ch / img.height)
    im = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    left = (im.width - cw) // 2
    top = int((im.height - ch) * 0.42)  # bias slightly up: faces sit high
    return im.crop((left, top, left + cw, top + ch))


p = argparse.ArgumentParser()
p.add_argument("--photos", nargs=4, required=True)
p.add_argument("--caption", default="")
p.add_argument("--top", type=int, default=150)
p.add_argument("--out", required=True)
a = p.parse_args()

canvas = Image.new("RGB", (W, H), (0, 0, 0))
grid_h = H - a.top * 2
cw, ch = W // 2, grid_h // 2

for i, path in enumerate(a.photos):
    img = Image.open(path).convert("RGB")
    cell = cover(img, cw, ch)
    x = (i % 2) * cw
    y = a.top + (i // 2) * ch
    canvas.paste(cell, (x, y))

if a.caption:
    d = ImageDraw.Draw(canvas, "RGBA")
    lines = a.caption.split("\n")
    font = load_font(34)
    pad_x, pad_y, gap = 26, 20, 10
    widths = [d.textbbox((0, 0), ln, font=font)[2] for ln in lines]
    line_h = d.textbbox((0, 0), "Hg", font=font)[3]
    box_w = max(widths) + pad_x * 2
    box_h = line_h * len(lines) + gap * (len(lines) - 1) + pad_y * 2
    bx = (W - box_w) // 2
    by = a.top + ch - box_h // 2
    d.rounded_rectangle([bx, by, bx + box_w, by + box_h], radius=14, fill=(48, 36, 38, 214))
    ty = by + pad_y
    for ln, lw in zip(lines, widths):
        d.text(((W - lw) // 2, ty), ln, font=font, fill=(255, 255, 255, 255))
        ty += line_h + gap

os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
canvas.save(a.out, "PNG")
print(a.out)
