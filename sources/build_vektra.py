#!/usr/bin/env python3
"""
Vektra — a minimal geometric sci-fi typeface built from lines, angles, arcs and triangles.

Construction rules
  * Every glyph is a skeleton of straight lines and true circular arcs.
  * Skeletons are expanded into a single 60-unit monoline: flat caps, mitred joins
    (mitre limit 4, so apexes stay sharp), and exact concentric offsets for arcs, which
    are written as quadratic curves.
  * Dots are solid triangles: the period, the i and j dots, the umlaut and dot accents.
  * Capitals and figures stand 700 units tall; lowercase sits on a 480-unit x-height
    with 720-unit ascenders and 200-unit descenders.

Character set
  Google Fonts Latin Core (Western, Central, and Eastern European Latin, punctuation,
  currency symbols, combining marks with mark/mkmk attachment).

Build
  This script writes the UFO source in sources/ufo/Vektra-Regular.ufo; gftools builder
  compiles and hints it into fonts/ttf and fonts/webfonts. Run sources/build.sh to do both.
  Usage:  python3 sources/build_vektra.py [--ufo sources/ufo]
"""
import math
import os
import shutil
import unicodedata

import numpy as np
import pathops
from pathops import Path, PathOp
from fontTools.agl import UV2AGL
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen

# --------------------------------------------------------------------------------------
# Design constants (1000 UPM font-unit coordinate space)
# --------------------------------------------------------------------------------------
UPM = 1000
CAP = 700           # capital & figure height
XH = 480            # lowercase x-height
ASC = 720           # ascender height (b, d, f, h, k, l, t)
DESC = -200         # descender depth (g, j, p, q, y)
W = 60              # monoline stroke weight
W_MARK = 52         # accent stroke weight
SIDE = 58           # sidebearing
MITRE_LIMIT = 4.0   # mitre length / half-width above which a join is bevelled
ARC_STEP = 45.0     # degrees of arc per quadratic segment (aligned to the axes)
MIN_ARC_SEG = 30.0  # arcs whose 45-degree pieces would be shorter than this use 90-degree pieces

FAMILY = "Vektra"
VERSION = "2.000"
REPO_URL = "https://github.com/q78717/font-vektra"
COPYRIGHT = f"Copyright 2026 The Vektra Project Authors ({REPO_URL})"


def union(a, b):
    return pathops.op(a, b, PathOp.UNION)


def difference(a, b):
    return pathops.op(a, b, PathOp.DIFFERENCE)


def path_bounds(path):
    bp = BoundsPen(None)
    path.draw(bp)
    return bp.bounds


def signed_area(path):
    ap = AreaPen()
    path.draw(ap)
    return ap.value


# --------------------------------------------------------------------------------------
# Stroke engine: lines + true arcs -> monoline outlines
# --------------------------------------------------------------------------------------
class Arc:
    """Circular arc, angles in degrees (y-up); runs from a0 to a1 in that direction."""

    def __init__(self, cx, cy, r, a0, a1):
        self.cx, self.cy, self.r, self.a0, self.a1 = float(cx), float(cy), float(r), float(a0), float(a1)

    def at(self, a, r=None):
        r = self.r if r is None else r
        t = math.radians(a)
        return (self.cx + r * math.cos(t), self.cy + r * math.sin(t))

    @property
    def start(self):
        return self.at(self.a0)

    @property
    def end(self):
        return self.at(self.a1)

    @property
    def full(self):
        return abs(self.a1 - self.a0) >= 359.99

    def tangent(self, a):
        s = 1.0 if self.a1 > self.a0 else -1.0
        t = math.radians(a)
        return (-s * math.sin(t), s * math.cos(t))


A = Arc


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _unit(dx, dy):
    L = math.hypot(dx, dy) or 1e-9
    return (dx / L, dy / L)


def segments(nodes, closed=False):
    """Turn a list of points and Arcs into ('L', p0, p1) / ('A', arc) segments."""
    segs, cur, first = [], None, None
    for nd in nodes:
        if isinstance(nd, Arc):
            s = nd.start
            if cur is not None and _dist(cur, s) > 0.5:
                segs.append(("L", cur, s))
            segs.append(("A", nd))
            first = first or s
            cur = nd.end
        else:
            nd = (float(nd[0]), float(nd[1]))
            if cur is not None and _dist(cur, nd) > 0.5:
                segs.append(("L", cur, nd))
            first = first or nd
            cur = nd
    if closed and cur is not None and _dist(cur, first) > 0.5:
        segs.append(("L", cur, first))
    return segs


def seg_dirs(seg):
    """Unit tangent at the start and end of a segment, plus its end point."""
    if seg[0] == "L":
        d = _unit(seg[2][0] - seg[1][0], seg[2][1] - seg[1][1])
        return d, d, seg[2]
    arc = seg[1]
    return arc.tangent(arc.a0), arc.tangent(arc.a1), arc.end


def _arc_to(path, arc, r, a0, a1):
    """Append quadratic segments approximating the arc of radius r from a0 to a1.

    Splits fall on multiples of ARC_STEP measured from 0 degrees, so every arc gets
    on-curve points at its horizontal and vertical extremes (as Google Fonts expects).
    """
    sgn = 1.0 if a1 > a0 else -1.0
    # Tight arcs (the inner side of small hooks) would get pieces too short for
    # FontBakery's outline_short_segments; 90-degree pieces still keep the extremes.
    st = ARC_STEP if r * math.radians(ARC_STEP) >= MIN_ARC_SEG else 90.0
    cuts = [a0]
    k = math.floor(a0 / st) + 1 if sgn > 0 else math.ceil(a0 / st) - 1
    while (k * st - a1) * sgn < -0.5:
        if abs(k * st - a0) > 8 and abs(k * st - a1) > 8:   # no sliver pieces
            cuts.append(k * st)
        k += int(sgn)
    cuts.append(a1)
    for b0, b1 in zip(cuts[:-1], cuts[1:]):
        step = b1 - b0
        mid = (b0 + b1) / 2.0
        c = arc.at(mid, r / math.cos(math.radians(step / 2.0)))
        e = arc.at(b1, r)
        path.quadTo(c[0], c[1], e[0], e[1])


def circle_path(arc, r):
    p = Path()
    p.moveTo(*arc.at(0, r))
    _arc_to(p, arc, r, 0, 360)
    p.close()
    return p


def seg_shape(seg, h):
    if seg[0] == "L":
        (x0, y0), (x1, y1) = seg[1], seg[2]
        ux, uy = _unit(x1 - x0, y1 - y0)
        nx, ny = -uy * h, ux * h
        p = Path()
        p.moveTo(x0 + nx, y0 + ny)
        p.lineTo(x1 + nx, y1 + ny)
        p.lineTo(x1 - nx, y1 - ny)
        p.lineTo(x0 - nx, y0 - ny)
        p.close()
        return p
    arc = seg[1]
    if arc.full:
        outer = circle_path(arc, arc.r + h)
        return outer if arc.r - h <= 1 else difference(outer, circle_path(arc, arc.r - h))
    p = Path()
    p.moveTo(*arc.at(arc.a0, arc.r + h))
    _arc_to(p, arc, arc.r + h, arc.a0, arc.a1)
    if arc.r - h > 1:
        p.lineTo(*arc.at(arc.a1, arc.r - h))
        _arc_to(p, arc, arc.r - h, arc.a1, arc.a0)
    else:
        p.lineTo(arc.cx, arc.cy)
    p.close()
    return p


def join_shape(P, d0, d1, h):
    """Mitre (or bevel) wedge filling the outer gap where two segments meet at P."""
    cross = d0[0] * d1[1] - d0[1] * d1[0]
    dot = d0[0] * d1[0] + d0[1] * d1[1]
    turn = math.atan2(cross, dot)
    if abs(math.degrees(turn)) < 0.5:
        return None
    sgn = -1.0 if cross > 0 else 1.0          # outer side is right of a left turn
    n0 = (-d0[1] * sgn * h, d0[0] * sgn * h)
    n1 = (-d1[1] * sgn * h, d1[0] * sgn * h)
    a = (P[0] + n0[0], P[1] + n0[1])
    b = (P[0] + n1[0], P[1] + n1[1])
    p = Path()
    p.moveTo(*P)
    p.lineTo(*a)
    c = math.cos(turn / 2.0)
    if c > 1e-6 and 1.0 / c <= MITRE_LIMIT:
        bis = _unit(n0[0] + n1[0], n0[1] + n1[1])
        L = h / c
        p.lineTo(P[0] + bis[0] * L, P[1] + bis[1] * L)
    p.lineTo(*b)
    p.close()
    return p


def stroke_outline(nodes, w=W, closed=False):
    h = w / 2.0
    segs = segments(nodes, closed)
    out = Path()
    for s in segs:
        out = union(out, seg_shape(s, h))
    n = len(segs)
    joins = range(n) if closed else range(n - 1)
    for i in joins:
        if not closed and i == n - 1:
            break
        _, d_end, P = seg_dirs(segs[i])
        d_start, _, _ = seg_dirs(segs[(i + 1) % n])
        j = join_shape(P, d_end, d_start, h)
        if j is not None:
            out = union(out, j)
    return out


