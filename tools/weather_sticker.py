#!/usr/bin/env python3
"""weather_sticker.py — BBC-style 3-day weather card for Leicester (Thu/Fri/Sat).

Generates a transparent-background RGBA PNG matching the reference sticker at
merchantsyard_tdg/HUB/refs/weathercheckaa-final.png, at 2x its resolution.

Data: open-meteo (free, no key). Stdlib + Pillow only.

Usage:
    python3 weather_sticker.py                 # merchants-yard, newest week folder
    python3 weather_sticker.py --venue moonshine
    python3 weather_sticker.py --out /path/to/file.png
"""

import argparse
import json
import math
import re
import sys
import urllib.request
from datetime import timedelta
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- constants

API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=52.6369&longitude=-1.1398"
    "&daily=temperature_2m_max,temperature_2m_min,weather_code"
    "&timezone=Europe%2FLondon"
)

VENUE_ROOTS = {
    "merchants-yard": Path("/Users/paulventura/merchantsyard_tdg"),
    "moonshine": Path("/Users/paulventura/moonshine_tdg"),
}

# Colours sampled from the reference PNG
NAVY = (53, 50, 81, 255)        # card outline
WHITE = (255, 255, 255, 255)    # card fill
YELLOW = (244, 198, 68, 255)    # sun
DARK = (20, 20, 20, 255)        # day names + temps (hi and lo)
GREY_TEXT = (85, 86, 88, 255)   # ordinal dates
CLOUD_GREY = (150, 150, 150, 255)
RULE_GREY = (207, 208, 209, 255)

# Reference geometry (units = pixels of the 654x187 reference)
REF_W, REF_H = 654, 187
OUT_SCALE = 2      # output = 2x reference
SS = 4             # supersampling for crisp vector edges
S = OUT_SCALE * SS  # canvas units per reference unit

BORDER = 3.0
CORNER_R = 10.5
RULE_XS = (217.5, 433.5)   # centres of the two vertical rules
RULE_W = 2.0
RULE_Y0, RULE_Y1 = 3.0, 178.0
COL_LEFTS = (3.0, 219.5, 435.5)   # interior left edge of each column

TEXT_PAD_X = 17.0          # day-name left inset from column edge
HEADER_INK_TOP = 21.0
HEADER_INK_H = 20.5        # 'Thu' ink height
DAY_DATE_GAP = 6.5
TEMPS_RIGHT = 196.0        # temp ink right edge, from column left
HI_INK_TOP = 71.0
HI_INK_H = 22.5            # digit ink height (hi and lo are the same size in the
LO_INK_TOP = 111.0         # reference; hi reads bigger only because it is bold)
LO_INK_H = 22.5

ICON_CX = 63.5             # sunny icon centre, from column left
ICON_CY = 101.5
SUN_DISC_R = 21.0
RAY_IN = 25.5              # ray inner radius
RAY_OUT = 39.0
RAY_W = 6.0
RAY_ROUND = 1.5

# partly-cloudy assembly (offsets from column left edge)
PARTLY_SUN_CX = 72.0       # rays-only sun centre (disc hidden by cloud)
PARTLY_CLOUD_CX = 50.5     # cloud centre
CLOUDY_CLOUD_CX = 63.5     # lone-cloud icon centre

# cloud geometry, offsets from cloud centre (cx, cy=101.5 column midline)
CLOUD_STROKE = 7.0
CLOUD_PILL = (-35.0, -13.5, 35.0, 14.5)   # x0,y0,x1,y1 rel; radius = h/2
CLOUD_BIG = (2.0, -10.5, 18.5)            # dx, dy, r  (big back lobe)
CLOUD_SMALL = (-9.0, -13.0, 11.0)         # dx, dy, r  (small front-left lobe)


# ---------------------------------------------------------------- dates/data

def pick_days(today):
    """Thu/Fri/Sat of the current Mon-Sun week; next week's if already past Sat."""
    monday = today - timedelta(days=today.weekday())
    thu = monday + timedelta(days=3)
    if today > thu + timedelta(days=2):   # today is Sunday
        thu += timedelta(days=7)
    return [thu, thu + timedelta(days=1), thu + timedelta(days=2)]


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def icon_for_code(code):
    if code in (0, 1):
        return "sunny"
    if code == 2:
        return "partly"
    return "cloudy"


def fetch_forecast(days):
    with urllib.request.urlopen(API_URL, timeout=30) as resp:
        data = json.load(resp)
    daily = data["daily"]
    by_date = {
        t: (daily["temperature_2m_max"][i],
            daily["temperature_2m_min"][i],
            daily["weather_code"][i])
        for i, t in enumerate(daily["time"])
    }
    out = []
    for d in days:
        key = d.isoformat()
        if key not in by_date:
            sys.exit(f"error: {key} not in forecast range {daily['time'][0]}..{daily['time'][-1]}")
        hi, lo, code = by_date[key]
        out.append({
            "date": d,
            "label": d.strftime("%a"),
            "ordinal": ordinal(d.day),
            "hi": round(hi),
            "lo": round(lo),
            "code": int(code),
            "icon": icon_for_code(int(code)),
        })
    return out


