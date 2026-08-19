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
SERIF = [
    "/System/Library/Fonts/Supplemental/Bodoni 72.ttc",
    "/System/Library/Fonts/Supplemental/Bodoni 72 OS.ttc",
]
SANS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]


def load_font(size, family="serif"):
    for path in (SERIF if family == "serif" else SANS):
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
p.add_argument("--top", type=int, default=0)
p.add_argument("--font", choices=["serif", "sans"], default="serif")
p.add_argument("--size", type=int, default=58)
p.add_argument("--track", type=float, default=2.5)
p.add_argument("--leading", type=float, default=1.02)
p.add_argument("--caps", action="store_true", default=True)
p.add_argument("--box", action="store_true", default=False)
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
    lines = [ln.upper() for ln in a.caption.split("\n")] if a.caps else a.caption.split("\n")
    max_w = W - 120

    def line_w(text, font, track):
        return sum(d.textlength(c, font=font) + track for c in text) - track if text else 0

    # auto-fit: shrink until the longest line sits inside the margins
    size, track = a.size, a.track
    while size > 18:
        font = load_font(size, a.font)
        if max(line_w(ln, font, track) for ln in lines) <= max_w:
            break
        size -= 2
    font = load_font(size, a.font)

    def draw_tracked(x, y, text, fill):
        for c in text:
            d.text((x, y), c, font=font, fill=fill)
            x += d.textlength(c, font=font) + track

    line_h = int(size * a.leading)
    total_h = line_h * len(lines)
    y = a.top + ch - total_h // 2
    for ln in lines:
        x = (W - line_w(ln, font, track)) / 2
        if a.box:
            pass
        else:
            draw_tracked(x + 2, y + 3, ln, (0, 0, 0, 130))   # soft shadow for legibility
        draw_tracked(x, y, ln, (255, 255, 255, 255))
        y += line_h

os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
canvas.save(a.out, "PNG")
print(a.out)
