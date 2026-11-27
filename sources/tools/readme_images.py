#!/usr/bin/env python3
"""Render the README and article images in documentation/ from the built font (`make images`)."""
import os

from rvfont.grid import grid, printing_chars
from rvfont.palette import DENIM, RED
from rvfont.raster import line as _line
from rvfont.raster import save_rows

F = "fonts/ttf/Vektra-Regular.ttf"
OUT = "documentation/images"
ART_OUT = "documentation/article"


def line(font, text, px, **kw):
    return _line(font, text, px, asc=980, desc=280, **kw)


def main():
    save_rows(
        [
            line(F, "VEKTRA", 210, pad=36),
            line(F, "Geometric sci-fi display type from lines, arcs & triangles.", 52, pad=36),
            line(F, "Orbital Station 2049 · Vector Drive", 96, color=RED, pad=36),
        ],
        os.path.join(OUT, "vektra-banner.png"),
    )
    save_rows(
        [
            line(F, "AVWMN  ·  KXYZ  ·  O Q G C", 120, pad=28),
            line(F, "i j ! ? : ; . … ä ö ü ż", 96, color=DENIM, pad=28),
        ],
        os.path.join(OUT, "geometry.png"),
    )
    save_rows(
        [
            line(F, "Sølvløve fra Tromsø & Ålesund · Þór & Óðinn", 64, pad=28),
            line(F, "Žluťoučký kůň úpěl ďábelské ódy", 64, pad=28),
            line(F, "Zażółć gęślą jaźń · Árvíztűrő tükörfúrógép", 64, pad=28),
            line(F, "«Quotes» “curly” — £12 €34 ¥56 ₹78 © ® ™", 64, pad=28),
        ],
        os.path.join(OUT, "languages.png"),
    )
    save_rows(
        [
            line(F, "Vektra", 170, pad=30),
            line(F, "Geometric sci-fi display · Ærøskøbing · Žluťoučký", 56, pad=30),
            line(F, "Orbital Station 2049", 92, color=RED, pad=30),
        ],
        os.path.join(ART_OUT, "vektra-article.png"),
    )
    grid(F, printing_chars(F), os.path.join(OUT, "glyphs.png"), px=88, cols=20, guides=(700, 480))


if __name__ == "__main__":
    main()
