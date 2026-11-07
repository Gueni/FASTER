#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                      _       ___     __           __
#?                     | |     / (_)___/ /___ ____  / /______
#?                     | | /| / / / __  / __ `/ _ \/ __/ ___/
#?                     | |/ |/ / / /_/ / /_/ /  __/ /_(__  )
#?                     |__/|__/_/\__,_/\__, /\___/\__/____/
#?                                    /____/
#?
#? Name:        widgets.py
#? Purpose:     Reusable building blocks: pages, cards, KPIs, tables, inputs, console, toasts.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Widgets shared by every page (design shared with Flash)."""

from __future__ import annotations

import html
import math
import weakref
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from PySide6.QtCore import (QAbstractTableModel, QEasingCurve, QModelIndex, QPoint, QPropertyAnimation, QRect,
                            QSize, QSortFilterProxyModel, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QComboBox, QFileDialog, QFrame,
                               QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLayout,
                               QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QTableView,
                               QToolButton, QVBoxLayout, QWidget, QWidgetItem)

from .theme import theme

_iconed: 'weakref.WeakKeyDictionary[QAbstractButton, tuple[str, str]]' = weakref.WeakKeyDictionary()


#? -------------------------------------------------------------------------------
def set_icon(button: QAbstractButton, name: str, role: str = 'text') -> None:
    _iconed[button] = (name, role)
    button.setIcon(theme().icon(name, role))


#? -------------------------------------------------------------------------------
def _refresh_icons(_palette) -> None:
    for button, (name, role) in list(_iconed.items()):
        try:
            button.setIcon(theme().icon(name, role))
        except RuntimeError:            # C++ object already deleted
            pass


theme().changed.connect(_refresh_icons)


#? -------------------------------------------------------------------------------
def button(text: str, icon_name: str | None = None, kind: str = '', tip: str = '',
           slot: Callable | None = None, big: bool = False) -> QPushButton:
    b = QPushButton(f' {text}' if icon_name and text else text)
    if kind:
        b.setProperty('kind', kind)
    if big:
        b.setProperty('size', 'big')
    if icon_name:
        set_icon(b, icon_name, {'primary': 'on-accent', 'danger': 'danger'}.get(kind, 'text'))
        b.setIconSize(QSize(18 if big else 16, 18 if big else 16))
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


#? -------------------------------------------------------------------------------
def icon_button(icon_name: str, tip: str, slot: Callable | None = None, checkable: bool = False,
                role: str = 'text', overlay: bool = False) -> QToolButton:
    b = QToolButton()
    b.setObjectName('Overlay' if overlay else 'Ghost')
    set_icon(b, icon_name, role)
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


#? -------------------------------------------------------------------------------
def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    for child in w.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)


