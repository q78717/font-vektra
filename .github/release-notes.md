**Vektra 2.000** is ready for Google Fonts.

**New**
- Full Google Fonts Latin Core character set: the Latin languages of Northern, Western, Central, and Eastern Europe, with curly quotes, guillemets, dashes, currency signs, and combining accents
- True circular arcs: curves are exact concentric offsets written as quadratic curves, replacing the faceted polyline approximation
- Solid triangular dots for punctuation, i/j, umlauts, and dot accents
- Class kerning measured from glyph profiles across all base and accented letters

**Fixed**
- Round capitals (C, G, O, Q, U) and the figures 0 and 2 no longer overshoot to 800/−100 units; they now match the flat capitals
- Parentheses now span the full cap and descender range, and the question mark's hook joins its stem
- Font names, copyright, vertical metrics, `.notdef`, `gasp`, `fsSelection`, and code pages meet the Google Fonts specification

**Under the hood**
- Built with Google's toolchain: `sources/build_vektra.py` writes the UFO source and `gftools builder` compiles and hints it
- FontBakery's Google Fonts profile passes with 0 FAILs

**What's in the zip**
- `ttf/`: `Vektra-Regular.ttf` for desktop apps
- `webfonts/`: `Vektra-Regular.woff2` for websites
- `Vektra-Specimen.html`: self-contained interactive specimen, works offline
- `OFL.txt`: SIL Open Font License 1.1
