#!/usr/bin/env python3
"""Smoke test for a built Vektra font. Exits non-zero on any failure.

Checks: Google Fonts Latin Core coverage, every printing glyph has ink, dotless i/j
substitution before top marks, mark attachment, kerning, and vertical metrics.
Usage: check_font.py fonts/ttf/Vektra-Regular.ttf
"""
import sys
import unicodedata

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
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
