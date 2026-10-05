# Design — Vektra

## 1. Introduction
Vektra is a minimalist geometric sci-fi typeface constructed from lines, angles, arcs, and triangles. Its technical philosophy is "Constructive Solid Geometry for Type": glyphs are described as polyline and arc skeletons, expanded into 2D polygon buffers with miter joins and flat caps, unioned via computational geometry, and compiled directly to TrueType.

## 2. Tech Stack
- **Language**: Python 3.10+
- **Computational Geometry**: `shapely` (geometric buffer operations, boolean polygon unions)
- **Font Generation**: `fontTools` (`FontBuilder`, `TTGlyphPen`)
- **Specimen**: HTML5, CSS3

## 3. Technical Architecture
- **Skeleton-to-Polygon Pipeline**: Each character is represented as a skeletal wireframe (polylines and sampled arc segments).
- **Geometric Buffering**: Wireframe lines are buffered using `shapely.geometry` with half the stroke weight (`SW = 30`), miter joins, and flat end-caps.
- **Unary Union**: Multi-stroke overlapping polygons are dissolved into single unified boundary contours via `shapely.ops.unary_union`.
- **TrueType Contour Emission**: Polygon exterior boundaries and holes are extracted, winding-corrected via `orient()`, and serialized to TTF glyph outlines via `TTGlyphPen`.

## 4. File Structure
```text
font-vektra/
├── vektra.py              # Computational geometry compiler and TTF synthesizer
├── Vektra-Regular.ttf     # Compiled TrueType font
└── vektra-specimen.html   # Interactive typography specimen and character map
```

## 5. Implementation Details
- **Grid Coordinates**: 1000 UPM grid, 700 Cap Height, 480 x-height, 720 Ascender, -200 Descender, 60-unit stroke weight, 58-unit sidebearing.
- **Arc Sampling**: Trigonometric approximation of circular and elliptical curves (`arc(cx, cy, r, a0, a1, step=7.0)`).
- **Glyph Coverage**: Full Latin uppercase, lowercase, figures (0-9), punctuation, and technical mathematical symbols.

## 6. Build & Run
- **Install Dependencies**: `pip install fonttools shapely`
- **Build Font**: `python3 vektra.py`
- **Preview**: Open `vektra-specimen.html` in any modern web browser.

## 7. Tooling & Dependencies
- `shapely`: C-based GEOS wrapper for robust 2D planar polygon buffering and unioning.
- `fontTools`: OpenType table builder for TrueType binary generation.

## 8. Security & Standards
- Strictly adheres to TrueType specification contour winding requirements (outer contours clockwise, inner cutouts counter-clockwise).
- Pure offline programmatic compilation with zero external network access.