def _svg_nodes(nodes, closed):
    parts, cur = [], None
    for seg in segments(nodes, closed):
        if seg[0] == "L":
            p0, p1 = seg[1], seg[2]
            if cur is None or _dist(cur, p0) > 0.5:
                parts.append(f"M{p0[0]:.0f} {p0[1]:.0f}")
            parts.append(f"L{p1[0]:.0f} {p1[1]:.0f}")
            cur = p1
        else:
            arc = seg[1]
            s, e = arc.start, arc.end
            if cur is None or _dist(cur, s) > 0.5:
                parts.append(f"M{s[0]:.0f} {s[1]:.0f}")
            sweep = 1 if arc.a1 > arc.a0 else 0
            r = f"{arc.r:.0f}"
            if arc.full:
                m = arc.at(arc.a0 + 180)
                parts.append(f"A{r} {r} 0 0 {sweep} {m[0]:.0f} {m[1]:.0f}")
                parts.append(f"A{r} {r} 0 0 {sweep} {e[0]:.0f} {e[1]:.0f}")
            else:
                large = 1 if abs(arc.a1 - arc.a0) > 180 else 0
                parts.append(f"A{r} {r} 0 {large} {sweep} {e[0]:.0f} {e[1]:.0f}")
            cur = e
    if closed:
        parts.append("Z")
    return " ".join(parts)