# ---------------------------------------------------------------- fonts

def load_face(style):
    """style: 'Bold' or 'Regular'. Returns (path, index)."""
    for path in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/HelveticaNeue.ttc"):
        for idx in range(12):
            try:
                f = ImageFont.truetype(path, 24, index=idx)
            except OSError:
                break
            if f.getname()[1] == style:
                return path, idx
    sys.exit(f"error: no system font with style {style} found")


def fit_font(path, idx, target_ink_h_ref, sample="0"):
    """Find the font size whose ink height for `sample` equals target (ref units * S)."""
    target = target_ink_h_ref * S

    def ink_h(size):
        b = ImageFont.truetype(path, size, index=idx).getbbox(sample)
        return b[3] - b[1]

    lo, hi = 4, 1200
    while lo < hi:                      # smallest size with ink_h >= target
        mid = (lo + hi) // 2
        if ink_h(mid) < target:
            lo = mid + 1
        else:
            hi = mid
    if lo > 4 and abs(ink_h(lo - 1) - target) < abs(ink_h(lo) - target):
        lo -= 1
    return ImageFont.truetype(path, lo, index=idx)


def draw_text_ink(draw, x, y_top, text, font, fill, align="left"):
    """Place text by its ink bounding box. Returns ink right edge (canvas units)."""
    b = draw.textbbox((0, 0), text, font=font)
    if align == "right":
        ox = x - b[2]
    else:
        ox = x - b[0]
    draw.text((ox, y_top - b[1]), text, font=font, fill=fill)
    return ox + b[2]


# ---------------------------------------------------------------- icons

def paste_ray_bar(canvas, cx, cy, angle_deg):
    """One sun ray: rounded bar pointing outward at angle_deg (0 = up), in ref units."""
    w = RAY_W * S
    ln = (RAY_OUT - RAY_IN) * S
    pad = int(w)  # padding so rotation doesn't clip
    tile = Image.new("RGBA", (int(w) + 2 * pad, int(ln) + 2 * pad), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.rounded_rectangle([pad, pad, pad + w, pad + ln], radius=RAY_ROUND * S, fill=YELLOW)
    tile = tile.rotate(-angle_deg, resample=Image.BICUBIC, expand=True)
    # bar centre sits at radius (RAY_IN+RAY_OUT)/2 from sun centre
    r_mid = (RAY_IN + RAY_OUT) / 2.0 * S
    a = math.radians(angle_deg)
    bx = cx * S + r_mid * math.sin(a)
    by = cy * S - r_mid * math.cos(a)
    canvas.alpha_composite(tile, (int(bx - tile.width / 2), int(by - tile.height / 2)))


def draw_sun(canvas, cx, cy, with_disc=True, rays=range(12)):
    for k in rays:
        paste_ray_bar(canvas, cx, cy, k * 30)
    if with_disc:
        d = ImageDraw.Draw(canvas)
        r = SUN_DISC_R * S
        d.ellipse([cx * S - r, cy * S - r, cx * S + r, cy * S + r], fill=YELLOW)


def draw_cloud(canvas, cx, cy):
    """Grey outlined cloud with white fill, BBC style: big lobe + front-left lobe + pill.

    Drawn as a union — every grey outer shape first, then every white inset.
    The white insets leave a stroke-wide ring around the silhouette; the big
    lobe's inner ring survives between the small lobe's and pill's white
    interiors, producing the little hook seen inside the reference cloud.
    """
    d = ImageDraw.Draw(canvas)
    st = CLOUD_STROKE * S

    def circle(dx, dy, r, fill, inset=0.0):
        x, y, rr = (cx + dx) * S, (cy + dy) * S, r * S - inset
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)

    def pill(fill, inset=0.0):
        x0, y0, x1, y1 = [v * S for v in (CLOUD_PILL[0] + cx, CLOUD_PILL[1] + cy,
                                          CLOUD_PILL[2] + cx, CLOUD_PILL[3] + cy)]
        rad = (y1 - y0) / 2 - inset
        d.rounded_rectangle([x0 + inset, y0 + inset, x1 - inset, y1 - inset],
                            radius=rad, fill=fill)

    circle(*CLOUD_BIG, fill=CLOUD_GREY)
    circle(*CLOUD_SMALL, fill=CLOUD_GREY)
    pill(CLOUD_GREY)
    circle(*CLOUD_BIG, fill=WHITE, inset=st)
    circle(*CLOUD_SMALL, fill=WHITE, inset=st)
    pill(WHITE, inset=st)


