**Vektra 2.100** cleans up outlines ahead of the Google Fonts submission.

**Changed**
- `e` (and `é è ê ë ě ę æ œ`): the crossbar sits 20 units higher, so its lower edge lines up with the arc's flat end and the small step on the right side is gone
- `ð`: the knee is higher, so the diagonal clears the bowl instead of leaving a thin sliver against it

**Fixed**
- `m`: the crotch between the arches no longer has tiny leftover curve pieces
- `@`, `˚`, `˜`, `¸`, `˛`, `§`: tight arcs are drawn with fewer, longer curve pieces (shape change of 3 units or less)
- FontBakery's Google Fonts profile reports no outline warnings (alignment, short segments, jaggy joins); 0 FAILs

**Under the hood**
- `sources/tools/check_font.py` now fails the build on off-zone points, short segments, and jaggy joins, using FontBakery's rules

**What's in the zip**
- `ttf/`: `Vektra-Regular.ttf` for desktop apps
- `webfonts/`: `Vektra-Regular.woff2` for websites
- `Vektra-Specimen.html`: self-contained interactive specimen, works offline
- `OFL.txt`: SIL Open Font License 1.1