# --------------------------------------------------------------------------------------
# Glyph construction kit
# --------------------------------------------------------------------------------------
class G:
    """Collects strokes and solid shapes in 1000-UPM space, with an optional transform.

    Transforms scale positions only: Vektra is monoline, so a scaled part keeps the
    stroke weight unless a weight is passed explicitly.
    """

    def __init__(self, k=1.0, sx=1, sy=1, ox=0.0, oy=0.0, w=W, skel=None, root=None):
        self.k, self.sx, self.sy, self.ox, self.oy, self.w = k, sx, sy, ox, oy, w
        self.root = root or self
        if root is None:
            self.paths = []
            self.skel = [] if skel is None else skel
            self.n_strokes = 0
            self.n_dots = 0

    # transforms ------------------------------------------------------------------
    def T(self, p):
        return (self.ox + self.sx * self.k * p[0], self.oy + self.sy * self.k * p[1])

    def TA(self, arc):
        cx, cy = self.T((arc.cx, arc.cy))
        a0, a1 = arc.a0, arc.a1
        if self.sx < 0:
            a0, a1 = 180 - a0, 180 - a1
        if self.sy < 0:
            a0, a1 = -a0, -a1
        return Arc(cx, cy, arc.r * self.k, a0, a1)

    def part(self, dx=0.0, dy=0.0, k_mul=1.0, sx=1, sy=1, w=None):
        """A child view: offset by (dx, dy), scaled by k_mul, mirrored by sx/sy (about its origin)."""
        return G(
            k=self.k * k_mul, sx=self.sx * sx, sy=self.sy * sy,
            ox=self.ox + self.sx * self.k * dx, oy=self.oy + self.sy * self.k * dy,
            w=self.w if w is None else w, root=self.root,
        )

    def rotated(self, cx, cy):
        """View rotated 180 degrees about (cx, cy)."""
        return self.part(2 * cx, 2 * cy, 1.0, -1, -1)

    # drawing ---------------------------------------------------------------------
    def stroke(self, nodes, closed=False, w=None):
        P = [self.TA(n) if isinstance(n, Arc) else self.T(n) for n in nodes]
        r = self.root
        r.paths.append(stroke_outline(P, self.w if w is None else w, closed))
        r.skel.append(_svg_nodes(P, closed))
        r.n_strokes += 1

    def line(self, p0, p1, w=None):
        self.stroke([p0, p1], w=w)

    def poly(self, pts, w=None):
        self.stroke(pts, w=w)

    def loop(self, pts, w=None):
        self.stroke(pts, closed=True, w=w)

    def circle(self, cx, cy, r, w=None):
        self.stroke([A(cx, cy, r, 0, 360)], w=w)

    def arc(self, cx, cy, r, a0, a1, w=None):
        self.stroke([A(cx, cy, r, a0, a1)], w=w)

    def fill(self, pts):
        P = [self.T(p) for p in pts]
        p = Path()
        p.moveTo(*P[0])
        for q in P[1:]:
            p.lineTo(*q)
        p.close()
        r = self.root
        r.paths.append(p)
        r.skel.append("M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in P) + " Z")
        r.n_dots += 1

    def tdot(self, cx, y0, s=1.0, down=False):
        """Vektra's dot: a solid triangle, 200 wide and 180 tall at s=1, apex up."""
        hw, ht = 100 * s, 180 * s
        if down:
            self.fill([(cx - hw, y0 + ht), (cx + hw, y0 + ht), (cx, y0)])
        else:
            self.fill([(cx - hw, y0), (cx, y0 + ht), (cx + hw, y0)])

    # output ----------------------------------------------------------------------
    def outline(self):
        out = Path()
        for p in self.root.paths:
            out = union(out, p)
        return pathops.simplify(out)

    def empty(self):
        return not self.root.paths


# --------------------------------------------------------------------------------------
# Glyph registry
# --------------------------------------------------------------------------------------
GLYPHS = {}   # name -> (codepoint, function)


def glyph(name, uni=None):
    def deco(f):
        GLYPHS[name] = (uni, f)
        return f
    return deco


# --------------------------------------------------------------------------------------
# Capitals (A–Z): width 560, cap height 700
# --------------------------------------------------------------------------------------
@glyph("A", 0x41)
def cap_A(g):
    g.poly([(0, 0), (280, 700), (560, 0)])
    g.line((112, 280), (448, 280))


@glyph("B", 0x42)
def cap_B(g):
    g.line((0, 0), (0, 700))
    g.stroke([(0, 700), (360, 700), A(360, 560, 140, 90, -90), (0, 420)])
    g.stroke([(0, 420), (350, 420), A(350, 210, 210, 90, -90), (0, 0)])


@glyph("C", 0x43)
def cap_C(g):
    g.stroke([A(280, 420, 280, 50, 180), (0, 280), A(280, 280, 280, 180, 310)])


@glyph("D", 0x44)
def cap_D(g):
    g.stroke([(0, 0), (0, 700), (280, 700), A(280, 420, 280, 90, 0), (560, 280),
              A(280, 280, 280, 0, -90)], closed=True)


@glyph("E", 0x45)
def cap_E(g):
    g.poly([(560, 700), (130, 700), (0, 570), (0, 130), (130, 0), (560, 0)])
    g.line((0, 350), (390, 350))


@glyph("F", 0x46)
def cap_F(g):
    g.poly([(560, 700), (130, 700), (0, 570), (0, 0)])
    g.line((0, 380), (380, 380))


@glyph("G", 0x47)
def cap_G(g):
    g.stroke([A(280, 420, 280, 50, 180), (0, 280), A(280, 280, 280, 180, 360), (560, 350), (300, 350)])


@glyph("H", 0x48)
def cap_H(g):
    g.line((0, 0), (0, 700))
    g.line((560, 0), (560, 700))
    g.line((0, 350), (560, 350))


@glyph("I", 0x49)
def cap_I(g):
    g.line((0, 0), (0, 700))


@glyph("J", 0x4A)
def cap_J(g):
    g.stroke([(560, 700), (560, 200), A(360, 200, 200, 0, -180)])


@glyph("K", 0x4B)
def cap_K(g):
    g.line((0, 0), (0, 700))
    g.line((560, 700), (0, 290))
    g.line((196, 405), (560, 0))


@glyph("L", 0x4C)
def cap_L(g):
    g.poly([(0, 700), (0, 130), (130, 0), (520, 0)])


@glyph("M", 0x4D)
def cap_M(g):
    g.poly([(0, 0), (0, 700), (280, 360), (560, 700), (560, 0)])


@glyph("N", 0x4E)
def cap_N(g):
    g.poly([(0, 0), (0, 700), (560, 0), (560, 700)])


def cap_O_ring(g, x0=0, x1=560, y0=0, y1=CAP):
    """Stadium: semicircular top and bottom joined by straight sides."""
    r = (x1 - x0) / 2.0
    cx = x0 + r
    g.stroke([(x0, y0 + r), (x0, y1 - r), A(cx, y1 - r, r, 180, 0), (x1, y0 + r),
              A(cx, y0 + r, r, 0, -180)], closed=True)


@glyph("O", 0x4F)
def cap_O(g):
    cap_O_ring(g)


@glyph("P", 0x50)
def cap_P(g):
    g.line((0, 0), (0, 700))
    g.stroke([(0, 700), (380, 700), A(380, 525, 175, 90, -90), (0, 350)])


@glyph("Q", 0x51)
def cap_Q(g):
    cap_O_ring(g)
    g.line((340, 170), (600, -90))


@glyph("R", 0x52)
def cap_R(g):
    cap_P(g)
    g.line((300, 350), (560, 0))


@glyph("S", 0x53)
def cap_S(g):
    g.stroke([A(280, 525, 175, 20, 270), A(280, 175, 175, 90, -160)])


@glyph("T", 0x54)
def cap_T(g):
    g.line((0, 700), (560, 700))
    g.line((280, 700), (280, 0))


@glyph("U", 0x55)
def cap_U(g):
    g.stroke([(0, 700), (0, 280), A(280, 280, 280, 180, 360), (560, 700)])


@glyph("V", 0x56)
def cap_V(g):
    g.poly([(0, 700), (280, 0), (560, 700)])


@glyph("W", 0x57)
def cap_W(g):
    g.poly([(0, 700), (140, 0), (280, 430), (420, 0), (560, 700)])


@glyph("X", 0x58)
def cap_X(g):
    g.line((0, 700), (560, 0))
    g.line((0, 0), (560, 700))


@glyph("Y", 0x59)
def cap_Y(g):
    g.poly([(0, 700), (280, 350), (560, 700)])
    g.line((280, 350), (280, 0))


@glyph("Z", 0x5A)
def cap_Z(g):
    g.poly([(0, 700), (560, 700), (0, 0), (560, 0)])


# --------------------------------------------------------------------------------------
# Lowercase (a–z): width 480, x-height 480
# --------------------------------------------------------------------------------------
@glyph("a", 0x61)
def lc_a(g):
    g.circle(230, 236, 236)
    g.line((480, 480), (480, 0))


@glyph("b", 0x62)
def lc_b(g):
    g.line((0, 720), (0, 0))
    g.circle(240, 240, 240)


@glyph("c", 0x63)
def lc_c(g):
    g.arc(240, 240, 240, 50, 310)


@glyph("d", 0x64)
def lc_d(g):
    g.line((480, 720), (480, 0))
    g.circle(240, 240, 240)


@glyph("e", 0x65)
def lc_e(g):
    # The bar's lower edge (270 - 30) lines up with the arc's flat end at y = 240,
    # so the right side has no step.
    g.line((0, 270), (480, 270))
    g.arc(240, 240, 240, 0, 325)


@glyph("f", 0x66)
def lc_f(g):
    g.stroke([A(300, 600, 120, 0, 180), (180, 0)])
    g.line((30, 470), (390, 470))


@glyph("g", 0x67)
def lc_g(g):
    g.circle(240, 240, 240)
    g.stroke([(480, 480), (480, -40), A(330, -40, 150, 0, -180)])


@glyph("h", 0x68)
def lc_h(g):
    g.line((0, 720), (0, 0))
    g.stroke([A(240, 240, 240, 180, 0), (480, 0)])


def dotlessi(g):
    g.line((240, 0), (240, 480))


def dotlessj(g):
    g.stroke([(300, 480), (300, 0), A(180, 0, 120, 0, -180)])


@glyph("i", 0x69)
def lc_i(g):
    dotlessi(g)
    g.tdot(240, 560)


@glyph("j", 0x6A)
def lc_j(g):
    dotlessj(g)
    g.tdot(300, 560)


@glyph("k", 0x6B)
def lc_k(g):
    g.line((0, 720), (0, 0))
    g.line((460, 480), (0, 190))
    g.line((150, 262), (470, 0))


@glyph("l", 0x6C)
def lc_l(g):
    g.poly([(180, 720), (180, 110), (290, 0), (400, 0)])


@glyph("m", 0x6D)
def lc_m(g):
    g.line((0, 0), (0, 480))
    g.stroke([A(120, 360, 120, 180, 0), (240, 0)])
    g.stroke([A(360, 360, 120, 180, 0), (480, 0)])


@glyph("n", 0x6E)
def lc_n(g):
    g.line((0, 0), (0, 480))
    g.stroke([A(240, 240, 240, 180, 0), (480, 0)])


@glyph("o", 0x6F)
def lc_o(g):
    g.circle(240, 240, 240)


@glyph("p", 0x70)
def lc_p(g):
    g.line((0, -200), (0, 480))
    g.circle(240, 240, 240)


@glyph("q", 0x71)
def lc_q(g):
    g.line((480, -200), (480, 480))
    g.circle(240, 240, 240)


@glyph("r", 0x72)
def lc_r(g):
    g.line((0, 0), (0, 480))
    g.arc(240, 240, 240, 180, 55)


@glyph("s", 0x73)
def lc_s(g):
    g.stroke([A(240, 350, 130, 20, 270), A(240, 130, 130, 90, -160)])


@glyph("t", 0x74)
def lc_t(g):
    g.stroke([(200, 720), (200, 120), A(320, 120, 120, 180, 270)])
    g.line((30, 470), (390, 470))


@glyph("u", 0x75)
def lc_u(g):
    g.stroke([(0, 480), (0, 240), A(240, 240, 240, 180, 360), (480, 480)])


@glyph("v", 0x76)
def lc_v(g):
    g.poly([(0, 480), (240, 0), (480, 480)])


@glyph("w", 0x77)
def lc_w(g):
    g.poly([(0, 480), (120, 0), (240, 300), (360, 0), (480, 480)])


@glyph("x", 0x78)
def lc_x(g):
    g.line((0, 480), (480, 0))
    g.line((0, 0), (480, 480))


@glyph("y", 0x79)
def lc_y(g):
    # The short arm stops on the long arm's centre line, so its flat cap sits inside
    # the long arm. Running it to (250, 0) left the cap corner poking out as a spur
    # with an off-baseline point at y = 2.
    s = 480 * 480 / (680 * 250 + 370 * 480)   # where the two centre lines cross
    g.line((0, 480), (480 - 370 * s, 480 - 680 * s))
    g.line((480, 480), (110, -200))


@glyph("z", 0x7A)
def lc_z(g):
    g.poly([(0, 480), (480, 480), (0, 0), (480, 0)])


# --------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------
@glyph("zero", 0x30)
def fig_zero(g):
    cap_O_ring(g)
    g.line((180, 250), (380, 450))


@glyph("one", 0x31)
def fig_one(g):
    g.poly([(90, 540), (300, 700), (300, 0)])


@glyph("two", 0x32)
def fig_two(g):
    g.stroke([A(280, 420, 280, 165, 0), (40, 0)])
    g.line((0, 0), (560, 0))


@glyph("three", 0x33)
def fig_three(g):
    g.stroke([A(280, 525, 175, 155, -90), A(280, 175, 175, 90, -155)])


@glyph("four", 0x34)
def fig_four(g):
    g.line((410, 0), (410, 700))
    g.poly([(410, 700), (0, 230), (560, 230)])


@glyph("five", 0x35)
def fig_five(g):
    g.stroke([(540, 700), (100, 700), (100, 400), (300, 400), A(300, 200, 200, 90, -140)])


@glyph("six", 0x36)
def fig_six(g):
    g.circle(280, 220, 220)
    g.stroke([(60, 220), (60, 470), A(280, 470, 220, 180, 55)])


@glyph("seven", 0x37)
def fig_seven(g):
    g.poly([(0, 700), (560, 700), (180, 0)])
    g.line((150, 320), (430, 320))


@glyph("eight", 0x38)
def fig_eight(g):
    g.circle(280, 520, 180)
    g.circle(280, 180, 180)


@glyph("nine", 0x39)
def fig_nine(g):
    g.circle(280, 480, 220)
    g.stroke([(500, 480), (500, 230), A(280, 230, 220, 0, -125)])


# --------------------------------------------------------------------------------------
# ASCII punctuation & symbols
# --------------------------------------------------------------------------------------
@glyph("space", 0x20)
def gl_space(g):
    pass


@glyph("exclam", 0x21)
def gl_exclam(g):
    g.line((100, 700), (100, 270))
    g.tdot(100, 0)


@glyph("quotedbl", 0x22)
def gl_quotedbl(g):
    g.line((60, 700), (0, 470))
    g.line((280, 700), (220, 470))


@glyph("numbersign", 0x23)
def gl_numbersign(g):
    g.line((150, 40), (230, 660))
    g.line((350, 40), (430, 660))
    g.line((40, 470), (540, 470))
    g.line((40, 230), (540, 230))


@glyph("dollar", 0x24)
def gl_dollar(g):
    cap_S(g)
    g.line((280, 800), (280, -100))


@glyph("percent", 0x25)
def gl_percent(g):
    g.circle(120, 570, 100)
    g.circle(440, 130, 100)
    g.line((40, 0), (520, 700))


@glyph("ampersand", 0x26)
def gl_ampersand(g):
    g.stroke([(560, 0), (166, 460), A(250, 560, 130, -130, -410), (75, 285),
              A(240, 190, 190, 150, 360), (440, 300)])


@glyph("quotesingle", 0x27)
def gl_quotesingle(g):
    g.line((60, 700), (0, 470))


@glyph("parenleft", 0x28)
def gl_parenleft(g):
    g.arc(600, 330, 600, 134, 226)


@glyph("parenright", 0x29)
def gl_parenright(g):
    g.arc(0, 330, 600, 46, -46)


@glyph("asterisk", 0x2A)
def gl_asterisk(g):
    for a in (90, 210, 330):
        t = math.radians(a)
        dx, dy = 150 * math.cos(t), 150 * math.sin(t)
        g.line((200 - dx, 530 - dy), (200 + dx, 530 + dy))


@glyph("plus", 0x2B)
def gl_plus(g):
    g.line((0, 330), (400, 330))
    g.line((200, 130), (200, 530))


@glyph("comma", 0x2C)
def gl_comma(g):
    g.tdot(100, 0)
    g.line((100, 40), (20, -170))


@glyph("hyphen", 0x2D)
def gl_hyphen(g):
    g.line((0, 330), (320, 330))


@glyph("period", 0x2E)
def gl_period(g):
    g.tdot(100, 0)


@glyph("slash", 0x2F)
def gl_slash(g):
    g.line((0, -60), (360, 760))


@glyph("colon", 0x3A)
def gl_colon(g):
    g.tdot(100, 0)
    g.tdot(100, 300)


@glyph("semicolon", 0x3B)
def gl_semicolon(g):
    gl_comma(g)
    g.tdot(100, 300)


@glyph("less", 0x3C)
def gl_less(g):
    g.poly([(400, 560), (0, 330), (400, 100)])


@glyph("equal", 0x3D)
def gl_equal(g):
    g.line((0, 430), (400, 430))
    g.line((0, 230), (400, 230))


@glyph("greater", 0x3E)
def gl_greater(g):
    g.poly([(0, 560), (400, 330), (0, 100)])


@glyph("question", 0x3F)
def gl_question(g):
    g.stroke([A(180, 540, 180, 180, -90), (180, 250)])
    g.tdot(180, 0)


@glyph("at", 0x40)
def gl_at(g):
    g.circle(300, 330, 120)
    g.stroke([(420, 450), (420, 270), A(480, 270, 60, 180, 360), (540, 330),
              A(300, 330, 240, 0, 300)])


@glyph("bracketleft", 0x5B)
def gl_bracketleft(g):
    g.poly([(200, 780), (0, 780), (0, -100), (200, -100)])


@glyph("backslash", 0x5C)
def gl_backslash(g):
    g.line((0, 760), (360, -60))


@glyph("bracketright", 0x5D)
def gl_bracketright(g):
    g.poly([(0, 780), (200, 780), (200, -100), (0, -100)])


@glyph("asciicircum", 0x5E)
def gl_asciicircum(g):
    g.poly([(0, 420), (160, 700), (320, 420)])


@glyph("underscore", 0x5F)
def gl_underscore(g):
    g.line((0, -120), (560, -120))


@glyph("braceleft", 0x7B)
def gl_braceleft(g):
    g.poly([(240, 780), (180, 780), (130, 730), (130, 390), (40, 340), (130, 290), (130, -50),
            (180, -100), (240, -100)])


@glyph("bar", 0x7C)
def gl_bar(g):
    g.line((0, 800), (0, -200))


@glyph("braceright", 0x7D)
def gl_braceright(g):
    gl_braceleft(g.part(280, 0, 1.0, sx=-1))


@glyph("asciitilde", 0x7E)
def gl_asciitilde(g):
    g.stroke([A(100, 330, 100, 180, 0), A(300, 330, 100, 180, 360)])


@glyph(".notdef")
def gl_notdef(g):
    g.loop([(0, 0), (440, 0), (440, 700), (0, 700)])
    g.line((0, 0), (440, 700))
    g.line((440, 0), (0, 700))


# --------------------------------------------------------------------------------------
# Combining marks & spacing accents (drawn around x = 0 from the attachment line up/down)
# --------------------------------------------------------------------------------------
LC_TOP = 560        # top-mark attachment line on x-height letters
CAP_TOP = 790       # ... on capitals and ascender letters
LC_BOT = 0          # bottom-mark attachment line
CAP_BOT = 0
TALL = 600          # glyphs taller than this get capital-height marks
MARK_CENTER = 0

MARKS = {}   # name -> dict(draw, kind, uni, spacing=(name, uni))


def mark(name, kind, uni=None, spacing=None):
    def deco(f):
        MARKS[name] = dict(draw=f, kind=kind, uni=uni, spacing=spacing)
        return f
    return deco


@mark("acutecomb", "top", 0x0301, ("acute", 0x00B4))
def m_acute(g):
    g.line((-45, 0), (55, 130))


@mark("gravecomb", "top", 0x0300, ("grave", 0x0060))
def m_grave(g):
    g.line((45, 0), (-55, 130))


@mark("circumflexcomb", "top", 0x0302, ("circumflex", 0x02C6))
def m_circumflex(g):
    g.poly([(-110, 0), (0, 115), (110, 0)])


@mark("caroncomb", "top", 0x030C, ("caron", 0x02C7))
def m_caron(g):
    g.poly([(-110, 125), (0, 10), (110, 125)])


@mark("tildecomb", "top", 0x0303, ("tilde", 0x02DC))
def m_tilde(g):
    g.stroke([A(-55, 65, 55, 180, 0), A(55, 65, 55, 180, 360)])


@mark("macroncomb", "top", 0x0304, ("macron", 0x00AF))
def m_macron(g):
    g.line((-120, 50), (120, 50))


@mark("brevecomb", "top", 0x0306, ("breve", 0x02D8))
def m_breve(g):
    g.arc(0, 125, 100, 180, 360)


@mark("dotaccentcomb", "top", 0x0307, ("dotaccent", 0x02D9))
def m_dot(g):
    g.tdot(0, 0, 0.62)


@mark("dieresiscomb", "top", 0x0308, ("dieresis", 0x00A8))
def m_dieresis(g):
    g.tdot(-95, 0, 0.62)
    g.tdot(95, 0, 0.62)


@mark("ringcomb", "top", 0x030A, ("ring", 0x02DA))
def m_ring(g):
    g.circle(0, 75, 60)


@mark("hungarumlautcomb", "top", 0x030B, ("hungarumlaut", 0x02DD))
def m_hungarumlaut(g):
    g.line((-115, 0), (-25, 130))
    g.line((25, 0), (115, 130))


@mark("commaturnedabovecomb", "top", 0x0312)
def m_commaturned(g):
    g.tdot(0, 0, 0.5, down=True)
    g.line((0, 80), (45, 180))


@mark("caroncomb.alt", "caronalt")
def m_caronalt(g):
    g.line((30, 130), (0, 0))


@mark("cedillacomb", "bottom", 0x0327, ("cedilla", 0x00B8))
def m_cedilla(g):
    g.stroke([(0, 20), (0, -50), A(0, -100, 50, 90, -150)])


@mark("commaaccentcomb", "bottom", 0x0326)
def m_commabelow(g):
    g.tdot(0, -150, 0.5)
    g.line((0, -140), (-45, -240))


@mark("ogonekcomb", "ogonek", 0x0328, ("ogonek", 0x02DB))
def m_ogonek(g):
    g.stroke([(0, 20), (0, -50), A(60, -50, 60, 180, 300)])


def mark_attach_y(kind):
    return {"top": LC_TOP, "caronalt": LC_TOP, "bottom": LC_BOT, "ogonek": LC_BOT}[kind]


def draw_mark(g, name, x, y):
    MARKS[name]["draw"](g.part(x, y, w=W_MARK))


def _register_marks():
    for name, m in MARKS.items():
        y = mark_attach_y(m["kind"])
        fn = (lambda nm, yy: (lambda g: draw_mark(g, nm, 0.0, yy)))(name, y)
        GLYPHS[name] = (m["uni"], fn)
        if m["spacing"]:
            sname, suni = m["spacing"]
            GLYPHS[sname] = (suni, fn)


# --------------------------------------------------------------------------------------
# Latin Core letters beyond A–Z
# --------------------------------------------------------------------------------------
glyph("dotlessi", 0x0131)(dotlessi)
glyph("dotlessj", 0x0237)(dotlessj)


@glyph("AE", 0x00C6)
def gl_AE(g):
    g.poly([(0, 0), (360, 700), (760, 700)])
    g.poly([(360, 700), (360, 0), (760, 0)])
    g.line((360, 350), (700, 350))
    g.line((130, 250), (360, 250))


@glyph("OE", 0x0152)
def gl_OE(g):
    g.stroke([(780, 700), (280, 700), A(280, 420, 280, 90, 180), (0, 280),
              A(280, 280, 280, 180, 270), (780, 0)])
    g.line((500, 700), (500, 0))
    g.line((500, 350), (720, 350))


@glyph("ae", 0x00E6)
def gl_ae(g):
    lc_a(g)
    lc_e(g.part(480, 0))


@glyph("oe", 0x0153)
def gl_oe(g):
    lc_o(g)
    lc_e(g.part(480, 0))


@glyph("Oslash", 0x00D8)
def gl_Oslash(g):
    cap_O(g)
    g.line((-20, -40), (580, 740))


@glyph("oslash", 0x00F8)
def gl_oslash(g):
    lc_o(g)
    g.line((-20, -40), (500, 520))


@glyph("Eth", 0x00D0)
def gl_Eth(g):
    cap_D(g.part(100, 0))
    g.line((0, 350), (260, 350))


@glyph("Dcroat", 0x0110)
def gl_Dcroat(g):
    gl_Eth(g)


@glyph("dcroat", 0x0111)
def gl_dcroat(g):
    lc_d(g)
    g.line((360, 620), (600, 620))


@glyph("eth", 0x00F0)
def gl_eth(g):
    lc_o(g)
    # The knee sits high enough that the diagonal clears the bowl instead of grazing
    # it, which would leave a thin sliver (FontBakery outline_jaggy_segments).
    g.poly([(480, 240), (480, 460), (300, 720)])
    g.line((280, 600), (500, 600))


@glyph("Hbar", 0x0126)
def gl_Hbar(g):
    cap_H(g.part(80, 0))
    g.line((0, 560), (720, 560))


@glyph("hbar", 0x0127)
def gl_hbar(g):
    lc_h(g.part(100, 0))
    g.line((0, 610), (280, 610))


@glyph("Lslash", 0x0141)
def gl_Lslash(g):
    cap_L(g.part(100, 0))
    g.line((20, 250), (290, 450))


@glyph("lslash", 0x0142)
def gl_lslash(g):
    lc_l(g)
    g.line((60, 300), (320, 500))


@glyph("Thorn", 0x00DE)
def gl_Thorn(g):
    g.line((0, 0), (0, 700))
    g.stroke([(0, 560), (330, 560), A(330, 385, 175, 90, -90), (0, 210)])


@glyph("thorn", 0x00FE)
def gl_thorn(g):
    g.line((0, 720), (0, -200))
    g.circle(240, 240, 240)


@glyph("germandbls", 0x00DF)
def gl_germandbls(g):
    g.stroke([(0, 0), (0, 570), A(150, 570, 150, 180, -90)])
    g.stroke([(150, 420), (200, 420), A(200, 210, 210, 90, -90), (100, 0)])


@glyph("Germandbls", 0x1E9E)
def gl_Germandbls(g):
    g.stroke([(0, 0), (0, 520), A(180, 520, 180, 180, 0), (220, 400), (360, 400),
              A(360, 200, 200, 90, -90), (180, 0)])


@glyph("dottedCircle", 0x25CC)
def gl_dottedCircle(g):
    for i in range(12):
        t = math.radians(90 + i * 30)
        g.tdot(280 + 270 * math.cos(t), 330 + 270 * math.sin(t) - 30, 0.4)


# --------------------------------------------------------------------------------------
# Latin Core punctuation, currency & symbols
# --------------------------------------------------------------------------------------
@glyph("exclamdown", 0x00A1)
def gl_exclamdown(g):
    gl_exclam(g.rotated(100, 240))


@glyph("questiondown", 0x00BF)
def gl_questiondown(g):
    gl_question(g.rotated(180, 250))


@glyph("cent", 0x00A2)
def gl_cent(g):
    lc_c(g)
    g.line((240, -90), (240, 570))


@glyph("sterling", 0x00A3)
def gl_sterling(g):
    g.stroke([A(330, 550, 150, 15, 180), (180, 0)])
    g.line((40, 0), (520, 0))
    g.line((40, 330), (380, 330))


@glyph("yen", 0x00A5)
def gl_yen(g):
    cap_Y(g)
    g.line((100, 250), (460, 250))
    g.line((100, 120), (460, 120))


@glyph("Euro", 0x20AC)
def gl_Euro(g):
    cap_C(g.part(80, 0))
    g.line((0, 410), (380, 410))
    g.line((0, 290), (380, 290))


@glyph("rupeeIndian", 0x20B9)
def gl_rupeeIndian(g):
    g.line((0, 700), (500, 700))
    g.line((0, 540), (500, 540))
    g.stroke([(0, 700), (200, 700), A(200, 540, 160, 90, -90), (0, 380), (400, 0)])


SEPARATORS = {"uni2028": 0x2028, "uni2029": 0x2029}
for _n, _u in SEPARATORS.items():
    GLYPHS[_n] = (_u, lambda g: None)


def s_shape(g, cx, cy_top, r):
    g.stroke([A(cx, cy_top, r, 20, 270), A(cx, cy_top - 2 * r, r, 90, -160)])


@glyph("section", 0x00A7)
def gl_section(g):
    s_shape(g, 220, 590, 110)
    s_shape(g, 220, 370, 110)


@glyph("paragraph", 0x00B6)
def gl_paragraph(g):
    g.stroke([(420, 700), (160, 700), A(160, 540, 160, 90, 270), (300, 380)])
    g.line((300, 700), (300, -100))
    g.line((420, 700), (420, -100))


def _ringed(g, inner):
    g.circle(330, 350, 330)
    inner(g.part(204, 192, 0.45))


@glyph("copyright", 0x00A9)
def gl_copyright(g):
    _ringed(g, cap_C)


@glyph("registered", 0x00AE)
def gl_registered(g):
    _ringed(g, cap_R)


@glyph("trademark", 0x2122)
def gl_trademark(g):
    cap_T(g.part(0, 420, 0.4, w=44))
    cap_M(g.part(260, 420, 0.4, w=44))


@glyph("ordfeminine", 0x00AA)
def gl_ordfeminine(g):
    lc_a(g.part(0, 400, 0.5, w=48))
    g.line((0, 320), (250, 320), w=48)


@glyph("ordmasculine", 0x00BA)
def gl_ordmasculine(g):
    lc_o(g.part(0, 400, 0.5, w=48))
    g.line((0, 320), (240, 320), w=48)


@glyph("degree", 0x00B0)
def gl_degree(g):
    g.circle(100, 600, 100)


@glyph("periodcentered", 0x00B7)
def gl_periodcentered(g):
    g.tdot(100, 240)


@glyph("bullet", 0x2022)
def gl_bullet(g):
    g.tdot(175, 170, 1.75)


@glyph("ellipsis", 0x2026)
def gl_ellipsis(g):
    for x in (100, 360, 620):
        g.tdot(x, 0)


@glyph("endash", 0x2013)
def gl_endash(g):
    g.line((0, 330), (460, 330))


@glyph("emdash", 0x2014)
def gl_emdash(g):
    g.line((0, 330), (700, 330))


@glyph("minus", 0x2212)
def gl_minus(g):
    g.line((0, 330), (400, 330))


@glyph("multiply", 0x00D7)
def gl_multiply(g):
    g.line((50, 180), (350, 480))
    g.line((50, 480), (350, 180))


@glyph("divide", 0x00F7)
def gl_divide(g):
    g.line((0, 330), (400, 330))
    g.tdot(200, 430, 0.7)
    g.tdot(200, 104, 0.7, down=True)


def _quote(g, x, y, turned=False):
    """Curly quote: a comma lifted to cap height (turned 180 degrees for opening quotes)."""
    if turned:
        gl_comma(g.part(x, y).rotated(100, 5))
    else:
        gl_comma(g.part(x, y))


@glyph("quoteright", 0x2019)
def gl_quoteright(g):
    _quote(g, 0, 540)


@glyph("quoteleft", 0x2018)
def gl_quoteleft(g):
    _quote(g, 0, 540, turned=True)


@glyph("quotedblright", 0x201D)
def gl_quotedblright(g):
    _quote(g, 0, 540)
    _quote(g, 260, 540)


@glyph("quotedblleft", 0x201C)
def gl_quotedblleft(g):
    _quote(g, 0, 540, turned=True)
    _quote(g, 260, 540, turned=True)


@glyph("quotesinglbase", 0x201A)
def gl_quotesinglbase(g):
    _quote(g, 0, 0)


@glyph("quotedblbase", 0x201E)
def gl_quotedblbase(g):
    _quote(g, 0, 0)
    _quote(g, 260, 0)


@glyph("guilsinglleft", 0x2039)
def gl_guilsinglleft(g):
    g.poly([(170, 420), (0, 250), (170, 80)])


@glyph("guilsinglright", 0x203A)
def gl_guilsinglright(g):
    g.poly([(0, 420), (170, 250), (0, 80)])


@glyph("guillemetleft", 0x00AB)
def gl_guillemetleft(g):
    gl_guilsinglleft(g)
    gl_guilsinglleft(g.part(200, 0))


@glyph("guillemetright", 0x00BB)
def gl_guillemetright(g):
    gl_guilsinglright(g)
    gl_guilsinglright(g.part(200, 0))


# --------------------------------------------------------------------------------------
# Accented composites (Google Fonts Latin Core)
# --------------------------------------------------------------------------------------
TOP_X = {
    "dotlessi": 240, "dotlessj": 300, "l": 180, "L": 150, "t": 200, "J": 460,
    "I": 0, "a": 230,
}
BOTTOM_X = {"t": 260, "L": 260, "l": 290, "T": 280, "G": 280, "C": 280, "c": 240, "S": 280, "s": 240}
OGONEK_AT = {
    "A": (545, 0), "a": (480, 0), "E": (520, 0), "e": (330, 0),
    "I": (0, 0), "i": (240, 0), "dotlessi": (240, 0),
    "U": (380, 0), "u": (400, 20), "dottedCircle": (280, 60),
}
CARONALT_AT = {"d": (590, 590), "l": (290, 590), "t": (300, 590), "L": (140, 570)}

COMB = {
    0x0300: "gravecomb", 0x0301: "acutecomb", 0x0302: "circumflexcomb", 0x0303: "tildecomb",
    0x0304: "macroncomb", 0x0306: "brevecomb", 0x0307: "dotaccentcomb", 0x0308: "dieresiscomb",
    0x030A: "ringcomb", 0x030B: "hungarumlautcomb", 0x030C: "caroncomb", 0x0326: "commaaccentcomb",
    0x0327: "cedillacomb", 0x0328: "ogonekcomb",
}
COMMA_BELOW_LETTERS = set("GKLNRgklnr")
CARONALT_LETTERS = set("dltL")

COMPOSITES = {}
_ANCHOR_CACHE = {}


def base_bounds(base):
    if base not in _ANCHOR_CACHE:
        g = G()
        GLYPHS[base][1](g)
        _ANCHOR_CACHE[base] = path_bounds(g.outline())
    return _ANCHOR_CACHE[base]


def anchor(base, kind):
    x0, y0, x1, y1 = base_bounds(base)
    if kind == "top":
        return (TOP_X.get(base, (x0 + x1) / 2.0), CAP_TOP if y1 > TALL else LC_TOP)
    if kind == "bottom":
        return (BOTTOM_X.get(base, (x0 + x1) / 2.0), CAP_BOT if y1 > TALL else LC_BOT)
    if kind == "ogonek":
        return OGONEK_AT[base]
    if kind == "caronalt":
        return CARONALT_AT[base]
    raise KeyError(kind)


def glyph_name_for(cp):
    special = {
        0x0110: "Dcroat", 0x0111: "dcroat", 0x0122: "Gcommaaccent", 0x0123: "gcommaaccent",
        0x0136: "Kcommaaccent", 0x0137: "kcommaaccent", 0x013B: "Lcommaaccent",
        0x013C: "lcommaaccent", 0x0145: "Ncommaaccent", 0x0146: "ncommaaccent",
        0x0156: "Rcommaaccent", 0x0157: "rcommaaccent", 0x0218: "Scommaaccent",
        0x0219: "scommaaccent", 0x021A: "Tcommaaccent", 0x021B: "tcommaaccent",
        0x0130: "Idotaccent", 0x1E80: "Wgrave", 0x1E81: "wgrave", 0x1E82: "Wacute",
        0x1E83: "wacute", 0x1E84: "Wdieresis", 0x1E85: "wdieresis", 0x1EF2: "Ygrave",
        0x1EF3: "ygrave", 0x0150: "Ohungarumlaut", 0x0151: "ohungarumlaut",
        0x0170: "Uhungarumlaut", 0x0171: "uhungarumlaut",
    }
    return special.get(cp) or UV2AGL.get(cp) or f"uni{cp:04X}"


LATIN_CORE_COMPOSITES = [
    0x00C0, 0x00C1, 0x00C2, 0x00C3, 0x00C4, 0x00C5, 0x00C7, 0x00C8, 0x00C9, 0x00CA, 0x00CB, 0x00CC,
    0x00CD, 0x00CE, 0x00CF, 0x00D1, 0x00D2, 0x00D3, 0x00D4, 0x00D5, 0x00D6, 0x00D9, 0x00DA, 0x00DB,
    0x00DC, 0x00DD, 0x00E0, 0x00E1, 0x00E2, 0x00E3, 0x00E4, 0x00E5, 0x00E7, 0x00E8, 0x00E9, 0x00EA,
    0x00EB, 0x00EC, 0x00ED, 0x00EE, 0x00EF, 0x00F1, 0x00F2, 0x00F3, 0x00F4, 0x00F5, 0x00F6, 0x00F9,
    0x00FA, 0x00FB, 0x00FC, 0x00FD, 0x00FF, 0x0100, 0x0101, 0x0102, 0x0103, 0x0104, 0x0105, 0x0106,
    0x0107, 0x010A, 0x010B, 0x010C, 0x010D, 0x010E, 0x010F, 0x0112, 0x0113, 0x0116, 0x0117, 0x0118,
    0x0119, 0x011A, 0x011B, 0x011E, 0x011F, 0x0120, 0x0121, 0x0122, 0x0123, 0x012A, 0x012B, 0x012E,
    0x012F, 0x0130, 0x0136, 0x0137, 0x0139, 0x013A, 0x013B, 0x013C, 0x013D, 0x013E, 0x0143, 0x0144,
    0x0145, 0x0146, 0x0147, 0x0148, 0x0150, 0x0151, 0x0154, 0x0155, 0x0158, 0x0159, 0x015A, 0x015B,
    0x015E, 0x015F, 0x0160, 0x0161, 0x0164, 0x0165, 0x016A, 0x016B, 0x016E, 0x016F, 0x0170, 0x0171,
    0x0172, 0x0173, 0x0174, 0x0175, 0x0176, 0x0177, 0x0178, 0x0179, 0x017A, 0x017B, 0x017C, 0x017D,
    0x017E, 0x0218, 0x0219, 0x021A, 0x021B, 0x1E80, 0x1E81, 0x1E82, 0x1E83, 0x1E84, 0x1E85, 0x1EF2,
    0x1EF3,
]


def _add_composites():
    for cp in LATIN_CORE_COMPOSITES:
        dec = unicodedata.decomposition(chr(cp)).split()
        base_ch, marks = chr(int(dec[0], 16)), [int(m, 16) for m in dec[1:]]
        base = glyph_name_for(ord(base_ch))
        out = []
        for m in marks:
            mname = COMB[m]
            kind = MARKS[mname]["kind"]
            if m == 0x0327 and base_ch in COMMA_BELOW_LETTERS:
                if base_ch == "g":
                    mname, kind = "commaturnedabovecomb", "top"
                else:
                    mname, kind = "commaaccentcomb", "bottom"
            if m == 0x030C and base_ch in CARONALT_LETTERS:
                mname, kind = "caroncomb.alt", "caronalt"
            if kind == "top" and base_ch in "ij":
                base = "dotlessi" if base_ch == "i" else "dotlessj"
            out.append((mname, kind))
        COMPOSITES[glyph_name_for(cp)] = (cp, base, out)


def composite_fn(base, marks):
    def fn(g):
        GLYPHS[base][1](g)
        for mname, kind in marks:
            x, y = anchor(base, kind)
            draw_mark(g, mname, x, y)
    return fn


_register_marks()
_add_composites()
COMPOSITES["iogonek.dotless"] = (None, "dotlessi", [("ogonekcomb", "ogonek")])
for _n, (_cp, _b, _m) in COMPOSITES.items():
    GLYPHS[_n] = (_cp, composite_fn(_b, _m))


def ccmp_fea():
    tops = " ".join(n for n, m in MARKS.items() if m["uni"] and m["kind"] == "top")
    bottoms = " ".join(n for n, m in MARKS.items() if m["uni"] and m["kind"] in ("bottom", "ogonek"))
    return (
        f"@TOP_MARKS = [{tops}];\n"
        f"@BOTTOM_MARKS = [{bottoms}];\n"
        "lookup DOTLESS { sub i by dotlessi; sub j by dotlessj; sub iogonek by iogonek.dotless; } DOTLESS;\n"
        "feature ccmp {\n"
        "  sub [i j iogonek]' lookup DOTLESS @TOP_MARKS;\n"
        "  sub [i j iogonek]' lookup DOTLESS @BOTTOM_MARKS @TOP_MARKS;\n"
        "  sub [i j iogonek]' lookup DOTLESS @BOTTOM_MARKS @BOTTOM_MARKS @TOP_MARKS;\n"
        "} ccmp;\n"
    )


# --------------------------------------------------------------------------------------
# Spacing & auto-kerning
# --------------------------------------------------------------------------------------
PANOSE = [2, 11, 4, 3, 2, 2, 2, 2, 2, 4]   # sans, light, modern proportions
MATH_SIGNS = ["plus", "minus", "less", "equal", "greater", "asciitilde", "multiply", "divide"]
TIGHT_SIDE = {"period": 40, "comma": 40, "colon": 40, "semicolon": 40, "exclam": 40,
              "quotesingle": 40, "quotedbl": 40, "periodcentered": 40}

KERN_EXTRA = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "period", "comma", "colon", "semicolon", "hyphen", "endash", "emdash",
    "quotesingle", "quotedbl", "quoteleft", "quoteright", "quotedblleft", "quotedblright",
    "quotesinglbase", "quotedblbase", "guilsinglleft", "guilsinglright",
    "guillemetleft", "guillemetright", "parenleft", "parenright", "slash", "exclam",
    "question", "ampersand", "ellipsis",
]
KERN_ROWS_STEP = 8
KERN_WINDOW = 32
KERN_FACTOR = 0.72
KERN_MAX = 160
KERN_MIN = 12
KERN_TARGET = 2 * SIDE


