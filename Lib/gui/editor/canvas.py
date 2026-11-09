#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#? Name:        canvas.py
#? Purpose:     Interactive schematic editing canvas (tools, selection, drag, wiring).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------

"""Schematic editing canvas.

The canvas edits a :class:`~Lib.schematic.model.Schematic` in place and emits
:attr:`Canvas.committed` after every finished edit; the owner serialises the
model (one undo step) and calls :meth:`Canvas.rebuild`.

Keys follow LTspice where it has one: F2 component, F3 wire, F4 label, G ground,
R/C/L/D parts, T comment, S directive, F5/Del delete, F6 duplicate, F7 move,
F8 drag, Ctrl+R rotate, Ctrl+E mirror, Space zoom to fit, Esc cancel.
"""

from __future__ import annotations

import copy
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from ...schematic.model import (Flag, Part, Schematic, Text, Wire, mirror_orient, mirror_point, on_segment,
                                rotate_orient, rotate_point, snap)
from .graphics import Colors, OverlayItem, PartItem, SchItem, WireItem, make_item

MIME = 'application/x-faster-asc'
SNAP_TO_PIN = 8          # snap to a connection point closer than this (sheet units)


#? -------------------------------------------------------------------------------
class Canvas(QGraphicsView):
    committed     = Signal(str)               # description of the edit
    status        = Signal(str)               # hint for the status line
    position      = Signal(int, int)          # cursor position (sheet units)
    tool_changed  = Signal(str)
    edit_object   = Signal(object)            # double-click on a model object
    probe_clicked = Signal(object)            # ('net', point) | ('part', part, pin index | None)
    probe_hover   = Signal(object)
    request       = Signal(str)               # 'component', 'label', 'text', 'directive', 'undo', 'redo'
    context_menu  = Signal(object, object)    # (model object | None, global QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.scene().setSceneRect(-60000, -60000, 120000, 120000)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(False)

        self.sch: Schematic | None = None
        self.colors: Colors | None = None
        self.show_grid = True
        self.items_by_obj: dict[int, SchItem] = {}
        self.tool = 'select'

        # interaction state
        self._press_scene: QPointF | None = None
        self._press_view = None
        self._dragging   = False
        self._drag_mode  = 'drag'                 # 'drag' keeps wires connected, 'move' does not
        self._stretch: list[tuple[WireItem, bool, bool]] = []
        self._rubber: QGraphicsRectItem | None = None
        self._pan_from = None
        self._wire_start: tuple[int, int] | None = None
        self._wire_hfirst: bool | None = None
        self._wire_preview: list[WireItem] = []
        self._frag: Schematic | None = None         # fragment being placed
        self._frag_repeat = False
        self._frag_items: list[SchItem] = []
        self._frag_name = ''
        self._last_mouse = QPointF(0, 0)
        self._fitted = False

    #? model
    def set_schematic(self, sch: Schematic, colors: Colors, fit: bool = False) -> None:
        self.sch, self.colors = sch, colors
        self.rebuild()
        if fit or not self._fitted:
            self.fit()

    def set_colors(self, colors: Colors) -> None:
        self.colors = colors
        self.rebuild()

    def rebuild(self) -> None:
        """Recreate the scene from the model, keeping the selection."""
        selected = {id(it.obj) for it in self.selected_items()}
        self._clear_previews()
        self.scene().clear()
        self.items_by_obj.clear()
        self._frag_items = []
        if self.sch is None or self.colors is None:
            return
        for obj in self.sch.items():
            item = make_item(obj, self.colors, self.sch.directory)
            self.scene().addItem(item)
            self.items_by_obj[id(obj)] = item
            if id(obj) in selected:
                item.setSelected(True)
        conn = self.sch.connectivity()
        self.scene().addItem(OverlayItem(conn.junctions(), conn.unconnected_pins(), self.colors))
        if self._frag is not None:
            self._show_fragment()
        self.viewport().update()

    def commit(self, what: str) -> None:
        self.sch.cleanup()
        self.committed.emit(what)

    def selected_items(self) -> list[SchItem]:
        return [it for it in self.scene().selectedItems() if isinstance(it, SchItem) and it not in self._frag_items]

    def selected_objects(self) -> list:
        return [it.obj for it in self.selected_items()]

    def select_objects(self, objs) -> None:
        self.scene().clearSelection()
        for o in objs:
            it = self.items_by_obj.get(id(o))
            if it:
                it.setSelected(True)

    #? view
    def fit(self) -> None:
        if self.sch is None:
            return
        rect = QRectF()
        for it in self.items_by_obj.values():
            rect = rect.united(it.sceneBoundingRect())
        if rect.isEmpty():
            rect = QRectF(-200, -150, 400, 300)
        self.fitInView(rect.adjusted(-48, -48, 48, 48), Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 3:
            self.resetTransform()
            self.scale(3, 3)
            self.centerOn(rect.center())
        self._fitted = True

    def zoom(self, factor: float) -> None:
        s = self.transform().m11() * factor
        if 0.02 < s < 40:
            self.scale(factor, factor)

    def wheelEvent(self, e) -> None:      # noqa: N802
        self.zoom(1.2 ** (e.angleDelta().y() / 120))

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:      # noqa: N802
        if self.colors is None:
            return super().drawBackground(painter, rect)
        painter.fillRect(rect, QColor(self.colors.sheet))
        scale = self.transform().m11()
        if not self.show_grid:
            return
        step = 16
        while step * scale < 10:
            step *= 4
        col = QColor(self.colors.grid)
        painter.setPen(QPen(col, 0))
        x0 = math.floor(rect.left() / step) * step
        y0 = math.floor(rect.top() / step) * step
        points = []
        y = y0
        while y <= rect.bottom():
            x = x0
            while x <= rect.right():
                points.append(QPointF(x, y))
                x += step
            y += step
        if len(points) < 40000:
            pen = QPen(col, 2.0 / scale)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(points)

    #? snapping
    def connection_points(self) -> list[tuple[int, int]]:
        pts: list[tuple[int, int]] = []
        if self.sch is None:
            return pts
        for w in self.sch.wires:
            pts += w.points()
        for f in self.sch.flags:
            pts.append((f.x, f.y))
        for p in self.sch.parts:
            pts += p.pin_points(self.sch.directory)
        return pts

    def snap_point(self, sp: QPointF, to_pins: bool = True) -> tuple[int, int]:
        if to_pins:
            best, hit = SNAP_TO_PIN, None
            for q in self.connection_points():
                d = math.hypot(q[0] - sp.x(), q[1] - sp.y())
                if d < best:
                    best, hit = d, q
            if hit:
                return hit
        return snap(sp.x()), snap(sp.y())

    def is_connection(self, p: tuple[int, int]) -> bool:
        if p in self.connection_points():
            return True
        return any(on_segment(p, w.p1, w.p2) for w in self.sch.wires)

    #? tools
    def set_tool(self, tool: str) -> None:
        self._cancel_wire()
        if tool != 'place':
            self._frag = None
        self._clear_previews()
        self.tool = tool
        cursors = {'select': Qt.CursorShape.ArrowCursor, 'wire': Qt.CursorShape.CrossCursor,
                   'place': Qt.CursorShape.CrossCursor, 'delete': Qt.CursorShape.ForbiddenCursor,
                   'probe': Qt.CursorShape.PointingHandCursor}
        self.viewport().setCursor(cursors.get(tool, Qt.CursorShape.ArrowCursor))
        hints = {'select': 'Click to select, drag to move (wires follow), double-click to edit. '
                           'Drag on empty space to box-select.',
                 'wire': 'Click to start a wire, click to add corners, right-click or Esc to stop.',
                 'place': 'Click to place. Ctrl+R rotate, Ctrl+E mirror, Esc to stop.',
                 'delete': 'Click an object (or drag a box) to delete it. Esc to stop.',
                 'probe': 'Click a wire for its voltage, a part for its current. Esc to stop.'}
        self.status.emit(hints.get(tool, ''))
        self.tool_changed.emit(tool)

    def place(self, frag: Schematic, repeat: bool = False) -> None:
        """Start placing ``frag`` (positioned around 0,0) at the cursor."""
        self.set_tool('place')
        self._frag, self._frag_repeat = frag, repeat
        self._show_fragment()

    def place_part(self, symbol: str, prefix: str, value: str = '', attrs: dict | None = None) -> None:
        frag = Schematic(directory=self.sch.directory if self.sch else '')
        part = Part(symbol, 0, 0, 'R0', {'InstName': '', **({'Value': value} if value else {}), **(attrs or {})})
        frag.parts.append(part)
        self._frag_name = prefix
        self.place(frag, repeat=True)

    def place_flag(self, name: str, port: str | None = None) -> None:
        frag = Schematic()
        frag.flags.append(Flag(0, 0, name, port))
        self._frag_name = ''
        self.place(frag, repeat=name == '0')

    def place_text(self, text: str, directive: bool) -> None:
        frag = Schematic()
        frag.texts.append(Text(0, 0, 'Left', 2, '!' if directive else ';', text))
        self._frag_name = ''
        self.place(frag, repeat=False)

    def _show_fragment(self) -> None:
        for it in self._frag_items:
            if it.scene():
                self.scene().removeItem(it)
        self._frag_items = []
        if self._frag is None or self.colors is None:
            return
        for obj in self._frag.items():
            it = make_item(obj, self.colors, self._frag.directory or (self.sch.directory if self.sch else ''))
            it.setOpacity(0.55)
            it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            it.setAcceptHoverEvents(False)
            it.setZValue(50)
            self.scene().addItem(it)
            self._frag_items.append(it)
        self._move_fragment(self._last_mouse)

    def _move_fragment(self, sp: QPointF) -> None:
        x, y = snap(sp.x()), snap(sp.y())
        for it in self._frag_items:
            it.setPos(x, y)

    def _drop_fragment(self, sp: QPointF) -> None:
        x, y = snap(sp.x()), snap(sp.y())
        frag = copy.deepcopy(self._frag)
        for obj in frag.items():
            obj.transform(lambda px, py: (px + x, py + y))
        for p in frag.parts:
            if not p.name:
                p.attrs['InstName'] = self.sch.next_name(self._frag_name or 'X')
                if not p.attrs.get('Value'):
                    p.attrs.pop('Value', None)
                p.attrs = {'InstName': p.attrs.pop('InstName'), **p.attrs}
        added = self.sch.merge(frag, rename=True)
        self.commit('Place')
        if not self._frag_repeat:
            self._frag = None
            self.set_tool('select')
            self.select_objects(added)

    def transform_fragment(self, how: str) -> None:
        if self._frag is None:
            return
        for obj in self._frag.items():
            if how == 'rotate':
                obj.transform(lambda px, py: rotate_point(px, py, 0, 0))
                if isinstance(obj, Part):
                    obj.orient = rotate_orient(obj.orient)
            else:
                obj.transform(lambda px, py: mirror_point(px, py, 0, 0))
                if isinstance(obj, Part):
                    obj.orient = mirror_orient(obj.orient)
                if isinstance(obj, Text):
                    obj.align = {'Left': 'Right', 'Right': 'Left'}.get(obj.align, obj.align)
        self._show_fragment()

    #? edits on the selection
    def _pivot(self, objs) -> tuple[int, int]:
        pts = [p for o in objs for p in o.points()]
        for o in objs:
            if isinstance(o, Part):
                pts += o.pin_points(self.sch.directory)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return snap((min(xs) + max(xs)) / 2), snap((min(ys) + max(ys)) / 2)

    def rotate_selection(self) -> None:
        if self.tool == 'place':
            return self.transform_fragment('rotate')
        objs = self.selected_objects()
        if not objs:
            return
        px, py = self._pivot(objs)
        for o in objs:
            o.transform(lambda x, y: rotate_point(x, y, px, py))
            if isinstance(o, Part):
                o.orient = rotate_orient(o.orient)
        self.commit('Rotate')

    def mirror_selection(self) -> None:
        if self.tool == 'place':
            return self.transform_fragment('mirror')
        objs = self.selected_objects()
        if not objs:
            return
        px, py = self._pivot(objs)
        for o in objs:
            o.transform(lambda x, y: mirror_point(x, y, px, py))
            if isinstance(o, Part):
                o.orient = mirror_orient(o.orient)
            if isinstance(o, Text):
                o.align = {'Left': 'Right', 'Right': 'Left'}.get(o.align, o.align)
        self.commit('Mirror')

    def delete_objects(self, objs) -> None:
        if not objs:
            return
        for o in objs:
            self.sch.remove(o)
        self.commit('Delete')

    def delete_selection(self) -> None:
        self.delete_objects(self.selected_objects())

    def select_all(self) -> None:
        for it in self.items_by_obj.values():
            it.setSelected(True)

    def copy_selection(self, cut: bool = False) -> bool:
        objs = self.selected_objects()
        if not objs:
            return False
        frag = self.sch.copy_items(objs)
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setData(MIME, frag.to_text().encode('utf-8'))
        md.setText(frag.to_text())
        QGuiApplication.clipboard().setMimeData(md)
        if cut:
            self.delete_objects(objs)
        return True

    def paste(self) -> bool:
        md = QGuiApplication.clipboard().mimeData()
        if md is None:
            return False
        text = bytes(md.data(MIME)).decode('utf-8') if md.hasFormat(MIME) else md.text()
        if not text.lstrip().startswith(('Version', 'WIRE', 'SYMBOL', 'FLAG', 'TEXT')):
            return False
        frag = Schematic.parse(text, self.sch.directory)
        if not frag.items():
            return False
        x0, y0, x1, y1 = frag.bbox()
        cx, cy = snap((x0 + x1) / 2), snap((y0 + y1) / 2)
        for o in frag.items():
            o.transform(lambda x, y: (x - cx, y - cy))
        self._frag_name = ''
        self.place(frag, repeat=False)
        return True

    def duplicate(self) -> None:
        if self.copy_selection():
            self.paste()

    #? wire tool
    def _cancel_wire(self) -> None:
        self._wire_start = None
        self._wire_hfirst = None
        self._clear_previews()

    def _clear_previews(self) -> None:
        for it in self._wire_preview:
            if it.scene():
                self.scene().removeItem(it)
        self._wire_preview = []
        if self._rubber is not None and self._rubber.scene():
            self.scene().removeItem(self._rubber)
        self._rubber = None

    def _wire_corner(self, end: tuple[int, int]) -> tuple[int, int]:
        sx, sy = self._wire_start
        ex, ey = end
        if self._wire_hfirst is None and (abs(ex - sx) >= 16 or abs(ey - sy) >= 16):
            self._wire_hfirst = abs(ex - sx) >= abs(ey - sy)
        if (ex, ey) == (sx, sy):
            self._wire_hfirst = None
        return (ex, sy) if self._wire_hfirst in (True, None) else (sx, ey)

    def _update_wire_preview(self, end: tuple[int, int]) -> None:
        for it in self._wire_preview:
            if it.scene():
                self.scene().removeItem(it)
        self._wire_preview = []
        if self._wire_start is None:
            return
        corner = self._wire_corner(end)
        for a, b in ((self._wire_start, corner), (corner, end)):
            if a != b:
                it = WireItem(Wire(*a, *b), self.colors)
                it.dashed = True
                it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                it.setZValue(60)
                self.scene().addItem(it)
                self._wire_preview.append(it)

    def _wire_click(self, sp: QPointF) -> None:
        end = self.snap_point(sp)
        if self._wire_start is None:
            self._wire_start = end
            self._wire_hfirst = None
            self.status.emit('Click to add a corner or finish on a pin / wire. Right-click to stop.')
            return
        if end == self._wire_start:
            return
        finish = self.is_connection(end)
        corner = self._wire_corner(end)
        for a, b in ((self._wire_start, corner), (corner, end)):
            if a != b:
                self.sch.wires.append(Wire(*a, *b))
        self._wire_start = None if finish else end
        self._wire_hfirst = None
        self.commit('Wire')
        if self._wire_start is not None:
            self._update_wire_preview(end)

    #? hit testing
    def item_at(self, view_pos) -> SchItem | None:
        for it in self.items(view_pos):
            if isinstance(it, SchItem) and it not in self._frag_items and it not in self._wire_preview:
                return it
        return None

    def _probe_target(self, view_pos):
        it = self.item_at(view_pos)
        sp = self.mapToScene(view_pos)
        if isinstance(it, PartItem):
            pin = it.pin_at(sp, 10 / max(0.2, min(1.0, self.transform().m11())))
            return ('part', it.obj, pin)
        if isinstance(it, WireItem):
            return ('net', it.obj.p1)
        if it is not None and it.kind == 'flag':
            return ('net', (it.obj.x, it.obj.y))
        return None

    #? mouse
    def mousePressEvent(self, e) -> None:      # noqa: N802
        sp = self.mapToScene(e.position().toPoint())
        self._last_mouse = sp
        if e.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._pan_from = e.position()
            self._pan_moved = False
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool == 'wire':
            self._wire_click(sp)
            return
        if self.tool == 'place':
            self._drop_fragment(sp)
            return
        if self.tool == 'probe':
            t = self._probe_target(e.position().toPoint())
            if t:
                self.probe_clicked.emit(t)
            return
        it = self.item_at(e.position().toPoint())
        self._press_scene, self._press_view = sp, e.position()
        self._dragging = False
        if self.tool == 'delete':
            if it is not None:
                self.delete_objects([it.obj])
                self._press_scene = None
            return
        shift = bool(e.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier))
        if it is None:
            if not shift:
                self.scene().clearSelection()
            return
        if shift:
            it.setSelected(not it.isSelected())
            self._press_scene = None
        elif not it.isSelected():
            self.scene().clearSelection()
            it.setSelected(True)

    def mouseMoveEvent(self, e) -> None:      # noqa: N802
        sp = self.mapToScene(e.position().toPoint())
        self._last_mouse = sp
        self.position.emit(snap(sp.x()), snap(sp.y()))
        if self._pan_from is not None:
            d = e.position() - self._pan_from
            if abs(d.x()) + abs(d.y()) > 2:
                self._pan_moved = True
            self._pan_from = e.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y()))
            return
        if self.tool == 'wire':
            if self._wire_start is not None:
                self._update_wire_preview(self.snap_point(sp))
            return
        if self.tool == 'place':
            self._move_fragment(sp)
            return
        if self.tool == 'probe':
            self.probe_hover.emit(self._probe_target(e.position().toPoint()))
            return
        if self._press_scene is None or not (e.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self._dragging and (e.position() - self._press_view).manhattanLength() < 5:
            return
        if self.selected_items() and self.tool == 'select' and self._rubber is None and \
                (self._dragging or self.item_at(self._press_view.toPoint()) is not None):
            if not self._dragging:
                self._begin_drag()
            dx = snap(sp.x() - self._press_scene.x())
            dy = snap(sp.y() - self._press_scene.y())
            self._drag_to(dx, dy)
            return
        # rubber band
        if self._rubber is None:
            self._rubber = QGraphicsRectItem()
            self._rubber.setZValue(100)
            col = QColor(self.colors.hover)
            pen = QPen(col, 0, Qt.PenStyle.DashLine)
            self._rubber.setPen(pen)
            col.setAlpha(30)
            self._rubber.setBrush(col)
            self.scene().addItem(self._rubber)
        self._rubber.setRect(QRectF(self._press_scene, sp).normalized())

    def mouseReleaseEvent(self, e) -> None:      # noqa: N802
        sp = self.mapToScene(e.position().toPoint())
        if self._pan_from is not None and e.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._pan_from = None
            if e.button() == Qt.MouseButton.RightButton and not self._pan_moved:
                self._right_click(e)
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging:
            dx = snap(sp.x() - self._press_scene.x())
            dy = snap(sp.y() - self._press_scene.y())
            self._end_drag(dx, dy)
        elif self._rubber is not None:
            rect = self._rubber.rect()
            mode = Qt.ItemSelectionMode.ContainsItemShape if sp.x() >= self._press_scene.x() \
                else Qt.ItemSelectionMode.IntersectsItemShape
            hits = [it for it in self.scene().items(rect, mode) if isinstance(it, SchItem)]
            self._clear_previews()
            if self.tool == 'delete':
                self.delete_objects([it.obj for it in hits])
            else:
                for it in hits:
                    it.setSelected(True)
        self._press_scene = None
        self._dragging = False

    def mouseDoubleClickEvent(self, e) -> None:      # noqa: N802
        if self.tool == 'wire' and self._wire_start is not None:
            self._cancel_wire()
            return
        if self.tool != 'select':
            return
        it = self.item_at(e.position().toPoint())
        if it is not None:
            self.edit_object.emit(it.obj)

    def _right_click(self, e) -> None:
        if self.tool == 'wire' and self._wire_start is not None:
            self._cancel_wire()
            return
        if self.tool != 'select':
            self.set_tool('select')
            return
        it = self.item_at(e.position().toPoint())
        if it is not None and not it.isSelected():
            self.scene().clearSelection()
            it.setSelected(True)
        self.context_menu.emit(it.obj if it else None, e.globalPosition().toPoint())

    #? dragging
    def _begin_drag(self) -> None:
        self._dragging = True
        sel = self.selected_items()
        anchors: set[tuple[int, int]] = set()
        for it in sel:
            o = it.obj
            if isinstance(o, Wire):
                anchors.update(o.points())
            elif isinstance(o, Flag):
                anchors.add((o.x, o.y))
            elif isinstance(o, Part):
                anchors.update(o.pin_points(self.sch.directory))
        self._stretch = []
        if self._drag_mode == 'drag':
            sel_ids = {id(it.obj) for it in sel}
            for w in self.sch.wires:
                if id(w) in sel_ids:
                    continue
                m1, m2 = w.p1 in anchors, w.p2 in anchors
                if m1 or m2:
                    self._stretch.append((self.items_by_obj[id(w)], m1, m2))

    def _drag_to(self, dx: int, dy: int) -> None:
        for it in self.selected_items():
            it.setPos(dx, dy)
        for it, m1, m2 in self._stretch:
            w = it.obj
            it.set_points(QPointF(w.x1 + dx * m1, w.y1 + dy * m1), QPointF(w.x2 + dx * m2, w.y2 + dy * m2))

    def _end_drag(self, dx: int, dy: int) -> None:
        if dx == 0 and dy == 0:
            self._drag_to(0, 0)
            return
        for it in self.selected_items():
            it.obj.transform(lambda x, y: (x + dx, y + dy))
        for it, m1, m2 in self._stretch:
            w = it.obj
            if m1:
                w.x1, w.y1 = w.x1 + dx, w.y1 + dy
            if m2:
                w.x2, w.y2 = w.x2 + dx, w.y2 + dy
        self._stretch = []
        self.commit('Move')

    #? keyboard
    def keyPressEvent(self, e) -> None:      # noqa: N802
        key, mods = e.key(), e.modifiers()
        ctrl  = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        K = Qt.Key
        if key == K.Key_Escape:
            if self.tool == 'wire' and self._wire_start is not None:
                self._cancel_wire()
            elif self.tool != 'select':
                self.set_tool('select')
            else:
                self.scene().clearSelection()
            return
        if ctrl:
            actions = {K.Key_R: self.rotate_selection, K.Key_E: self.mirror_selection, K.Key_A: self.select_all,
                       K.Key_C: self.copy_selection, K.Key_X: lambda: self.copy_selection(cut=True),
                       K.Key_V: self.paste, K.Key_Z: lambda: self.request.emit('undo'),
                       K.Key_Y: lambda: self.request.emit('redo')}
            if key in actions:
                actions[key]()
                return
            return super().keyPressEvent(e)
        if mods & Qt.KeyboardModifier.AltModifier:
            return super().keyPressEvent(e)
        simple = {
            K.Key_F2: lambda: self.request.emit('component'),
            K.Key_F3: lambda: self.set_tool('wire'),
            K.Key_F4: lambda: self.request.emit('label'),
            K.Key_F5: lambda: self.delete_selection() if self.selected_items() else self.set_tool('delete'),
            K.Key_Delete: self.delete_selection,
            K.Key_Backspace: self.delete_selection,
            K.Key_F6: self.duplicate,
            K.Key_F7: lambda: self._set_drag_mode('move'),
            K.Key_F8: lambda: self._set_drag_mode('drag'),
            K.Key_F9: lambda: self.request.emit('redo' if shift else 'undo'),
            K.Key_Space: self.fit,
            K.Key_G: lambda: self.place_flag('0'),
            K.Key_R: lambda: self.request.emit('part:res'),
            K.Key_C: lambda: self.request.emit('part:cap'),
            K.Key_L: lambda: self.request.emit('part:ind'),
            K.Key_D: lambda: self.request.emit('part:diode'),
            K.Key_T: lambda: self.request.emit('text'),
            K.Key_S: lambda: self.request.emit('directive'),
            K.Key_P: lambda: self.request.emit('probe'),
            K.Key_W: lambda: self.set_tool('wire'),
            K.Key_Plus: lambda: self.zoom(1.25),
            K.Key_Equal: lambda: self.zoom(1.25),
            K.Key_Minus: lambda: self.zoom(0.8),
        }
        if key in simple:
            simple[key]()
            return
        super().keyPressEvent(e)

    def _set_drag_mode(self, mode: str) -> None:
        self._drag_mode = mode
        self.set_tool('select')
        self.status.emit('Move: dragged objects detach from wires.' if mode == 'move'
                         else 'Drag: wires stay connected to dragged objects.')

#? -------------------------------------------------------------------------------
