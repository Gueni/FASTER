#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                     ____                 __
#?                    / __ \___  ____  ____/ /__  ________  _____
#?                   / /_/ / _ \/ __ \/ __  / _ \/ ___/ _ \/ ___/
#?                  / _, _/  __/ / / / /_/ /  __/ /  /  __/ /
#?                 /_/ |_|\___/_/ /_/\__,_/\___/_/   \___/_/
#?
#? Name:        renderer.py
#? Purpose:     Export an LTspice schematic (.asc) as an SVG image.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Draw an ``.asc`` schematic with the symbol graphics of the LTspice library.

LTspice has no command-line image export, so the schematic is drawn
directly from the file: wires, junctions, ground/net flags, symbols (from
their ``.asy`` files), instance names/values and SPICE directives. The
result is an SVG that matches the layout seen in LTspice.

    python -m Lib.schematic.renderer circuit.asc [out.svg]
"""

from __future__ import annotations

import html
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .asc_parser import _read_lines
from .symbols import Symbol, find_symbol, parse_shape_line, parse_text

#? style                                                                            
COLORS = {
    'background': '#ffffff',
    'wire'      : '#1e3a8a',
    'symbol'    : '#202020',
    'text'      : '#111111',
    'directive' : '#111111',
    'comment'   : '#1d4ed8',
    'flag'      : '#202020',
    'missing'   : '#b91c1c',
}
FONT_SIZES = (0.625, 1.0, 1.5, 2.0, 2.5, 3.5, 5.0, 7.0)    # LTspice text size index -> scale
FONT_BASE  = 13.0
MARGIN     = 40

# Window number -> symbol attribute
WINDOW_ATTRS = {0: 'InstName', 3: 'Value', 123: 'Value2', 38: 'SpiceModel', 39: 'SpiceLine', 40: 'SpiceLine2'}

# Orientation -> 2x2 matrix (x' = a*x + b*y, y' = c*x + d*y). LTspice: R90 maps (x, y) -> (-y, x).
ORIENTATIONS = {
    'R0'  : (1, 0, 0, 1),   'R90' : (0, -1, 1, 0),  'R180': (-1, 0, 0, -1), 'R270': (0, 1, -1, 0),
    'M0'  : (-1, 0, 0, 1),  'M90' : (0, 1, 1, 0),   'M180': (1, 0, 0, -1),  'M270': (0, -1, -1, 0),
}


#? -------------------------------------------------------------------------------
@dataclass
class Instance:
    symbol  : str
    x       : int
    y       : int
    orient  : str
    attrs   : dict[str, str] = field(default_factory=dict)
    windows : dict[int, tuple[int, int, str, int]] = field(default_factory=dict)


#? -------------------------------------------------------------------------------
class _Canvas:
    def __init__(self, colors: dict[str, str] | None = None):
        self.items: list[str] = []
        self.c       = {**COLORS, **(colors or {})}
        self.xmin    = self.ymin = math.inf
        self.xmax    = self.ymax = -math.inf
        self.viewbox = (0.0, 0.0, 100.0, 100.0)
        self._grp: list[float] | None = None      # bounding box of the shapes of the current part

    def _grow(self, x: float, y: float) -> None:
        self.xmin, self.xmax = min(self.xmin, x), max(self.xmax, x)
        self.ymin, self.ymax = min(self.ymin, y), max(self.ymax, y)

    def _shape(self, x: float, y: float) -> None:
        self._grow(x, y)
        g = self._grp
        if g is not None:
            g[0], g[1], g[2], g[3] = min(g[0], x), min(g[1], y), max(g[2], x), max(g[3], y)

    def begin_part(self) -> None:
        self._grp = [math.inf, math.inf, -math.inf, -math.inf]

    def end_part(self) -> tuple[float, float, float, float] | None:
        g, self._grp = self._grp, None
        return tuple(g) if g and g[0] != math.inf else None

    def line(self, x1, y1, x2, y2, color, width=2.0):
        self._shape(x1, y1); self._shape(x2, y2)
        self.items.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')

    def polygon(self, pts, color, width=2.0, fill='none', dash=False):
        for x, y in pts:
            self._shape(x, y)
        d     = ' '.join(f'{x},{y}' for x, y in pts)
        extra = ' stroke-dasharray="6 4"' if dash else ''
        self.items.append(f'<polygon points="{d}" stroke="{color}" stroke-width="{width}" fill="{fill}" stroke-linejoin="round"{extra}/>')

    def ellipse(self, cx, cy, rx, ry, color, width=2.0, fill='none'):
        self._shape(cx - rx, cy - ry); self._shape(cx + rx, cy + ry)
        self.items.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" stroke="{color}" stroke-width="{width}" fill="{fill}"/>')

    def path(self, d, color, width=2.0, bbox=()):
        for x, y in bbox:
            self._shape(x, y)
        self.items.append(f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round"/>')

    def text(self, x, y, s, size_idx=2, align='Left', vertical=False, color=None):
        if not s:
            return
        color  = color or self.c['text']
        fs     = FONT_BASE * FONT_SIZES[max(0, min(size_idx, len(FONT_SIZES) - 1))]
        lines  = s.split('\\n')
        anchor = {'start': 'start', 'end': 'end'}.get(align, 'middle')
        if align in ('start', 'end', 'middle'):
            perp = 'center'
        else:
            perp = align
        n = len(lines)
        # vertical offset (in reading frame) of the first baseline
        first  = {'center': -(n - 1) / 2 * 1.2 + 0.35, 'top': 0.9, 'bottom': -(n - 1) * 1.2 - 0.25}[perp]
        width  = max(len(l) for l in lines) * fs * 0.6
        height = n * fs * 1.2
        # bbox estimate
        ox      = {'start': 0, 'middle': -width / 2, 'end': -width}[anchor]
        oy      = {'center': -height / 2, 'top': 0, 'bottom': -height}[perp]
        corners = [(ox, oy), (ox + width, oy + height)]
        for cx, cy in corners:
            self._grow(x + cy, y - cx) if vertical else self._grow(x + cx, y + cy)
        rot = f' transform="rotate(-90 {x} {y})"' if vertical else ''
        tspans = ''.join(f'<tspan x="{x}" dy="{(first if i == 0 else 1.2):.3f}em">{html.escape(l)}</tspan>'
                         for i, l in enumerate(lines))
        self.items.append(f'<text x="{x}" y="{y}" font-size="{fs:.1f}" text-anchor="{anchor}" fill="{color}"{rot}>{tspans}</text>')

    def svg(self) -> str:
        if self.xmin == math.inf:
            self.xmin = self.ymin = 0
            self.xmax = self.ymax = 100
        x0, y0 = self.xmin - MARGIN, self.ymin - MARGIN
        w, h = self.xmax - self.xmin + 2 * MARGIN, self.ymax - self.ymin + 2 * MARGIN
        self.viewbox = (x0, y0, w, h)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" '
                f'width="{w:.0f}" height="{h:.0f}" font-family="Arial, Helvetica, sans-serif">'
                f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{self.c["background"]}"/>'
                + ''.join(self.items) + '</svg>')


#? text alignment                                                                     
_ALIGN = {  # LTspice alignment -> (vertical?, along-reading, perpendicular)
    'Left': (False, 'start', 'center'), 'Right': (False, 'end', 'center'), 'Center': (False, 'middle', 'center'),
    'Top': (False, 'middle', 'top'), 'Bottom': (False, 'middle', 'bottom'),
    'VLeft': (True, 'start', 'center'), 'VRight': (True, 'end', 'center'), 'VCenter': (True, 'middle', 'center'),
    'VTop': (True, 'middle', 'top'), 'VBottom': (True, 'middle', 'bottom'),
}


#? -------------------------------------------------------------------------------
def _oriented_align(align: str, m: tuple[int, int, int, int]) -> tuple[bool, str]:
    """Transform an alignment through a symbol orientation, keeping text readable."""
    vertical, along, perp = _ALIGN.get(align, _ALIGN['Left'])
    a, b, c, d = m
    u    = (0, -1) if vertical else (1, 0)          # reading direction
    nrm  = (-1, 0) if vertical else (0, -1)       # "up" side of the glyphs
    u2   = (a * u[0] + b * u[1], c * u[0] + d * u[1])
    n2   = (a * nrm[0] + b * nrm[1], c * nrm[0] + d * nrm[1])
    vert = u2[0] == 0
    cu, cn = ((0, -1), (-1, 0)) if vert else ((1, 0), (0, -1))
    if u2 != cu:
        along = {'start': 'end', 'end': 'start'}.get(along, along)
    if n2 != cn:
        perp = {'top': 'bottom', 'bottom': 'top'}.get(perp, perp)
    return vert, along if perp == 'center' else perp


#? -------------------------------------------------------------------------------
def _plain_align(align: str) -> tuple[bool, str]:
    vertical, along, perp = _ALIGN.get(align, _ALIGN['Left'])
    return vertical, along if perp == 'center' else perp


#? -------------------------------------------------------------------------------
#? drawing                                                                            
def _draw_symbol(cv: _Canvas, inst: Instance, sym: Symbol, pin_counter: Counter) -> tuple | None:
    """Draw one symbol instance; return the bounding box of its graphics."""
    m = ORIENTATIONS.get(inst.orient, ORIENTATIONS['R0'])
    a, b, c, d = m
    mirrored = (a * d - b * c) < 0

    def tf(x, y):
        return inst.x + a * x + b * y, inst.y + c * x + d * y

    col = cv.c['symbol']
    cv.begin_part()
    for x1, y1, x2, y2 in sym.lines:
        cv.line(*tf(x1, y1), *tf(x2, y2), col)
    for x1, y1, x2, y2 in sym.rects:
        cv.polygon([tf(x1, y1), tf(x2, y1), tf(x2, y2), tf(x1, y2)], col)
    for x1, y1, x2, y2 in sym.circles:
        (p1x, p1y), (p2x, p2y) = tf(x1, y1), tf(x2, y2)
        cv.ellipse((p1x + p2x) / 2, (p1y + p2y) / 2, abs(p2x - p1x) / 2, abs(p2y - p1y) / 2, col)
    for x1, y1, x2, y2, sx, sy, ex, ey in sym.arcs:
        (p1x, p1y), (p2x, p2y) = tf(x1, y1), tf(x2, y2)
        cx, cy = (p1x + p2x) / 2, (p1y + p2y) / 2
        rx, ry = abs(p2x - p1x) / 2, abs(p2y - p1y) / 2
        if rx == 0 or ry == 0:
            continue
        (sx, sy), (ex, ey) = tf(sx, sy), tf(ex, ey)
        ts = math.atan2(-(sy - cy) / ry, (sx - cx) / rx)
        te = math.atan2(-(ey - cy) / ry, (ex - cx) / rx)
        # LTspice arcs run counter-clockwise from start to end; a mirror reverses that
        span  = (ts - te) % (2 * math.pi) if mirrored else (te - ts) % (2 * math.pi)
        sweep = 1 if mirrored else 0
        large = 1 if span > math.pi else 0
        p0    = (cx + rx * math.cos(ts), cy - ry * math.sin(ts))
        p1    = (cx + rx * math.cos(te), cy - ry * math.sin(te))
        cv.path(f'M {p0[0]:.2f} {p0[1]:.2f} A {rx:.2f} {ry:.2f} 0 {large} {sweep} {p1[0]:.2f} {p1[1]:.2f}',
                col, bbox=[(cx - rx, cy - ry), (cx + rx, cy + ry)])
    for x, y, align, size, text in sym.texts:
        vert, al = _oriented_align(align, m)
        cv.text(*tf(x, y), text, size, al, vert)
    for px, py in sym.pins:
        pin_counter[tf(px, py)] += 1

    if not sym.found:   # unknown symbol: dashed box around its location
        cv.polygon([(inst.x - 24, inst.y - 8), (inst.x + 56, inst.y - 8), (inst.x + 56, inst.y + 104),
                    (inst.x - 24, inst.y + 104)], cv.c['missing'], dash=True)
        cv.text(inst.x + 16, inst.y + 48, inst.symbol.split('\\')[-1], 1, 'middle', color=cv.c['missing'])
    bbox = cv.end_part()

    # attribute windows: symbol defaults overridden by the schematic
    windows = {**sym.windows, **inst.windows}
    for num, (wx, wy, align, size) in windows.items():
        attr  = WINDOW_ATTRS.get(num)
        value = inst.attrs.get(attr) if attr else None
        if value is None and attr == 'Value':
            value = sym.attrs.get('Value')
        if not value or size == 0:
            continue
        vert, al = _oriented_align(align, m)
        cv.text(*tf(wx, wy), value, size, al, vert)
    return bbox


#? -------------------------------------------------------------------------------
def _draw_flag(cv: _Canvas, x: int, y: int, name: str) -> None:
    col = cv.c['flag']
    if name == '0':
        cv.polygon([(x - 16, y), (x + 16, y), (x, y + 16)], col)
    else:
        cv.text(x, y - 6, name, 2, 'bottom', color=cv.c['wire'])


#? -------------------------------------------------------------------------------
@dataclass
class Rendering:
    svg     : str
    viewbox : tuple[float, float, float, float]                 # x0, y0, width, height (schematic units)
    parts   : dict[str, tuple[float, float, float, float]]      # instance name -> x0, y0, x1, y1


#? -------------------------------------------------------------------------------
def render(asc_file: str | os.PathLike, text: str | None = None,
           colors: dict[str, str] | None = None) -> Rendering:
    """Render a schematic and return the SVG plus the position of every part.

    ``text`` renders unsaved content (symbols are still looked up next to ``asc_file``);
    ``colors`` overrides entries of :data:`COLORS` (e.g. a dark theme).
    """
    asc_file = Path(asc_file)
    sch_dir  = str(asc_file.parent)
    cv       = _Canvas(colors)
    wires, flags, texts, instances = [], [], [], []
    shapes = Symbol('schematic')       # free graphics drawn on the sheet
    current: Instance | None = None
    lines  = text.splitlines() if text is not None else _read_lines(asc_file)

    for raw in lines:
        line = raw.strip()
        keyword, _, rest = line.partition(' ')
        parts = rest.split()
        if keyword == 'SYMBOL' and len(parts) >= 3:
            current = Instance(parts[0], int(parts[1]), int(parts[2]), parts[3] if len(parts) > 3 else 'R0')
            instances.append(current)
            continue
        if keyword == 'SYMATTR' and current is not None:
            attr, _, value = rest.partition(' ')
            current.attrs[attr] = value
            continue
        if keyword == 'WINDOW' and current is not None and len(parts) >= 5:
            current.windows[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3], int(parts[4]))
            continue
        current = None
        if keyword == 'WIRE' and len(parts) >= 4:
            wires.append(tuple(int(p) for p in parts[:4]))
        elif keyword == 'FLAG' and len(parts) >= 3:
            flags.append((int(parts[0]), int(parts[1]), parts[2]))
        elif keyword == 'TEXT':
            t = parse_text(rest)
            if t:
                texts.append(t)
        elif keyword in ('LINE', 'RECTANGLE', 'CIRCLE', 'ARC'):
            parse_shape_line(keyword, parts, shapes)

    pins: Counter = Counter()
    parts: dict[str, tuple[float, float, float, float]] = {}
    for inst in instances:
        bbox = _draw_symbol(cv, inst, find_symbol(inst.symbol, sch_dir), pins)
        name = inst.attrs.get('InstName')
        if name and bbox:
            parts[name] = bbox
    _draw_symbol(cv, Instance('schematic', 0, 0, 'R0'), shapes, Counter())

    ends: Counter = Counter()
    for x1, y1, x2, y2 in wires:
        cv.line(x1, y1, x2, y2, cv.c['wire'], 2.5)
        ends[(x1, y1)] += 1
        ends[(x2, y2)] += 1
    for x, y, name in flags:
        _draw_flag(cv, x, y, name)
    for (x, y), n in ends.items():
        if n + pins.get((x, y), 0) >= 3:
            cv.ellipse(x, y, 5, 5, cv.c['wire'], 1, fill=cv.c['wire'])

    for x, y, align, size, txt in texts:
        vert, al = _plain_align(align)
        if txt.startswith('!'):
            cv.text(x, y, txt[1:], size, al, vert, cv.c['directive'])
        elif txt.startswith(';'):
            cv.text(x, y, txt[1:], size, al, vert, cv.c['comment'])
        else:
            cv.text(x, y, txt, size, al, vert, cv.c['comment'])

    svg = cv.svg()
    return Rendering(svg, cv.viewbox, parts)


#? -------------------------------------------------------------------------------
def render_schematic(asc_file: str | os.PathLike, out_file: str | os.PathLike | None = None,
                     colors: dict[str, str] | None = None) -> str:
    """Render ``asc_file`` to SVG text; also write it to ``out_file`` if given."""
    svg = render(asc_file, colors=colors).svg
    if out_file:
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        Path(out_file).write_text(svg, encoding='utf-8')
    return svg


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        sys.exit('usage: python -m Lib.schematic.renderer <file.asc> [out.svg]')
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix('.svg')
    render_schematic(src, dst)
    print(f'Schematic image written to {dst}')

#? -------------------------------------------------------------------------------