def _flat_contours(path, dx):
    class FlatPen(BasePen):
        def __init__(self):
            super().__init__(None)
            self.contours, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            for i in range(1, 9):
                t = i / 8.0
                a_, b_, c_ = (1 - t) ** 2, 2 * (1 - t) * t, t * t
                self.cur.append((a_ * p0[0] + b_ * p1[0] + c_ * p2[0], a_ * p0[1] + b_ * p1[1] + c_ * p2[1]))

        def _closePath(self):
            self.contours.append(self.cur)
            self.cur = []

        _endPath = _closePath

    pen = FlatPen()
    path.draw(TransformPen(pen, (1, 0, 0, 1, dx, 0)))
    return pen.contours


def profile(path, dx, rows):
    L = np.full(rows.shape, np.inf)
    Rr = np.full(rows.shape, -np.inf)
    for c in _flat_contours(path, dx):
        if not c:
            continue
        pts = np.array(c + [c[0]], dtype=float)
        for xa, ya, xb, yb in zip(pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1]):
            lo, hi = min(ya, yb), max(ya, yb)
            m = (rows >= lo) & (rows <= hi)
            if not m.any():
                continue
            xs = xa if ya == yb else xa + (rows[m] - ya) * (xb - xa) / (yb - ya)
            L[m] = np.minimum(L[m], xs)
            Rr[m] = np.maximum(Rr[m], xs)
    k = KERN_WINDOW // KERN_ROWS_STEP
    Lw, Rw = L.copy(), Rr.copy()
    for s_ in range(1, k + 1):
        Lw[s_:] = np.minimum(Lw[s_:], L[:-s_])
        Lw[:-s_] = np.minimum(Lw[:-s_], L[s_:])
        Rw[s_:] = np.maximum(Rw[s_:], Rr[:-s_])
        Rw[:-s_] = np.maximum(Rw[:-s_], Rr[s_:])
    return Lw, Rw


