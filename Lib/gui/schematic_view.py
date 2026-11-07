# Purpose:     Interactive schematic viewer: zoom, pan, hover and click on components.
"""Schematic viewer.

The schematic is drawn by :mod:`Lib.schematic.renderer` (theme coloured SVG)
and shown in a QGraphicsView. Every part gets an invisible hot-spot: hovering
highlights it, a click selects it, a double click asks to edit its value.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (QFrame, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
                               QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from ..schematic.renderer import Rendering
from .theme import theme
from .widgets import icon_button

PAD = 8        # hot-spot padding around a part (schematic units)


#? -------------------------------------------------------------------------------
class _HotSpot(QGraphicsRectItem):
    def __init__(self, view: 'SchematicView', name: str, rect: QRectF, tip: str) -> None:
        super().__init__(rect)
        self.view, self.name = view, name
        self.setAcceptHoverEvents(True)
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(10)
        self.hovered = False
        self.selected = False
        self.restyle()

    def restyle(self) -> None:
        p = theme().palette
        if self.selected:
            color = QColor(p.accent)
            self.setPen(QPen(color, 2.5))
            fill = QColor(p.accent)
            fill.setAlpha(45)
            self.setBrush(QBrush(fill))
        elif self.hovered:
            color = QColor(p.accent)
            color.setAlpha(170)
            self.setPen(QPen(color, 1.8, Qt.PenStyle.DashLine))
            fill = QColor(p.accent)
            fill.setAlpha(22)
            self.setBrush(QBrush(fill))
        else:
            self.setPen(QPen(Qt.PenStyle.NoPen))
            self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    def hoverEnterEvent(self, event) -> None:      # noqa: N802
        self.hovered = True
        self.restyle()
        self.view.hovered.emit(self.name)

    def hoverLeaveEvent(self, event) -> None:      # noqa: N802
        self.hovered = False
        self.restyle()
        self.view.hovered.emit('')

    def mousePressEvent(self, event) -> None:      # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.view.select(self.name)
            self.view.part_clicked.emit(self.name)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:      # noqa: N802
        self.view.part_activated.emit(self.name)
        event.accept()


#? -------------------------------------------------------------------------------
class SchematicView(QGraphicsView):
    part_clicked   = Signal(str)
    part_activated = Signal(str)
    hovered        = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
                            | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._svg_item: QGraphicsSvgItem | None = None
        self._renderer: QSvgRenderer | None = None
        self._spots: dict[str, _HotSpot] = {}
        self._selected = ''
        self._fitted   = False
        theme().changed.connect(lambda *_: self._apply_bg())
        self._apply_bg()

    def _apply_bg(self) -> None:
        self.setBackgroundBrush(QBrush(QColor(theme().palette.sheet)))
        for spot in self._spots.values():
            spot.restyle()

    def set_rendering(self, rendering: Rendering, tips: dict[str, str] | None = None, keep_view: bool = True) -> None:
        """Show a new rendering; keeps zoom / scroll position when the layout is unchanged."""
        old_transform = self.transform()
        old_center    = self.mapToScene(self.viewport().rect().center())
        same_box      = self._renderer is not None and getattr(self, '_viewbox', None) == rendering.viewbox
        scene = self.scene()
        scene.clear()
        self._spots.clear()
        self._renderer = QSvgRenderer(QByteArray(rendering.svg.encode('utf-8')), self)
        self._svg_item = QGraphicsSvgItem()
        self._svg_item.setSharedRenderer(self._renderer)
        x0, y0, w, h = rendering.viewbox
        self._viewbox = rendering.viewbox
        self._svg_item.setPos(x0, y0)
        scene.addItem(self._svg_item)
        scene.setSceneRect(QRectF(x0 - 200, y0 - 200, w + 400, h + 400))
        for name, (bx0, by0, bx1, by1) in rendering.parts.items():
            rect = QRectF(bx0 - PAD, by0 - PAD, (bx1 - bx0) + 2 * PAD, (by1 - by0) + 2 * PAD)
            spot = _HotSpot(self, name, rect, (tips or {}).get(name, name))
            spot.selected = name == self._selected
            spot.restyle()
            scene.addItem(spot)
            self._spots[name] = spot
        if keep_view and same_box and self._fitted:
            self.setTransform(old_transform)
            self.centerOn(old_center)
        else:
            self.fit()

    def clear(self) -> None:
        self.scene().clear()
        self._spots.clear()
        self._renderer = None
        self._fitted   = False

    def select(self, name: str) -> None:
        self._selected = name
        for n, spot in self._spots.items():
            spot.selected = n == name
            spot.restyle()

    def focus_part(self, name: str) -> None:
        self.select(name)
        spot = self._spots.get(name)
        if spot is not None:
            self.ensureVisible(spot, 80, 80)

    def fit(self) -> None:
        if self._svg_item is None:
            return
        self.resetTransform()
        rect = self._svg_item.sceneBoundingRect().adjusted(-20, -20, 20, 20)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._fitted = True

    def zoom(self, factor: float) -> None:
        current = self.transform().m11()
        if 0.05 < current * factor < 40:
            self.scale(factor, factor)

    def wheelEvent(self, event) -> None:      # noqa: N802
        self.zoom(1.0015 ** event.angleDelta().y())

    def resizeEvent(self, event) -> None:      # noqa: N802
        super().resizeEvent(event)
        if not self._fitted:
            self.fit()


#? -------------------------------------------------------------------------------
class SchematicPanel(QFrame):
    """Viewer with floating zoom controls and a hover read-out."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('Viewer')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        self.view = SchematicView()
        lay.addWidget(self.view)
        self.empty = QLabel('Open or drop an LTspice schematic (.asc)', self)
        self.empty.setObjectName('Empty')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.tools = QWidget(self)
        tl = QHBoxLayout(self.tools)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        for name, tip, slot in (('zoom-in', 'Zoom in', lambda: self.view.zoom(1.25)),
                                ('zoom-out', 'Zoom out', lambda: self.view.zoom(0.8)),
                                ('fit', 'Fit to window', self.view.fit)):
            tl.addWidget(icon_button(name, tip, slot, overlay=True))
        self.readout = QLabel('', self)
        self.readout.setObjectName('Chip')
        self.readout.hide()
        self.view.hovered.connect(self._hover)
        self._tips: dict[str, str] = {}
        self.show_empty(True)

    def _hover(self, name: str) -> None:
        if name:
            self.readout.setText(self._tips.get(name, name).replace('\n', '   ·   '))
            self.readout.adjustSize()
            self.readout.show()
            self._place()
        else:
            self.readout.hide()

    def show_empty(self, empty: bool) -> None:
        self.empty.setVisible(empty)
        self.view.setVisible(not empty)
        self.tools.setVisible(not empty)

    def set_rendering(self, rendering: Rendering, tips: dict[str, str]) -> None:
        self._tips = tips
        self.show_empty(False)
        self.view.set_rendering(rendering, tips)

    def _place(self) -> None:
        self.tools.adjustSize()
        self.tools.move(self.width() - self.tools.width() - 12, 12)
        self.readout.move(12, self.height() - self.readout.height() - 12)
        self.empty.setGeometry(self.rect())

    def resizeEvent(self, event) -> None:      # noqa: N802
        super().resizeEvent(event)
        self._place()
