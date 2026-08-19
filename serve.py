#!/usr/bin/env python3
"""TDG Hub local server.

Serves the QC site, venue media, and write-back APIs.
Run:  python3 /Users/paulventura/tdg-hub/serve.py   (port 4870)

APIs
  GET  /api/venues                       venue list + current week
  GET  /api/weeks?venue=<slug>           all weeks with their slots
  GET  /media/<venue>/<week>/<path>      file from that week folder
  POST /api/slot                         patch a slot (status/caption/alternates/add_note)
  POST /api/render                       re-render a template after layout edit
"""
import json
import os
import re
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

HUB = os.path.dirname(os.path.abspath(__file__))
PORT = 4870

VENUES = {
    "merchants-yard": {"root": "/Users/paulventura/merchantsyard_tdg", "name": "Merchants Yard"},
    "moonshine": {"root": "/Users/paulventura/moonshine_tdg", "name": "Moonshine"},
}

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def week_dir(venue, week):
    root = VENUES[venue]["root"]
    d = os.path.realpath(os.path.join(root, "WEEKS", week))
    if not d.startswith(os.path.realpath(os.path.join(root, "WEEKS"))):
        raise ValueError("bad path")
    return d


def load_weeks(venue):
    root = os.path.join(VENUES[venue]["root"], "WEEKS")
    weeks = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            wj = os.path.join(root, name, "week.json")
            if os.path.isfile(wj):
                try:
                    with open(wj) as f:
                        weeks.append(json.load(f))
                except json.JSONDecodeError as e:
                    print(f"warn: {wj}: {e}")
    return weeks


