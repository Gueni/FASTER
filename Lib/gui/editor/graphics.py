#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#? Name:        graphics.py
#? Purpose:     QGraphicsItems that draw schematic objects in the FASTER theme.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------

"""Graphics items for the schematic editor.

Every item keeps a reference to its model object (``item.obj``). Items are
cheap to rebuild: the editor recreates the scene from the model after each
edit. Symbol graphics are built once per symbol and cached.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPainterPathStroker, QPen,
                           QTransform)
from PySide6.QtWidgets import QGraphicsItem

from ...schematic.model import Flag, Part, Shape, Text, Wire
from ...schematic.renderer import FONT_BASE, FONT_SIZES, WINDOW_ATTRS, _oriented_align, _plain_align
from ...schematic.symbols import Symbol


#? -------------------------------------------------------------------------------
@dataclass
class Colors:
    sheet    : str
    wire     : str
    symbol   : str
    text     : str
    comment  : str
    select   : str
    hover    : str
    missing  : str
    muted    : str
    grid     : str

    @classmethod
    def from_palette(cls, p) -> 'Colors':
        return cls(sheet=p.sheet, wire=p.wire, symbol=p.symbol, text=p.text, comment=p.accent,
                   select=p.warning, hover=p.accent_hover, missing=p.danger, muted=p.muted, grid=p.border)


#? -------------------------------------------------------------------------------
#? text
_FONTS: dict[int, QFont] = {}


def text_font(size_idx: int) -> QFont:
    size_idx = max(0, min(size_idx, len(FONT_SIZES) - 1))
    if size_idx not in _FONTS:
        f = QFont('Arial')
        f.setPixelSize(max(1, round(FONT_BASE * FONT_SIZES[size_idx])))
        _FONTS[size_idx] = f
    return _FONTS[size_idx]


@dataclass
class Label:
    """A piece of text in sheet coordinates (``align`` from renderer: start/end/middle/top/bottom)."""
    x     : float
    y     : float
    text  : str
    size  : int
    vert  : bool
    align : str

    def local_rect(self) -> tuple[QRectF, Qt.AlignmentFlag]:
        fm    = QFontMetricsF(text_font(self.size))
        lines = self.text.split('\n')
        w     = max(fm.horizontalAdvance(l) for l in lines) + 2
        h     = fm.height() * len(lines)
        A     = Qt.AlignmentFlag
        if self.align == 'start':
            return QRectF(0, -h / 2, w, h), A.AlignLeft | A.AlignVCenter
        if self.align == 'end':
            return QRectF(-w, -h / 2, w, h), A.AlignRight | A.AlignVCenter
        if self.align == 'top':
            return QRectF(-w / 2, 0, w, h), A.AlignHCenter | A.AlignTop
        if self.align == 'bottom':
            return QRectF(-w / 2, -h, w, h), A.AlignHCenter | A.AlignBottom
        return QRectF(-w / 2, -h / 2, w, h), A.AlignCenter

    def transform(self) -> QTransform:
        t = QTransform().translate(self.x, self.y)
        return t.rotate(-90) if self.vert else t

    def scene_rect(self) -> QRectF:
        return self.transform().mapRect(self.local_rect()[0])

    def paint(self, painter: QPainter, color: QColor) -> None:
        if not self.text:
            return
        rect, flags = self.local_rect()
        painter.save()
        painter.setTransform(self.transform(), True)
        painter.setFont(text_font(self.size))
        painter.setPen(color)
        painter.drawText(rect, int(flags), self.text)
        painter.restore()


#? -------------------------------------------------------------------------------
#? symbol graphics cache
_SYMBOL_PATHS: dict[int, QPainterPath] = {}


def symbol_path(sym: Symbol) -> QPainterPath:
    """Line work of a symbol in its own coordinates (cached per symbol object)."""
    key = id(sym)
    if key in _SYMBOL_PATHS:
        return _SYMBOL_PATHS[key]
    path = QPainterPath()
    for x1, y1, x2, y2 in sym.lines:
        path.moveTo(x1, y1)
        path.lineTo(x2, y2)
    for x1, y1, x2, y2 in sym.rects:
        path.addRect(QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized())
    for x1, y1, x2, y2 in sym.circles:
        path.addEllipse(QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized())
    for x1, y1, x2, y2, sx, sy, ex, ey in sym.arcs:
        rect = QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized()
        if rect.width() == 0 or rect.height() == 0:
            continue
        cx, cy = rect.center().x(), rect.center().y()
        rx, ry = rect.width() / 2, rect.height() / 2
        ts = math.degrees(math.atan2(-(sy - cy) / ry, (sx - cx) / rx))
        te = math.degrees(math.atan2(-(ey - cy) / ry, (ex - cx) / rx))
        span = (te - ts) % 360 or 360
        path.arcMoveTo(rect, ts)
        path.arcTo(rect, ts, span)
    _SYMBOL_PATHS[key] = path
    return path


def _stroke(path: QPainterPath, width: float) -> QPainterPath:
    s = QPainterPathStroker()
    s.setWidth(width)
    return s.createStroke(path)


#? -------------------------------------------------------------------------------
class SchItem(QGraphicsItem):
    """Base class: selection / hover state and colours."""
    kind = ''

    def __init__(self, obj, colors: Colors) -> None:
        super().__init__()
        self.obj     = obj
        self.colors  = colors
        self.hovered = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    def color(self, base: str) -> QColor:
        if self.isSelected():
            return QColor(self.colors.select)
        if self.hovered:
            return QColor(self.colors.hover)
        return QColor(base)

    def hoverEnterEvent(self, e) -> None:      # noqa: N802
        self.hovered = True
        self.update()

    def hoverLeaveEvent(self, e) -> None:      # noqa: N802
        self.hovered = False
        self.update()


#? -------------------------------------------------------------------------------
class WireItem(SchItem):
    kind = 'wire'

    def __init__(self, wire: Wire, colors: Colors) -> None:
        super().__init__(wire, colors)
        self.setZValue(2)
        self.p1 = QPointF(wire.x1, wire.y1)
        self.p2 = QPointF(wire.x2, wire.y2)
        self.dashed = False

    def set_points(self, p1: QPointF, p2: QPointF) -> None:
        self.prepareGeometryChange()
        self.p1, self.p2 = p1, p2

    def _path(self) -> QPainterPath:
        p = QPainterPath(self.p1)
        p.lineTo(self.p2)
        return p

    def boundingRect(self) -> QRectF:      # noqa: N802
        return QRectF(self.p1, self.p2).normalized().adjusted(-6, -6, 6, 6)

    def shape(self) -> QPainterPath:
        return _stroke(self._path(), 10)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen = QPen(self.color(self.colors.wire), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if self.dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(self.p1, self.p2)


#? -------------------------------------------------------------------------------
class FlagItem(SchItem):
    kind = 'flag'

    def __init__(self, flag: Flag, colors: Colors) -> None:
        super().__init__(flag, colors)
        self.setZValue(3)
        x, y = flag.x, flag.y
        if flag.is_ground:
            self.label = None
            self.path  = QPainterPath()
            self.path.moveTo(x - 16, y)
            self.path.lineTo(x + 16, y)
            self.path.lineTo(x, y + 16)
            self.path.closeSubpath()
        else:
            self.label = Label(x, y - 4, flag.name, 2, False, 'bottom')
            self.path  = QPainterPath()
            if flag.port:
                # port: arrow-ended box around the name (In points left, Out right, BiDir both)
                r  = self.label.scene_rect().adjusted(-4, 0, 4, 0)
                cy, h = r.center().y(), r.height() / 2
                lt = r.left() - (h if flag.port.lower() in ('in', 'bidir') else 0)
                rt = r.right() + (h if flag.port.lower() in ('out', 'bidir') else 0)
                self.path.moveTo(lt, cy)
                self.path.lineTo(r.left(), r.top())
                self.path.lineTo(r.right(), r.top())
                self.path.lineTo(rt, cy)
                self.path.lineTo(r.right(), r.bottom())
                self.path.lineTo(r.left(), r.bottom())
                self.path.closeSubpath()
            # small tick that shows where the label attaches
            self.path.moveTo(x - 3, y)
            self.path.lineTo(x + 3, y)

    def boundingRect(self) -> QRectF:      # noqa: N802
        r = self.path.boundingRect()
        if self.label:
            r = r.united(self.label.scene_rect())
        return r.adjusted(-4, -4, 4, 4)

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(self.boundingRect())
        return p

    def paint(self, painter: QPainter, option, widget=None) -> None:
        col = self.color(self.colors.symbol if self.obj.is_ground else self.colors.wire)
        painter.setPen(QPen(col, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path)
        if self.label:
            self.label.paint(painter, col)


#? -------------------------------------------------------------------------------
class TextItem(SchItem):
    kind = 'text'

    def __init__(self, text: Text, colors: Colors) -> None:
        super().__init__(text, colors)
        self.setZValue(4)
        vert, al   = _plain_align(text.align)
        self.label = Label(text.x, text.y, text.text, text.size, vert, al)

    def boundingRect(self) -> QRectF:      # noqa: N802
        return self.label.scene_rect().adjusted(-3, -3, 3, 3)

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(self.boundingRect())
        return p

    def paint(self, painter: QPainter, option, widget=None) -> None:
        base = self.colors.text if self.obj.is_directive else self.colors.comment
        self.label.paint(painter, self.color(base))
        if self.isSelected():
            painter.setPen(QPen(QColor(self.colors.select), 1, Qt.PenStyle.DashLine))
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))


#? -------------------------------------------------------------------------------
class ShapeItem(SchItem):
    kind = 'shape'

    def __init__(self, shape: Shape, colors: Colors) -> None:
        super().__init__(shape, colors)
        self.setZValue(1)
        sym = Symbol('shape')
        c   = shape.coords
        {'LINE': sym.lines, 'RECTANGLE': sym.rects, 'CIRCLE': sym.circles, 'ARC': sym.arcs}[shape.keyword] \
            .append(tuple(c))
        self.path   = QPainterPath(symbol_path(sym))
        _SYMBOL_PATHS.pop(id(sym), None)
        self.dashed = bool(shape.tail and shape.tail[-1] not in ('0', ''))

    def boundingRect(self) -> QRectF:      # noqa: N802
        return self.path.boundingRect().adjusted(-4, -4, 4, 4)

    def shape(self) -> QPainterPath:
        return _stroke(self.path, 8)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen = QPen(self.color(self.colors.symbol), 2)
        if self.dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path)


#? -------------------------------------------------------------------------------
class PartItem(SchItem):
    kind = 'part'

    def __init__(self, part: Part, sym: Symbol, colors: Colors) -> None:
        super().__init__(part, colors)
        self.setZValue(5)
        self.sym = sym
        a, b, c, d = part.matrix()
        self.tf = QTransform(a, c, b, d, part.x, part.y)
        if sym.found:
            self.path = self.tf.map(symbol_path(sym))
        else:
            self.path = QPainterPath()
            self.path.addRect(QRectF(part.x - 24, part.y - 8, 80, 112))
        self.pins = [self.tf.map(QPointF(px, py)) for px, py in sym.pins]
        m = part.matrix()
        self.labels: list[Label] = []
        for x, y, align, size, text in sym.texts:
            vert, al = _oriented_align(align, m)
            sx, sy   = part.to_sheet(x, y)
            self.labels.append(Label(sx, sy, text, size, vert, al))
        windows = {**sym.windows, **part.windows}
        for num, (wx, wy, align, size) in windows.items():
            attr  = WINDOW_ATTRS.get(num)
            value = part.attrs.get(attr) if attr else None
            if value is None and attr == 'Value':
                value = sym.attrs.get('Value')
            if not value or size == 0:
                continue
            vert, al = _oriented_align(align, m)
            sx, sy   = part.to_sheet(wx, wy)
            self.labels.append(Label(sx, sy, value, size, vert, al))
        if not sym.found:
            self.labels.append(Label(part.x + 16, part.y + 48, part.symbol.split('\\')[-1], 1, False, 'middle'))
        self.body = self.path.boundingRect()
        if self.body.isEmpty() and self.pins:
            xs = [p.x() for p in self.pins]
            ys = [p.y() for p in self.pins]
            self.body = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        self.body = self.body.adjusted(-4, -4, 4, 4)
        self._bounds = self.body
        for lab in self.labels:
            self._bounds = self._bounds.united(lab.scene_rect())
        self._bounds = self._bounds.adjusted(-4, -4, 4, 4)

    def pin_at(self, p: QPointF, tol: float = 10.0) -> int | None:
        best, idx = tol, None
        for i, q in enumerate(self.pins):
            dist = math.hypot(q.x() - p.x(), q.y() - p.y())
            if dist <= best:
                best, idx = dist, i
        return idx

    def boundingRect(self) -> QRectF:      # noqa: N802
        return self._bounds

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(self.body)
        for lab in self.labels:
            p.addRect(lab.scene_rect())
        return p

    def paint(self, painter: QPainter, option, widget=None) -> None:
        col = self.color(self.colors.symbol if self.sym.found else self.colors.missing)
        pen = QPen(col, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if not self.sym.found:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path)
        tcol = self.color(self.colors.text)
        for lab in self.labels:
            lab.paint(painter, tcol)


#? -------------------------------------------------------------------------------
class OverlayItem(QGraphicsItem):
    """Junction dots and open-pin markers (not selectable)."""

    def __init__(self, junctions, open_pins, colors: Colors) -> None:
        super().__init__()
        self.setZValue(10)
        self.junctions = [QPointF(*p) for p in junctions]
        self.open_pins = [QPointF(*p) for p in open_pins]
        self.colors    = colors
        pts = self.junctions + self.open_pins
        if pts:
            xs = [p.x() for p in pts]
            ys = [p.y() for p in pts]
            self._rect = QRectF(min(xs) - 8, min(ys) - 8, max(xs) - min(xs) + 16, max(ys) - min(ys) + 16)
        else:
            self._rect = QRectF()

    def boundingRect(self) -> QRectF:      # noqa: N802
        return self._rect

    def paint(self, painter: QPainter, option, widget=None) -> None:
        col = QColor(self.colors.wire)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(col))
        for p in self.junctions:
            painter.drawEllipse(p, 5, 5)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(self.colors.muted), 1.5))
        for p in self.open_pins:
            painter.drawRect(QRectF(p.x() - 4, p.y() - 4, 8, 8))


#? -------------------------------------------------------------------------------
def make_item(obj, colors: Colors, directory: str = '') -> SchItem:
    if isinstance(obj, Wire):
        return WireItem(obj, colors)
    if isinstance(obj, Flag):
        return FlagItem(obj, colors)
    if isinstance(obj, Text):
        return TextItem(obj, colors)
    if isinstance(obj, Shape):
        return ShapeItem(obj, colors)
    return PartItem(obj, obj.sym(directory), colors)

#? -------------------------------------------------------------------------------
