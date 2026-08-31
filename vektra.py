#!/usr/bin/env python3
"""VEKTRA — a minimal geometric sci-fi typeface built from lines, angles, arcs and triangles.

Each glyph is a skeleton (polylines + arcs). Skeletons are buffered by half the
stroke weight with mitre joins and flat caps, unioned, and emitted as TrueType
contours.
"""
import math, json
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

UPM   = 1000
CAP   = 700
XH    = 480
ASC   = 720
DESC  = -200
W     = 60          # stroke weight
SW    = W / 2.0
SIDE  = 58          # side bearing

def arc(cx, cy, r, a0, a1, step=7.0):
    """Sampled arc, angles in degrees, y-up."""
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

def tri(pts):
    return list(pts) + [pts[0]]

# ---------------------------------------------------------------- glyph skeletons
G = {}

# ---- UPPERCASE  (width 560, cap 700) -------------------------------------------
G['A'] = [[(0,0),(280,700),(560,0)], [(112,280),(448,280)]]
G['B'] = [[(0,0),(0,700)],
          [(0,700),(360,700)] + arc(360,560,140,90,-90) + [(0,420)],
          [(0,420),(350,420)] + arc(350,210,210,90,-90) + [(0,0)]]
G['C'] = [arc(280,490,280,180,50) , [(0,490),(0,210)], arc(280,210,280,180,310)]
G['D'] = [[(0,0),(0,700)], [(0,700),(280,700)], arc(280,420,280,90,0),
          [(560,420),(560,280)], arc(280,280,280,0,-90), [(280,0),(0,0)]]
G['E'] = [[(560,700),(130,700),(0,570),(0,130),(130,0),(560,0)], [(0,350),(390,350)]]
G['F'] = [[(560,700),(130,700),(0,570),(0,0)], [(0,380),(380,380)]]
G['G'] = [arc(280,490,280,180,50), [(0,490),(0,210)], arc(280,210,280,180,360),
          [(560,210),(560,350),(300,350)]]
G['H'] = [[(0,0),(0,700)], [(560,0),(560,700)], [(0,350),(560,350)]]
G['I'] = [[(0,0),(0,700)]]
G['J'] = [[(560,700),(560,200)], arc(360,200,200,0,-180)]
G['K'] = [[(0,0),(0,700)], [(560,700),(0,290)], [(196,405),(560,0)]]
G['L'] = [[(0,700),(0,130),(130,0),(520,0)]]
G['M'] = [[(0,0),(0,700),(280,360),(560,700),(560,0)]]
G['N'] = [[(0,0),(0,700),(560,0),(560,700)]]
G['O'] = [[(0,210),(0,490)], arc(280,490,280,180,0), [(560,490),(560,210)],
          arc(280,210,280,180,360)]
G['P'] = [[(0,0),(0,700)], [(0,700),(380,700)] + arc(380,525,175,90,-90) + [(0,350)]]
G['Q'] = G['O'] + [[(330,190),(600,-80)]]
G['R'] = [[(0,0),(0,700)], [(0,700),(380,700)] + arc(380,525,175,90,-90) + [(0,350)],
          [(300,350),(560,0)]]
G['S'] = [arc(280,525,175,20,270), arc(280,175,175,90,-160)]
G['T'] = [[(0,700),(560,700)], [(280,700),(280,0)]]
G['U'] = [[(0,700),(0,210)], arc(280,210,280,180,360), [(560,210),(560,700)]]
G['V'] = [[(0,700),(280,0),(560,700)]]
G['W'] = [[(0,700),(140,0),(280,430),(420,0),(560,700)]]
G['X'] = [[(0,700),(560,0)], [(0,0),(560,700)]]
G['Y'] = [[(0,700),(280,350),(560,700)], [(280,350),(280,0)]]
G['Z'] = [[(0,700),(560,700),(0,0),(560,0)]]

