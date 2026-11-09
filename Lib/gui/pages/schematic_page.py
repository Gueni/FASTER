#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#? Name:        schematic_page.py
#? Purpose:     Schematic editor page: draw, edit and simulate LTspice circuits.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------

"""Schematic editor page.

The page owns a :class:`~Lib.schematic.model.Schematic` parsed from the
session text. Canvas edits change the model; the page then writes the model
back to the session (one undo step). Edits made elsewhere (component table,
undo, revert) re-parse the model.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPlainTextEdit, QSplitter, QVBoxLayout, QWidget

from ...core.config import find_ltspice
from ...schematic.model import Flag, Part, Schematic, Text
from ...schematic.symbols import find_symbol
from .. import settings
from ..editor.canvas import Canvas
from ..editor.dialogs import (LabelDialog, OpPointDialog, PartDialog, SimCommandDialog, SymbolBrowser, TextDialog,
                              TextViewer, name_prefix)
from ..editor.graphics import Colors
from ..editor.plot import WavePlot
from ..editor.simulate import SimResult, SimRunner
from ..theme import theme
from ..widgets import BasePage, button, icon_button, label

#: quick-place parts (key -> symbol)
QUICK_PARTS = {'res': 'res', 'cap': 'cap', 'ind': 'ind', 'diode': 'diode'}


#? -------------------------------------------------------------------------------
class SchematicPage(BasePage):
    title     = 'Schematic'
    subtitle  = 'Draw, edit and simulate circuits (LTspice compatible)'
    icon_name = 'wire'
    sim_busy_changed = Signal(bool)      # an LTspice run of the editor started / ended

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        self.session = ctx.session
        self.sch: Schematic | None = None
        self._text = ''
        self.result: SimResult | None = None
        self._stale = False
        self.runner = SimRunner(self)
        self.runner.finished.connect(self._sim_finished)
        self.runner.output.connect(lambda t: self.ctx.log(t, 'muted'))
        self.canvas = Canvas()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 8)
        outer.setSpacing(6)
        outer.addWidget(self._build_toolbar())

        # empty state
        self.empty = QFrame()
        self.empty.setObjectName('DropZone')
        ev = QVBoxLayout(self.empty)
        ev.addStretch(1)
        t = label('Start a schematic', 'BigTitle')
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(t)
        s = label('Create a new circuit or open an LTspice .asc file. Draw wires (F3), place parts (F2, R, C, L, D, '
                  'G), add a simulation command and press Run - then click wires to see their voltages.',
                  'Hint', wrap=True)
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setMaximumWidth(600)
        ev.addWidget(s, 0, Qt.AlignmentFlag.AlignHCenter)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button('New schematic', 'file-plus', 'primary', slot=self.new_schematic, big=True))
        row.addWidget(button('Open…', 'open', slot=ctx.open_dialog, big=True))
        row.addStretch(1)
        ev.addLayout(row)
        ev.addStretch(2)
        outer.addWidget(self.empty, 1)

        # canvas + waveforms
        self.split = QSplitter(Qt.Orientation.Horizontal)      # schematic | waveforms
        self.split.setChildrenCollapsible(False)
        frame = QFrame()
        frame.setObjectName('Card')
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.addWidget(self.canvas)
        self.split.addWidget(frame)
        self.plot = WavePlot()
        self.plot.setMinimumWidth(320)
        self.plot.closed.connect(lambda: self.plot.setVisible(False))
        self.plot.setVisible(False)
        self.split.addWidget(self.plot)
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 1)
        outer.addWidget(self.split, 1)

        status = QHBoxLayout()
        self.hint = label('', 'Hint')
        self.coords = label('', 'Hint')
        self.sim_state = label('', 'Hint')
        status.addWidget(self.hint, 1)
        status.addWidget(self.sim_state)
        status.addSpacing(16)
        status.addWidget(self.coords)
        outer.addLayout(status)

        c = self.canvas
        c.committed.connect(self._committed)
        c.status.connect(self.hint.setText)
        c.position.connect(lambda x, y: self.coords.setText(f'x {x}   y {y}'))
        c.tool_changed.connect(self._tool_changed)
        c.edit_object.connect(self.edit_object)
        c.request.connect(self._request)
        c.context_menu.connect(self._context_menu)
        c.probe_clicked.connect(self._probe)
        c.probe_hover.connect(self._probe_hover)
        self.session.loaded.connect(lambda *_: self.reload(fit=True))
        self.session.closed.connect(lambda: self.reload(fit=True))
        self.session.changed.connect(self._session_changed)
        self.session.modified_changed.connect(lambda *_: self._sync())
        theme().changed.connect(lambda *_: self.canvas.set_colors(Colors.from_palette(theme().palette)))
        self.reload(fit=True)

    #? toolbar
    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)

        def sep() -> None:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setObjectName('Separator')
            line.setFixedWidth(10)
            h.addWidget(line)

        def tb(icon: str, tip: str, slot, checkable: bool = False):
            b = icon_button(icon, tip, slot, checkable=checkable)
            h.addWidget(b)
            return b

        tb('file-plus', 'New schematic', self.new_schematic)
        tb('open', 'Open schematic (Ctrl+O)', self.ctx.open_dialog)
        self.save_btn = tb('save', 'Save (Ctrl+S)', self.ctx.save)
        sep()
        self.undo_btn = tb('undo', 'Undo (Ctrl+Z / F9)', self.undo)
        self.redo_btn = tb('redo', 'Redo (Ctrl+Y / Shift+F9)', self.redo)
        tb('trash', 'Delete (Del / F5)', lambda: self.canvas.delete_selection() if self.canvas.selected_items()
           else self.canvas.set_tool('delete'))
        tb('rotate', 'Rotate (Ctrl+R)', self.canvas.rotate_selection)
        tb('mirror', 'Mirror (Ctrl+E)', self.canvas.mirror_selection)
        sep()
        self.tool_btns = {
            'select': tb('pointer', 'Select / drag (Esc)', lambda: self.canvas.set_tool('select'), True),
            'wire'  : tb('wire', 'Draw wire (F3 / W)', lambda: self.canvas.set_tool('wire'), True),
        }
        tb('ground', 'Ground (G)', lambda: self.canvas.place_flag('0'))
        tb('tag', 'Net label (F4)', lambda: self._request('label'))
        tb('resistor', 'Resistor (R)', lambda: self._request('part:res'))
        tb('capacitor', 'Capacitor (C)', lambda: self._request('part:cap'))
        tb('inductor', 'Inductor (L)', lambda: self._request('part:ind'))
        tb('diode', 'Diode (D)', lambda: self._request('part:diode'))
        tb('component', 'Component library (F2)', lambda: self._request('component'))
        tb('text', 'Comment (T)', lambda: self._request('text'))
        tb('directive', 'SPICE directive (S)', lambda: self._request('directive'))
        sep()
        tb('sliders', 'Edit simulation command', self.edit_sim_command)
        self.run_btn = button('Run', 'play', 'primary', tip='Simulate with LTspice (F11)', slot=self.run_sim)
        self.run_btn.setMinimumWidth(self.run_btn.sizeHint().width())
        h.addWidget(self.run_btn)
        self.stop_btn = tb('stop', 'Stop the simulation', self.runner.stop)
        self.tool_btns['probe'] = tb('probe', 'Probe: click wires / parts to plot them (P)',
                                     lambda: self.canvas.set_tool('probe'), True)
        tb('activity', 'Show / hide the waveform pane', self._toggle_plot)
        tb('report', 'SPICE error log', self.show_log)
        tb('list', 'View SPICE netlist', self.show_netlist)
        h.addStretch(1)
        tb('grid', 'Show / hide grid', self._toggle_grid)
        tb('fit', 'Zoom to fit (Space)', self.canvas.fit)
        tb('external', 'Open the saved file in LTspice', self.ctx.open_in_ltspice)
        self.busy_actions(self.run_btn)
        return bar

    #? model <-> session
    def reload(self, fit: bool = False) -> None:
        has = self.session.is_open
        self.empty.setVisible(not has)
        self.split.setVisible(has)
        if has:
            self._text = self.session.text
            self.sch = Schematic.parse(self._text, str(self.session.path.parent))
            self.canvas.set_schematic(self.sch, Colors.from_palette(theme().palette), fit=fit)
            if fit:
                self.result = None
                self.plot.setVisible(False)
                self.sim_state.setText('')
        else:
            self.sch = None
        self._sync()

    def _session_changed(self) -> None:
        if not self.session.is_open:
            return
        if self.session.text == self._text:
            self.canvas.rebuild()
        else:
            self.reload()
        self._mark_stale()
        self._sync()

    def _committed(self, what: str) -> None:
        before = self.session.text
        text   = self.sch.to_text().rstrip('\n') + '\n'
        self._text = text                  # set first: the session emits `changed` synchronously
        self.session.set_text(text)
        self._text = self.session.text
        if self.session.text == before:
            self.canvas.rebuild()

    def _mark_stale(self) -> None:
        if self.result is not None and not self._stale:
            self._stale = True
            self.sim_state.setText('Schematic changed - run again to update the results')

    def _sync(self) -> None:
        s = self.session
        self.undo_btn.setEnabled(s.is_open and s.can_undo)
        self.redo_btn.setEnabled(s.is_open and s.can_redo)
        self.save_btn.setEnabled(s.is_open and (s.modified or s.draft))
        # one run at a time: the editor simulation and the analysis share LTspice and the working copy
        analysing = self.ctx.worker.busy
        self.run_btn.setEnabled(s.is_open and not self.runner.busy and not analysing)
        self.run_btn.setToolTip('An analysis is running - wait for it or stop it first' if analysing
                                else 'Simulate with LTspice (F11)')
        self.stop_btn.setEnabled(self.runner.busy)

    def undo(self) -> None:
        if self.session.is_open:
            self.session.undo()

    def redo(self) -> None:
        if self.session.is_open:
            self.session.redo()

    def new_schematic(self) -> None:
        self.ctx.new_schematic()

    #? tools
    def _tool_changed(self, tool: str) -> None:
        for k, b in self.tool_btns.items():
            b.setChecked(k == tool)

    def _toggle_grid(self) -> None:
        self.canvas.show_grid = not self.canvas.show_grid
        self.canvas.viewport().update()

    def _toggle_plot(self) -> None:
        if self.plot.isVisible():
            self.plot.setVisible(False)
        else:
            self._show_plot()

    def _show_plot(self) -> None:
        if self.plot.isVisible():
            return
        self.plot.setVisible(True)
        w = self.split.width()
        self.split.setSizes([int(w * 0.55), int(w * 0.45)])

    def handle_escape(self) -> bool:
        """Esc pressed anywhere on the page; True if consumed."""
        if self.canvas.tool != 'select':
            self.canvas.set_tool('select')
            return True
        return False

    def _request(self, what: str) -> None:
        if self.sch is None:
            return
        if what == 'undo':
            return self.undo()
        if what == 'redo':
            return self.redo()
        if what == 'probe':
            return self.canvas.set_tool('probe')
        if what.startswith('part:'):
            return self.place_symbol(QUICK_PARTS.get(what[5:], what[5:]))
        if what == 'component':
            dlg = SymbolBrowser(self)
            if dlg.exec() and dlg.choice:
                self.place_symbol(dlg.choice)
            return
        if what == 'label':
            dlg = LabelDialog(self.sch.connectivity().net_names(), parent=self)
            if dlg.exec():
                name, port = dlg.result_value()
                if name:
                    self.canvas.place_flag(name, port)
            return
        if what in ('text', 'directive'):
            dlg = TextDialog(directive=what == 'directive', parent=self)
            if dlg.exec():
                text, directive, size = dlg.result_value()
                if text:
                    if directive and not text.startswith('.') and not text.startswith(('+', '*')):
                        text = '.' + text
                    self.canvas.place_text(text, directive)
                    if self.canvas._frag is not None:
                        self.canvas._frag.texts[0].size = size
                        self.canvas._show_fragment()

    def place_symbol(self, symbol: str) -> None:
        sym = find_symbol(symbol, self.sch.directory)
        name = symbol.replace('\\\\', '\\').replace('\\', '\\\\')     # .asc spelling: Folder\\name
        self.canvas.place_part(name, name_prefix(sym))
        self.canvas.setFocus()

    #? editing objects
    def edit_object(self, obj) -> None:
        if isinstance(obj, Part):
            dlg = PartDialog(obj, obj.sym(self.sch.directory), self)
            if dlg.exec():
                attrs = dlg.attributes()
                if attrs != obj.attrs:
                    obj.attrs = attrs
                    self.canvas.commit('Attributes')
        elif isinstance(obj, Flag):
            dlg = LabelDialog(self.sch.connectivity().net_names(), obj.name, obj.port, self)
            if dlg.exec():
                name, port = dlg.result_value()
                if name and (name, port) != (obj.name, obj.port):
                    obj.name, obj.port = name, port
                    self.canvas.commit('Label')
        elif isinstance(obj, Text):
            if obj.is_directive and obj is self.sch.analysis() and len(obj.text.splitlines()) == 1:
                return self.edit_sim_command()
            dlg = TextDialog(obj.text, obj.is_directive, obj.size, self)
            if dlg.exec():
                text, directive, size = dlg.result_value()
                if text:
                    obj.text, obj.kind, obj.size = text, '!' if directive else ';', size
                    self.canvas.commit('Text')

    def _context_menu(self, obj, gpos) -> None:
        m = QMenu(self)
        if obj is not None:
            m.addAction('Edit…', lambda: self.edit_object(obj))
            m.addSeparator()
            m.addAction('Rotate\tCtrl+R', self.canvas.rotate_selection)
            m.addAction('Mirror\tCtrl+E', self.canvas.mirror_selection)
            m.addAction('Duplicate\tF6', self.canvas.duplicate)
            m.addAction('Cut\tCtrl+X', lambda: self.canvas.copy_selection(cut=True))
            m.addAction('Copy\tCtrl+C', self.canvas.copy_selection)
            m.addSeparator()
            m.addAction('Delete\tDel', self.canvas.delete_selection)
            if isinstance(obj, Part) and self.result is not None:
                m.addSeparator()
                m.addAction(f'Plot current of {obj.name}', lambda: self._probe(('part', obj, None)))
        else:
            m.addAction('Paste\tCtrl+V', self.canvas.paste)
            m.addAction('Select all\tCtrl+A', self.canvas.select_all)
            m.addSeparator()
            m.addAction('Place component…\tF2', lambda: self._request('component'))
            m.addAction('Draw wire\tF3', lambda: self.canvas.set_tool('wire'))
            m.addAction('Net label…\tF4', lambda: self._request('label'))
            m.addAction('Ground\tG', lambda: self.canvas.place_flag('0'))
            m.addAction('SPICE directive…\tS', lambda: self._request('directive'))
            m.addAction('Comment…\tT', lambda: self._request('text'))
            m.addSeparator()
            m.addAction('Edit simulation command…', self.edit_sim_command)
            m.addAction('Run\tF11', self.run_sim)
            m.addAction('Zoom to fit\tSpace', self.canvas.fit)
        m.exec(gpos)

    #? simulation
    def edit_sim_command(self) -> bool:
        if self.sch is None:
            return False
        current = self.sch.analysis()
        line = ''
        if current is not None:
            line = next(ln for ln in current.text.splitlines()
                        if ln.strip().lower().split(' ', 1)[0] in ('.tran', '.ac', '.dc', '.op', '.noise', '.tf'))
        dlg = SimCommandDialog(line.strip(), self)
        if not dlg.exec():
            return False
        cmd = dlg.result_cmd
        if current is not None:
            current.text = '\n'.join(cmd if ln == line else ln for ln in current.text.splitlines())
        else:
            x0, y0, x1, y1 = self.sch.bbox()
            self.sch.texts.append(Text(x0, y1 + 48 if self.sch.items() else 0, 'Left', 2, '!', cmd))
        self.canvas.commit('Simulation command')
        return True

    def run_sim(self) -> None:
        if not self.session.is_open or self.runner.busy:
            return
        if self.ctx.worker.busy:
            self.ctx.toast('An analysis is running - wait for it or stop it first.', 'warning')
            return
        exe = find_ltspice(settings.get('run/ltspice', '') or None)
        if exe is None:
            self.ctx.toast('LTspice not found - set its path in Settings.', 'warning')
            return
        if self.sch.analysis() is None and not self.edit_sim_command():
            return
        asc, _name, _cleanup = self.session.analysis_input()
        self.sim_state.setText('Simulating…')
        self.ctx.log(f'Simulating {asc.name} with LTspice…', 'info')
        self.runner.start(exe, Path(asc))
        self._sync()
        self.sim_busy_changed.emit(self.runner.busy)

    def _sim_finished(self, res: SimResult) -> None:
        self._sync()
        self.sim_busy_changed.emit(False)
        self.result = res if res.raw else self.result
        self._stale = False
        if not res.ok:
            self.sim_state.setText('Simulation failed')
            self.ctx.log(res.error, 'error')
            if res.log:
                self.ctx.log(res.log.strip(), 'muted')
            self.ctx.toast(res.error, 'error', 5000)
            if res.log:
                self._viewer('SPICE error log', res.log)
            return
        self.result = res
        self.sim_state.setText(f'Simulated in {res.seconds:.1f} s')
        self.ctx.log(f'Simulation finished in {res.seconds:.1f} s  ·  {res.raw}', 'success')
        for ln in res.log.splitlines():
            low = ln.lower()
            if any(w in low for w in ('error', 'warning', 'singular', 'failed')) or ':' in ln and '=' in ln:
                self.ctx.log(ln, 'warning' if 'error' not in low else 'error')
        if not self.plot.set_raw(res.raw):
            self.ctx.toast(f'Cannot read {res.raw.name}', 'error')
            return
        if self.plot.point_count() <= 1:          # .op: show the operating point table
            self._op_dialog = OpPointDialog(self.plot.op_values(), self)
            self._op_dialog.show()
            return
        self._show_plot()
        if not self.plot.traces:
            self.canvas.set_tool('probe')

    #? probing
    def _node_at(self, point) -> str | None:
        """SPICE node name of the net through ``point``."""
        conn = self.sch.connectivity()
        root = conn.net_of(point)
        if root is None:
            return None
        name = conn.names.get(root)
        if name:
            return name
        if self.result is None:
            return None
        for p in self.sch.parts:
            sym  = p.sym(self.sch.directory)
            pins = conn.part_pins.get(id(p), [])
            order = sym.spice_pins()
            nodes = self.result.nodes_of(self._element_names(p, sym), len(order))
            if not nodes:
                continue
            for k, idx in enumerate(order):
                if k < len(nodes) and idx < len(pins) and conn.net_of(pins[idx]) == root:
                    return nodes[k]
        return None

    @staticmethod
    def _element_names(p: Part, sym) -> list[str]:
        prefix = (sym.attrs.get('Prefix') or 'X')[:1]
        return [p.name, prefix + p.name, 'X' + p.name]

    def _probe_trace(self, target) -> tuple[str | None, str]:
        if target is None or self.result is None:
            return None, ''
        if target[0] == 'net':
            node = self._node_at(target[1])
            if node is None:
                return None, 'Net not in the simulation'
            if node == '0':
                return None, 'Ground (0 V)'
            name = f'V({node})'
            return (name if self.plot.has(name) else None), name
        _, part, pin = target
        sym  = part.sym(self.sch.directory)
        cand = []
        if pin is not None and len(sym.pins) > 2:
            pname = sym.pin_names[pin]
            cand += [f'I{pname}({part.name})', f'Ix({part.name}:{pname})', f'I{pname[:1]}({part.name})']
        cand += [f'I({part.name})', f'Ix({part.name}:{sym.pin_names[0] if sym.pin_names else ""})']
        for c in cand:
            if self.plot.has(c):
                return c, c
        return None, f'No current saved for {part.name}'

    def _probe_hover(self, target) -> None:
        name, text = self._probe_trace(target)
        self.hint.setText(f'Probe: {text}' if text else 'Click a wire for its voltage, a part for its current.')

    def _probe(self, target) -> None:
        name, text = self._probe_trace(target)
        if name is None:
            self.ctx.toast(text or 'Run a simulation first.', 'info', 2000)
            return
        self._show_plot()
        self.plot.add_trace(name)

    #? viewers
    def show_log(self) -> None:
        if self.result is None or not self.result.log:
            self.ctx.toast('No simulation log yet - press Run first.', 'info')
            return
        self._viewer('SPICE error log', self.result.log)

    def show_netlist(self) -> None:
        if self.result is not None and self.result.netlist:
            self._viewer('SPICE netlist', self.result.netlist)
            return
        self.ctx.toast('Run a simulation to generate the netlist.', 'info')

    def _viewer(self, title: str, text: str) -> None:
        """Non-modal text window (one per title, reused)."""
        if not hasattr(self, '_viewers'):
            self._viewers: dict[str, TextViewer] = {}
        dlg = self._viewers.get(title)
        if dlg is None:
            dlg = self._viewers[title] = TextViewer(title, text, self)
        dlg.findChild(QPlainTextEdit).setPlainText(text)
        dlg.show()
        dlg.raise_()

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self._sync()

#? -------------------------------------------------------------------------------
