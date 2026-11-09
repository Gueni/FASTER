#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                       __  ___          __     __
#?                      /  |/  /___  ____/ /__  / /
#?                     / /|_/ / __ \/ __  / _ \/ /
#?                    / /  / / /_/ / /_/ /  __/ /
#?                   /_/  /_/\____/\__,_/\___/_/
#?
#? Name:        model.py
#? Purpose:     Editable object model of an LTspice schematic (.asc) with connectivity.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Editable schematic model.

:class:`Schematic` parses every line of an ``.asc`` file into objects (wires,
flags, parts, texts, shapes). Lines it does not understand are kept verbatim,
so ``Schematic.parse(text).to_text()`` round-trips any LTspice file.

Geometry follows LTspice: integer coordinates, y pointing down, a 16 unit
grid, and the eight orientations ``R0..R270`` / ``M0..M270``.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .symbols import Symbol, find_symbol

GRID = 16

#: Orientation -> 2x2 matrix (x' = a*x + b*y, y' = c*x + d*y). LTspice R90 maps (x, y) -> (-y, x);
#: Mn rotates by n first, then mirrors x (M90 = M0 * R90).
ORIENTATIONS = {
    'R0'  : (1, 0, 0, 1),   'R90' : (0, -1, 1, 0),  'R180': (-1, 0, 0, -1), 'R270': (0, 1, -1, 0),
    'M0'  : (-1, 0, 0, 1),  'M90' : (0, 1, 1, 0),   'M180': (1, 0, 0, -1),  'M270': (0, -1, -1, 0),
}
_MATRIX_TO_ORIENT = {m: o for o, m in ORIENTATIONS.items()}
_ROT90  = (0, -1, 1, 0)
_MIRROR = (-1, 0, 0, 1)

#: SPICE analysis commands (only one of them is active in LTspice)
ANALYSES = ('.tran', '.ac', '.dc', '.op', '.noise', '.tf')

Point = tuple[int, int]


#? -------------------------------------------------------------------------------
#? geometry helpers
def _mul(m1, m2):
    a1, b1, c1, d1 = m1
    a2, b2, c2, d2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2, c1 * a2 + d1 * c2, c1 * b2 + d1 * d2)


def rotate_orient(orient: str) -> str:
    """Orientation after a 90° clockwise (on screen) rotation."""
    return _MATRIX_TO_ORIENT[_mul(_ROT90, ORIENTATIONS.get(orient, ORIENTATIONS['R0']))]


def mirror_orient(orient: str) -> str:
    """Orientation after a left/right mirror."""
    return _MATRIX_TO_ORIENT[_mul(_MIRROR, ORIENTATIONS.get(orient, ORIENTATIONS['R0']))]


def rotate_point(x: int, y: int, px: int, py: int) -> Point:
    return px - (y - py), py + (x - px)


def mirror_point(x: int, y: int, px: int, _py: int = 0) -> Point:
    return 2 * px - x, y


def snap(v: float, grid: int = GRID) -> int:
    return int(round(v / grid)) * grid