# ---- lowercase (width 480, x-height 480) ---------------------------------------
G['a'] = [arc(230,236,236,0,360), [(480,480),(480,0)]]
G['b'] = [[(0,720),(0,0)], arc(240,240,240,0,360)]
G['c'] = [arc(240,240,240,50,310)]
G['d'] = [[(480,720),(480,0)], arc(240,240,240,0,360)]
G['e'] = [[(0,250),(480,250)], arc(240,240,240,0,325)]
G['f'] = [arc(300,600,120,0,180), [(180,600),(180,0)], [(30,470),(390,470)]]
G['g'] = [arc(240,240,240,0,360), [(480,480),(480,-40)], arc(330,-40,150,0,-180)]
G['h'] = [[(0,720),(0,0)], arc(240,240,240,180,0), [(480,240),(480,0)]]
G['i'] = [[(240,0),(240,480)], tri([(160,560),(240,700),(320,560)])]
G['j'] = [[(300,0),(300,480)], arc(180,0,120,0,-180), tri([(220,560),(300,700),(380,560)])]
G['k'] = [[(0,720),(0,0)], [(460,480),(0,190)], [(150,262),(470,0)]]
G['l'] = [[(180,720),(180,110),(290,0),(400,0)]]
G['m'] = [[(0,0),(0,480)], arc(120,360,120,180,0), [(240,360),(240,0)],
          arc(360,360,120,180,0), [(480,360),(480,0)]]
G['n'] = [[(0,0),(0,480)], arc(240,240,240,180,0), [(480,240),(480,0)]]
G['o'] = [arc(240,240,240,0,360)]
G['p'] = [[(0,-200),(0,480)], arc(240,240,240,0,360)]
G['q'] = [[(480,-200),(480,480)], arc(240,240,240,0,360)]
G['r'] = [[(0,0),(0,480)], arc(240,240,240,180,55)]
G['s'] = [arc(240,350,130,20,270), arc(240,130,130,90,-160)]
G['t'] = [[(200,720),(200,120)], arc(320,120,120,180,270), [(30,470),(390,470)]]
G['u'] = [[(0,480),(0,240)], arc(240,240,240,180,360), [(480,240),(480,480)]]
G['v'] = [[(0,480),(240,0),(480,480)]]
G['w'] = [[(0,480),(120,0),(240,300),(360,0),(480,480)]]
G['x'] = [[(0,480),(480,0)], [(0,0),(480,480)]]
G['y'] = [[(0,480),(250,0)], [(480,480),(110,-200)]]
G['z'] = [[(0,480),(480,480),(0,0),(480,0)]]

# ---- digits --------------------------------------------------------------------
G['zero']  = G['O'] + [[(180,250),(380,450)]]
G['one']   = [[(90,540),(300,700),(300,0)]]
G['two']   = [arc(280,470,280,165,0), [(560,470),(40,0)], [(0,0),(560,0)]]
G['three'] = [arc(280,525,175,155,-90), arc(280,175,175,90,-155)]
G['four']  = [[(410,0),(410,700)], [(410,700),(0,230),(560,230)]]
G['five']  = [[(540,700),(110,700),(90,400),(300,400)], arc(300,200,200,90,-140)]
G['six']   = [arc(280,220,220,0,360), [(60,220),(60,470)], arc(280,470,220,180,55)]
G['seven'] = [[(0,700),(560,700),(180,0)], [(150,320),(430,320)]]
G['eight'] = [arc(280,520,180,0,360), arc(280,180,180,0,360)]
G['nine']  = [arc(280,480,220,0,360), [(500,480),(500,230)], arc(280,230,220,0,-125)]

# ---- punctuation ----------------------------------------------------------------
G['period']    = [tri([(0,0),(80,150),(160,0)])]
G['comma']     = [tri([(0,0),(80,150),(160,0)]), [(80,0),(0,-150)]]
G['colon']     = [tri([(0,0),(80,150),(160,0)]), tri([(0,400),(80,550),(160,400)])]
G['semicolon'] = [tri([(0,0),(80,150),(160,0)]), [(80,0),(0,-150)], tri([(0,400),(80,550),(160,400)])]
G['exclam']    = [[(80,700),(80,220)], tri([(0,0),(80,150),(160,0)])]
G['question']  = [arc(180,540,180,180,-60), [(180,300),(180,220)], tri([(100,0),(180,150),(260,0)])]
G['hyphen']    = [[(0,330),(320,330)]]
G['slash']     = [[(0,-60),(360,760)]]
G['parenleft'] = [arc(360,320,380,145,215)]
G['parenright']= [arc(0,320,380,35,-35)]
G['quotesingle']=[[(60,700),(0,470)]]
G['quotedbl']  = [[(60,700),(0,470)], [(280,700),(220,470)]]
G['endash']    = [[(0,330),(460,330)]]
G['emdash']    = [[(0,330),(700,330)]]
G['underscore']= [[(0,-120),(560,-120)]]
G['plus']      = [[(0,330),(400,330)], [(200,130),(200,530)]]
G['equal']     = [[(0,430),(400,430)], [(0,230),(400,230)]]

