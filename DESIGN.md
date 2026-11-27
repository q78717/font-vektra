# Design — Vektra

## 1. Introduction
Vektra is a minimal geometric sci-fi display typeface built from lines, angles, arcs, and triangles. Its technical philosophy is **Constructive Solid Geometry for Type**. Each glyph is described as a skeleton of straight lines and true circular arcs. The skeleton is expanded into a monoline outline with flat caps and mitred joins, and the pieces are unioned with boolean path operations. The script writes a standard UFO source, which Google Fonts' `gftools builder` pipeline compiles.

## 2. Tech Stack
- **Language**: Python 3.10+
- **Outline Synthesis & Boolean Geometry**: `skia-pathops`, `fontTools`, `ufoLib2`, `numpy`
- **Font Compilation & Hinting**: `gftools builder`, `fontmake`, `ufo2ft`, `ttfautohint-py`
- **Quality Assurance**: `FontBakery` (`googlefonts` profile) / `fontspector`, `rvfont check-font` from [font-tools](https://github.com/q78717/font-tools)
- **License**: SIL Open Font License 1.1 (`OFL.txt`)

## 3. Technical Architecture
- **Skeletons**: Glyphs are lists of strokes. A stroke mixes points and `Arc(cx, cy, r, a0, a1)` nodes, and consecutive nodes are joined by straight segments.
- **Monoline Expansion** (`stroke_outline`): A line segment becomes a rectangle of width `W = 60` with flat caps. An arc becomes an annular sector, made from concentric arcs at `r ± 30`, so offsets are exact. Arcs are written as quadratic curves split every 45°, aligned to the axes, which gives every curve on-curve points at its extremes. Tight arcs, whose 45° pieces would be shorter than `MIN_ARC_SEG = 30` units, are split every 90° instead.
- **Joins**: Where tangents change direction, a mitre wedge fills the outer gap. Wedges with a mitre ratio above `MITRE_LIMIT = 4` become bevels. Tangent line-to-arc joins need no wedge.
- **Triangular Dots** (`G.tdot`): The period, colon, `i`/`j` dots, dieresis, and dot accents are solid triangles, 200 × 180 units at full size.
- **Union & Cleanup**: Pieces are unioned with `skia-pathops`. Contours are then rounded, with tiny segments removed and colinear points merged, including across the contour start. Short quadratic stubs left where two arcs cross (the crotch of `m`) are folded into their smooth neighbour: re-split as two equal arc pieces when both lie on one circle, otherwise merged into one quadratic, and only when the result stays within 1 unit of the original.
- **Marks & Composites**: There are 16 combining marks with `_top`, `_bottom`, and `_ogonek` anchors. The 151 Latin Core composites are built as components. The `ccmp` feature swaps in dotless `i`/`j` before top marks, and `caroncomb.alt` serves `ď ľ ť Ľ`.
- **Profile-Based Class Kerning**: `auto_kern()` measures scanline profiles of base glyphs and tightens pairs toward a gap of two sidebearings (about 4,500 pairs). It only tightens pairs, never loosens them.

## 4. Repository Layout (Google Fonts Template)
```text
font-vektra/
├── .github/workflows/            # CI build/test, GitHub Pages specimen, Release packaging
├── AUTHORS.txt / CONTRIBUTORS.txt
├── DESIGN.md                     # This document
├── Makefile                      # help, venv, clean; build, test, qa, proof, images, update from font-tools (.rvfont.mk)
├── OFL.txt                       # SIL Open Font License 1.1
├── README.md
├── requirements.in / requirements.txt / requirements-qa.txt
├── documentation/
│   ├── article/                  # Google Fonts article & image
│   ├── images/                   # README images
│   └── specimen/index.html       # Self-contained interactive specimen
├── fonts/
│   ├── ttf/Vektra-Regular.ttf
│   └── webfonts/Vektra-Regular.woff2
└── sources/
    ├── build.sh                  # Single-command build pipeline
    ├── build_vektra.py           # Algorithmic UFO generator
    ├── build_specimen.py         # Specimen compiler
    ├── config.yaml               # gftools builder configuration
    ├── specimen_template.html
    ├── tools/                    # STAT builder, README image renderer
    └── ufo/Vektra-Regular.ufo    # Generated UFO source
```

## 5. Metrics
- 1000 UPM; cap height 700, x-height 480, ascender 720, descender −200.
- Stroke 60 (accents 52); sidebearings 58 (40 for the period, comma, colon, semicolon, exclam, and straight quotes).
- Line metrics are computed from the glyph bounds (currently 960 / −260) and kept at 1.2 em or more. `USE_TYPO_METRICS` is set.

## 6. Build & QA Verification
- **Build All Artifacts**: `make build` (or `./sources/build.sh`)
- **Regenerate Documentation Images**: `make images`
- **Google Fonts QA**: `make qa`. Both the `googlefonts` and `universal` profiles report 0 FAILs.
