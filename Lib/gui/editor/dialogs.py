#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#? Name:        dialogs.py
#? Purpose:     Editor dialogs: component browser, attributes, labels, text, simulation command.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------

from __future__ import annotations

import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGraphicsScene, QGraphicsView, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QRadioButton, QSplitter, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ...schematic.model import Part
from ...schematic.symbols import Symbol, library_symbols, load_symbol_file
from ..theme import theme
from .graphics import Colors, PartItem


#? -------------------------------------------------------------------------------
def _buttons(dlg: QDialog, ok: str = 'OK') -> QDialogButtonBox:
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    box.button(QDialogButtonBox.StandardButton.Ok).setText(ok)
    box.button(QDialogButtonBox.StandardButton.Ok).setProperty('kind', 'primary')
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    return box


def _mono(w: QWidget) -> None:
    f = w.font()
    f.setFamily(theme().mono)
    w.setFont(f)


def name_prefix(sym: Symbol) -> str:
    """Instance-name prefix LTspice uses for a symbol (X subcircuits are called U1, U2...)."""
    prefix = (sym.attrs.get('Prefix') or 'X').strip()
    return 'U' if prefix.upper().startswith('X') else prefix[0].upper()


#? -------------------------------------------------------------------------------
class SymbolPreview(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setMinimumSize(260, 220)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def show_symbol(self, sym: Symbol | None, name: str = '') -> None:
        self.scene().clear()
        colors = Colors.from_palette(theme().palette)
        self.setBackgroundBrush(QColor(colors.sheet))
        if sym is None:
            return
        part = Part(name or sym.name, 0, 0, 'R0', {'InstName': name_prefix(sym) + '1'})
        item = PartItem(part, sym, colors)
        item.setAcceptHoverEvents(False)
        self.scene().addItem(item)
        rect = item.boundingRect().adjusted(-24, -24, 24, 24)
        self.scene().setSceneRect(rect)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 2.5:
            self.resetTransform()
            self.scale(2.5, 2.5)

    def resizeEvent(self, e) -> None:      # noqa: N802
        super().resizeEvent(e)
        if self.scene().items():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


#? -------------------------------------------------------------------------------
class SymbolBrowser(QDialog):
    """Pick a symbol from the LTspice library (F2)."""
    _last = 'res'

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Select component symbol')
        self.resize(820, 560)
        self.choice: str | None = None
        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search symbols (e.g. LT1001, nmos, res)…')
        self.search.setClearButtonEnabled(True)
        lay.addWidget(self.search)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        split.addWidget(self.tree)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        self.preview = SymbolPreview()
        rv.addWidget(self.preview, 1)
        self.title = QLabel()
        self.title.setObjectName('CardTitle')
        rv.addWidget(self.title)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setObjectName('Hint')
        rv.addWidget(self.desc)
        split.addWidget(right)
        split.setSizes([360, 460])
        lay.addWidget(split, 1)
        lay.addWidget(_buttons(self, 'Place'))
        self._items: list[tuple[str, QTreeWidgetItem]] = []
        self._fill()
        self._timer = QTimer(self, singleShot=True, interval=150)
        self._timer.timeout.connect(self._filter)
        self.search.textChanged.connect(lambda *_: self._timer.start())
        self.tree.currentItemChanged.connect(self._current)
        self.tree.itemDoubleClicked.connect(lambda it, _c: it.data(0, Qt.ItemDataRole.UserRole) and self.accept())
        self.search.setFocus()

    def _fill(self) -> None:
        folders: dict[str, QTreeWidgetItem] = {}
        top: list[QTreeWidgetItem] = []
        select = None
        for rel, path in library_symbols():
            parts = rel.split('\\')
            parent = None
            for i in range(len(parts) - 1):
                key = '\\'.join(parts[:i + 1]).lower()
                if key not in folders:
                    f = QTreeWidgetItem([parts[i]])
                    f.setIcon(0, theme().icon('folder', 'muted'))
                    (parent.addChild(f) if parent else top.append(f))
                    folders[key] = f
                parent = folders[key]
            it = QTreeWidgetItem([parts[-1]])
            it.setData(0, Qt.ItemDataRole.UserRole, rel)
            it.setData(0, Qt.ItemDataRole.UserRole + 1, str(path))
            (parent.addChild(it) if parent else top.append(it))
            self._items.append((rel.lower(), it))
            if rel.lower() == self._last.lower():
                select = it
        folders_first = sorted([t for t in top if t.childCount()], key=lambda t: t.text(0).lower()) + \
                        [t for t in top if not t.childCount()]
        self.tree.addTopLevelItems(folders_first)
        if select:
            self.tree.setCurrentItem(select)

    def _filter(self) -> None:
        t = self.search.text().strip().lower()
        self.tree.setUpdatesEnabled(False)
        first = None
        def visit(item: QTreeWidgetItem) -> bool:
            nonlocal first
            if item.childCount():
                any_child = False
                for i in range(item.childCount()):
                    any_child |= visit(item.child(i))
                item.setHidden(not any_child)
                item.setExpanded(bool(t) and any_child)
                return any_child
            rel = (item.data(0, Qt.ItemDataRole.UserRole) or '').lower()
            hit = not t or t in rel
            item.setHidden(not hit)
            if hit and t and first is None:
                first = item
            return hit
        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))
        self.tree.setUpdatesEnabled(True)
        if first is not None:
            self.tree.setCurrentItem(first)

    def _current(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        rel = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not rel:
            self.preview.show_symbol(None)
            self.title.setText(item.text(0) if item else '')
            self.desc.setText('')
            return
        from pathlib import Path
        sym = load_symbol_file(Path(item.data(0, Qt.ItemDataRole.UserRole + 1)), rel)
        self.preview.show_symbol(sym if sym.found else None, rel)
        self.title.setText(rel)
        info = [sym.attrs.get('Description', '')]
        if sym.attrs.get('Prefix'):
            info.append(f"Prefix {sym.attrs['Prefix']}  ·  {len(sym.pins)} pins")
        if sym.attrs.get('Value'):
            info.append(f"Default value: {sym.attrs['Value']}")
        if not sym.found:
            info.append('This symbol cannot be drawn (encrypted or unsupported format).')
        self.desc.setText('\n'.join(i for i in info if i))

    def accept(self) -> None:
        item = self.tree.currentItem()
        rel  = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not rel:
            return
        self.choice = rel
        SymbolBrowser._last = rel
        super().accept()


#? -------------------------------------------------------------------------------
#? independent sources: LTspice "Advanced" source functions
SOURCE_FUNCTIONS: dict[str, list[str]] = {
    '(none)': ['DC value'],
    'PULSE' : ['V1 / I1 (initial)', 'V2 / I2 (on)', 'Tdelay', 'Trise', 'Tfall', 'Ton', 'Tperiod', 'Ncycles'],
    'SINE'  : ['DC offset', 'Amplitude', 'Freq', 'Tdelay', 'Theta (damping)', 'Phi (deg)', 'Ncycles'],
    'EXP'   : ['V1 / I1', 'V2 / I2', 'Td1', 'Tau1', 'Td2', 'Tau2'],
    'SFFM'  : ['DC offset', 'Amplitude', 'Carrier freq', 'Modulation index', 'Signal freq'],
    'PWL'   : ['Points (t1 v1 t2 v2 …)'],
}
_FUNC_RE = re.compile(r'^\s*(PULSE|SINE|SIN|EXP|SFFM|PWL)\s*\((.*?)\)\s*(.*)$', re.I | re.S)


def _split_ac(rest: str) -> tuple[str, str, str]:
    """``'AC 1 0 Rser=1'`` -> (amplitude, phase, remainder)."""
    m = re.search(r'\bAC\s+(\S+)(?:\s+([-+\d.eE]+))?', rest, re.I)
    if not m:
        return '', '', rest.strip()
    remainder = (rest[:m.start()] + rest[m.end():]).strip()
    return m.group(1), m.group(2) or '', remainder


class SourceEditor(QWidget):
    """Function editor for voltage / current sources."""

    def __init__(self, value: str, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.func = QComboBox()
        self.func.addItems(list(SOURCE_FUNCTIONS))
        form = QFormLayout()
        form.addRow('Function', self.func)
        lay.addLayout(form)
        self.stack = QStackedWidget()
        self.fields: dict[str, list[QLineEdit]] = {}
        for name, params in SOURCE_FUNCTIONS.items():
            page = QWidget()
            fl = QFormLayout(page)
            fl.setContentsMargins(0, 0, 0, 0)
            self.fields[name] = []
            for p in params:
                e = QLineEdit()
                fl.addRow(p, e)
                self.fields[name].append(e)
            self.stack.addWidget(page)
        lay.addWidget(self.stack)
        ac = QFormLayout()
        self.ac_amp, self.ac_phase, self.extra = QLineEdit(), QLineEdit(), QLineEdit()
        self.ac_amp.setPlaceholderText('e.g. 1  (for .ac analysis)')
        self.extra.setPlaceholderText('e.g. Rser=0.1')
        ac.addRow('AC amplitude', self.ac_amp)
        ac.addRow('AC phase', self.ac_phase)
        ac.addRow('Parasitics', self.extra)
        lay.addLayout(ac)
        self.func.currentIndexChanged.connect(self.stack.setCurrentIndex)
        self._load(value)

    def _load(self, value: str) -> None:
        m = _FUNC_RE.match(value or '')
        if m:
            name = m.group(1).upper().replace('SIN', 'SINE').replace('SINEE', 'SINE')
            args = m.group(2).split() if name != 'PWL' else [m.group(2).strip()]
            self.func.setCurrentText(name)
            for e, a in zip(self.fields[name], args):
                e.setText(a)
            rest = m.group(3)
        else:
            self.func.setCurrentText('(none)')
            tokens = (value or '').split()
            dc = ''
            if tokens and not tokens[0].upper() == 'AC':
                dc = tokens.pop(0)
                if dc.upper() == 'DC' and tokens:
                    dc = tokens.pop(0)
            self.fields['(none)'][0].setText(dc)
            rest = ' '.join(tokens)
        amp, phase, remainder = _split_ac(rest)
        self.ac_amp.setText(amp)
        self.ac_phase.setText(phase)
        self.extra.setText(remainder)

    def value(self) -> str:
        name = self.func.currentText()
        args = [e.text().strip() for e in self.fields[name]]
        while args and not args[-1]:
            args.pop()
        if name == '(none)':
            out = args[0] if args else ''
        else:
            out = f"{name}({' '.join(a or '0' for a in args)})"
        if self.ac_amp.text().strip():
            out += f' AC {self.ac_amp.text().strip()}' + (f' {self.ac_phase.text().strip()}'
                                                         if self.ac_phase.text().strip() else '')
        if self.extra.text().strip():
            out += ' ' + self.extra.text().strip()
        return out.strip()


#? -------------------------------------------------------------------------------
BASIC_ATTRS = ['InstName', 'Value', 'Value2', 'SpiceModel', 'SpiceLine', 'SpiceLine2']


class PartDialog(QDialog):
    """Edit the attributes of a placed component."""

    def __init__(self, part: Part, sym: Symbol, parent=None) -> None:
        super().__init__(parent)
        self.part = part
        self.setWindowTitle(f'{part.name or part.symbol} - attributes')
        self.resize(560, 460)
        lay = QVBoxLayout(self)
        head = QLabel(f"<b>{part.symbol.replace(chr(92) * 2, chr(92))}</b>  ·  {sym.attrs.get('Description', '')}")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # attributes table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Attribute', 'Value'])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        keys = list(BASIC_ATTRS) + [k for k in part.attrs if k not in BASIC_ATTRS]
        for k in keys:
            self._add_row(k, part.attrs.get(k, ''), placeholder=sym.attrs.get(k, ''))
        tw = QWidget()
        tv = QVBoxLayout(tw)
        tv.addWidget(self.table, 1)
        tb = QHBoxLayout()
        add = QPushButton('Add attribute')
        add.clicked.connect(lambda: self._add_row('NewAttr', '', edit=True))
        rem = QPushButton('Remove')
        rem.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()) if self.table.currentRow() >= len(BASIC_ATTRS) else None)
        tb.addWidget(add)
        tb.addWidget(rem)
        tb.addStretch(1)
        tv.addLayout(tb)
        hint = QLabel('Empty values are removed. The symbol default is shown in grey.')
        hint.setObjectName('Hint')
        tv.addWidget(hint)
        self.tabs.addTab(tw, 'Attributes')

        # source function editor
        self.source: SourceEditor | None = None
        prefix = (sym.attrs.get('Prefix') or '').upper()
        if prefix in ('V', 'I'):
            self.source = SourceEditor(part.attrs.get('Value', ''))
            self.tabs.addTab(self.source, 'Source function')
            self.tabs.setCurrentWidget(self.source)
            self.tabs.currentChanged.connect(self._sync_tabs)
        lay.addWidget(_buttons(self))

    def _add_row(self, key: str, value: str, placeholder: str = '', edit: bool = False) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        k = QTableWidgetItem(key)
        if key in BASIC_ATTRS:
            k.setFlags(k.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, k)
        v = QTableWidgetItem(value)
        if not value and placeholder:
            v.setToolTip(f'Symbol default: {placeholder}')
        self.table.setItem(r, 1, v)
        if edit:
            self.table.editItem(k)

    def _row_value(self, key: str) -> str:
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == key:
                return self.table.item(r, 1).text()
        return ''

    def _set_row(self, key: str, value: str) -> None:
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == key:
                self.table.item(r, 1).setText(value)

    def _sync_tabs(self, idx: int) -> None:
        if self.source is None:
            return
        if self.tabs.widget(idx) is self.source:
            self.source._load(self._row_value('Value'))
        else:
            self._set_row('Value', self.source.value())

    def attributes(self) -> dict[str, str]:
        if self.source is not None and self.tabs.currentWidget() is self.source:
            self._set_row('Value', self.source.value())
        out: dict[str, str] = {}
        for r in range(self.table.rowCount()):
            k = self.table.item(r, 0).text().strip()
            v = self.table.item(r, 1).text().strip() if self.table.item(r, 1) else ''
            if k and (v or k == 'InstName'):
                out[k] = v
        # keep file order for existing attributes, new ones at the end
        ordered = {k: out[k] for k in self.part.attrs if k in out}
        ordered.update({k: v for k, v in out.items() if k not in ordered})
        return ordered


