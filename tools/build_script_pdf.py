#!/usr/bin/env python3
"""Build the simple black and white talking-head script PDF for a week.

Reads the week's talking-head.json (lines + options) and
talking-head-selections.json (Paul's picks, in take order) and writes
talking-head-script.pdf beside them, plus a copy in ~/Downloads.

Deliberately plain: title, take 1 full script, take 2 full script, then line
by line. No brief, no shoot notes, no em dashes.

Run:  python3 tools/build_script_pdf.py <venue-root> <monday>
      python3 tools/build_script_pdf.py /Users/paulventura/TDG/merchants-yard 2026-08-24
"""
import json
import os
import shutil
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

TITLE = "Carnival in the Courtyard, talking head"


def takes_for(line, sel):
    picks = (sel.get(line["id"]) or {}).get("picks") or []
    out = [line["options"][i] for i in picks if 0 <= i < len(line["options"])]
    custom = (sel.get(line["id"]) or {}).get("custom")
    if custom:
        out.append(custom)
    return out


def build(root, week):
    rdir = os.path.join(root, "WEEKS", week, "renders")
    data = json.load(open(os.path.join(rdir, "talking-head.json")))
    sel_path = os.path.join(rdir, "talking-head-selections.json")
    sel = json.load(open(sel_path)) if os.path.isfile(sel_path) else {}

    # only lines with something picked make the script
    lines = [(l, takes_for(l, sel)) for l in data["lines"]]
    lines = [(l, t) for l, t in lines if t]
    if not lines:
        sys.exit("nothing picked yet")

    out = os.path.join(rdir, "talking-head-script.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            title=TITLE, author="Merchants Yard")
    title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=2)
    head = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=12, leading=16,
                          spaceBefore=14, spaceAfter=4)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=11.5, leading=17, alignment=TA_LEFT)
    lab = ParagraphStyle("l", fontName="Helvetica-Bold", fontSize=10, leading=14, spaceBefore=8)

    story = [Paragraph(TITLE, title), Spacer(1, 4)]
    most = max(len(t) for _, t in lines)
    for n in range(most):
        story.append(Paragraph(f"Take {n + 1}, full script", head))
        for _, t in lines:
            # a line with only one take is said the same way in every pass
            story.append(Paragraph(t[n] if n < len(t) else t[-1], body))

    story.append(Paragraph("Line by line", head))
    for i, (line, t) in enumerate(lines, 1):
        # renumber so a removed line does not leave a gap
        name = line["label"].split(" · ", 1)[-1]
        story.append(Paragraph(f"{i} · {name}", lab))
        for n, text in enumerate(t, 1):
            story.append(Paragraph(f"Take {n}: {text}", body))

    # hooks go last and stay one line each, the detail lives on the QC page
    hooks = data.get("visual_hooks") or []
    if hooks:
        story.append(Paragraph("Visual hooks", head))
        for i, h in enumerate(hooks, 1):
            story.append(Paragraph(f"{i} \u00b7 {h['name']}", lab))
            story.append(Paragraph(h.get("brief") or h["how"], body))

    doc.build(story)
    dl = os.path.expanduser("~/Downloads/carnival-talking-head-script.pdf")
    shutil.copyfile(out, dl)
    print(f"built {out}")
    print(f"copied {dl}")
    print(f"  {len(lines)} lines, {sum(len(t) for _, t in lines)} takes")
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/Users/paulventura/TDG/merchants-yard"
    week = sys.argv[2] if len(sys.argv) > 2 else "2026-08-24"
    build(root, week)
