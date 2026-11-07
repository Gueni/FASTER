# Purpose:     Circuit page: open, view and edit the LTspice schematic (values and SPICE directives).
"""Circuit page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget, QFrame)

from ...knowledge.failures import FAILURE_MODES
from .. import settings
from ..schematic_view import SchematicPanel
from ..theme import schematic_colors, theme
from ..widgets import BasePage, Card, button, icon_button, label

COLS = ['Component', 'Type', 'Value', 'Attributes', 'Modes']


#? -------------------------------------------------------------------------------
class DropZone(QFrame):
    """Empty state: big drop target with open button and recent files."""

    def __init__(self, page: 'CircuitPage') -> None:
        super().__init__()
        self.setObjectName('DropZone')
        self.page = page
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(14)
        lay.addStretch(1)
        title = label('Open an LTspice schematic', 'BigTitle')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)
        sub = label('Drop a .asc file here, or pick one. FASTER shows the circuit, lets you edit values and '
                    'directives, and runs FMEDA, ISO 26262 metrics, FTA, worst-case and Monte Carlo analyses.',
                    'Hint', wrap=True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setMaximumWidth(560)
        lay.addWidget(sub, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(button('Open schematic…', 'open', 'primary', slot=page.ctx.open_dialog, big=True),
                      0, Qt.AlignmentFlag.AlignHCenter)
        self.recent = QVBoxLayout()
        self.recent.setSpacing(4)
        lay.addLayout(self.recent)
        lay.addStretch(2)

    def refresh(self) -> None:
        while self.recent.count():
            w = self.recent.takeAt(0).widget()
            if w:
                w.deleteLater()
        files = settings.recent_files()
        if files:
            head = label('RECENT', 'FieldLabel')
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.recent.addWidget(head)
        for path in files[:6]:
            b = button(Path(path).name, 'file', 'ghost', tip=path,
                       slot=lambda _=False, p=path: self.page.ctx.open_path(p))
            self.recent.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)

    def _set_active(self, on: bool) -> None:
        self.setProperty('active', on)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e) -> None:      # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, e) -> None:      # noqa: N802
        self._set_active(False)

    def dropEvent(self, e) -> None:      # noqa: N802
        self._set_active(False)
        for url in e.mimeData().urls():
            if url.toLocalFile().lower().endswith('.asc'):
                self.page.ctx.open_path(url.toLocalFile())
                return


#? -------------------------------------------------------------------------------
class CircuitPage(BasePage):
    title     = 'Circuit'
    subtitle  = 'View the schematic, edit component values and SPICE directives'
    icon_name = 'circuit'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        self.session  = ctx.session
        self._loading = False
        self.setAcceptDrops(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.open_btn = button('Open', 'open', tip='Open a schematic (Ctrl+O)', slot=ctx.open_dialog)
        self.recent_menu = QMenu(self)
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        self.recent_btn = icon_button('history', 'Recent schematics')
        self.recent_btn.setPopupMode(self.recent_btn.ToolButtonPopupMode.InstantPopup)
        self.recent_btn.setMenu(self.recent_menu)
        self.save_btn   = button('Save', 'save', tip='Save edits to the schematic (Ctrl+S)', slot=ctx.save)
        self.saveas_btn = button('Save as…', 'save-as', slot=ctx.save_as)
        self.revert_btn = button('Revert', 'undo', tip='Discard unsaved edits', slot=ctx.revert)
        self.ltspice_btn = button('Open in LTspice', 'external', 'ghost', slot=ctx.open_in_ltspice)
        for w in (self.open_btn, self.recent_btn, self.save_btn, self.saveas_btn, self.revert_btn):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(self.ltspice_btn)
        outer.addLayout(bar)
        self.busy_actions(self.open_btn, self.save_btn, self.saveas_btn, self.revert_btn)

        self.drop = DropZone(self)
        outer.addWidget(self.drop, 1)

        # main area
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.schematic = SchematicPanel()
        self.schematic.setMinimumWidth(360)
        self.split.addWidget(self.schematic)

        side = QWidget()
        sv   = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(12)
        self.comp_card = Card('Components', 'Double-click a value to edit it, or double-click the part in '
                              'the schematic.', 'list', expand=True)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter components…')
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        self.comp_card.add(self.filter)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                   | QAbstractItemView.EditTrigger.EditKeyPressed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._item_changed)
        self.table.itemSelectionChanged.connect(self._row_selected)
        self.comp_card.add(self.table, 1)
        sv.addWidget(self.comp_card, 3)

        self.dir_card = Card('SPICE directives', 'Analysis commands, parameters, models. Double-click to edit.',
                             'zap')
        self.dir_list = QListWidget()
        self.dir_list.setMinimumHeight(110)
        self.dir_list.itemChanged.connect(self._directive_changed)
        self.dir_card.add(self.dir_list)
        db = QHBoxLayout()
        db.addWidget(button('Add', 'plus', slot=self._add_directive))
        db.addWidget(button('Remove', 'trash', slot=self._remove_directive))
        db.addStretch(1)
        self.dir_card.add(db)
        sv.addWidget(self.dir_card, 1)
        side.setMinimumWidth(380)
        self.split.addWidget(side)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        outer.addWidget(self.split, 1)

        self._render_timer = QTimer(self, singleShot=True, interval=90)
        self._render_timer.timeout.connect(self._render)
        self.schematic.view.part_clicked.connect(self._select_row)
        self.schematic.view.part_activated.connect(self._edit_part)
        self.session.loaded.connect(lambda *_: self.reload())
        self.session.changed.connect(self._content_changed)
        self.session.closed.connect(self.reload)
        self.session.modified_changed.connect(self._sync_buttons)
        theme().changed.connect(lambda *_: self.session.is_open and self._render_timer.start())
        self.reload()

    # -- refresh -----------------------------------------------------------------------
    def reload(self) -> None:
        has = self.session.is_open
        self.drop.setVisible(not has)
        self.split.setVisible(has)
        for w in (self.save_btn, self.saveas_btn, self.revert_btn, self.ltspice_btn):
            w.setVisible(has)
        self.drop.refresh()
        if has:
            self._fill_table()
            self._fill_directives()
            self._render()
        self._sync_buttons()

    def _content_changed(self) -> None:
        self._fill_table(keep_selection=True)
        self._fill_directives()
        self._render_timer.start()

    def _sync_buttons(self, *_) -> None:
        mod = self.session.modified
        self.save_btn.setEnabled(mod)
        self.revert_btn.setEnabled(mod)

    def _tips(self) -> dict[str, str]:
        tips = {}
        for c in self.session.components():
            extra = ', '.join(f'{k}={v}' for k, v in c['attributes'].items() if k not in ('InstName', 'Value'))
            tips[c['name']] = f"{c['name']}  ·  {c['type']}  ·  {c['value'] or '-'}" + (f'\n{extra}' if extra else '')
        return tips

    def _render(self) -> None:
        if not self.session.is_open:
            return
        try:
            rendering = self.session.rendering(schematic_colors(theme().palette))
        except Exception as exc:                      # malformed schematic: keep the tables usable
            self.ctx.log(f'Schematic preview failed: {exc}', 'warning')
            return
        self.schematic.set_rendering(rendering, self._tips())

    def _fill_table(self, keep_selection: bool = False) -> None:
        selected = self._current_name() if keep_selection else ''
        self._loading = True
        comps = self.session.components()
        self.table.setRowCount(len(comps))
        for r, c in enumerate(comps):
            attrs = ', '.join(f'{k}={v}' for k, v in c['attributes'].items() if k not in ('InstName', 'Value'))
            entry = FAILURE_MODES.get(c['type'])
            cells = [c['name'], c['type'], c['value'] or '', attrs, str(len(entry.modes)) if entry else '-']
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col != 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setToolTip('Double-click to edit the value')
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, col, item)
        self._loading = False
        self._apply_filter(self.filter.text())
        if selected:
            self._select_row(selected)

    def _fill_directives(self) -> None:
        self._loading = True
        self.dir_list.clear()
        for idx, text in self.session.directives():
            item = QListWidgetItem(text.replace('\n', ' ⏎ '))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.dir_list.addItem(item)
        self._loading = False

    def _apply_filter(self, text: str) -> None:
        t = text.lower().strip()
        for r in range(self.table.rowCount()):
            hit = not t or any(t in (self.table.item(r, c).text().lower() if self.table.item(r, c) else '')
                               for c in range(self.table.columnCount()))
            self.table.setRowHidden(r, not hit)

    # -- interaction ---------------------------------------------------------------------
    def _current_name(self) -> str:
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        return it.text() if it else ''

    def _row_selected(self) -> None:
        name = self._current_name()
        if name:
            self.schematic.view.focus_part(name)

    def _select_row(self, name: str) -> None:
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0) and self.table.item(r, 0).text() == name:
                self.table.blockSignals(True)
                self.table.selectRow(r)
                self.table.blockSignals(False)
                self.table.scrollToItem(self.table.item(r, 0))
                self.schematic.view.select(name)
                return

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != 2:
            return
        name = self.table.item(item.row(), 0).text()
        if item.text().strip():
            self.session.set_value(name, item.text())
            self.ctx.log(f'{name} value set to {item.text().strip()}', 'muted')

    def _edit_part(self, name: str) -> None:
        comp = next((c for c in self.session.components() if c['name'] == name), None)
        if comp is None:
            return
        value, ok = QInputDialog.getText(self, f'Edit {name}', f'{name} ({comp["type"]}) value:',
                                         QLineEdit.EchoMode.Normal, comp['value'] or '')
        if ok and value.strip() and value.strip() != (comp['value'] or ''):
            self.session.set_value(name, value)
            self.ctx.log(f'{name} value set to {value.strip()}', 'muted')

    def _directive_changed(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        self.session.set_directive(idx, item.text().replace(' ⏎ ', '\n'))

    def _add_directive(self) -> None:
        text, ok = QInputDialog.getText(self, 'Add directive', 'SPICE directive (e.g. .param k=2, .tran 10m):')
        if ok and text.strip():
            self.session.add_directive(text if text.strip().startswith('.') else '.' + text.strip())

    def _remove_directive(self) -> None:
        item = self.dir_list.currentItem()
        if item is not None:
            self.session.remove_directive(item.data(Qt.ItemDataRole.UserRole))

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        files = settings.recent_files()
        if not files:
            self.recent_menu.addAction('No recent schematics').setEnabled(False)
        for path in files:
            self.recent_menu.addAction(Path(path).name, lambda p=path: self.ctx.open_path(p)).setToolTip(path)

    # -- drag & drop on the whole page -----------------------------------------------------
    def dragEnterEvent(self, e) -> None:      # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:      # noqa: N802
        for url in e.mimeData().urls():
            if url.toLocalFile().lower().endswith('.asc'):
                self.ctx.open_path(url.toLocalFile())
                return