#? -------------------------------------------------------------------------------
class LabelDialog(QDialog):
    """Net name (F4): label, ground or port."""

    def __init__(self, nets: list[str], name: str = '', port: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Net name')
        lay = QVBoxLayout(self)
        self.name = QComboBox()
        self.name.setEditable(True)
        self.name.addItems(nets)
        self.name.setCurrentText(name)
        form = QFormLayout()
        form.addRow('Name', self.name)
        lay.addLayout(form)
        self.group = QButtonGroup(self)
        row = QHBoxLayout()
        for i, (text, val) in enumerate((('Net label', None), ('Ground (0)', 'GND'), ('Input', 'In'),
                                         ('Output', 'Out'), ('Bi-direct.', 'BiDir'))):
            rb = QRadioButton(text)
            rb.setProperty('val', val)
            self.group.addButton(rb, i)
            row.addWidget(rb)
            if (val == port) or (val is None and port is None and name != '0') or (val == 'GND' and name == '0'):
                rb.setChecked(True)
        lay.addLayout(row)
        lay.addWidget(_buttons(self))
        self.name.setFocus()
        self.name.lineEdit().selectAll()

    def result_value(self) -> tuple[str, str | None]:
        val = self.group.checkedButton().property('val') if self.group.checkedButton() else None
        if val == 'GND':
            return '0', None
        return self.name.currentText().strip(), val


#? -------------------------------------------------------------------------------
class TextDialog(QDialog):
    """Comment or SPICE directive (T / S)."""

    def __init__(self, text: str = '', directive: bool = True, size: int = 2, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('SPICE directive' if directive else 'Comment')
        self.resize(560, 300)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.comment_rb = QRadioButton('Comment')
        self.spice_rb   = QRadioButton('SPICE directive')
        (self.spice_rb if directive else self.comment_rb).setChecked(True)
        row.addWidget(self.comment_rb)
        row.addWidget(self.spice_rb)
        row.addStretch(1)
        row.addWidget(QLabel('Size'))
        self.size = QComboBox()
        self.size.addItems(['0.625x', '1x', '1.5x', '2x', '2.5x', '3.5x', '5x', '7x'])
        self.size.setCurrentIndex(size)
        row.addWidget(self.size)
        lay.addLayout(row)
        self.edit = QPlainTextEdit(text)
        _mono(self.edit)
        self.edit.setPlaceholderText('.param R=1k\n.step param R list 1k 2k 5k\n.meas tran vmax MAX V(out)\n'
                                     '.include mymodels.lib')
        lay.addWidget(self.edit, 1)
        hint = QLabel('Directives: .param .step .meas .include .lib .model .subckt .ic .nodeset .options .temp '
                      '.four .save .func …   (Ctrl+Enter to accept)')
        hint.setWordWrap(True)
        hint.setObjectName('Hint')
        lay.addWidget(hint)
        lay.addWidget(_buttons(self))
        self.edit.setFocus()

    def keyPressEvent(self, e) -> None:      # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.accept()
            return
        super().keyPressEvent(e)

    def result_value(self) -> tuple[str, bool, int]:
        return self.edit.toPlainText().strip(), self.spice_rb.isChecked(), self.size.currentIndex()


#? -------------------------------------------------------------------------------
class SimCommandDialog(QDialog):
    """Edit the simulation command (.tran / .ac / .dc / .noise / .op / .tf)."""

    TABS = ['Transient', 'AC Analysis', 'DC sweep', 'Noise', 'DC op pnt', 'DC Transfer']

    def __init__(self, current: str = '', parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Edit simulation command')
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.f: dict[str, QWidget] = {}

        def tab(title: str, rows: list[tuple[str, str, QWidget | None]], note: str = '') -> None:
            w = QWidget()
            fl = QFormLayout(w)
            if note:
                n = QLabel(note)
                n.setWordWrap(True)
                n.setObjectName('Hint')
                fl.addRow(n)
            for key, label, widget in rows:
                widget = widget or QLineEdit()
                self.f[key] = widget
                if isinstance(widget, QCheckBox):
                    fl.addRow(widget)
                else:
                    fl.addRow(label, widget)
                if isinstance(widget, QLineEdit):
                    widget.textChanged.connect(self._preview)
                elif isinstance(widget, QComboBox):
                    widget.currentIndexChanged.connect(self._preview)
                elif isinstance(widget, QCheckBox):
                    widget.toggled.connect(self._preview)
            self.tabs.addTab(w, title)

        def combo(items):
            c = QComboBox()
            c.addItems(items)
            return c

        tab('Transient', [('tran_stop', 'Stop time', None), ('tran_start', 'Time to start saving data', None),
                          ('tran_step', 'Maximum timestep', None),
                          ('tran_startup', '', QCheckBox('Start external DC supply voltages at 0 V (startup)')),
                          ('tran_steady', '', QCheckBox('Stop simulating if steady state is detected (steady)')),
                          ('tran_nodiscard', '', QCheckBox("Don't reset T=0 when steady state is detected")),
                          ('tran_uic', '', QCheckBox('Skip initial operating point solution (uic)'))],
            'Time-domain simulation. Values accept SPICE suffixes: 10m, 1u, 5n …')
        tab('AC Analysis', [('ac_type', 'Type of sweep', combo(['dec', 'oct', 'lin', 'list'])),
                            ('ac_points', 'Number of points', None), ('ac_start', 'Start frequency', None),
                            ('ac_stop', 'Stop frequency', None)],
            'Small-signal frequency response. Give a source an "AC 1" amplitude.')
        tab('DC sweep', [('dc_src', 'Name of 1st source to sweep', None),
                         ('dc_type', 'Type of sweep', combo(['lin', 'oct', 'dec', 'list'])),
                         ('dc_start', 'Start value', None), ('dc_stop', 'Stop value', None),
                         ('dc_incr', 'Increment / points', None)],
            'Sweeps the DC value of a source (or a .param via "param name").')
        tab('Noise', [('noise_out', 'Output', None), ('noise_in', 'Input source', None),
                      ('noise_type', 'Type of sweep', combo(['dec', 'oct', 'lin', 'list'])),
                      ('noise_points', 'Number of points', None), ('noise_start', 'Start frequency', None),
                      ('noise_stop', 'Stop frequency', None)])
        tab('DC op pnt', [], 'Computes the DC operating point (capacitors open, inductors shorted).')
        tab('DC Transfer', [('tf_out', 'Output', None), ('tf_src', 'Source', None)],
            'Small-signal DC transfer function, input and output impedance.')
        self.f['ac_points'].setText('100')
        self.f['noise_points'].setText('100')

        self.preview = QLineEdit()
        self.preview.setReadOnly(True)
        _mono(self.preview)
        form = QFormLayout()
        form.addRow('Syntax', self.preview)
        lay.addLayout(form)
        lay.addWidget(_buttons(self))
        self.tabs.currentChanged.connect(self._preview)
        self._load(current)
        self._preview()

    def _t(self, key: str) -> str:
        w = self.f[key]
        return w.currentText() if isinstance(w, QComboBox) else w.text().strip()

    def _load(self, cmd: str) -> None:
        tok = cmd.split()
        if not tok:
            return
        head = tok[0].lower()
        args = tok[1:]
        if head == '.tran':
            self.tabs.setCurrentIndex(0)
            nums = [a for a in args if a.lower() not in ('startup', 'steady', 'nodiscard', 'uic')]
            for flag in ('startup', 'steady', 'nodiscard', 'uic'):
                self.f[f'tran_{flag}'].setChecked(flag in [a.lower() for a in args])
            if len(nums) == 1:
                self.f['tran_stop'].setText(nums[0])
            elif len(nums) >= 2:
                self.f['tran_stop'].setText(nums[1])
                if len(nums) > 2:
                    self.f['tran_start'].setText(nums[2])
                if len(nums) > 3:
                    self.f['tran_step'].setText(nums[3])
        elif head == '.ac' and len(args) >= 4:
            self.tabs.setCurrentIndex(1)
            self.f['ac_type'].setCurrentText(args[0].lower())
            for k, v in zip(('ac_points', 'ac_start', 'ac_stop'), args[1:]):
                self.f[k].setText(v)
        elif head == '.dc' and args:
            self.tabs.setCurrentIndex(2)
            if args[0].lower() in ('lin', 'oct', 'dec', 'list'):
                self.f['dc_type'].setCurrentText(args[0].lower())
                args = args[1:]
            for k, v in zip(('dc_src', 'dc_start', 'dc_stop', 'dc_incr'), args):
                self.f[k].setText(v)
        elif head == '.noise' and len(args) >= 5:
            self.tabs.setCurrentIndex(3)
            for k, v in zip(('noise_out', 'noise_in', 'noise_type', 'noise_points', 'noise_start', 'noise_stop'), args):
                if isinstance(self.f[k], QComboBox):
                    self.f[k].setCurrentText(v.lower())
                else:
                    self.f[k].setText(v)
        elif head == '.op':
            self.tabs.setCurrentIndex(4)
        elif head == '.tf' and len(args) >= 2:
            self.tabs.setCurrentIndex(5)
            self.f['tf_out'].setText(args[0])
            self.f['tf_src'].setText(args[1])

    def command(self) -> str:
        i, t = self.tabs.currentIndex(), self._t
        if i == 0:
            stop, start, step = t('tran_stop'), t('tran_start'), t('tran_step')
            cmd = f'.tran 0 {stop} {start or 0}' + (f' {step}' if step else '') if (start or step) else f'.tran {stop}'
            for flag in ('startup', 'steady', 'nodiscard', 'uic'):
                if self.f[f'tran_{flag}'].isChecked():
                    cmd += f' {flag}'
            return cmd
        if i == 1:
            return f".ac {t('ac_type')} {t('ac_points')} {t('ac_start')} {t('ac_stop')}"
        if i == 2:
            typ = t('dc_type')
            return f".dc {'' if typ == 'lin' else typ + ' '}{t('dc_src')} {t('dc_start')} {t('dc_stop')} {t('dc_incr')}"
        if i == 3:
            return (f".noise {t('noise_out')} {t('noise_in')} {t('noise_type')} {t('noise_points')} "
                    f"{t('noise_start')} {t('noise_stop')}")
        if i == 4:
            return '.op'
        return f".tf {t('tf_out')} {t('tf_src')}"

    def _preview(self, *_) -> None:
        self.preview.setText(' '.join(self.command().split()))

    def accept(self) -> None:
        cmd = self.command()
        i   = self.tabs.currentIndex()
        if i == 0 and not self._t('tran_stop'):
            self.f['tran_stop'].setFocus()
            return
        if i in (1, 3) and not all(self._t(k) for k in (('ac_points', 'ac_start', 'ac_stop') if i == 1 else
                                                         ('noise_out', 'noise_in', 'noise_start', 'noise_stop'))):
            return
        if i == 2 and not all(self._t(k) for k in ('dc_src', 'dc_start', 'dc_stop', 'dc_incr')):
            return
        self.result_cmd = ' '.join(cmd.split())
        super().accept()


#? -------------------------------------------------------------------------------
class TextViewer(QDialog):
    """Read-only text (SPICE error log, netlist)."""

    def __init__(self, title: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)
        lay = QVBoxLayout(self)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        _mono(view)
        lay.addWidget(view, 1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)


#? -------------------------------------------------------------------------------
class OpPointDialog(QDialog):
    """Operating point results (like LTspice's .op window)."""

    def __init__(self, rows: list[tuple[str, float]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Operating point')
        self.resize(460, 520)
        lay = QVBoxLayout(self)
        filt = QLineEdit()
        filt.setPlaceholderText('Filter…')
        filt.setClearButtonEnabled(True)
        lay.addWidget(filt)
        table = QTableWidget(len(rows), 3)
        table.setHorizontalHeaderLabels(['Quantity', 'Value', 'Unit'])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (name, val) in enumerate(rows):
            unit = 'A' if name.upper().startswith('I') else ('V' if name.upper().startswith('V(') else '')
            table.setItem(r, 0, QTableWidgetItem(name))
            it = QTableWidgetItem(f'{val:.6g}')
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(r, 1, it)
            table.setItem(r, 2, QTableWidgetItem(unit))
        filt.textChanged.connect(lambda t: [table.setRowHidden(r, t.lower() not in table.item(r, 0).text().lower())
                                            for r in range(table.rowCount())])
        lay.addWidget(table, 1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

#? -------------------------------------------------------------------------------
