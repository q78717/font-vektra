#!/usr/bin/env python3
"""Smoke test for a built Vektra font. Exits non-zero on any failure.

Checks: Google Fonts Latin Core coverage, every printing glyph has ink, on-curve
points near vertical zones, short and jaggy segments, dotless i/j
substitution before top marks, mark attachment, kerning, and vertical metrics.
Usage: check_font.py fonts/ttf/Vektra-Regular.ttf
"""
import math
import sys
import unicodedata

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.misc.bezierTools import calcQuadraticArcLength
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

FAILS = []


def check(ok, msg):
    if not ok:
        FAILS.append(msg)
        print("FAIL", msg)


def shape(font, text, features=None):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {})
    return [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos], buf.glyph_positions


def contour_segments(rec):
    """Split a decomposed recording into contours of ("L", p0, p1) / ("Q", p0, c, p1)."""
    contours, cur, here, start = [], [], None, None
    for op, args in rec:
        if op == "moveTo":
            here = start = args[0]
            cur = []
        elif op == "lineTo":
            cur.append(("L", here, args[0]))
            here = args[0]
        elif op == "qCurveTo":
            offs, end = list(args[:-1]), args[-1]
            if end is None:   # all off-curve contour
                end = ((offs[-1][0] + offs[0][0]) / 2, (offs[-1][1] + offs[0][1]) / 2)
                here = start = end
            for i, c in enumerate(offs):
                e = end if i == len(offs) - 1 else ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2)
                cur.append(("Q", here, c, e))
                here = e
        elif op in ("closePath", "endPath"):
            if here is not None and start is not None and here != start:
                cur.append(("L", here, start))
            if cur:
                contours.append(cur)
            cur, here = [], None
    return contours


def seg_length(s):
    if s[0] == "L":
        return math.dist(s[1], s[2])
    return calcQuadraticArcLength(s[1], s[2], s[3])


def outline_problems(rec):
    """Short and jaggy segments, as FontBakery's outline_short_segments and
    outline_jaggy_segments define them (0.6% of the contour length; joins under 0.25 rad)."""
    short, jaggy = [], []
    for segs in contour_segments(rec):
        total = sum(seg_length(s) for s in segs)
        prev_line = segs[-1][0] == "L"
        for s in segs:
            n = seg_length(s)
            if n < 1e-6 or ((n < 3 or n < 0.006 * total) and (prev_line or s[0] == "Q")):
                short.append(s[-1])
            prev_line = s[0] == "L"
        for prev, s in zip(segs[-1:] + segs[:-1], segs):
            a = prev[-1]
            b = prev[-2]                      # in-tangent, reversed: end -> previous point
            c = s[2]                          # out-tangent: start -> next point
            v_in = (b[0] - a[0], b[1] - a[1])
            v_out = (c[0] - a[0], c[1] - a[1])
            m = math.hypot(*v_in) * math.hypot(*v_out)
            if not m:
                continue
            cos = (v_in[0] * v_out[0] + v_in[1] * v_out[1]) / m
            if -1 <= cos <= 1 and 0 < math.acos(cos) <= 0.25:
                jaggy.append(a)
    return short, jaggy


def main(path):
    tt = TTFont(path)
    cmap = tt.getBestCmap()
    gs = tt.getGlyphSet()

    try:
        import glyphsets
        need = set(glyphsets.unicodes_per_glyphset("GF_Latin_Core"))
    except Exception as e:  # glyphsets is part of gftools; fall back to ASCII if missing
        print("note: glyphsets unavailable,", e)
        need = set(range(0x20, 0x7F))
    missing = sorted(cp for cp in need if cp not in cmap)
    check(not missing, "missing GF Latin Core: " + " ".join(f"U+{c:04X}" for c in missing))

    blank = []
    for cp, name in cmap.items():
        cat = unicodedata.category(chr(cp))
        if cat.startswith("Z") or cat == "Cc" or cp in (0x2028, 0x2029):
            continue
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        if bp.bounds is None:
            blank.append(f"U+{cp:04X}")
    check(not blank, "printing characters with no outline: " + " ".join(blank))

    # On-curve points within 2 units of a vertical zone are almost always merge debris.
    # Mirrors FontBakery's outline_alignment_miss: baseline, typo ascender/descender,
    # cap height, and x-height (lowercase letters only).
    os2 = tt["OS/2"]
    zones = (0, os2.sTypoAscender, os2.sTypoDescender, os2.sCapHeight)
    lower = {n for cp, n in cmap.items() if unicodedata.category(chr(cp)) == "Ll"}
    near_miss = []
    for name in sorted(set(cmap.values())):
        rp = DecomposingRecordingPen(gs)
        gs[name].draw(rp)
        lines = zones + ((os2.sxHeight,) if name in lower else ())
        for op, args in rp.value:
            if op in ("moveTo", "lineTo", "qCurveTo", "curveTo") and args and args[-1]:
                x, y = args[-1]
                if any(0 < abs(y - z) <= 2 for z in lines):
                    near_miss.append(f"{name}@({x:.0f},{y:.0f})")
    check(not near_miss, "on-curve points just off a vertical zone: " + " ".join(near_miss))

    short, jaggy = [], []
    for name in sorted(set(cmap.values())):
        rp = DecomposingRecordingPen(gs)
        gs[name].draw(rp)
        s, j = outline_problems(rp.value)
        short += [f"{name}@({p[0]:.0f},{p[1]:.0f})" for p in s]
        jaggy += [f"{name}@({p[0]:.0f},{p[1]:.0f})" for p in j]
    check(not short, "short segments: " + " ".join(short))
    check(not jaggy, "jaggy joins: " + " ".join(jaggy))

    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    # No precomposed forms exist for these, so HarfBuzz must use ccmp and mark attachment.
    names, _ = shape(font, "i" + chr(0x0303) + "j" + chr(0x0301))
    check(names[0] == "dotlessi" and names[2] in ("dotlessj", "uni0237"), f"ccmp dotless i/j: {names}")

    _, pos = shape(font, "x" + chr(0x0301))
    _, pos_cap = shape(font, "X" + chr(0x0301))
    check(len(pos) == 2 and len(pos_cap) == 2 and pos[1].y_offset == 0 and pos_cap[1].y_offset > 150,
          f"mark attachment: x+acute {[p.y_offset for p in pos]}, X+acute {[p.y_offset for p in pos_cap]}")

    for pair in ("AV", "To", "LT", "Yo"):
        _, kerned = shape(font, pair, {"kern": True})
        _, plain = shape(font, pair, {"kern": False})
        check(kerned[0].x_advance < plain[0].x_advance, f"no kerning for {pair}")

    hhea, os2 = tt["hhea"], tt["OS/2"]
    check(hhea.ascent - hhea.descent >= 1.2 * tt["head"].unitsPerEm, "line height below 1.2 em")
    check(os2.usWinAscent >= tt["head"].yMax and os2.usWinDescent >= -tt["head"].yMin,
          "usWin metrics clip glyphs")

    print("font checks ok" if not FAILS else f"{len(FAILS)} font check(s) failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "fonts/ttf/Vektra-Regular.ttf"))
