#!/usr/bin/env python3
"""Build a client-sendable share page for one venue-week.

The page is the REAL hub board, not a lookalike: it reuses index.html's markup
and loads the same app.css / app.js, with window.SHARE pinning it to one venue
and one week. app.js's share mode strips the studio chrome (venue switcher,
week nav, prep box, links, comment inputs) and drops any hidden days. Keeping
one template means the share link can never drift from the board Paul QCs.

Requires build.py to have run first: share pages read data/<venue>/<week>.json
and the media proxies under media/<venue>/<week>/.

Run:  python3 tools/share_week.py merchants-yard 2026-08-24 [--push]
"""
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORT = {"merchants-yard": "my", "moonshine": "ms"}
NAMES = {"merchants-yard": "Merchants Yard", "moonshine": "Moonshine"}
HIDE_DAYS = ["Monday"]        # Paul, 25 Aug 2026: Monday off the client link
VID_EXT = (".mp4", ".mov", ".m4v", ".webm")


def stamp():
    """Cache-buster so a client reload picks up new app.js / app.css."""
    t = max(os.path.getmtime(os.path.join(HUB, f)) for f in ("app.js", "app.css"))
    return str(int(t))


def page_body():
    """index.html's <body>, minus its own app.js tag (we add a based one)."""
    with open(os.path.join(HUB, "index.html")) as f:
        doc = f.read()
    body = doc[doc.index("<body>") + len("<body>"):doc.rindex("</body>")]
    return re.sub(r'\s*<script src="app\.js[^"]*"></script>', "", body).strip()


def make_posters(venue, week):
    """A poster frame beside each proxy video, so nothing shows as a black box."""
    root = os.path.join(HUB, "media", venue, week)
    made = 0
    for dirpath, _, files in os.walk(root):
        for f in files:
            if not f.lower().endswith(VID_EXT):
                continue
            src = os.path.join(dirpath, f)
            dst = os.path.splitext(src)[0] + ".jpg"
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                continue
            r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "1",
                                "-i", src, "-frames:v", "1", "-q:v", "4", dst],
                               capture_output=True)
            if r.returncode == 0:
                made += 1
    return made


def build(venue, week):
    data_path = os.path.join(HUB, "data", venue, week + ".json")
    if not os.path.isfile(data_path):
        sys.exit(f"no bundled data at {data_path}. Run build.py first.")
    with open(data_path) as f:
        data = json.load(f)
    dropped = [s for s in data.get("slots", [])
               if (s.get("day") or "").lower() in {d.lower() for d in HIDE_DAYS}]
    monday = datetime.strptime(week, "%Y-%m-%d")
    v = stamp()

    page = f"""<!doctype html>
<html lang="en" data-venue="{venue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>{NAMES[venue]} · w/c {monday.strftime("%-d %b %Y")}</title>
<link rel="stylesheet" href="../../app.css?v={v}">
<script>
  window.SHARE = {{
    base: "../../",
    venue: {json.dumps(venue)},
    name: {json.dumps(NAMES[venue])},
    week: {json.dumps(week)},
    hideDays: {json.dumps(HIDE_DAYS)}
  }};
</script>
</head>
<body>
{page_body()}
<script src="../../app.js?v={v}"></script>
</body>
</html>
"""
    out_dir = os.path.join(HUB, "share", f"{SHORT[venue]}-{week}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(page)

    posters = make_posters(venue, week)
    rel = f"share/{SHORT[venue]}-{week}/"
    print(f"built {rel}index.html")
    print(f"  posters generated: {posters}")
    print(f"  days hidden: {', '.join(HIDE_DAYS)} ({len(dropped)} slot(s))")
    return rel


def push():
    r = subprocess.run(["git", "-C", HUB, "status", "--porcelain"], capture_output=True, text=True)
    if not r.stdout.strip():
        print("nothing to push")
        return
    subprocess.run(["git", "-C", HUB, "add", "-A"], check=True)
    subprocess.run(["git", "-C", HUB, "commit", "-m", "week share page",
                    "-m", "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"], check=True)
    subprocess.run(["git", "-C", HUB, "push"], check=True)
    print("pushed")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--push"]
    venue = args[0] if args else "merchants-yard"
    week = args[1] if len(args) > 1 else date.today().strftime("%Y-%m-%d")
    rel = build(venue, week)
    if "--push" in sys.argv:
        push()
    print("url path:", rel)