def kern_groups(names):
    groups = {}
    for n in names:
        base = COMPOSITES[n][1] if n in COMPOSITES else n
        base = {"dotlessi": "i", "dotlessj": "j", "Dcroat": "Eth"}.get(base, base)
        groups.setdefault(base, []).append(n)
    return groups


def auto_kern(glyphs, names):
    """Kern each pair of groups so the closest approach of their profiles nears the
    default gap (two sidebearings). Profiles use the base letter's outline, so accents
    never push pairs apart."""
    rows = np.arange(-300, 950, KERN_ROWS_STEP, dtype=float)
    groups = kern_groups(names)
    prof = {}
    for gname, members in groups.items():
        gl = glyphs[members[0]] if gname not in glyphs else glyphs[gname]
        Lp, Rp = profile(gl["path"], gl["dx"], rows)
        prof[gname] = (Lp, Rp, gl["adv"])
    kerning = {}
    for ga, (_, Ra, adv) in prof.items():
        for gb, (Lb, _, _) in prof.items():
            m = np.isfinite(Ra) & np.isfinite(Lb)
            if not m.any():
                continue
            dmin = float(np.min(adv - Ra[m] + Lb[m]))
            kv = -int(round(min(KERN_MAX, KERN_FACTOR * (dmin - KERN_TARGET)) / 2.0) * 2)
            if kv > 0:
                continue          # only tighten; open pairs are left to the sidebearings
            if abs(kv) >= KERN_MIN:
                left = f"public.kern1.{ga}" if len(groups[ga]) > 1 else ga
                right = f"public.kern2.{gb}" if len(groups[gb]) > 1 else gb
                kerning[(left, right)] = kv
    plist = {}
    for gname, members in groups.items():
        if len(members) > 1:
            plist[f"public.kern1.{gname}"] = list(members)
            plist[f"public.kern2.{gname}"] = list(members)
    return plist, kerning