ORDER = (list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + list('abcdefghijklmnopqrstuvwxyz') +
         ['zero','one','two','three','four','five','six','seven','eight','nine',
          'period','comma','colon','semicolon','exclam','question','hyphen','slash',
          'parenleft','parenright','quotesingle','quotedbl',
          'endash','emdash','underscore','plus','equal'])

CHARMAP = {n: ord(n) for n in ORDER if len(n) == 1}
CHARMAP.update({'zero':48,'one':49,'two':50,'three':51,'four':52,'five':53,'six':54,
                'seven':55,'eight':56,'nine':57,'period':46,'comma':44,'colon':58,
                'semicolon':59,'exclam':33,'question':63,'hyphen':45,'slash':47,
                'parenleft':40,'parenright':41,'quotesingle':39,'quotedbl':34,
                'endash':0x2013,'emdash':0x2014,'underscore':95,'plus':43,'equal':61})

# ---------------------------------------------------------------- outline builder
def outline(strokes):
    lines = [LineString(s) for s in strokes if len(s) > 1]
    solid = unary_union([l.buffer(SW, cap_style=2, join_style=2, mitre_limit=4.0,
                                  resolution=8) for l in lines])
    if solid.geom_type == 'Polygon':
        polys = [solid]
    else:
        polys = [g for g in solid.geoms if g.geom_type == 'Polygon']
    return polys

def contours(polys, dx):
    out = []
    for p in polys:
        p = orient(p, -1.0)           # exterior clockwise (TrueType filled)
        rings = [p.exterior] + list(p.interiors)
        for i, r in enumerate(rings):
            pts = [(round(x + dx), round(y)) for x, y in r.coords[:-1]]
            # drop consecutive duplicates
            ded = [pts[0]]
            for q in pts[1:]:
                if q != ded[-1]:
                    ded.append(q)
            if len(ded) > 2:
                out.append(ded)
    return out

glyphs, widths, svgs = {}, {}, {}
pen_order = ['.notdef', 'space'] + ORDER

for name in ORDER:
    polys = outline(G[name])
    minx = min(p.bounds[0] for p in polys)
    maxx = max(p.bounds[2] for p in polys)
    dx = SIDE - minx
    pen = TTGlyphPen(None)
    for c in contours(polys, dx):
        pen.moveTo(c[0])
        for pt in c[1:]:
            pen.lineTo(pt)
        pen.closePath()
    glyphs[name] = pen.glyph()
    widths[name] = int(round(maxx - minx + 2 * SIDE))
    # svg path for the spec sheet
    d = []
    for c in contours(outline(G[name]), dx):
        d.append('M' + ' L'.join(f'{x},{y}' for x, y in c) + ' Z')
    svgs[name] = ' '.join(d)

for n in ('.notdef', 'space'):
    glyphs[n] = TTGlyphPen(None).glyph()
    widths[n] = 300

fb = FontBuilder(UPM, isTTF=True)
fb.setupGlyphOrder(pen_order)
cmap = {cp: n for n, cp in CHARMAP.items()}
cmap[32] = 'space'
fb.setupCharacterMap(cmap)
fb.setupGlyf(glyphs)
fb.setupHorizontalMetrics({g: (widths[g], 0) for g in pen_order})
fb.setupHorizontalHeader(ascent=ASC + 60, descent=DESC - 40, lineGap=0)
fb.setupNameTable({
    'familyName': 'Vektra',
    'styleName': 'Regular',
    'psName': 'Vektra-Regular',
    'copyright': 'Vektra — geometric sci-fi display face.',
    'designer': 'Built for RV',
    'version': 'Version 1.000',
})
fb.setupOS2(sTypoAscender=ASC, sTypoDescender=DESC, usWinAscent=ASC + 60,
            usWinDescent=abs(DESC) + 40, sxHeight=XH, sCapHeight=CAP,
            achVendID='RVKT', fsType=0)
fb.setupPost(isFixedPitch=0, italicAngle=0, underlinePosition=-120, underlineThickness=60)
fb.save('/home/claude/Vektra-Regular.ttf')

json.dump({'svgs': svgs, 'widths': widths}, open('/home/claude/glyphs.json', 'w'))
print('ok', len(ORDER), 'glyphs')
