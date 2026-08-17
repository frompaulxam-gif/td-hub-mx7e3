#!/usr/bin/env python3
"""Turn a 4:5 grid graphic into a postable 9:16 story.

The source art sits full-width centred on a blurred, darkened blow-up of
itself, so nothing gets cropped and the story feels intentional.

Usage: python3 story_from_grid.py <in.png> <out.png>
"""
import sys

from PIL import Image, ImageFilter, ImageEnhance

W, H = 1080, 1920

src = Image.open(sys.argv[1]).convert("RGB")
# background: cover-scale, blur, darken
scale = max(W / src.width, H / src.height)
bg = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2,
              (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
bg = bg.filter(ImageFilter.GaussianBlur(40))
bg = ImageEnhance.Brightness(bg).enhance(0.55)
# foreground: fit width
fw = W
fh = int(src.height * (fw / src.width))
fg = src.resize((fw, fh), Image.LANCZOS)
canvas = bg.copy()
canvas.paste(fg, (0, (H - fh) // 2))
canvas.save(sys.argv[2], "PNG")
print(sys.argv[2])