# --------------------------------------------------------------------------------------
# UFO assembly & cleanup
# --------------------------------------------------------------------------------------
def is_mark(name):
    return name in MARKS and MARKS[name]["uni"] is not None


def glyph_order():
    names = [n for n in GLYPHS if n not in (".notdef", "space")]
    return [".notdef", "space"] + names


def draw(name):
    """Return the G with the glyph drawn into it."""
    g = G()
    GLYPHS[name][1](g)
    return g


def _draw_glyph(name):
    g = draw(name)
    return Path() if g.empty() else g.outline()


def build_glyphs():
    out = {}
    for name in glyph_order():
        uni, _ = GLYPHS[name]
        path = Path() if name == "space" else _draw_glyph(name)
        b = path_bounds(path)
        if name in SEPARATORS:
            out[name] = dict(path=Path(), dx=0, adv=0, unicodes=[uni])
            continue
        if is_mark(name):
            dx, adv = -MARK_CENTER, 0
        elif b is None:
            dx, adv = 0, 300
        else:
            sb = TIGHT_SIDE.get(name, SIDE)
            dx = round(sb - b[0])
            adv = round(b[2] - b[0] + 2 * sb)
        out[name] = dict(path=path, dx=dx, adv=adv, unicodes=[uni] if uni is not None else [])
    out["space"]["unicodes"] = [0x20, 0xA0]
    for name, c in COMPOSITES.items():
        base = out[c[1]]
        g = out[name]
        g["dx"] = base["dx"]
        g["adv"] = base["adv"]
        b = path_bounds(g["path"])
        if b is not None:
            # widen the advance when a mark (e.g. the d/l/t caron) reaches past the base
            g["adv"] = max(g["adv"], round(b[2] + g["dx"] + SIDE / 2))
    signs = [n for n in MATH_SIGNS if n in out]
    adv = max(out[n]["adv"] for n in signs)
    for n in signs:
        b = path_bounds(out[n]["path"])
        out[n]["dx"] = round((adv - (b[2] - b[0])) / 2.0 - b[0])
        out[n]["adv"] = adv
    return out


