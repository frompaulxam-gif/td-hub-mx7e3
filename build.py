#!/usr/bin/env python3
"""Build the static snapshot of the hub for GitHub Pages.

Collects week.json from both venue folders into data/, generates small web
proxies of all referenced media into media/, and writes data/manifest.json.
The live site (serve.py) never uses these; they exist only so the published
read-only snapshot can show previews without shipping 100MB originals.

Run:  python3 /Users/paulventura/tdg-hub/build.py          (build only)
      python3 /Users/paulventura/tdg-hub/build.py --push   (build + commit + push)
"""
import json
import os
import shutil
import subprocess
import sys

HUB = os.path.dirname(os.path.abspath(__file__))
VENUES = {
    "merchants-yard": {"root": "/Users/paulventura/merchantsyard_tdg", "name": "Merchants Yard"},
    "moonshine": {"root": "/Users/paulventura/moonshine_tdg", "name": "Moonshine"},
}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VID_EXT = {".mp4", ".mov", ".m4v", ".webm"}


def newer(src, dst):
    return not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)


def proxy_image(src, dst):
    if not newer(src, dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if dst.endswith(".png"):
        shutil.copyfile(src, dst)  # renders/stickers stay lossless, they are small
    else:
        subprocess.run(["sips", "-Z", "1080", "-s", "format", "jpeg",
                        "-s", "formatOptions", "78", src, "--out", dst],
                       check=True, capture_output=True)


def proxy_video(src, dst):
    if not newer(src, dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src,
        "-vf", "scale='min(720,iw)':-2", "-c:v", "libx264", "-crf", "28",
        "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", dst,
    ], check=True, capture_output=True)


def build():
    manifest = {"venues": []}
    for slug, v in VENUES.items():
        weeks_dir = os.path.join(v["root"], "WEEKS")
        week_names = []
        if os.path.isdir(weeks_dir):
            for name in sorted(os.listdir(weeks_dir)):
                wj = os.path.join(weeks_dir, name, "week.json")
                if not os.path.isfile(wj):
                    continue
                with open(wj) as f:
                    data = json.load(f)
                for slot in data.get("slots", []):
                    ref = slot.get("reference")
                    if ref:
                        src = os.path.join(v["root"], ref)
                        if os.path.isfile(src):
                            base = os.path.basename(ref)
                            ext = os.path.splitext(base)[1].lower()
                            try:
                                if ext in VID_EXT:
                                    dst = os.path.join(HUB, "media", slug, "refs", os.path.splitext(base)[0] + ".mp4")
                                    proxy_video(src, dst)
                                else:
                                    out_base = base if ext == ".png" else os.path.splitext(base)[0] + ".jpg"
                                    dst = os.path.join(HUB, "media", slug, "refs", out_base)
                                    proxy_image(src, dst)
                            except subprocess.CalledProcessError as e:
                                print(f"  ref proxy failed {ref}: {e}")
                    new_media = []
                    for rel in slot.get("media", []):
                        src = os.path.join(weeks_dir, name, rel)
                        if not os.path.isfile(src):
                            continue
                        stem, ext = os.path.splitext(rel)
                        ext = ext.lower()
                        if ext in VID_EXT:
                            out_rel = stem + ".mp4"
                            dst = os.path.join(HUB, "media", slug, name, out_rel)
                            try:
                                proxy_video(src, dst)
                            except subprocess.CalledProcessError as e:
                                print(f"  video proxy failed {rel}: {e.stderr.decode()[-200:] if e.stderr else e}")
                                continue
                        elif ext in IMG_EXT:
                            out_rel = stem + (".png" if ext == ".png" else ".jpg")
                            dst = os.path.join(HUB, "media", slug, name, out_rel)
                            try:
                                proxy_image(src, dst)
                            except subprocess.CalledProcessError as e:
                                print(f"  image proxy failed {rel}: {e}")
                                continue
                        else:
                            continue
                        new_media.append(out_rel)
                    slot["media"] = new_media
                os.makedirs(os.path.join(HUB, "data", slug), exist_ok=True)
                with open(os.path.join(HUB, "data", slug, name + ".json"), "w") as f:
                    json.dump(data, f, indent=1, ensure_ascii=False)
                week_names.append(name)
                print(f"{slug}/{name}: bundled")
        manifest["venues"].append({"slug": slug, "name": v["name"], "weeks": week_names})
    with open(os.path.join(HUB, "data", "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("manifest written")


def push():
    r = subprocess.run(["git", "-C", HUB, "status", "--porcelain"], capture_output=True, text=True)
    if not r.stdout.strip():
        print("nothing to push")
        return
    subprocess.run(["git", "-C", HUB, "add", "-A"], check=True)
    subprocess.run(["git", "-C", HUB, "commit", "-m", "hub snapshot",
                    "-m", "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"], check=True)
    subprocess.run(["git", "-C", HUB, "push"], check=True)
    print("pushed")


if __name__ == "__main__":
    build()
    if "--push" in sys.argv:
        push()
