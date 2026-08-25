#!/usr/bin/env python3
"""Burn an Instagram-style caption onto a clip, output 9:16 SDR.

Fonts are the closest legitimate matches to Instagram's (Instagram Sans is
proprietary and not licensed outside the app):
  classic    -> Inter 700          (IG "Classic")
  strong     -> Archivo Black      (IG "Strong")
  typewriter -> Courier New Bold   (IG "Typewriter", effectively exact)

Inter is a variable font whose axes are [opsz, wght] IN THAT ORDER. Passing a
single value silently sets opsz and leaves weight at 400, which renders thin.

Usage:
  story_caption.py <clip> <text> <classic|strong|typewriter> <pos 0-1> <out.mp4>
  Use \n in text for line breaks. pos is the CENTRE of the text block.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

INTER = os.path.expanduser("~/Library/Fonts/Inter-Variable.ttf")
ARCHIVO = os.path.expanduser("~/Library/Fonts/ArchivoBlack.ttf")
COURIER = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
FONTS = {"classic": (INTER, [32, 700]), "strong": (ARCHIVO, None), "typewriter": (COURIER, None)}


def build(src, text, style, pos, out):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", src],
        capture_output=True, text=True).stdout.strip().strip(",").split(",")
    w, h = int(probe[0]), int(probe[1])
    W, H = (h, w) if w > h else (w, h)     # iPhone clips carry a rotation matrix

    path, axes = FONTS[style]
    lines = text.split("\n")
    size = int(W * 0.048)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    while size > 20:
        f = ImageFont.truetype(path, size)
        if axes:
            try:
                f.set_variation_by_axes(axes)
            except Exception:
                pass
        if max(d.textlength(l, font=f) for l in lines) <= W * 0.84:
            break
        size -= 2

    lh = int(size * 1.34)
    y = int(H * pos) - (lh * len(lines)) // 2
    for l in lines:
        tw = d.textlength(l, font=f)
        d.text(((W - tw) / 2, y), l, font=f, fill=(255, 255, 255, 255))
        y += lh

    # halo drawn from the type's own alpha, so the footage is never dimmed
    mask = layer.split()[3]
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for r, s in ((int(W * 0.012), 150), (int(W * 0.004), 120)):
        m = mask.filter(ImageFilter.GaussianBlur(r)).point(lambda p, s=s: int(p * s / 255))
        lay = Image.new("RGBA", (W, H), (8, 6, 4, 0))
        lay.putalpha(m)
        halo = Image.alpha_composite(halo, lay)
    png = "/tmp/_story_caption_overlay.png"
    Image.alpha_composite(halo, layer).save(png)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-i", png,
        "-filter_complex",
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[bg];"
        f"[bg][1:v]overlay=0:0,format=yuv420p,"
        f"setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv[v]",
        "-map", "[v]", "-map", "0:a:0?", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
        check=True)
    print(f"   {os.path.basename(out)}  {W}x{H}  {style} @ {size}px")


if __name__ == "__main__":
    src, text, style, pos, out = sys.argv[1:6]
    build(src, text, style, float(pos), out)
