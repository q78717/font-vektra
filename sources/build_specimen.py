#!/usr/bin/env python3
"""Build the self-contained specimen page (font and glyph construction data inlined).

Usage: python3 sources/build_specimen.py [--fonts fonts/webfonts] [--ttf fonts/ttf] [--out documentation/specimen/index.html]
"""
import argparse
import base64
import json
import os
import plistlib
import sys

from fontTools.pens.svgPathPen import SVGPathPen

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_vektra as B  # noqa: E402


def svg_outline(path):
    sp = SVGPathPen(None, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
    path.draw(sp)
    return sp.getCommands()


def glyph_data():
    out = []
    for name, (uni, _) in B.GLYPHS.items():
        if uni is None or name in ("space", "uni2028", "uni2029"):
            continue
        g = B.draw(name)
        if g.empty():
            continue
        path = g.outline()
        b = B.path_bounds(path)
        out.append(
            {
                "n": name,
                "c": chr(uni),
                "u": uni,
                "p": svg_outline(path),
                "s": " ".join(g.skel),
                "cx": round((b[0] + b[2]) / 2.0),
                "strokes": g.n_strokes,
                "dots": g.n_dots,
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="fonts/webfonts")
    ap.add_argument("--ttf", default="fonts/ttf")
    ap.add_argument("--template", default=os.path.join(HERE, "specimen_template.html"))
    ap.add_argument("--out", default="documentation/specimen/index.html")
    a = ap.parse_args()

    kplist = os.path.join(HERE, "ufo", f"{B.FAMILY}-Regular.ufo", "kerning.plist")
    with open(kplist, "rb") as fh:
        pairs = sum(len(v) for v in plistlib.load(fh).values())

    glist = glyph_data()
    meta = {"UPM": B.UPM, "CAP": B.CAP, "XH": B.XH, "W": B.W, "glyphs": len(glist), "kern": pairs}
    data = {"meta": meta, "glyphs": glist}

    t = open(a.template, encoding="utf-8").read()
    with open(os.path.join(a.fonts, f"{B.FAMILY}-Regular.woff2"), "rb") as fh:
        woff_b64 = base64.b64encode(fh.read()).decode()
    t = (
        t.replace("__FONT_REGULAR__", woff_b64)
        .replace("__GLYPH_DATA__", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
        .replace("__VERSION__", B.VERSION)
        .replace("__REPO__", B.REPO_URL)
        .replace("__KERN__", f"{pairs:,}")
        .replace("__CHARS__", str(meta["glyphs"]))
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(t)
    print(f"specimen -> {a.out} ({len(t):,} bytes, {len(glist)} glyphs, {pairs:,} kern pairs)")


if __name__ == "__main__":
    main()
