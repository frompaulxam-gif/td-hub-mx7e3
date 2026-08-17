#!/usr/bin/env python3
"""Shared HTML-to-PNG renderer for TDG templates.

A template is an HTML file containing the token __DATA__ inside a script tag:
    <script>window.DATA = __DATA__;</script>
render() replaces the token with {"layout": ..., "content": ...}, writes a temp
HTML next to the template (so relative assets keep working), and screenshots it
with headless Chrome at the requested size. Transparent where the page paints
no background.
"""
import json
import os
import subprocess
import tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def render(template_html, out_png, width, height, layout, content, scale=1):
    with open(template_html) as f:
        html = f.read()
    data = json.dumps({"layout": layout, "content": content}, ensure_ascii=False)
    html = html.replace("__DATA__", data)
    tdir = os.path.dirname(os.path.abspath(template_html))
    fd, tmp = tempfile.mkstemp(suffix=".html", dir=tdir)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(html)
        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        cmd = [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=%s" % scale,
            "--default-background-color=00000000",
            "--window-size=%d,%d" % (width, height),
            "--screenshot=%s" % os.path.abspath(out_png),
            "--virtual-time-budget=5000",
            "file://" + tmp,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if r.returncode != 0 or not os.path.isfile(out_png):
            raise RuntimeError("chrome render failed: " + (r.stderr or r.stdout)[-500:])
    finally:
        os.unlink(tmp)
    return out_png
