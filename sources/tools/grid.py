#!/usr/bin/env python3
"""Glyph grid proof: each glyph in a cell with cap-height, x-height and baseline guides."""
import sys
import freetype
from PIL import Image, ImageDraw

NAVY = (13, 27, 42)
OFF = (245, 243, 238)
RED = (215, 38, 56)
GUIDE = (213, 213, 211)


def grid(font, chars, out, px=96, cols=16, guides=True):
    face = freetype.Face(font)
    face.set_pixel_sizes(0, px)
    sc = px / face.units_per_EM
    cw = int(px * 1.15)
    ch = int(px * 1.40)
    rows = (len(chars) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw, rows * ch), OFF)
    d = ImageDraw.Draw(img)
    for i, c in enumerate(chars):
        gx, gy = (i % cols) * cw, (i // cols) * ch
        cx = gx + cw / 2
        base = gy + int(ch * 0.74)
        if guides:
            d.line([(gx + 6, base), (gx + cw - 6, base)], fill=(236, 182, 183))
            d.line([(gx + 6, base - 700 * sc), (gx + cw - 6, base - 700 * sc)], fill=GUIDE)
            d.line([(gx + 6, base - 480 * sc), (gx + cw - 6, base - 480 * sc)], fill=GUIDE)
        face.load_char(c, freetype.FT_LOAD_RENDER)
        g = face.glyph
        bm = g.bitmap
        adv = g.advance.x / 64
        ox = cx - adv / 2
        if bm.width and bm.rows:
            buf = bytes(bytearray(b for r_ in range(bm.rows) for b in bm.buffer[r_ * bm.pitch:r_ * bm.pitch + bm.width]))
            m = Image.frombytes("L", (bm.width, bm.rows), buf)
            img.paste(Image.new("RGB", m.size, NAVY), (int(ox + g.bitmap_left), int(base - g.bitmap_top)), m)
        lbl = c if ord(c) < 127 and c != " " else f"{ord(c):04X}"
        d.text((gx + 5, gy + 3), lbl, fill=RED)
    img.save(out)
    print(out)


if __name__ == "__main__":
    font, out = sys.argv[1], sys.argv[2]
    chars = sys.argv[3] if len(sys.argv) > 3 else None
    if chars is None:
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    grid(font, chars, out)
