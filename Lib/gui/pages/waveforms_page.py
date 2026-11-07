#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?             _       __                 ____
#?            | |     / /___ __   _____  / __/___  _________ ___  _____
#?            | | /| / / __ `/ | / / _ \/ /_/ __ \/ ___/ __ `__ \/ ___/
#?            | |/ |/ / /_/ /| |/ /  __/ __/ /_/ / /  / / / / / (__  )
#?            |__/|__/\__,_/ |___/\___/_/  \____/_/  /_/ /_/ /_/____/
#?
#? Name:        waveforms_page.py
#? Purpose:     Waveforms page: fast native plots of simulation traces and Monte Carlo runs.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Waveform viewer (pyqtgraph): voltages and currents on linked plots, crosshair read-out."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QSplitter, QVBoxLayout, QWidget)

from ...simulation.waveforms import axis_name, decimate_index, get_wave, open_raw
from ..theme import theme
from ..widgets import BasePage, Card, button, label

COLORS = ['#4c8dff', '#2fbf71', '#f5a524', '#e5484d', '#a78bfa', '#22c3ee', '#f472b6', '#84cc16', '#fb923c',
          '#94a3b8']
MAX_POINTS = 20000


#? -------------------------------------------------------------------------------
class WaveformsPage(BasePage):
    title     = 'Waveforms'
    subtitle  = 'Simulated voltages and currents of the nominal run and the Monte Carlo spread'
    icon_name = 'activity'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        pg.setConfigOptions(antialias=True)
        self.raw = None
        self.raw_path: Path | None = None
        self.mc_path: Path | None = None
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        outer.addWidget(split)

        side = Card('Traces', 'Tick the signals to plot.', 'list', expand=True)
        side.setMinimumWidth(240)
        side.setMaximumWidth(380)
        self.source = label('No simulation loaded', 'Hint', wrap=True)
        side.add(self.source)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter…')
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._filter)
        side.add(self.filter)
        self.list = QListWidget()
        self.list.itemChanged.connect(lambda *_: self.replot())
        side.add(self.list, 1)
        self.mc_check = QCheckBox('Overlay Monte Carlo runs')
        self.mc_check.toggled.connect(lambda *_: self.replot())
        side.add(self.mc_check)
        side.add(button('Open .raw file…', 'open', slot=self._open_raw))
        split.addWidget(side)

        plots = QWidget()
        pv    = QVBoxLayout(plots)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(8)
        self.readout = label('', 'Hint')
        pv.addWidget(self.readout)
        self.vplot = pg.PlotWidget()
        self.iplot = pg.PlotWidget()
        self.iplot.setXLink(self.vplot)
        for p, unit in ((self.vplot, 'V'), (self.iplot, 'A')):
            p.showGrid(x=True, y=True, alpha=0.18)
            p.setLabel('left', units=unit)
            p.setLabel('bottom', 'Time', units='s')
            p.addLegend(offset=(10, 10))
            p.setClipToView(True)
            p.setDownsampling(auto=True, mode='peak')
            pv.addWidget(p, 1)
        self.vline = pg.InfiniteLine(angle=90, movable=False)
        self.vplot.addItem(self.vline, ignoreBounds=True)
        self.vplot.scene().sigMouseMoved.connect(self._mouse_moved)
        split.addWidget(plots)
        split.setStretchFactor(1, 1)
        self._curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        theme().changed.connect(lambda *_: self._style())
        self._style()

    #? styling                                                                            
    def _style(self) -> None:
        p = theme().palette
        for plot in (self.vplot, self.iplot):
            plot.setBackground(p.surface)
            for ax in ('left', 'bottom'):
                a = plot.getAxis(ax)
                a.setPen(pg.mkPen(p.border))
                a.setTextPen(pg.mkPen(p.muted))
        self.vline.setPen(pg.mkPen(p.muted, width=1, style=Qt.PenStyle.DashLine))

    #? data                                                                               
    def load_run(self, raw: Path | None, mc_csv: Path | None) -> None:
        self.mc_path = mc_csv
        self.mc_check.setEnabled(mc_csv is not None)
        if raw is None:
            self.raw, self.raw_path = None, None
            self.list.clear()
            self.source.setText('This run has no simulation data (run with "Nominal simulation").')
            self.replot()
            return
        self.load_raw(raw)

    def load_raw(self, path: Path) -> None:
        try:
            self.raw = open_raw(path)
        except Exception as exc:
            self.ctx.toast(f'Cannot read {Path(path).name}: {exc}', 'error')
            return
        self.raw_path = Path(path)
        ax            = axis_name(self.raw)
        names         = [n for n in self.raw.get_trace_names() if n != ax]
        prev  = {self.list.item(i).text() for i in range(self.list.count())
                 if self.list.item(i).checkState() == Qt.CheckState.Checked}
        default = {n for n in names if n.lower() == 'v(out)'} or set(names[:1])
        self.list.blockSignals(True)
        self.list.clear()
        for n in names:
            it = QListWidgetItem(n)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if n in (prev & set(names) or default) else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        steps = len(list(self.raw.get_steps()))
        self.source.setText(f'{self.raw_path.name}  ·  {len(names)} traces' + (f'  ·  {steps} steps' if steps > 1 else ''))
        bottom = {'time': ('Time', 's'), 'frequency': ('Frequency', 'Hz')}.get((ax or '').lower(), ('Point', ''))
        for plot in (self.vplot, self.iplot):
            plot.setLabel('bottom', bottom[0], units=bottom[1])
            plot.setLogMode(x=(ax or '').lower() == 'frequency', y=False)
        self.replot()

    def _filter(self, text: str) -> None:
        t = text.lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def _open_raw(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Open LTspice raw file', str(self.raw_path or Path.home()),
                                              'LTspice raw (*.raw);;All files (*)')
        if path:
            self.load_raw(Path(path))

    #? plotting                                                                           
    def replot(self) -> None:
        for p in (self.vplot, self.iplot):
            p.clear()
            p.addLegend(offset=(10, 10))
        self.vplot.addItem(self.vline, ignoreBounds=True)
        self._curves.clear()
        if self.raw is None:
            return
        selected = [self.list.item(i).text() for i in range(self.list.count())
                    if self.list.item(i).checkState() == Qt.CheckState.Checked]
        steps = list(self.raw.get_steps())
        if self.mc_check.isChecked() and self.mc_path is not None:
            self._plot_mc()
        for k, name in enumerate(selected):
            plot = self.iplot if name.upper().startswith('I(') else self.vplot
            for s in steps:
                x, y = get_wave(self.raw, name, s)
                idx    = decimate_index([y], MAX_POINTS)
                label_ = name if len(steps) == 1 else f'{name} step {s}'
                pen    = pg.mkPen(COLORS[(k + s) % len(COLORS)], width=1.8)
                plot.plot(x[idx], y[idx], pen=pen, name=label_)
                self._curves[label_] = (x, y)
        self.iplot.setVisible(any(n.upper().startswith('I(') for n in selected))
        self.vplot.setVisible(any(not n.upper().startswith('I(') for n in selected) or not selected)

    def _plot_mc(self) -> None:
        try:
            df = pd.read_csv(self.mc_path)
        except Exception:
            return
        x     = df['Axis'].to_numpy()
        runs  = [c for c in df.columns if c.startswith('Run_')]
        p     = theme().palette
        color = pg.mkColor(p.muted)
        color.setAlpha(60)
        idx = decimate_index([df['Nominal'].to_numpy()], 3000)
        for i, c in enumerate(runs[:200]):
            self.vplot.plot(x[idx], df[c].to_numpy()[idx], pen=pg.mkPen(color, width=1),
                            name='Monte Carlo runs' if i == 0 else None)

    def _mouse_moved(self, pos) -> None:
        if not self._curves or not self.vplot.sceneBoundingRect().contains(pos):
            return
        xv = self.vplot.getPlotItem().vb.mapSceneToView(pos).x()
        self.vline.setPos(xv)
        parts = [f'x = {xv:.6g}']
        for name, (x, y) in list(self._curves.items())[:6]:
            if len(x):
                i = int(np.clip(np.searchsorted(x, xv), 0, len(x) - 1))
                parts.append(f'{name} = {y[i]:.5g}')
        self.readout.setText('   ·   '.join(parts))

#? -------------------------------------------------------------------------------