#? -------------------------------------------------------------------------------
def label(text: str = '', name: str = '', wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


#? -------------------------------------------------------------------------------
#? layouts
class FlowLayout(QLayout):
    """Lays widgets out left-to-right and wraps to new lines when space runs out."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing     = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:      # noqa: N802
        self._items.append(item)

    def addWidget(self, w: QWidget) -> None:      # noqa: N802
        self.addChildWidget(w)
        self.addItem(QWidgetItem(w))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):      # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):      # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):      # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:      # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:      # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect: QRect) -> None:      # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self) -> QSize:      # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:      # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, test: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = r.x(), r.y(), 0
        for item in self._items:
            if item.widget() is not None and item.widget().isHidden():
                continue
            hint   = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > r.right() + 1 and line_h > 0:
                x, y   = r.x(), y + line_h + self._spacing
                next_x = x + hint.width() + self._spacing
                line_h = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x      = next_x
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


#? -------------------------------------------------------------------------------
class ResponsiveGrid(QWidget):
    """Arranges cards in 1..N columns depending on the available width."""

    def __init__(self, min_column_width: int = 440, max_columns: int = 3, parent=None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(16)
        self._cards: list[tuple[QWidget, int]] = []
        self._min_w    = min_column_width
        self._max_cols = max_columns
        self._cols     = 0

    def add(self, card: QWidget, span: int = 1) -> QWidget:
        self._cards.append((card, span))
        self._relayout(force=True)
        return card

    def resizeEvent(self, event) -> None:      # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self, force: bool = False) -> None:
        width = max(self.width(), 1)
        cols  = max(1, min(self._max_cols, width // self._min_w))
        if cols == self._cols and not force:
            return
        self._cols = cols
        while self._grid.count():
            self._grid.takeAt(0)
        for c in range(self._max_cols):
            self._grid.setColumnStretch(c, 1 if c < cols else 0)
        row = col = 0
        for card, span in self._cards:
            span = min(span, cols)
            if col + span > cols:
                row, col = row + 1, 0
            self._grid.addWidget(card, row, col, 1, span, Qt.AlignmentFlag.AlignTop)
            col += span
            if col >= cols:
                row, col = row + 1, 0
        self._grid.setRowStretch(row + 1, 1)


#? -------------------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, title: str, subtitle: str = '', icon_name: str | None = None, parent=None,
                 expand: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName('Card')
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding if expand else QSizePolicy.Policy.Maximum)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 20)
        outer.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(10)
        self._icon = None
        if icon_name:
            ico        = QLabel()
            self._icon = (ico, icon_name)
            head.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = label(title, 'CardTitle')
        texts.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, 'CardSubtitle', wrap=True)
        self.subtitle_label.setVisible(bool(subtitle))
        texts.addWidget(self.subtitle_label)
        head.addLayout(texts, 1)
        self.header_actions = QHBoxLayout()
        self.header_actions.setSpacing(4)
        head.addLayout(self.header_actions)
        outer.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        outer.addLayout(self.body, 1 if expand else 0)
        self._paint_icon()
        theme().changed.connect(lambda *_: self._paint_icon())

    def _paint_icon(self) -> None:
        if self._icon is not None:
            lab, name = self._icon
            lab.setPixmap(theme().icon(name, theme().palette.accent).pixmap(QSize(20, 20)))

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def add(self, item, stretch: int = 0) -> None:
        if isinstance(item, QLayout):
            self.body.addLayout(item, stretch)
        else:
            self.body.addWidget(item, stretch)


#? -------------------------------------------------------------------------------
class BasePage(QWidget):
    """A page of the main window (full-height layout)."""

    title     = ''
    subtitle  = ''
    icon_name = 'info'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._actions: list[QWidget] = []

    def busy_actions(self, *widgets: QWidget) -> None:
        """Widgets disabled while an analysis is running."""
        self._actions.extend(widgets)

    def set_busy(self, busy: bool) -> None:
        for w in self._actions:
            w.setEnabled(not busy)


#? -------------------------------------------------------------------------------
class ScrollPage(BasePage):
    """A scrollable page holding a responsive grid of cards."""

    min_column_width = 440
    max_columns      = 3

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName('PageBody')
        self.layout_ = QVBoxLayout(body)
        self.layout_.setContentsMargins(24, 20, 24, 24)
        self.layout_.setSpacing(16)
        self.grid = ResponsiveGrid(self.min_column_width, self.max_columns)
        self.layout_.addWidget(self.grid)
        self.layout_.addStretch(1)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll)


#? -------------------------------------------------------------------------------
def field(text: str, widget: QWidget, hint: str = '') -> QWidget:
    w   = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(label(text.upper(), 'FieldLabel'))
    lay.addWidget(widget)
    if hint:
        lay.addWidget(label(hint, 'Hint', wrap=True))
    return w


#? -------------------------------------------------------------------------------
def row(*widgets: QWidget, stretch: list[int] | None = None, spacing: int = 12) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    for i, w in enumerate(widgets):
        if w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w, (stretch or [1] * len(widgets))[i])
    return lay


#? -------------------------------------------------------------------------------
def flow(*widgets: QWidget, spacing: int = 8) -> QWidget:
    holder = QWidget()
    fl     = FlowLayout(holder, spacing)
    for w in widgets:
        fl.addWidget(w)
    return holder


#? -------------------------------------------------------------------------------
def combo(items: list[str], current: str | None = None, editable: bool = False) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setEditable(editable)
    if current is not None:
        idx = c.findText(current)
        if idx >= 0:
            c.setCurrentIndex(idx)
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(6)
    return c


#? -------------------------------------------------------------------------------
class PathField(QWidget):
    """Path input with a browse button; accepts drag-and-drop."""

    changed = Signal(str)

    def __init__(self, placeholder: str = 'Select…', filters: str = 'All files (*)', directory: bool = False,
                 caption: str = 'Select') -> None:
        super().__init__()
        self._filters, self._dir, self._caption = filters, directory, caption
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self.changed)
        self.edit.textChanged.connect(self._check)
        lay.addWidget(self.edit, 1)
        lay.addWidget(icon_button('folder', 'Browse…', self.pick))
        self.setAcceptDrops(True)

    def _check(self) -> None:
        t   = self.edit.text().strip()
        bad = bool(t) and not (Path(t).is_dir() if self._dir else Path(t).is_file())
        if bool(self.edit.property('invalid')) != bad:
            self.edit.setProperty('invalid', bad)
            repolish(self.edit)

    def pick(self) -> str:
        start = self.text() or str(Path.home())
        if self._dir:
            path = QFileDialog.getExistingDirectory(self, self._caption, start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._caption, start, self._filters)
        if path:
            self.edit.setText(path)
        return path

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, text: str) -> None:      # noqa: N802
        self.edit.setText(text)

    def dragEnterEvent(self, e) -> None:      # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:      # noqa: N802
        urls = e.mimeData().urls()
        if urls:
            self.edit.setText(urls[0].toLocalFile())


#? -------------------------------------------------------------------------------
#? feedback
class StatusPill(QLabel):
    def __init__(self, text: str = '', state: str = 'idle') -> None:
        super().__init__(text)
        self.setObjectName('Pill')
        self.set_state(text, state)

    def set_state(self, text: str, state: str) -> None:
        self.setText(text)
        if self.property('state') != state:
            self.setProperty('state', state)
            self.style().unpolish(self)
            self.style().polish(self)


#? -------------------------------------------------------------------------------
class KpiCard(QFrame):
    """Big number with a caption; ``state`` pass / fail colours it green / red."""

    def __init__(self, caption: str, value: str = '-', sub: str = '') -> None:
        super().__init__()
        self.setObjectName('Kpi')
        self.setMinimumWidth(150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.caption = label(caption.upper(), 'KpiLabel')
        self.value   = label(value, 'KpiValue')
        self.sub     = label(sub, 'KpiSub', wrap=True)
        lay.addWidget(self.caption)
        lay.addWidget(self.value)
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = '', state: str = '') -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        if self.property('state') != state:
            self.setProperty('state', state)
            repolish(self)


#? -------------------------------------------------------------------------------
class Toast(QLabel):
    """Transient notification shown in the bottom-right corner of its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName('Toast')
        self.setWordWrap(True)
        self.setMaximumWidth(440)
        self.hide()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b'opacity', self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self._fade_out)
        self._hide_connected = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def show_message(self, text: str, kind: str = 'info', ms: int = 3500) -> None:
        self.setText(text)
        self.setProperty('kind', kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        self.place()
        self.show()
        self.raise_()
        self._anim.stop()
        if self._hide_connected:
            self._anim.finished.disconnect(self.hide)
            self._hide_connected = False
        self._anim.setStartValue(self._effect.opacity() if self.isVisible() else 0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms)

    def place(self) -> None:
        p = self.parentWidget()
        if p is not None:
            self.move(p.width() - self.width() - 24, p.height() - self.height() - 52)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        if not self._hide_connected:
            self._anim.finished.connect(self.hide)
            self._hide_connected = True
        self._anim.start()


#? -------------------------------------------------------------------------------
class Console(QPlainTextEdit):
    """Read-only log with coloured lines."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('Console')
        self.setReadOnly(True)
        self.setMaximumBlockCount(20000)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setUndoRedoEnabled(False)
        self.autoscroll = True

    def append_line(self, text: str, kind: str = 'info') -> None:
        p     = theme().palette
        color = {'error': p.danger, 'warning': p.warning, 'success': p.success, 'command': p.accent,
                 'muted': p.muted}.get(kind)
        safe  = html.escape(text) or '&nbsp;'
        if kind == 'command':
            safe = f'<b>{safe}</b>'
        self.appendHtml(f'<span style="color:{color}">{safe}</span>' if color else
                        f'<span style="white-space:pre-wrap">{safe}</span>')
        if self.autoscroll:
            bar = self.verticalScrollBar()
            bar.setValue(bar.maximum())


#? -------------------------------------------------------------------------------
#? tables
def _fmt(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float):
        if math.isnan(value):
            return ''
        return f'{value:.6g}'
    return str(value)


#? -------------------------------------------------------------------------------
class DataFrameModel(QAbstractTableModel):
    """Read-only pandas model; PASS / FAIL cells are coloured, numbers right-aligned and sortable."""

    def __init__(self, df: pd.DataFrame | None = None) -> None:
        super().__init__()
        self._df  = pd.DataFrame()
        self._num: set[int] = set()
        if df is not None:
            self.set_frame(df)

    def set_frame(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df  = df.reset_index(drop=True)
        self._num = {i for i, c in enumerate(self._df.columns) if pd.api.types.is_numeric_dtype(self._df[c])
                     and not pd.api.types.is_bool_dtype(self._df[c])}
        self.endResetModel()

    def frame(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent=QModelIndex()) -> int:      # noqa: N802
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:      # noqa: N802
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._df.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return _fmt(value)
        if role == Qt.ItemDataRole.UserRole:          # sort key
            return value if index.column() in self._num else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in self._num:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            text = _fmt(value)
            return text if len(text) > 40 else None
        if role in (Qt.ItemDataRole.ForegroundRole, Qt.ItemDataRole.BackgroundRole):
            v = str(value).strip().upper()
            p = theme().palette
            if v in ('PASS', 'FAIL'):
                if role == Qt.ItemDataRole.ForegroundRole:
                    return QColor(p.success if v == 'PASS' else p.danger)
                return QColor(p.success_soft if v == 'PASS' else p.danger_soft)
        if role == Qt.ItemDataRole.FontRole and str(value).strip().upper() in ('PASS', 'FAIL'):
            from PySide6.QtGui import QFont
            f = QFont()
            f.setBold(True)
            return f
        return None

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):      # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._df.columns[section]) if section < len(self._df.columns) else None
            return str(section + 1)
        return None


#? -------------------------------------------------------------------------------
class DataTable(QTableView):
    """Sortable, filterable table showing a DataFrame."""

    def __init__(self, df: pd.DataFrame | None = None, stretch_last: bool = True) -> None:
        super().__init__()
        self.model_ = DataFrameModel(df)
        self.proxy  = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model_)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.setModel(self.proxy)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        self.horizontalHeader().setStretchLastSection(stretch_last)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.sortByColumn(-1, Qt.SortOrder.AscendingOrder)

    def set_frame(self, df: pd.DataFrame) -> None:
        self.model_.set_frame(df)
        self.resizeColumnsToContents()
        for c in range(self.model_.columnCount()):
            if self.columnWidth(c) > 380:
                self.setColumnWidth(c, 380)

    def set_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)

#? -------------------------------------------------------------------------------
