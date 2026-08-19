#!/usr/bin/env python3
"""Burn Instagram-style text onto a clip and output a 9:16 story-ready mp4.

This ffmpeg build has no libass, so drawtext/subtitles do not exist. Text is
rendered to a transparent PNG with Pillow and composited with the overlay filter.

Instagram's own story fonts are proprietary and not distributable. These are the
closest legitimate matches:
  classic -> Helvetica Neue Bold  (IG's default "Classic")
  strong  -> Archivo Black        (IG's heavy "Strong")

Usage:
  python3 story_overlay.py --clip in.MOV --text "Line one\nLine two" --out out.mp4
    [--style classic|strong] [--pos 0.28] [--size 78] [--caps] [--trim 8]
"""
import argparse
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = {
    "classic": ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
    "strong": (os.path.expanduser("~/Library/Fonts/ArchivoBlack.ttf"), 0),
}


def load(style, size):
    path, idx = FONTS[style]
    return ImageFont.truetype(path, size, index=idx)


def wrap(draw, text, font, max_w):
    out = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        if not words:
            out.append("")
            continue
        for wd in words:
            t = (cur + " " + wd).strip()
            if draw.textlength(t, font=font) <= max_w or not cur:
                cur = t
            else:
                out.append(cur)
                cur = wd
        out.append(cur)
    return out


def strip_emoji(text):
    """Pillow + Helvetica render emoji as tofu boxes (see LEARNINGS).
    Baked art stays text-only; emoji get added as an IG sticker on top."""
    out = []
    for ch in text:
        cp = ord(ch)
        if (0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF
                or 0xFE00 <= cp <= 0xFE0F or 0x2190 <= cp <= 0x21FF and cp != 0x2192):
            continue
        out.append(ch)
    return "\n".join(ln.strip() for ln in "".join(out).split("\n"))


def build_overlay(text, style, size, pos, caps, png_path):
    text = strip_emoji(text)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if caps:
        text = text.upper()
    max_w = int(W * 0.82)
    font = load(style, size)
    lines = wrap(d, text, font, max_w)
    while len(lines) > 4 and size > 34:          # keep it readable in 5 seconds
        size -= 6
        font = load(style, size)
        lines = wrap(d, text, font, max_w)

    lh = int(size * 1.24)
    total = lh * len(lines)
    y = int(H * pos) - total // 2
    for ln in lines:
        tw = d.textlength(ln, font=font)
        x = (W - tw) / 2
        # IG-style soft shadow so white type survives a bright frame
        d.text((x + 2, y + 4), ln, font=font, fill=(0, 0, 0, 110))
        d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += lh
    img.save(png_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clip", required=True)
    p.add_argument("--text", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--style", choices=list(FONTS), default="classic")
    p.add_argument("--size", type=int, default=78)
    p.add_argument("--pos", type=float, default=0.28)   # 0=top, 1=bottom
    p.add_argument("--caps", action="store_true")
    p.add_argument("--trim", type=float, default=0)     # seconds, 0 = keep all
    a = p.parse_args()

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    # cover-fit the source into 1080x1920, honouring the iPhone rotation matrix
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    if a.trim:
        cmd += ["-t", str(a.trim)]
    cmd += ["-i", a.clip]

    tmp_png = None
    if a.text.strip():
        tmp_png = tempfile.mktemp(suffix=".png")
        build_overlay(a.text, a.style, a.size, a.pos, a.caps, tmp_png)
        cmd += ["-i", tmp_png,
                "-filter_complex", f"[0:v]{vf}[bg];[bg][1:v]overlay=0:0[v]",
                "-map", "[v]", "-map", "0:a:0?"]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", "0:a:0?"]

    cmd += ["-c:v", "libx264", "-crf", "19", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", a.out]
    subprocess.run(cmd, check=True)
    if tmp_png:
        os.remove(tmp_png)
    print(a.out)


if __name__ == "__main__":
    main()