TINY = 6.0
COLINEAR = 3.0
SNAP = 2
STUB = 30.0        # quadratic pieces shorter than this are merged into a smooth neighbour
STUB_TOL = 1.0     # ...if the merged curve stays within this many units of the original


def _colinear(a, b, c):
    """True when b sits on (or within a unit of) the straight line from a to c."""
    t1 = math.atan2(b[1] - a[1], b[0] - a[0])
    t2 = math.atan2(c[1] - b[1], c[0] - b[0])
    turn = abs((math.degrees(t2 - t1) + 180) % 360 - 180)
    if turn < COLINEAR:
        return True
    L = math.hypot(c[0] - a[0], c[1] - a[1])
    if L < 1e-6 or turn > 90:
        return False
    off = abs((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / L
    return off < 1.0


def _clean_contours(path, dx):
    rp = RecordingPen()
    path.draw(TransformPen(rp, (1, 0, 0, 1, dx, 0)))

    def rnd(pt):
        return None if pt is None else (round(pt[0]), round(pt[1]))

    def dist(p0, p1):
        return math.hypot(p0[0] - p1[0], p0[1] - p1[1])

    contours, cur = [], None
    for op, pts in rp.value:
        if op == "moveTo":
            cur = [rnd(pts[0]), []]
        elif op in ("lineTo", "qCurveTo"):
            if cur is None:
                cur = [None, []]
            cur[1].append((op, [rnd(q) for q in pts]))
        elif op in ("closePath", "endPath"):
            contours.append(cur)
            cur = None

    out = []
    for start, segs in contours:
        if start is None:
            out.append((None, segs))
            continue
        cleaned, here = [], start
        for op, pts in segs:
            end = pts[-1]
            if end is not None and all(q is None or dist(q, here) < TINY for q in pts):
                continue
            if op == "lineTo":
                ex, ey = end
                if 0 < abs(ex - here[0]) <= SNAP and abs(ey - here[1]) > 10:
                    pts = [(here[0], ey)]
                elif 0 < abs(ey - here[1]) <= SNAP and abs(ex - here[0]) > 10:
                    pts = [(ex, here[1])]
                end = pts[-1]
            cleaned.append([op, pts, here])
            here = end if end is not None else here
        while cleaned and cleaned[-1][0] == "lineTo" and dist(cleaned[-1][1][-1], start) < TINY:
            cleaned.pop()
        merged = []
        for seg in cleaned:
            if merged and seg[0] == "lineTo" and merged[-1][0] == "lineTo":
                a_, b_, c_ = merged[-1][2], merged[-1][1][-1], seg[1][-1]
                if _colinear(a_, b_, c_):
                    merged[-1][1] = [c_]
                    continue
            merged.append(seg)
        # the last point may sit on the implicit closing line back to the start
        while len(merged) >= 3 and merged[-1][0] == "lineTo" and _colinear(merged[-1][2], merged[-1][1][-1], start):
            merged.pop()
        # the start point itself may sit on a straight run (implicit closing line + first line)
        if len(merged) >= 3 and merged[0][0] == "lineTo" and merged[-1][1][-1] is not None:
            last, first_end = merged[-1][1][-1], merged[0][1][-1]
            if _colinear(last, start, first_end):
                start = first_end
                merged = merged[1:]
        segs = _merge_stubs(start, [(op, pts) for op, pts, _ in merged])
        if len(segs) >= 2:
            out.append((start, segs))
    return out


def _quad_pt(p0, c, p1, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0],
            u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1])