def on_segment(p: Point, a: Point, b: Point) -> bool:
    """``p`` lies on segment ``a``-``b`` (end points included)."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    if (bx - ax) * (py - ay) != (by - ay) * (px - ax):
        return False
    return min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by)


#? -------------------------------------------------------------------------------
#? objects
@dataclass(eq=False)
class Wire:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def p1(self) -> Point:
        return self.x1, self.y1

    @property
    def p2(self) -> Point:
        return self.x2, self.y2

    def points(self) -> list[Point]:
        return [self.p1, self.p2]

    def transform(self, f: Callable[[int, int], Point]) -> None:
        (self.x1, self.y1), (self.x2, self.y2) = f(self.x1, self.y1), f(self.x2, self.y2)

    def line(self) -> str:
        return f'WIRE {self.x1} {self.y1} {self.x2} {self.y2}'


@dataclass(eq=False)
class Flag:
    """Net label (``FLAG``); ``name == '0'`` is the ground symbol. ``port`` = IOPIN direction."""
    x    : int
    y    : int
    name : str
    port : str | None = None          # In, Out, BiDir

    @property
    def is_ground(self) -> bool:
        return self.name == '0'

    def points(self) -> list[Point]:
        return [(self.x, self.y)]

    def transform(self, f: Callable[[int, int], Point]) -> None:
        self.x, self.y = f(self.x, self.y)

    def lines(self) -> list[str]:
        out = [f'FLAG {self.x} {self.y} {self.name}']
        if self.port:
            out.append(f'IOPIN {self.x} {self.y} {self.port}')
        return out


@dataclass(eq=False)
class Text:
    """``TEXT``: SPICE directive (``kind='!'``) or comment (``kind=';'``)."""
    x     : int
    y     : int
    align : str
    size  : int
    kind  : str          # '!' or ';'
    text  : str          # real newlines

    @property
    def is_directive(self) -> bool:
        return self.kind == '!'

    def points(self) -> list[Point]:
        return [(self.x, self.y)]

    def transform(self, f: Callable[[int, int], Point]) -> None:
        self.x, self.y = f(self.x, self.y)

    def line(self) -> str:
        return f'TEXT {self.x} {self.y} {self.align} {self.size} {self.kind}{self.text.replace(chr(10), chr(92) + "n")}'


@dataclass(eq=False)
class Shape:
    """Free graphics on the sheet: LINE, RECTANGLE, CIRCLE, ARC (``style`` is usually ``Normal``)."""
    keyword : str
    style   : str
    coords  : list[int]
    tail    : list[str] = field(default_factory=list)      # trailing tokens (line style)

    def points(self) -> list[Point]:
        return [(self.coords[i], self.coords[i + 1]) for i in range(0, len(self.coords), 2)]

    def transform(self, f: Callable[[int, int], Point]) -> None:
        pts = [f(x, y) for x, y in self.points()]
        self.coords = [v for p in pts for v in p]

    def line(self) -> str:
        return ' '.join([self.keyword, self.style, *map(str, self.coords), *self.tail])


@dataclass(eq=False)
class Part:
    """A placed symbol (``SYMBOL`` block)."""
    symbol  : str
    x       : int
    y       : int
    orient  : str = 'R0'
    attrs   : dict[str, str] = field(default_factory=dict)                      # SYMATTR, in file order
    windows : dict[int, tuple[int, int, str, int]] = field(default_factory=dict)   # WINDOW n x y align size

    @property
    def name(self) -> str:
        return self.attrs.get('InstName', '')

    @property
    def value(self) -> str:
        return self.attrs.get('Value', '')

    def sym(self, schematic_dir: str = '') -> Symbol:
        return find_symbol(self.symbol, schematic_dir)

    def matrix(self) -> tuple[int, int, int, int]:
        return ORIENTATIONS.get(self.orient, ORIENTATIONS['R0'])

    def to_sheet(self, x: int, y: int) -> Point:
        a, b, c, d = self.matrix()
        return self.x + a * x + b * y, self.y + c * x + d * y

    def pin_points(self, schematic_dir: str = '') -> list[Point]:
        return [self.to_sheet(px, py) for px, py in self.sym(schematic_dir).pins]

    def points(self) -> list[Point]:
        return [(self.x, self.y)]

    def transform(self, f: Callable[[int, int], Point]) -> None:
        self.x, self.y = f(self.x, self.y)

    def lines(self) -> list[str]:
        out = [f'SYMBOL {self.symbol} {self.x} {self.y} {self.orient}']
        out += [f'WINDOW {n} {x} {y} {al} {sz}' for n, (x, y, al, sz) in self.windows.items()]
        out += [f'SYMATTR {k} {v}' if v != '' else f'SYMATTR {k}' for k, v in self.attrs.items()]
        return out


Item = Wire | Flag | Text | Shape | Part


#? -------------------------------------------------------------------------------
@dataclass(eq=False)
class Schematic:
    version : str = '4'
    sheet   : str = 'SHEET 1 880 680'
    wires   : list[Wire]  = field(default_factory=list)
    flags   : list[Flag]  = field(default_factory=list)
    parts   : list[Part]  = field(default_factory=list)
    texts   : list[Text]  = field(default_factory=list)
    shapes  : list[Shape] = field(default_factory=list)
    other   : list[str]   = field(default_factory=list)    # verbatim (DATAFLAG, BUSTAP, ...)
    directory : str = ''                                   # folder of the file (local symbols)

    #? parse / serialise
    @classmethod
    def parse(cls, text: str, directory: str = '') -> 'Schematic':
        sch = cls(directory=directory)
        part: Part | None = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            keyword, _, rest = line.partition(' ')
            parts = rest.split()
            if part is not None and keyword in ('SYMATTR', 'WINDOW'):
                if keyword == 'SYMATTR':
                    k, _, v = rest.partition(' ')
                    part.attrs[k] = v
                elif len(parts) >= 5:
                    try:
                        part.windows[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3], int(parts[4]))
                    except ValueError:
                        pass
                continue
            part = None
            try:
                if keyword == 'Version':
                    sch.version = rest.strip()
                elif keyword == 'SHEET':
                    sch.sheet = line
                elif keyword == 'WIRE' and len(parts) >= 4:
                    sch.wires.append(Wire(*(int(p) for p in parts[:4])))
                elif keyword == 'FLAG' and len(parts) >= 3:
                    sch.flags.append(Flag(int(parts[0]), int(parts[1]), parts[2]))
                elif keyword == 'IOPIN' and len(parts) >= 3:
                    pos = (int(parts[0]), int(parts[1]))
                    for f in reversed(sch.flags):
                        if (f.x, f.y) == pos:
                            f.port = parts[2]
                            break
                    else:
                        sch.other.append(line)
                elif keyword == 'SYMBOL' and len(parts) >= 3:
                    part = Part(parts[0], int(parts[1]), int(parts[2]), parts[3] if len(parts) > 3 else 'R0')
                    sch.parts.append(part)
                elif keyword == 'TEXT':
                    t = _parse_text(rest)
                    if t is None:
                        sch.other.append(line)
                    else:
                        sch.texts.append(t)
                elif keyword in ('LINE', 'RECTANGLE', 'CIRCLE', 'ARC') and len(parts) >= 5:
                    n = 8 if keyword == 'ARC' else 4
                    sch.shapes.append(Shape(keyword, parts[0], [int(p) for p in parts[1:1 + n]], parts[1 + n:]))
                else:
                    sch.other.append(line)
            except ValueError:
                sch.other.append(line)
        return sch

    def to_text(self) -> str:
        out = [f'Version {self.version}', self.sheet]
        out += [w.line() for w in self.wires]
        for f in self.flags:
            out += f.lines()
        out += self.other
        for p in self.parts:
            out += p.lines()
        out += [t.line() for t in self.texts]
        out += [s.line() for s in self.shapes]
        return '\n'.join(out) + '\n'

    #? queries
    def items(self) -> list[Item]:
        return [*self.wires, *self.flags, *self.parts, *self.texts, *self.shapes]

    def part(self, name: str) -> Part | None:
        low = name.lower()
        return next((p for p in self.parts if p.name.lower() == low), None)

    def directives(self) -> list[Text]:
        return [t for t in self.texts if t.is_directive]

    def analysis(self) -> Text | None:
        """The directive that holds the analysis command (``.tran``, ``.ac``...)."""
        for t in self.directives():
            for ln in t.text.splitlines():
                if ln.strip().lower().split(' ', 1)[0] in ANALYSES:
                    return t
        return None

    def bbox(self) -> tuple[int, int, int, int]:
        pts = [p for it in self.items() for p in it.points()]
        for p in self.parts:
            pts += p.pin_points(self.directory)
        if not pts:
            return 0, 0, 0, 0
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def next_name(self, prefix: str) -> str:
        """First free instance name ``<prefix><n>``."""
        used = {p.name.upper() for p in self.parts}
        n = 1
        while f'{prefix}{n}'.upper() in used:
            n += 1
        return f'{prefix}{n}'

    #? editing
    def add(self, item: Item) -> None:
        self._list(item).append(item)

    def remove(self, item: Item) -> None:
        lst = self._list(item)
        if item in lst:
            lst.remove(item)

    def _list(self, item: Item) -> list:
        return {Wire: self.wires, Flag: self.flags, Part: self.parts, Text: self.texts, Shape: self.shapes}[type(item)]

    def cleanup(self) -> None:
        """Drop zero-length and duplicate wires."""
        seen, keep = set(), []
        for w in self.wires:
            key = tuple(sorted((w.p1, w.p2)))
            if w.p1 != w.p2 and key not in seen:
                seen.add(key)
                keep.append(w)
        self.wires = keep

    def copy_items(self, items: Iterable[Item]) -> 'Schematic':
        """A new schematic that holds deep copies of ``items``."""
        frag = Schematic(directory=self.directory)
        for it in items:
            frag.add(copy.deepcopy(it))
        return frag

    def merge(self, frag: 'Schematic', rename: bool = True) -> list[Item]:
        """Add the items of ``frag`` (renaming parts whose name is taken). Returns the added items."""
        added: list[Item] = []
        for it in frag.items():
            it = copy.deepcopy(it)
            if isinstance(it, Part) and rename and it.name and self.part(it.name) is not None:
                prefix = re.match(r'^(.*?)(\d*)$', it.name).group(1) or 'X'
                it.attrs['InstName'] = self.next_name(prefix)
            self.add(it)
            added.append(it)
        return added

    #? connectivity
    def connectivity(self) -> 'Connectivity':
        return Connectivity(self)


#? -------------------------------------------------------------------------------
def _parse_text(rest: str) -> Text | None:
    """``x y align size [!|;]text``."""
    parts = rest.split(' ', 4)
    if len(parts) < 5:
        return None
    try:
        x, y, size = int(parts[0]), int(parts[1]), int(parts[3])
    except ValueError:
        return None
    body = parts[4]
    kind = body[0] if body[:1] in ('!', ';') else ';'
    if body[:1] in ('!', ';'):
        body = body[1:]
    return Text(x, y, parts[2], size, kind, body.replace('\\n', '\n'))


#? -------------------------------------------------------------------------------
class Connectivity:
    """Nets of a schematic: which points are electrically connected.

    Wires connect their end points and every point lying on them (T junctions,
    pins dropped on a wire); pins and flags connect where they touch.
    """

    def __init__(self, sch: Schematic) -> None:
        self.sch = sch
        self._parent: dict[Point, Point] = {}
        self.pin_count: dict[Point, int] = {}
        self.part_pins: dict[int, list[Point]] = {}           # id(part) -> pin points (symbol order)
        points: set[Point] = set()
        for w in sch.wires:
            points.update(w.points())
        for f in sch.flags:
            points.add((f.x, f.y))
        for p in sch.parts:
            pins = p.pin_points(sch.directory)
            self.part_pins[id(p)] = pins
            for q in pins:
                points.add(q)
                self.pin_count[q] = self.pin_count.get(q, 0) + 1
        for q in points:
            self._parent[q] = q
        # junction degree: wire ends + pins + 2 for every wire a point lies inside
        self.degree: dict[Point, int] = dict(self.pin_count)
        for w in sch.wires:
            self._union(w.p1, w.p2)
            for q in (w.p1, w.p2):
                self.degree[q] = self.degree.get(q, 0) + 1
            for q in points:
                if q != w.p1 and q != w.p2 and on_segment(q, w.p1, w.p2):
                    self._union(q, w.p1)
                    self.degree[q] = self.degree.get(q, 0) + 2
        # labels with the same name are the same net (case-insensitive, like SPICE)
        first: dict[str, Point] = {}
        for f in sch.flags:
            key = f.name.lower()
            if key in first:
                self._union((f.x, f.y), first[key])
            else:
                first[key] = (f.x, f.y)
        # names
        self.names: dict[Point, str] = {}
        for f in sch.flags:
            root = self.find((f.x, f.y))
            if f.name == '0' or root not in self.names:
                self.names[root] = f.name

    def _union(self, a: Point, b: Point) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def find(self, p: Point) -> Point:
        parent = self._parent
        if p not in parent:
            return p
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def net_of(self, p: Point) -> Point | None:
        return self.find(p) if p in self._parent else None

    def name_of(self, p: Point) -> str | None:
        """Label of the net through ``p`` (``'0'`` for ground), or None if unlabelled."""
        root = self.net_of(p)
        return self.names.get(root) if root is not None else None

    def junctions(self) -> list[Point]:
        """Points that get a junction dot (three or more connections)."""
        return [p for p, n in self.degree.items() if n >= 3]

    def net_names(self) -> list[str]:
        return sorted({n for n in self.names.values() if n != '0'}, key=str.lower)

    def unconnected_pins(self) -> list[Point]:
        """Pins that touch nothing else."""
        return [p for p, n in self.degree.items() if n == 1 and self.pin_count.get(p)
                and not any(f.x == p[0] and f.y == p[1] for f in self.sch.flags)]

#? -------------------------------------------------------------------------------
