#!/usr/bin/env python3
"""Build a single-week, single-venue share page into the Pages repo.

Creates share/<venue-short>-<week>/index.html referencing the media proxies
that build.py already bundled. The page is what Paul sends as a link: day by
day, visuals, titles, soft status chips, captions on grid posts only. No
studio notes, no checklists, no songs, no alerts (board display rules,
25 Aug 2026).

Run:  python3 tools/share_week.py merchants-yard 2026-08-24 [--push]
"""
import html
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from urllib.parse import quote

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORT = {"merchants-yard": "my", "moonshine": "ms"}
NAMES = {"merchants-yard": "Merchants Yard", "moonshine": "Moonshine"}
HANDLE = {"merchants-yard": "@merchants.yard", "moonshine": "@moonshinespeakeasy"}
VID_EXT = (".mp4", ".mov", ".m4v", ".webm")
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Any day"]

STATUS_LABEL = {
    "posted": ("Posted", "posted"),
    "scheduled": ("Scheduled", "scheduled"),
    "ready": ("Ready", "ready"),
    "approved": ("Ready", "ready"),
}


def chip(status):
    label, cls = STATUS_LABEL.get(status, ("In progress", "progress"))
    return f'<span class="chip chip-{cls}">{label}</span>'


def media_tag(venue, week, rel):
    enc = lambda r: "/".join(quote(p) for p in r.split("/"))
    src = f"../../media/{venue}/{week}/{enc(rel)}"
    if rel.lower().endswith(VID_EXT):
        stem = os.path.splitext(rel)[0]
        poster = ""
        if os.path.exists(os.path.join(HUB, "media", venue, week, stem + ".jpg")):
            poster = f' poster="../../media/{venue}/{week}/{enc(stem + ".jpg")}"'
        return f'<video controls playsinline preload="metadata"{poster} src="{src}"></video>'
    return f'<img loading="lazy" alt="" src="{src}">'


def day_date(slots):
    for s in slots:
        d = s.get("date")
        if d:
            try:
                return datetime.strptime(d, "%Y-%m-%d").strftime("%-d %B")
            except ValueError:
                pass
    return ""


def build(venue, week):
    with open(os.path.join(HUB, "data", venue, week + ".json")) as f:
        data = json.load(f)

    by_day = {}
    for s in data.get("slots", []):
        day = s.get("day") or "Any day"
        day = day.title() if day.lower() == "any day" else day
        by_day.setdefault(day if day in DAY_ORDER else "Any day", []).append(s)

    monday = datetime.strptime(week, "%Y-%m-%d")
    sections = []
    for day in DAY_ORDER:
        slots = by_day.get(day, [])
        if day == "Any day" and not slots:
            continue
        slots.sort(key=lambda s: 0 if s.get("kind") == "grid" else 1)
        cards = []
        for s in slots:
            kind = "Grid post" if s.get("kind") == "grid" else "Story"
            media = "".join(media_tag(venue, week, m) for m in s.get("media", []))
            if media:
                media = f'<div class="media">{media}</div>'
            caption = ""
            # captions only on upcoming grid posts: posted slots' caption fields
            # sometimes hold internal notes, and the live caption is on IG anyway
            if s.get("kind") == "grid" and s.get("caption") and s.get("status") != "posted":
                caption = f'<div class="caption">{html.escape(s["caption"])}</div>'
            cards.append(
                '<article class="card">'
                f'{media}'
                '<div class="card-body">'
                f'<div class="meta"><span class="kind">{kind}</span>{chip(s.get("status", ""))}</div>'
                f'<h3>{html.escape(s.get("title") or s.get("slot") or "")}</h3>'
                f'{caption}'
                "</div></article>"
            )
        if not cards:
            cards = ['<p class="quiet">No posts.</p>']
        sections.append(
            f'<section><h2>{day}<span class="date">{day_date(slots)}</span></h2>'
            + "".join(cards) + "</section>"
        )

    name = NAMES[venue]
    wc = monday.strftime("%-d %B %Y")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>{name} · w/c {monday.strftime("%-d %b")}</title>
<style>
  :root {{ --bg:#fbfaf8; --ink:#211a12; --mid:#6d655a; --line:#e7e1d8; --green:#2e6b38; }}
  * {{ box-sizing:border-box; margin:0; }}
  body {{ background:var(--bg); color:var(--ink); font:16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  main {{ max-width:640px; margin:0 auto; padding:28px 18px 64px; }}
  header {{ padding:6px 0 18px; border-bottom:1px solid var(--line); margin-bottom:26px; }}
  header h1 {{ font-size:22px; letter-spacing:.01em; }}
  header p {{ color:var(--mid); font-size:14px; margin-top:2px; }}
  section {{ margin-bottom:34px; }}
  h2 {{ font-size:16px; text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px; }}
  h2 .date {{ color:var(--mid); font-weight:400; text-transform:none; letter-spacing:0; margin-left:8px; font-size:14px; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:14px; overflow:hidden; margin-bottom:14px; }}
  .media img, .media video {{ display:block; width:100%; max-height:78vh; object-fit:contain; background:#171310; }}
  .media img + img, .media * + video, .media video + img {{ border-top:1px solid var(--line); }}
  .card-body {{ padding:12px 14px 14px; }}
  .meta {{ display:flex; gap:8px; align-items:center; margin-bottom:4px; }}
  .kind {{ font-size:11px; text-transform:uppercase; letter-spacing:.09em; color:var(--mid); }}
  .chip {{ font-size:11px; text-transform:uppercase; letter-spacing:.07em; padding:2px 8px; border-radius:99px; }}
  .chip-posted {{ background:rgba(46,107,56,.12); color:var(--green); }}
  .chip-scheduled {{ background:rgba(109,101,90,.12); color:var(--mid); }}
  .chip-ready {{ border:1px solid var(--line); color:var(--mid); }}
  .chip-progress {{ background:rgba(109,101,90,.08); color:var(--mid); }}
  h3 {{ font-size:16px; font-weight:600; }}
  .caption {{ white-space:pre-line; color:var(--ink); font-size:14.5px; margin-top:10px; padding-top:10px; border-top:1px dashed var(--line); }}
  .quiet {{ color:var(--mid); font-size:14px; }}
  footer {{ color:var(--mid); font-size:13px; border-top:1px solid var(--line); padding-top:16px; }}
</style>
</head>
<body>
<main>
<header>
  <h1>{name}</h1>
  <p>Instagram · week commencing Monday {wc}</p>
</header>
{"".join(sections)}
<footer>{HANDLE[venue]} · Freeschool Lane, Leicester</footer>
</main>
</body>
</html>
"""
    out_dir = os.path.join(HUB, "share", f"{SHORT[venue]}-{week}")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "index.html")
    with open(out, "w") as f:
        f.write(page)
    print("built", os.path.relpath(out, HUB))
    return f"share/{SHORT[venue]}-{week}/"


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