def save_week(venue, week, data):
    path = os.path.join(week_dir(venue, week), "week.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _slug(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def _crop_45(src, dst, pos):
    """Bake the Instagram 4:5 crop using the saved objectPosition percentages."""
    from PIL import Image
    px, py = 50.0, 50.0
    m = re.match(r"([\d.]+)%\s+([\d.]+)%", pos or "")
    if m:
        px, py = float(m.group(1)), float(m.group(2))
    img = Image.open(src)
    img = img.convert("RGB")
    w, h = img.size
    target = 4 / 5
    if w / h > target:
        cw, ch = int(h * target), h
        x = int((w - cw) * px / 100)
        box = (x, 0, x + cw, ch)
    else:
        cw, ch = w, int(w / target)
        y = int((h - ch) * py / 100)
        box = (0, y, cw, y + ch)
    img = img.crop(box).resize((1080, 1350), Image.LANCZOS)
    img.save(dst, "JPEG", quality=92)


def build_export(venue, week, day=None):
    """The week as a handover zip: w-c folder, grid post + story post,
    numbered day files, baked 4:5 carousel crops, placeholders for gaps,
    captions.txt so anyone can post it."""
    import shutil
    import tempfile
    weeks = load_weeks(venue)
    data = next((w for w in weeks if w.get("week_start") == week), None)
    if not data:
        raise ValueError("unknown week")
    wdir = week_dir(venue, week)
    label = _slug(data.get("label") or ("w c " + week))
    if day:
        label = f"{label} {_slug(day)}"
    stage = tempfile.mkdtemp(prefix="hub-export-")
    root = os.path.join(stage, label)
    gdir = os.path.join(root, "grid post")
    sdir = os.path.join(root, "story post")
    os.makedirs(gdir)
    os.makedirs(sdir)

    def day_sort(s):
        d = (s.get("day") or "").lower()
        anyday = "any" in d or "quiet" in d
        return ("9999-99-99" if anyday else (s.get("date") or "9999-99-98"))

    captions = {"grid post": [], "story post": []}
    for kind, outdir, foldername in (("grid", gdir, "grid post"), ("story", sdir, "story post")):
        slots = sorted([s for s in data["slots"] if s.get("kind") == kind], key=day_sort)
        if day:
            slots = [s for s in slots if (s.get("day") or "").lower().startswith(day.lower())]
        n = 0
        for s in slots:
            n += 1
            dayslug = _slug(s.get("day"))
            title = _slug(s.get("title") or s.get("slot"))
            base = f"{n} {dayslug} {title}".strip()
            status = s.get("status", "")
            approved = status in ("approved", "scheduled", "posted")
            media = s.get("media") or []
            crops = s.get("crops") or {}
            if not media:
                why = [status]
                for c in s.get("checklist") or []:
                    why.append("- " + (c["text"] if isinstance(c, dict) else str(c)))
                with open(os.path.join(outdir, base + " - PLACEHOLDER.txt"), "w") as f:
                    f.write(f"{s.get('title')}\nStatus: {status}\n" + "\n".join(why[1:]) + "\n")
            else:
                multi = len(media) > 1
                for i, rel in enumerate(media, 1):
                    src = os.path.join(wdir, rel)
                    if not os.path.isfile(src):
                        continue
                    ext = os.path.splitext(rel)[1].lower()
                    suffix = f" {i}" if multi else ""
                    flag = "" if approved else " (not approved)"
                    is_photo = ext in (".jpg", ".jpeg", ".png") and s.get("candidates")
                    if is_photo and ext != ".png":
                        dst = os.path.join(outdir, base + suffix + flag + ".jpg")
                        _crop_45(src, dst, crops.get(rel))
                    else:
                        dst = os.path.join(outdir, base + suffix + flag + ext)
                        shutil.copyfile(src, dst)
            cap = (s.get("caption") or "").strip()
            captions[foldername].append(f"{n} {dayslug} {title}  [{status}]\n{cap or '(no caption yet)'}\n")

    with open(os.path.join(root, "captions.txt"), "w") as f:
        f.write("GRID POSTS\n==========\n\n" + "\n".join(captions["grid post"]))
        f.write("\n\nSTORIES\n=======\n\n" + "\n".join(captions["story post"]))

    zbase = os.path.join(stage, label)
    shutil.make_archive(zbase, "zip", stage, label)
    return zbase + ".zip"


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        # app shell must never go stale; media stays cacheable (busted via ?v=)
        if self.path.startswith(("/media/", "/root/")):
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/chic-source":
            q = parse_qs(u.query)
            venue = q.get("venue", [""])[0]
            slide = unquote(q.get("slide", [""])[0])
            if venue not in VENUES or not slide:
                return self.send_error(404)
            root = VENUES[venue]["root"]
            H = os.path.join(root, "HUB", "refs", "H-chic")
            fn = os.path.basename(slide)
            tail = os.path.splitext(fn)[0].split("-", 1)[-1]
            src = None
            # route 1: the 52-slide bank, mapped to its pool photo
            try:
                with open(os.path.join(H, "slide-to-photo.json")) as f:
                    m = json.load(f)
                hit = m.get(fn) or next(
                    (v for k, v in m.items()
                     if os.path.splitext(k)[0].split("-", 1)[-1] == tail), None)
                if hit:
                    # "src" points anywhere under HUB (full-res delivery originals);
                    # "photo" is a file in the H-chic pool
                    if hit.get("src"):
                        cand = os.path.realpath(os.path.join(root, "HUB", hit["src"]))
                        if cand.startswith(os.path.realpath(root)) and os.path.isfile(cand):
                            src = cand
                    if not src:
                        cand = os.path.join(H, "photos", hit["photo"])
                        if os.path.isfile(cand):
                            src = cand
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            # route 2: older slides carry their photo id, which maps to the full-res delivery
            if not src:
                pm = re.search(r"(\d{4}-\d{3})", fn)
                if pm:
                    try:
                        with open(os.path.join(H, "pool-manifest.json")) as f:
                            man = json.load(f)
                        rel = man.get(pm.group(1))
                        if rel:
                            cand = os.path.realpath(os.path.join(root, "HUB", rel))
                            if cand.startswith(os.path.realpath(root)) and os.path.isfile(cand):
                                src = cand
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
            if not src:
                return self.send_error(404)
            with open(src, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition",
                             f'attachment; filename="{tail}.jpg"')
            self.end_headers()
            return self.wfile.write(body)
        if u.path == "/api/kinda-chic-photos":
            q = parse_qs(u.query)
            venue = q.get("venue", [""])[0]
            if venue not in VENUES:
                return self._json({"error": "unknown venue"}, 400)
            pool = os.path.join(VENUES[venue]["root"], "HUB", "refs", "H-chic", "photos")
            files = sorted(os.listdir(pool)) if os.path.isdir(pool) else []
            return self._json({"photos": [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png"))]})
        if u.path == "/api/template":
            q = parse_qs(u.query)
            venue = q.get("venue", [""])[0]
            week = q.get("week", [""])[0]
            slot_id = q.get("id", [""])[0]
            try:
                slot, _ = self._find_slot(venue, week, slot_id)
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
            tpl = slot.get("template") or {}
            root = VENUES[venue]["root"]
            out = {"template": tpl}
            for key in ("layout", "content"):
                p = tpl.get(key)
                if p and os.path.isfile(os.path.join(root, p)):
                    with open(os.path.join(root, p)) as f:
                        out[key] = json.load(f)
            return self._json(out)
        if u.path == "/api/venues":
            return self._json({
                "live": True,
                "venues": [{"slug": k, "name": v["name"]} for k, v in VENUES.items()],
            })
        if u.path == "/api/weeks":
            q = parse_qs(u.query)
            venue = q.get("venue", [""])[0]
            if venue not in VENUES:
                return self._json({"error": "unknown venue"}, 400)
            return self._json({"weeks": load_weeks(venue)})
        m = re.match(r"^/media/([a-z-]+)/([0-9-]+)/(.+)$", u.path)
        if m:
            venue, week, rel = m.group(1), m.group(2), unquote(m.group(3))
            if venue not in VENUES:
                return self.send_error(404)
            base = week_dir(venue, week)
            path = os.path.realpath(os.path.join(base, rel))
            if not path.startswith(base) or not os.path.isfile(path):
                return self.send_error(404)
            return self._serve_file(path)
        m = re.match(r"^/root/([a-z-]+)/(.+)$", u.path)
        if m:
            venue, rel = m.group(1), unquote(m.group(2))
            if venue not in VENUES:
                return self.send_error(404)
            base = os.path.realpath(VENUES[venue]["root"])
            path = os.path.realpath(os.path.join(base, rel))
            if not path.startswith(base) or not os.path.isfile(path):
                return self.send_error(404)
            return self._serve_file(path)
        if u.path == "/api/export":
            q = parse_qs(u.query)
            venue = q.get("venue", [""])[0]
            week = q.get("week", [""])[0]
            day = q.get("day", [""])[0] or None
            if venue not in VENUES:
                return self._json({"error": "unknown venue"}, 400)
            try:
                zpath = build_export(venue, week, day)
            except Exception as e:
                return self._json({"error": str(e)}, 500)
            with open(zpath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition",
                             f'attachment; filename="{os.path.basename(zpath)}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/api/photos":
            q = parse_qs(u.query)
            venue = q.get("venue", [""])[0]
            if venue not in VENUES:
                return self._json({"error": "unknown venue"}, 400)
            return self._json({"photos": self._recent_photos(venue)})
        # static site files from the hub directory
        self.directory = HUB
        return super().do_GET()

    def _serve_file(self, path):
        ctype = self.guess_type(path)
        size = os.path.getsize(path)
        # naive range support so <video> scrubbing works in Safari
        rng = self.headers.get("Range")
        with open(path, "rb") as f:
            if rng:
                m = re.match(r"bytes=(\d+)-(\d*)", rng)
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
                f.seek(start)
                data = f.read(end - start + 1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                data = f.read()
                self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json({"error": "bad json"}, 400)

        if u.path == "/api/slot":
            return self._patch_slot(body)
        if u.path == "/api/week":
            return self._patch_week(body)
        if u.path == "/api/render":
            return self._render(body)
        if u.path == "/api/setbg":
            return self._setbg(body)
        if u.path == "/api/song-used":
            return self._song_used(body)
        if u.path == "/api/reactive":
            return self._reactive(body)
        if u.path == "/api/kinda-chic-render":
            return self._kinda_chic_render(body)
        return self._json({"error": "unknown endpoint"}, 404)

    def _kinda_chic_render(self, body):
        """Re-render one kinda-chic slide with a new line and/or photo."""
        venue = body.get("venue")
        photo = body.get("photo", "")
        line = (body.get("line") or "").strip()
        out_rel = body.get("out", "")
        if venue not in VENUES or not photo or not line or not out_rel:
            return self._json({"error": "missing fields"}, 400)
        if "/" in photo or ".." in photo:
            return self._json({"error": "bad photo"}, 400)
        week_root = os.path.realpath(week_dir(venue, body.get("week_start", "")))
        out_path = os.path.realpath(os.path.join(week_root, out_rel))
        if not out_path.startswith(week_root):
            return self._json({"error": "bad path"}, 400)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        renderer = os.path.join(VENUES[venue]["root"], "HUB", "refs", "H-chic", "render.py")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("chic_render", renderer)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.render(photo, line, out_path)
        except Exception as e:
            return self._json({"error": str(e)}, 500)
        return self._json({"ok": True})

    def _reactive(self, body):
        """Keep/skip decisions from the swipe QC page."""
        venue = body.get("venue")
        if venue not in VENUES:
            return self._json({"error": "unknown venue"}, 400)
        path = os.path.join(VENUES[venue]["root"], "reactive-ideas.json")
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._json({"error": "no ideas file"}, 404)
        if body.get("reset"):
            for x in data["ideas"]:
                x["status"] = "new"
        else:
            idea = next((x for x in data["ideas"] if x["id"] == body.get("id")), None)
            if not idea:
                return self._json({"error": "unknown idea"}, 404)
            idea["status"] = body.get("status", "new")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return self._json({"ok": True})

    def _song_used(self, body):
        """Log a song as used so future suggestions avoid repeats."""
        venue = body.get("venue")
        song = (body.get("song") or "").strip()
        if venue not in VENUES or not song:
            return self._json({"error": "bad request"}, 400)
        path = os.path.join(VENUES[venue]["root"], "songs-used.json")
        try:
            with open(path) as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log = []
        key = song.split("\u00b7")[0].strip().lower()
        existing = next((r for r in log if r.get("key") == key), None)
        if body.get("undo"):
            log = [r for r in log if r.get("key") != key]
        elif not existing:
            from datetime import date
            log.append({"key": key, "song": song.split("\u00b7")[0].strip(),
                        "date": str(date.today()), "week": body.get("week_start", ""),
                        "slot": body.get("title", "")})
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return self._json({"ok": True, "used": [r["key"] for r in log]})

    def _setbg(self, body):
        """Point a templated slot's content at a different photo, then re-render."""
        venue = body.get("venue")
        photo = body.get("photo", "")
        try:
            slot, _ = self._find_slot(venue, body.get("week_start"), body.get("id"))
        except LookupError as e:
            return self._json({"error": str(e)}, 404)
        tpl = slot.get("template") or {}
        if not tpl.get("content"):
            return self._json({"error": "slot has no editable content"}, 400)
        root = os.path.realpath(VENUES[venue]["root"])
        photo_abs = os.path.realpath(os.path.join(root, photo))
        if not photo_abs.startswith(root) or not os.path.isfile(photo_abs):
            return self._json({"error": "photo not found"}, 404)
        cpath = os.path.join(root, tpl["content"])
        with open(cpath) as f:
            content = json.load(f)
        if isinstance(content.get("slides"), list) and content["slides"]:
            content["slides"][0]["bg"] = photo_abs
        else:
            content["bg"] = photo_abs
        tmp = cpath + ".tmp"
        with open(tmp, "w") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        os.replace(tmp, cpath)
        return self._render({"venue": venue, "week_start": body.get("week_start"), "id": body.get("id")})

    def _recent_photos(self, venue, limit=80):
        """Latest delivery/week images for the photo picker, newest folders first."""
        root = VENUES[venue]["root"]
        candidates = []
        search_dirs = []
        hub_deliveries = os.path.join(root, "HUB", "deliveries")
        if os.path.isdir(hub_deliveries):
            for d in sorted(os.listdir(hub_deliveries), reverse=True):
                p = os.path.join(hub_deliveries, d)
                if os.path.isdir(p):
                    search_dirs.append(p)
        weeks_dir = os.path.join(root, "WEEKS")
        if os.path.isdir(weeks_dir):
            for d in sorted(os.listdir(weeks_dir), reverse=True):
                p = os.path.join(weeks_dir, d)
                if os.path.isdir(p):
                    search_dirs.append(p)
        for d in search_dirs:
            if len(candidates) >= limit:
                break
            for dirpath, _dirnames, filenames in os.walk(d):
                for name in sorted(filenames):
                    if name.lower().endswith((".jpg", ".jpeg", ".png")) and not name.startswith("."):
                        rel = os.path.relpath(os.path.join(dirpath, name), root)
                        candidates.append(rel)
                        if len(candidates) >= limit:
                            break
                if len(candidates) >= limit:
                    break
        return candidates

    def _find_slot(self, venue, week, slot_id):
        if venue not in VENUES:
            raise LookupError("unknown venue")
        weeks = load_weeks(venue)
        data = next((w for w in weeks if w.get("week_start") == week), None)
        if not data:
            raise LookupError("unknown week")
        slot = next((s for s in data["slots"] if s.get("id") == slot_id), None)
        if not slot:
            raise LookupError("unknown slot")
        return slot, data

    def _patch_week(self, body):
        venue = body.get("venue")
        week = body.get("week_start")
        if venue not in VENUES:
            return self._json({"error": "unknown venue"}, 400)
        weeks = load_weeks(venue)
        data = next((w for w in weeks if w.get("week_start") == week), None)
        if not data:
            return self._json({"error": "unknown week"}, 404)
        for k, v in (body.get("set") or {}).items():
            if k in {"prep", "alerts", "key_dates"}:
                data[k] = v
        save_week(venue, week, data)
        return self._json({"ok": True, "week": {k: data.get(k) for k in ("prep", "alerts", "key_dates")}})

    def _patch_slot(self, body):
        venue = body.get("venue")
        week = body.get("week_start")
        try:
            slot, data = self._find_slot(venue, week, body.get("id"))
        except LookupError as e:
            return self._json({"error": str(e)}, 404)
        allowed = {"status", "caption", "alternates", "title", "checklist", "caption_ref", "media", "candidates", "crops", "songs"}
        for k, v in (body.get("set") or {}).items():
            if k in allowed:
                slot[k] = v
        note = body.get("add_note")
        if note and note.get("text"):
            from datetime import date
            slot.setdefault("notes", []).append(
                {"ts": str(date.today()), "text": note["text"], "by": "paul"})
        save_week(venue, week, data)
        return self._json({"ok": True, "slot": slot})

    def _render(self, body):
        """Re-render a slot's template, optionally saving an edited layout first."""
        venue = body.get("venue")
        try:
            slot, _ = self._find_slot(venue, body.get("week_start"), body.get("id"))
        except LookupError as e:
            return self._json({"error": str(e)}, 404)
        tpl = slot.get("template") or {}
        name = tpl.get("name", "")
        if not re.match(r"^[a-z0-9-]+$", name):
            return self._json({"error": "slot has no template"}, 400)
        root = VENUES[venue]["root"]
        script = os.path.join(root, "TEMPLATES", name, "render.py")
        if not os.path.isfile(script):
            return self._json({"error": f"no renderer at {script}"}, 404)
        layout = body.get("layout")
        layout_path = os.path.join(root, tpl.get("layout") or f"TEMPLATES/{name}/layout.json")
        if layout is not None:
            os.makedirs(os.path.dirname(layout_path), exist_ok=True)
            tmp = layout_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(layout, f, indent=2, ensure_ascii=False)
            os.replace(tmp, layout_path)
        content = body.get("content")
        if content is not None and tpl.get("content"):
            cpath = os.path.join(root, tpl["content"])
            tmp = cpath + ".tmp"
            with open(tmp, "w") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            os.replace(tmp, cpath)
        args = [sys.executable, script, "--layout", layout_path]
        if tpl.get("content"):
            args += ["--content", os.path.join(root, tpl["content"])]
        if tpl.get("outdir"):
            args += ["--outdir", os.path.join(root, tpl["outdir"])]
        elif tpl.get("out"):
            args += ["--out", os.path.join(root, tpl["out"])]
        else:
            return self._json({"error": "template has no out path"}, 400)
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return self._json({"error": "render timed out"}, 500)
        if out.returncode != 0:
            return self._json({"error": (out.stderr or out.stdout)[-2000:]}, 500)
        return self._json({"ok": True, "stdout": out.stdout[-1000:]})


if __name__ == "__main__":
    os.chdir(HUB)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"TDG Hub on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