def _line_x(p, d, q, e):
    """Intersection of the lines p + s*d and q + t*e, as (point, s, t), or None."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    t = ((q[0] - p[0]) * d[1] - (q[1] - p[1]) * d[0]) / den
    return (p[0] + s * d[0], p[1] + s * d[1]), s, t


def _merge_stubs(start, segs):
    """Fold short quadratic stubs left by the boolean union into a smooth neighbour.

    Where two arcs cross just past a split point (the crotch of m, for example), the
    union leaves a few-unit quadratic piece. If it continues its neighbour smoothly,
    the pair is redrawn: as two equal pieces when both lie on one circle, otherwise as
    one quadratic through the outer tangents. The result must stay within STUB_TOL of
    the old pair.
    """
    if start is None:
        return segs
    # Expand to single pieces: ("L", end) or ("Q", ctrl, end, end_is_implied).
    q = []
    for op, pts in segs:
        if op == "lineTo":
            q.append(["L", None, pts[-1], False])
            continue
        offs, end = pts[:-1], pts[-1]
        if end is None:
            return segs
        for i, c in enumerate(offs):
            if i < len(offs) - 1:
                n = offs[i + 1]
                q.append(["Q", c, ((c[0] + n[0]) / 2.0, (c[1] + n[1]) / 2.0), True])
            else:
                q.append(["Q", c, end, False])

    def begin(i):
        return q[i - 1][2] if i > 0 else start

    def try_merge(i):
        """Merge pieces i and i + 1 (both quadratic) if that is safe."""
        a, b = q[i], q[i + 1]
        p0, p1, p2 = begin(i), a[2], b[2]
        d0 = (a[1][0] - p0[0], a[1][1] - p0[1])
        d1 = (b[1][0] - p2[0], b[1][1] - p2[1])
        t_in = math.atan2(p1[1] - a[1][1], p1[0] - a[1][0])
        t_out = math.atan2(b[1][1] - p1[1], b[1][0] - p1[0])
        if abs((math.degrees(t_out - t_in) + 180) % 360 - 180) > 6:   # not smooth
            return False
        hit = _line_x(p0, d0, p2, d1)
        if hit is None or hit[1] <= 0 or hit[2] <= 0:
            return False
        c = hit[0]
        # If both ends sit on one circle (tangent lines of equal length), re-split the
        # whole arc into two equal pieces instead of one wide quadratic.
        la, lb = math.dist(p0, c), math.dist(p2, c)
        pieces = [(c, p2)]
        if abs(la - lb) < 1.5 and math.dist(p0, p2) >= 2 * STUB:
            half = math.acos(max(-1.0, min(1.0, (d0[0] * -d1[0] + d0[1] * -d1[1]) /
                                           (math.hypot(*d0) * math.hypot(*d1))))) / 4.0
            r = (la + lb) / 2.0 / math.tan(2 * half)
            nrm = (-d0[1] / math.hypot(*d0), d0[0] / math.hypot(*d0))
            centre = None
            for sgn in (1, -1):
                o = (p0[0] + sgn * r * nrm[0], p0[1] + sgn * r * nrm[1])
                if abs(math.dist(o, p2) - r) < 1.5:
                    centre = o
            if centre is not None:
                a0 = math.atan2(p0[1] - centre[1], p0[0] - centre[0])
                a2 = math.atan2(p2[1] - centre[1], p2[0] - centre[0])
                da = (a2 - a0 + math.pi) % (2 * math.pi) - math.pi
                am = a0 + da / 2
                m = (centre[0] + r * math.cos(am), centre[1] + r * math.sin(am))
                k = r / math.cos(da / 4)
                c1 = (centre[0] + k * math.cos(a0 + da / 4), centre[1] + k * math.sin(a0 + da / 4))
                c2 = (centre[0] + k * math.cos(am + da / 4), centre[1] + k * math.sin(am + da / 4))
                pieces = [(c1, m), (c2, p2)]
        pieces = [((round(cc[0]), round(cc[1])), (round(e[0]), round(e[1]))) for cc, e in pieces]
        new, here = [], p0
        for cc, e in pieces:
            new += [_quad_pt(here, cc, e, k / 64.0) for k in range(65)]
            here = e
        old = [_quad_pt(p0, a[1], p1, k / 16.0) for k in range(17)] + \
              [_quad_pt(p1, b[1], p2, k / 16.0) for k in range(17)]
        if max(min(math.hypot(o[0] - n[0], o[1] - n[1]) for n in new) for o in old) > STUB_TOL:
            return False
        if i > 0 and q[i - 1][3]:
            q[i - 1][2] = (round(p0[0]), round(p0[1]))   # the start is no longer implied
            q[i - 1][3] = False
        q[i:i + 2] = [["Q", cc, e, False] for cc, e in pieces]
        return True

    changed = True
    while changed:
        changed = False
        for i, piece in enumerate(q):
            if piece[0] != "Q":
                continue
            p0 = begin(i)
            if math.hypot(piece[2][0] - p0[0], piece[2][1] - p0[1]) >= STUB:
                continue
            if (i > 0 and q[i - 1][0] == "Q" and try_merge(i - 1)) or \
               (i + 1 < len(q) and q[i + 1][0] == "Q" and try_merge(i)):
                changed = True
                break

    out, offs = [], []
    for kind, c, end, implied in q:
        if kind == "L":
            out.append(("lineTo", [end]))
            continue
        offs.append(c)
        if not implied:
            out.append(("qCurveTo", offs + [end]))
            offs = []
    if offs:   # an implied point cannot end the contour; keep the original segments
        return segs
    return out


def _draw_ufo_outline(glyph, path, dx):
    if path_bounds(path) is None:
        return
    pen = glyph.getPen()
    if signed_area(path) < 0:
        pen = ReverseContourPen(pen)
    for start, segs in _clean_contours(path, dx):
        if start is not None:
            pen.moveTo(start)
        for op, pts in segs:
            getattr(pen, op)(*pts)
        pen.closePath()


def vertical_metrics(glyphs):
    """Clear every glyph; keep the line height at least 1.2 em (Google Fonts guidance)."""
    ys = [path_bounds(g["path"]) for g in glyphs.values() if path_bounds(g["path"]) is not None]
    asc = int(math.ceil(max(b[3] for b in ys) / 10.0) * 10)
    desc = int(math.floor(min(b[1] for b in ys) / 10.0) * 10)
    if asc - desc < 1.2 * UPM:
        asc = int(1.2 * UPM) + desc
    return asc, desc


def production_name(name, unicodes):
    if not unicodes:
        return name
    cp = unicodes[0]
    if cp in UV2AGL:
        return UV2AGL[cp]
    return f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}"


def write_ufo(path_out):
    import ufoLib2
    from ufoLib2.objects import Anchor

    glyphs = build_glyphs()
    ufo = ufoLib2.Font()
    info = ufo.info
    info.familyName = FAMILY
    info.styleName = "Regular"
    info.styleMapFamilyName = FAMILY
    info.styleMapStyleName = "regular"
    major, minor = VERSION.split(".")
    info.versionMajor, info.versionMinor = int(major), int(minor)
    info.copyright = COPYRIGHT
    info.openTypeNameDesigner = "RV"
    info.openTypeNameManufacturer = "The Vektra Project Authors"
    info.openTypeNameManufacturerURL = REPO_URL
    info.openTypeNameLicense = (
        "This Font Software is licensed under the SIL Open Font License, "
        "Version 1.1. This license is available with a FAQ at: "
        "https://openfontlicense.org"
    )
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeNameDescription = (
        "Minimal geometric sci-fi display typeface built from monoline lines, arcs, "
        "sharp mitred angles, and triangular dots."
    )
    info.unitsPerEm = UPM
    asc, desc = vertical_metrics(glyphs)
    info.ascender, info.descender = asc, desc
    info.xHeight = XH
    info.capHeight = CAP
    info.openTypeHheaAscender, info.openTypeHheaDescender, info.openTypeHheaLineGap = asc, desc, 0
    info.openTypeOS2TypoAscender, info.openTypeOS2TypoDescender, info.openTypeOS2TypoLineGap = asc, desc, 0
    info.openTypeOS2WinAscent, info.openTypeOS2WinDescent = asc, -desc
    info.openTypeOS2Selection = [7, 8]
    info.openTypeOS2Type = []
    info.openTypeOS2VendorID = "RVKT"
    info.openTypeOS2WeightClass = 400
    info.openTypeOS2WidthClass = 5
    info.openTypeOS2Panose = PANOSE
    info.openTypeOS2StrikeoutSize = W
    info.openTypeOS2StrikeoutPosition = 330
    info.postscriptUnderlinePosition = -120
    info.postscriptUnderlineThickness = W
    info.postscriptIsFixedPitch = False
    info.postscriptFontName = f"{FAMILY}-Regular"

    order = list(glyphs)
    categories = {}
    for name in order:
        g = glyphs[name]
        gl = ufo.newGlyph(name)
        gl.width = g["adv"]
        gl.unicodes = g["unicodes"]
        comp = COMPOSITES.get(name)
        if comp:
            _, base, marks = comp
            pen = gl.getPen()
            pen.addComponent(base, (1, 0, 0, 1, 0, 0))
            for mname, kind in marks:
                ax, ay = anchor(base, kind)
                mx = ax + glyphs[base]["dx"] - glyphs[mname]["dx"]
                my = ay - mark_attach_y(kind)
                pen.addComponent(mname, (1, 0, 0, 1, round(mx), round(my)))
        elif name == "Dcroat":
            gl.getPen().addComponent("Eth", (1, 0, 0, 1, 0, 0))
        else:
            _draw_ufo_outline(gl, g["path"], g["dx"])
        if is_mark(name):
            categories[name] = "mark"
            kind = MARKS[name]["kind"]
            aname = {"top": "_top", "bottom": "_bottom", "ogonek": "_ogonek"}.get(kind)
            if aname:
                ay = mark_attach_y(kind)
                gl.anchors.append(Anchor(round(g["dx"]), round(ay), aname))
                b = path_bounds(g["path"])
                if kind == "top":
                    gl.anchors.append(Anchor(round(g["dx"]), round(b[3] + 40), "top"))
                elif kind == "bottom":
                    gl.anchors.append(Anchor(round(g["dx"]), round(b[1] - 30), "bottom"))
        elif g["unicodes"] or name in COMPOSITES:
            categories[name] = "base"

    bases = set(c[1] for c in COMPOSITES.values()) | set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghklmnopqrstuvwxyz")
    bases |= {"dotlessi", "dotlessj", "dottedCircle"}
    bases -= set(COMPOSITES)
    for base in sorted(bases):
        if base not in ufo:
            continue
        gl = ufo[base]
        dx = glyphs[base]["dx"]
        for kind, aname in (("top", "top"), ("bottom", "bottom")):
            ax, ay = anchor(base, kind)
            gl.anchors.append(Anchor(round(ax + dx), round(ay), aname))
        if base in OGONEK_AT:
            ax, ay = OGONEK_AT[base]
            gl.anchors.append(Anchor(round(ax + dx), round(ay), "ogonek"))

    ufo.lib["public.glyphOrder"] = order
    ufo.lib["public.openTypeMeta"] = {"dlng": ["Latn"], "slng": ["Latn"]}
    ufo.lib["com.github.googlei18n.ufo2ft.filters"] = [{"name": "propagateAnchors", "pre": True}]
    ufo.lib["public.openTypeCategories"] = categories
    ufo.lib["public.postscriptNames"] = {n: production_name(n, glyphs[n]["unicodes"]) for n in order}

    ufo.features.text = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n\n" + ccmp_fea()

    names = [
        n for n in order
        if n in glyphs and (
            (glyphs[n]["unicodes"] and unicodedata.category(chr(glyphs[n]["unicodes"][0])).startswith("L"))
            or n in KERN_EXTRA
        )
    ]
    groups, kerning = auto_kern(glyphs, names)
    ufo.groups.update(groups)
    ufo.kerning.update(kerning)

    if os.path.exists(path_out):
        shutil.rmtree(path_out)
    ufo.save(path_out)
    return path_out, len(order), len(ufo.kerning)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Write the Vektra UFO source.")
    ap.add_argument("--ufo", default="sources/ufo", help="folder for the .ufo source")
    args = ap.parse_args()
    os.makedirs(args.ufo, exist_ok=True)
    p, n, nk = write_ufo(os.path.join(args.ufo, f"{FAMILY}-Regular.ufo"))
    print(f"wrote {p}: {n} glyphs, {nk} kerning pairs")
