# Purpose:     Library page: browse failure modes and FIT rates, override base FIT values.
"""Reliability knowledge base browser with FIT overrides."""

from __future__ import annotations

import json

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QHeaderView, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ...knowledge.failures import FAILURE_MODES
from ...knowledge.fit_rates import BASE_FIT, environment_factor, temperature_factor
from .. import settings
from ..widgets import BasePage, Card, DataTable, button, label, row

COLS = ['Type', 'Description', 'Base FIT', 'Ea (eV)', 'FIT @ profile', 'Override', 'Source']


#? -------------------------------------------------------------------------------
class LibraryPage(BasePage):
    title     = 'Library'
    subtitle  = 'Failure modes, mechanisms and FIT rates of every component class'
    icon_name = 'book'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        outer.addWidget(split)

        top = Card('Component classes', 'Base FIT at 40 °C / ground benign (SN 29500, IEC 61709, MIL-HDBK-217F). '
                   'Set an override (FIT at reference conditions) to use your own or supplier data; 0 = none.',
                   'book', expand=True)
        self.profile = label('', 'Hint')
        top.add(self.profile)
        self.table = QTableWidget(len(FAILURE_MODES), len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.overrides = self._load_overrides()
        self.spins: dict[str, QDoubleSpinBox] = {}
        for r, (ctype, entry) in enumerate(FAILURE_MODES.items()):
            data = BASE_FIT[ctype]
            for c, text in enumerate([ctype, entry.description, f'{data.fit:g}', f'{data.ea:g}', '', '', data.source]):
                if c == 5:
                    continue
                it = QTableWidgetItem(text)
                if c in (2, 3, 4):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, it)
            spin = QDoubleSpinBox()
            spin.setRange(0, 1e6)
            spin.setDecimals(3)
            spin.setSpecialValueText('-')
            spin.setValue(float(self.overrides.get(ctype, 0)))
            spin.valueChanged.connect(lambda v, t=ctype: self._override(t, v))
            self.table.setCellWidget(r, 5, spin)
            self.spins[ctype] = spin
        self.table.itemSelectionChanged.connect(self._show_modes)
        top.add(self.table, 1)
        top.add(row(button('Clear overrides', 'undo', slot=self._clear), None, stretch=[0, 1]))
        split.addWidget(top)

        bottom = Card('Failure modes', '', 'alert', expand=True)
        self.modes = DataTable()
        bottom.add(self.modes, 1)
        self.modes_card = bottom
        split.addWidget(bottom)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self.table.selectRow(0)
        self.refresh_profile()

    # -- overrides -----------------------------------------------------------------------
    @staticmethod
    def _load_overrides() -> dict[str, float]:
        try:
            return {k: float(v) for k, v in json.loads(settings.get('library/overrides', '{}') or '{}').items()}
        except (TypeError, ValueError):
            return {}

    def _override(self, ctype: str, value: float) -> None:
        if value > 0:
            self.overrides[ctype] = value
        else:
            self.overrides.pop(ctype, None)
        settings.put('library/overrides', json.dumps(self.overrides))
        self.refresh_profile()

    def _clear(self) -> None:
        for spin in self.spins.values():
            spin.setValue(0)

    def fit_overrides(self) -> dict[str, float]:
        return dict(self.overrides)

    # -- display -------------------------------------------------------------------------
    def refresh_profile(self) -> None:
        page = getattr(self.ctx, 'analysis_page', None)
        temp = page.temperature.value() if page else 40.0
        env  = page.environment.currentData() if page else 'GB'
        pi_e = environment_factor(env)
        self.profile.setText(f'Mission profile from the Analysis page: {temp:g} °C, {env} (πE = {pi_e:g}).')
        for r, ctype in enumerate(FAILURE_MODES):
            data = BASE_FIT[ctype]
            base = self.overrides.get(ctype, data.fit)
            fit  = base * temperature_factor(data.ea, temp) * pi_e
            self.table.item(r, 4).setText(f'{fit:.4g}')

    def _show_modes(self) -> None:
        r = self.table.currentRow()
        if r < 0:
            return
        ctype = self.table.item(r, 0).text()
        entry = FAILURE_MODES[ctype]
        self.modes_card.title_label.setText(f'Failure modes - {ctype}')
        self.modes_card.set_subtitle(f'{entry.description}  ·  source: {entry.source}')
        self.modes.set_frame(pd.DataFrame([{'Failure mode': m.name, 'Distribution (%)': m.distribution,
                                            'Mechanism': m.mechanism, 'Effect': m.effect} for m in entry.modes]))