def draw_icon(canvas, col_left, kind):
    if kind == "sunny":
        draw_sun(canvas, col_left + ICON_CX, ICON_CY)
    elif kind == "partly":
        # reference shows only the right-side ray fan (12 through 6 o'clock),
        # no disc — the cloud then overlaps the fan's inner edge
        draw_sun(canvas, col_left + PARTLY_SUN_CX, ICON_CY + 0.5,
                 with_disc=False, rays=range(7))
        draw_cloud(canvas, col_left + PARTLY_CLOUD_CX, ICON_CY)
    else:
        draw_cloud(canvas, col_left + CLOUDY_CLOUD_CX, ICON_CY)


# ---------------------------------------------------------------- card

def render(forecast):
    W, H = REF_W * S, REF_H * S
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    # card: navy outline, white fill, transparent outside rounded corners
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=CORNER_R * S, fill=NAVY)
    b = BORDER * S
    d.rounded_rectangle([b, b, W - 1 - b, H - 1 - b],
                        radius=(CORNER_R - BORDER) * S, fill=WHITE)

    # vertical rules
    for rx in RULE_XS:
        d.rectangle([(rx - RULE_W / 2) * S, RULE_Y0 * S,
                     (rx + RULE_W / 2) * S, RULE_Y1 * S], fill=RULE_GREY)

    # fonts
    bold_path, bold_idx = load_face("Bold")
    reg_path, reg_idx = load_face("Regular")
    f_day = fit_font(bold_path, bold_idx, HEADER_INK_H, "T")
    f_date = fit_font(reg_path, reg_idx, HEADER_INK_H, "1")
    f_hi = fit_font(bold_path, bold_idx, HI_INK_H, "3")
    f_lo = fit_font(reg_path, reg_idx, LO_INK_H, "1")

    for col_left, day in zip(COL_LEFTS, forecast):
        # header: bold day + grey ordinal
        right = draw_text_ink(d, (col_left + TEXT_PAD_X) * S, HEADER_INK_TOP * S,
                              day["label"], f_day, DARK)
        draw_text_ink(d, right + DAY_DATE_GAP * S, HEADER_INK_TOP * S,
                      day["ordinal"], f_date, GREY_TEXT)
        # icon
        draw_icon(canvas, col_left, day["icon"])
        d = ImageDraw.Draw(canvas)  # canvas may have been composited on
        # temps, right-aligned
        draw_text_ink(d, (col_left + TEMPS_RIGHT) * S, HI_INK_TOP * S,
                      f"{day['hi']}°", f_hi, DARK, align="right")
        draw_text_ink(d, (col_left + TEMPS_RIGHT) * S, LO_INK_TOP * S,
                      f"{day['lo']}°", f_lo, DARK, align="right")

    return canvas.resize((REF_W * OUT_SCALE, REF_H * OUT_SCALE), Image.LANCZOS)


# ---------------------------------------------------------------- output path

def newest_week_dir(root):
    weeks = root / "WEEKS"
    if not weeks.is_dir():
        sys.exit(f"error: {weeks} not found")
    candidates = []
    for p in sorted(weeks.iterdir()):
        if not (p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)):
            continue
        wj = p / "week.json"
        archived = False
        if wj.is_file():
            try:
                archived = bool(json.loads(wj.read_text()).get("archived"))
            except (json.JSONDecodeError, OSError):
                pass
        if not archived:
            candidates.append(p)
    if not candidates:
        sys.exit(f"error: no non-archived week folders in {weeks}")
    return max(candidates, key=lambda p: p.name)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="BBC-style Thu/Fri/Sat weather sticker for Leicester")
    ap.add_argument("--venue", choices=sorted(VENUE_ROOTS), default="merchants-yard")
    ap.add_argument("--out", type=Path, default=None, help="explicit output PNG path")
    args = ap.parse_args()

    today = datetime.now(ZoneInfo("Europe/London")).date()
    days = pick_days(today)
    forecast = fetch_forecast(days)

    print("Leicester forecast (open-meteo):")
    for f in forecast:
        print(f"  {f['label']} {f['date'].isoformat()}  hi {f['hi']}°  lo {f['lo']}°  "
              f"code {f['code']} -> {f['icon']}")

    img = render(forecast)

    if args.out:
        out = args.out
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        week = newest_week_dir(VENUE_ROOTS[args.venue])
        stories = week / "stories"
        stories.mkdir(exist_ok=True)
        out = stories / f"weather-sticker-{days[0].isoformat()}.png"

    img.save(out)
    print(f"saved: {out}  ({img.width}x{img.height}, corner alpha={img.getpixel((0, 0))[3]})")


if __name__ == "__main__":
    main()
