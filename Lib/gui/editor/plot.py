#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#? Name:        plot.py
#? Purpose:     Waveform pane of the schematic editor (probed traces).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------

"""Waveform pane.

Probed voltages go to the *V* pane, currents to the *I* pane (shared x axis).
AC results are shown as magnitude in dB with the phase in a third pane;
``.step`` runs draw one curve per step. Any trace of the raw file can also be
typed in the trace box.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ...simulation.waveforms import decimate_index
from ..theme import theme
from ..widgets import FlowLayout, icon_button

COLORS = ['#4c8dff', '#2fbf71', '#f5a524', '#e5484d', '#a78bfa', '#22c3ee', '#f472b6', '#84cc16', '#fb923c',
          '#94a3b8']
MAX_POINTS = 20000


#? -------------------------------------------------------------------------------
class WavePlot(QWidget):
    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        self.raw = None
        self.raw_path: Path | None = None
        self.names: list[str] = []
        self.axis = ''
        self.kind = 'tran'
        self.traces: list[str] = []
        self._curves: list[tuple[str, np.ndarray, np.ndarray, str]] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(4)
        # side panel: title + buttons / trace box / trace chips (wrap) / cursor read-out (wraps)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.title = QLabel('Waveforms')
        self.title.setObjectName('CardTitle')
        top.addWidget(self.title, 1)
        top.addWidget(icon_button('fit', 'Auto-range', self.autorange))
        top.addWidget(icon_button('trash', 'Remove all traces', self.clear_traces))
        top.addWidget(icon_button('x', 'Hide the waveform pane', self.closed.emit))
        lay.addLayout(top)
        self.add_box = QComboBox()
        self.add_box.setEditable(True)
        self.add_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.add_box.lineEdit().setPlaceholderText('Add trace…  e.g. V(out)')
        self.add_box.lineEdit().returnPressed.connect(self._add_typed)
        self.add_box.activated.connect(lambda *_: self._add_typed())
        lay.addWidget(self.add_box)
        self.chips = QWidget()
        self.chip_lay = FlowLayout(self.chips, spacing=4)
        lay.addWidget(self.chips)
        self.readout = QLabel('')
        self.readout.setObjectName('Hint')
        self.readout.setWordWrap(True)
        self.readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.readout)

        self.glw = pg.GraphicsLayoutWidget()
        lay.addWidget(self.glw, 1)
        self.panes: dict[str, pg.PlotItem] = {}
        for key, unit in (('V', 'V'), ('I', 'A'), ('P', '°')):
            p = self.glw.addPlot(row=len(self.panes), col=0)
            p.showGrid(x=True, y=True, alpha=0.18)
            p.setLabel('left', units=unit)
            p.setClipToView(True)
            p.setDownsampling(auto=True, mode='peak')
            self.panes[key] = p
        self.panes['I'].setXLink(self.panes['V'])
        self.panes['P'].setXLink(self.panes['V'])
        self.cursor = {k: pg.InfiniteLine(angle=90, movable=False) for k in self.panes}
        for k, p in self.panes.items():
            p.addItem(self.cursor[k], ignoreBounds=True)
        self.glw.scene().sigMouseMoved.connect(self._mouse_moved)
        theme().changed.connect(lambda *_: self._style())
        self._style()
        self._layout_panes()

    #? style
    def _style(self) -> None:
        p = theme().palette
        self.glw.setBackground(p.surface)
        for plot in self.panes.values():
            for ax in ('left', 'bottom'):
                a = plot.getAxis(ax)
                a.setPen(pg.mkPen(p.border))
                a.setTextPen(pg.mkPen(p.muted))
        for line in self.cursor.values():
            line.setPen(pg.mkPen(p.muted, width=1, style=Qt.PenStyle.DashLine))

    #? data
    def set_raw(self, path: Path) -> bool:
        from PyLTSpice import RawRead
        try:
            raw = RawRead(str(path))
        except Exception:
            return False
        self.raw, self.raw_path = raw, Path(path)
        self.names = list(raw.get_trace_names())
        self.axis  = self.names[0] if self.names else ''
        plot = (raw.get_raw_property('Plotname') or '').lower() if hasattr(raw, 'get_raw_property') else ''
        self.kind = 'ac' if 'ac' in plot.split() or self.axis.lower() == 'frequency' else \
                    'tran' if self.axis.lower() == 'time' else 'dc'
        self.add_box.blockSignals(True)
        self.add_box.clear()
        self.add_box.addItems(self.names[1:])
        self.add_box.setCurrentIndex(-1)
        self.add_box.blockSignals(False)
        comp = QCompleter(self.names[1:], self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.add_box.setCompleter(comp)
        self.traces = [t for t in (self.resolve(t) for t in self.traces) if t]
        bottom = {'tran': ('Time', 's'), 'ac': ('Frequency', 'Hz')}.get(self.kind, (self.axis, ''))
        for p in self.panes.values():
            p.setLabel('bottom', bottom[0], units=bottom[1])
            p.setLogMode(x=self.kind == 'ac', y=False)
        self.panes['V'].setLabel('left', 'Magnitude' if self.kind == 'ac' else '', units='dB' if self.kind == 'ac' else 'V')
        self.title.setText(f"Waveforms  ·  {self.raw_path.stem.lstrip('~').replace('.faster', '').replace('.op', '')}")
        self.replot()
        return True

    def point_count(self) -> int:
        try:
            return len(self.raw.get_trace(self.axis).get_wave(0)) if self.raw is not None else 0
        except Exception:
            return 0

    def op_values(self) -> list[tuple[str, float]]:
        out = []
        for n in self.names:
            try:
                v = self.raw.get_trace(n).get_wave(0)
                out.append((n, float(np.real(v[0]))))
            except Exception:
                pass
        return out

    def resolve(self, name: str) -> str | None:
        """Trace name as stored in the raw file (case-insensitive), or None."""
        low = name.lower()
        return next((n for n in self.names if n.lower() == low), None)

    def has(self, name: str) -> bool:
        return self.resolve(name) is not None

    def add_trace(self, name: str, replace: bool = False) -> bool:
        real = self.resolve(name)
        if real is None:
            return False
        if replace:
            self.traces = []
        if real not in self.traces:
            self.traces.append(real)
        self.replot()
        return True

    def remove_trace(self, name: str) -> None:
        if name in self.traces:
            self.traces.remove(name)
            self.replot()

    def clear_traces(self) -> None:
        self.traces = []
        self.replot()

    def _add_typed(self) -> None:
        text = self.add_box.currentText().strip()
        if text and not self.add_trace(text):
            self.readout.setText(f'No trace called {text} in this simulation.')
        self.add_box.setCurrentIndex(-1)
        self.add_box.clearEditText()

    #? plotting
    def _wave(self, name: str, step: int) -> tuple[np.ndarray, np.ndarray]:
        y = np.asarray(self.raw.get_trace(name).get_wave(step))
        x = np.asarray(self.raw.get_trace(self.axis).get_wave(step))
        x = np.abs(x) if np.iscomplexobj(x) or self.kind == 'tran' else x
        return np.real(x).astype(float), y

    def replot(self) -> None:
        for k, p in self.panes.items():
            p.clear()
            if getattr(p, "legend", None) is not None:
                p.legend.clear()
            p.addItem(self.cursor[k], ignoreBounds=True)
        self._curves.clear()
        self._fill_chips()
        lines = 1 + min(len(self.traces) * (2 if self.kind == 'ac' else 1), 8) if self.traces else 0
        self.readout.setFixedHeight(int(self.readout.fontMetrics().lineSpacing() * lines) + (4 if lines else 0))
        self.readout.clear()
        if self.raw is None:
            self._layout_panes()
            return
        try:
            steps = list(self.raw.get_steps())
        except Exception:
            steps = [0]
        for k, name in enumerate(self.traces):
            pane  = 'I' if name.upper().startswith('I') and '(' in name else 'V'
            color = COLORS[k % len(COLORS)]
            for j, s in enumerate(steps):
                try:
                    x, y = self._wave(name, s)
                except Exception:
                    continue
                label = name if len(steps) == 1 else (f'{name}' if j == 0 else None)
                c = pg.mkColor(color)
                if len(steps) > 1:
                    c = pg.mkColor(COLORS[(k + j) % len(COLORS)])
                if self.kind == 'ac':
                    mag = 20 * np.log10(np.maximum(np.abs(y), 1e-30))
                    ph  = np.degrees(np.unwrap(np.angle(y)))
                    self._plot('V' if pane == 'V' else 'I', x, mag, c, label, f'{name} dB')
                    self._plot('P', x, ph, c, label, f'{name} phase', dash=True)
                else:
                    yr = np.real(y).astype(float)
                    self._plot(pane, x, yr, c, label, name)
        self._layout_panes()

    def _plot(self, pane: str, x, y, color, label, key: str, dash: bool = False) -> None:
        idx = decimate_index([y], MAX_POINTS)
        pen = pg.mkPen(color, width=1.8, style=Qt.PenStyle.DashLine if dash else Qt.PenStyle.SolidLine)
        self.panes[pane].plot(x[idx], y[idx], pen=pen, name=label)
        self._curves.append((key, x, y, pane))

    def _layout_panes(self) -> None:
        used = {pane for *_, pane in self._curves}
        if not used:
            used = {'V'}
        for k, p in self.panes.items():
            p.setVisible(k in used)
        self.panes['I'].setLabel('left', 'Magnitude' if self.kind == 'ac' else '',
                                 units='dB' if self.kind == 'ac' else 'A')

    def _fill_chips(self) -> None:
        while self.chip_lay.count():
            w = self.chip_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        for k, name in enumerate(self.traces):
            b = QToolButton()
            b.setText(f'{name}  ✕')
            b.setToolTip('Remove this trace')
            b.setStyleSheet(f'QToolButton {{ color: {COLORS[k % len(COLORS)]}; border: 1px solid '
                            f'{theme().palette.border}; border-radius: 8px; padding: 1px 8px; }}')
            b.clicked.connect(lambda _=False, n=name: self.remove_trace(n))
            self.chip_lay.addWidget(b)

    def autorange(self) -> None:
        for p in self.panes.values():
            p.enableAutoRange()

    def _mouse_moved(self, pos) -> None:
        if not self._curves:
            return
        for p in self.panes.values():
            if p.isVisible() and p.sceneBoundingRect().contains(pos):
                xv = p.vb.mapSceneToView(pos).x()
                break
        else:
            return
        if self.kind == 'ac':
            xv = 10 ** xv
        for k, line in self.cursor.items():
            line.setPos(np.log10(xv) if self.kind == 'ac' and xv > 0 else xv)
        parts = [f'{self.axis or "x"} = {xv:.6g}']
        for key, x, y, pane in self._curves[:8]:
            if len(x):
                i = int(np.clip(np.searchsorted(x, xv), 0, len(x) - 1))
                v = y[i]
                parts.append(f'{key} = {float(np.real(v)):.5g}')
        self.readout.setText('\n'.join(parts))

#? -------------------------------------------------------------------------------
