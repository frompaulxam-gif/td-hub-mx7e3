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


def load_font(size, family="serif", bold=False):
    if family == "serif" and bold:
        return ImageFont.truetype(SERIF[0], size, index=2)   # Bodoni 72 Bold
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
p.add_argument("--ratio", type=float, default=0.72)
p.add_argument("--margin", type=int, default=110)
p.add_argument("--bold", action="store_true", default=False)
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
    raw = a.caption.split("\n")
    if a.caps:
        raw = [ln.upper() for ln in raw]
    # a blank line splits the caption: everything after it renders smaller
    if "" in [ln.strip() for ln in raw]:
        cut = [ln.strip() for ln in raw].index("")
        blocks = [[l for l in raw[:cut] if l.strip()], [l for l in raw[cut:] if l.strip()]]
    else:
        blocks = [[l for l in raw if l.strip()], []]
    max_w = W - a.margin * 2

    def line_w(text, font, track):
        return sum(d.textlength(c, font=font) + track for c in text) - track if text else 0

    # auto-fit: shrink both blocks together until the widest line fits the margins
    size, track = a.size, a.track
    while size > 18:
        f1 = load_font(size, a.font, a.bold)
        f2 = load_font(max(14, int(size * a.ratio)), a.font, a.bold)
        widest = max([line_w(l, f1, track) for l in blocks[0]] or [0] +
                     [line_w(l, f2, track) for l in blocks[1]] or [0])
        if blocks[1]:
            widest = max(widest, max(line_w(l, f2, track) for l in blocks[1]))
        if widest <= max_w:
            break
        size -= 2
    f1 = load_font(size, a.font, a.bold)
    size2 = max(14, int(size * a.ratio))
    f2 = load_font(size2, a.font, a.bold)

    def draw_tracked(x, y, text, font):
        for c in text:
            d.text((x, y), c, font=font, fill=(255, 255, 255, 255))
            x += d.textlength(c, font=font) + track

    lh1, lh2 = int(size * a.leading), int(size2 * a.leading)
    gap = int(size * 0.30) if blocks[1] else 0
    total_h = lh1 * len(blocks[0]) + gap + lh2 * len(blocks[1])
    y = a.top + ch - total_h // 2
    for ln in blocks[0]:
        draw_tracked((W - line_w(ln, f1, track)) / 2, y, ln, f1)
        y += lh1
    y += gap
    for ln in blocks[1]:
        draw_tracked((W - line_w(ln, f2, track)) / 2, y, ln, f2)
        y += lh2

os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
canvas.save(a.out, "PNG")
print(a.out)
