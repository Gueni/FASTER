# Purpose:     Analysis page: choose the analyses and set every parameter (mission profile, ISO 26262, tolerances).
"""Analysis setup page.

Global choices (steps, mission profile, ASIL, Monte Carlo settings) are
remembered between sessions; the per-component setup (tolerances, safety
mechanisms, outputs) is remembered per circuit.
"""

from __future__ import annotations

import copy
import json
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView,
                               QListWidget, QListWidgetItem, QSpinBox, QTableWidget, QTableWidgetItem, QWidget)

from ...core.config import load_config
from ...knowledge.fit_rates import ENVIRONMENTS
from .. import settings
from ..session import numeric
from ..widgets import Card, ScrollPage, button, combo, field, flow, label, row

PASSIVE     = ('resistor', 'capacitor', 'electrolytic capacitor', 'inductor', 'ferrite bead')
DEFAULT_TOL = {'resistor': 1.0, 'capacitor': 10.0, 'electrolytic capacitor': 20.0, 'inductor': 20.0,
               'ferrite bead': 25.0}
DC_LEVELS   = ['none', 'low', 'medium', 'high']
DC_TIPS     = 'Diagnostic coverage (ISO 26262-5 Annex D): none 0 %, low 60 %, medium 90 %, high 99 %'
TWO_PIN     = ('resistor', 'capacitor', 'electrolytic capacitor', 'inductor', 'ferrite bead', 'diode', 'zener',
               'schottky', 'tvs', 'LED', 'voltage', 'current', 'fuse', 'battery')


#? -------------------------------------------------------------------------------
def _spec_tolerance(comp: dict) -> float | None:
    """Tolerance written in the schematic, e.g. ``SpiceLine tol=1``."""
    for key in ('SpiceLine', 'SpiceLine2', 'Value2'):
        m = re.search(r'\btol\s*=\s*([\d.]+)', comp['attributes'].get(key, ''), re.I)
        if m:
            return float(m.group(1))
    return None


#? -------------------------------------------------------------------------------
def _level(value) -> str:
    if isinstance(value, str) and value.lower() in DC_LEVELS:
        return value.lower()
    try:
        v = float(str(value).rstrip('%'))
    except ValueError:
        return 'none'
    v = v * 100 if v <= 1 else v
    return 'high' if v >= 99 else 'medium' if v >= 90 else 'low' if v >= 60 else 'none'


#? -------------------------------------------------------------------------------
def _check_item(checked: bool) -> QTableWidgetItem:
    it = QTableWidgetItem()
    it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return it


#? -------------------------------------------------------------------------------
def _text_item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return it


#? -------------------------------------------------------------------------------
def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(40)
    t.setAlternatingRowColors(True)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.setMinimumHeight(220)
    return t


#? -------------------------------------------------------------------------------
class AnalysisPage(ScrollPage):
    title            = 'Analysis'
    subtitle         = 'Choose what to run and set the analysis parameters'
    icon_name        = 'flask'
    min_column_width = 460

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        self.session = ctx.session
        self.project = load_config()
        self._building = False
        self._build_run_card()
        self._build_profile_card()
        self._build_mc_card()
        self._build_tol_card()
        self._build_iso_card()
        self._build_wca_card()
        self._restore_globals()
        self.session.loaded.connect(lambda *_: self.load_circuit())
        self.session.changed.connect(self._circuit_edited)
        self.session.closed.connect(self.load_circuit)
        self.load_circuit()

    # -- cards ---------------------------------------------------------------------------
    def _build_run_card(self) -> None:
        card = Card('Run', 'Pick the steps to perform. FMEDA, ISO 26262 metrics, FTA, the schematic image, '
                    'the HTML report and log.log are always produced.', 'play')
        self.chk_sim = QCheckBox('Nominal simulation')
        self.chk_wca = QCheckBox('Worst-case analysis')
        self.chk_mc  = QCheckBox('Monte Carlo')
        self.chk_keep = QCheckBox('Keep LTspice files')
        self.chk_sim.setToolTip('Run LTspice: needed for waveforms, WCA and Monte Carlo')
        for c in (self.chk_sim, self.chk_wca, self.chk_mc, self.chk_keep):
            c.toggled.connect(self._update_estimate)
        self.chk_sim.toggled.connect(lambda on: (self.chk_wca.setEnabled(on), self.chk_mc.setEnabled(on)))
        steps = flow(*(self._fixed(t) for t in ('FMEDA', 'ISO 26262', 'FTA', 'Report')),
                     self.chk_sim, self.chk_wca, self.chk_mc, self.chk_keep, spacing=14)
        card.add(steps)
        self.estimate = label('', 'Hint')
        self.run_btn  = button('Run analysis', 'play', 'primary', tip='Run the selected analyses (Ctrl+R)',
                               slot=self.ctx.run_analysis, big=True)
        card.add(row(self.estimate, None, self.run_btn, stretch=[1, 1, 0]))
        self.busy_actions(self.run_btn)
        self.grid.add(card, span=3)

    @staticmethod
    def _fixed(text: str) -> QCheckBox:
        c = QCheckBox(text)
        c.setChecked(True)
        c.setEnabled(False)
        return c

    def _build_profile_card(self) -> None:
        card = Card('Mission profile', 'Component temperature and environment scale the base FIT rates '
                    '(IEC 61709 temperature factor, MIL-HDBK-217F environment factor).', 'thermometer')
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(-55, 175)
        self.temperature.setDecimals(0)
        self.temperature.setSuffix(' °C')
        self.environment = QComboBox()
        for code, (factor, desc) in ENVIRONMENTS.items():
            self.environment.addItem(f'{code}  -  {desc}', code)
            self.environment.setItemData(self.environment.count() - 1, f'πE = {factor:g}', Qt.ItemDataRole.ToolTipRole)
        self.mission = QSpinBox()
        self.mission.setRange(1, 1_000_000)
        self.mission.setSingleStep(1000)
        self.mission.setSuffix(' h')
        self.asil = combo(['QM', 'A', 'B', 'C', 'D'], 'B')
        self.asil.setToolTip('Target ASIL: sets the SPFM / LFM / PMHF targets (ISO 26262-5 Tables 4-6)')
        card.add(row(field('Temperature', self.temperature), field('Mission time', self.mission)))
        card.add(field('Environment', self.environment))
        card.add(field('Target ASIL', self.asil, 'SPFM / LFM / PMHF targets: B 90 % / 60 % / 100 FIT, '
                       'C 97 % / 80 % / 100 FIT, D 99 % / 90 % / 10 FIT'))
        self.grid.add(card)

    def _build_mc_card(self) -> None:
        card = Card('Monte Carlo', 'Random component values inside their tolerance, simulated in parallel.', 'dice')
        self.mc_runs = QSpinBox()
        self.mc_runs.setRange(2, 100_000)
        self.mc_runs.setSingleStep(10)
        self.mc_runs.valueChanged.connect(self._update_estimate)
        self.mc_dist = combo(['uniform', 'gaussian'])
        self.mc_dist.setToolTip('gaussian: 3 sigma = tolerance, clipped to the tolerance band')
        self.mc_seed = QSpinBox()
        self.mc_seed.setRange(0, 2_147_483_647)
        self.mc_seed.setSpecialValueText('random')
        self.mc_output = QComboBox()
        self.mc_output.setEditable(True)
        card.add(row(field('Runs', self.mc_runs), field('Distribution', self.mc_dist)))
        card.add(row(field('Seed', self.mc_seed), field('Output', self.mc_output)))
        self.grid.add(card)

    def _build_wca_card(self) -> None:
        card = Card('Worst-case outputs', 'Signals compared between the nominal and the extreme cases.', 'target')
        self.outputs = QListWidget()
        self.outputs.setMinimumHeight(170)
        self.outputs.itemChanged.connect(lambda *_: self._update_estimate())
        self.max_corners = QSpinBox()
        self.max_corners.setRange(1, 16)
        self.max_corners.setToolTip('All 2^N corners are simulated up to this many components; '
                                    'above it, components are varied one at a time.')
        self.max_corners.valueChanged.connect(self._update_estimate)
        card.add(self.outputs)
        card.add(field('Full corner search up to', self.max_corners, 'components (2^N simulations)'))
        self.grid.add(card)

    def _build_tol_card(self) -> None:
        card = Card('Tolerances', 'Tolerance (±%) of each component and whether it is varied in the worst-case '
                    'and Monte Carlo analyses. Defaults come from tol= in the schematic.', 'settings')
        self.tol_table = _table(['Component', 'Type', 'Value', 'Tolerance', 'WCA', 'Monte Carlo'])
        self.tol_table.itemChanged.connect(lambda *_: self._update_estimate())
        card.add(self.tol_table)
        card.add(row(button('Passives only', 'check', slot=lambda: self._bulk_tol('passive')),
                     button('All', 'check', slot=lambda: self._bulk_tol('all')),
                     button('None', 'x', slot=lambda: self._bulk_tol('none')),
                     button('Reset tolerances', 'undo', slot=lambda: self._bulk_tol('reset')), None,
                     stretch=[0, 0, 0, 0, 1]))
        self.grid.add(card, span=3)

    def _build_iso_card(self) -> None:
        card = Card('ISO 26262 safety mechanisms', 'Safe fraction and diagnostic coverage per component. '
                    + DC_TIPS + '.', 'shield')
        self.iso_table = _table(['Component', 'Type', 'Safety related', 'Diagnostic coverage', 'Latent coverage',
                                 'Safe fraction'])
        card.add(self.iso_table)
        self.bulk_dc  = combo(DC_LEVELS, 'medium')
        self.bulk_lat = combo(DC_LEVELS, 'medium')
        card.add(row(label('Set all:', 'FieldLabel'), self.bulk_dc,
                     button('Diagnostic coverage', slot=lambda: self._bulk_iso(3, self.bulk_dc.currentText())),
                     self.bulk_lat,
                     button('Latent coverage', slot=lambda: self._bulk_iso(4, self.bulk_lat.currentText())),
                     None, stretch=[0, 0, 0, 0, 0, 1]))
        self.grid.add(card, span=3)

    # -- circuit -------------------------------------------------------------------------
    def load_circuit(self) -> None:
        """Rebuild the tables for the open circuit: defaults < config.json < saved setup."""
        self._building = True
        comps = self.session.components() if self.session.is_open else []
        saved = settings.load_circuit_state(self.session.path) if self.session.is_open else {}
        proj_wca = self.project['wca'].get('components', {}) or {}
        proj_mc  = self.project['montecarlo'].get('tolerances', {}) or {}
        proj_iso = self.project['iso26262']

        self.tol_table.setRowCount(0)
        self.iso_table.setRowCount(0)
        self._tol_spins: dict[str, QDoubleSpinBox] = {}
        self._iso_widgets: dict[str, tuple] = {}
        for comp in comps:
            name, ctype, value = comp['name'], comp['type'], comp['value'] or ''
            nominal = numeric(value)
            # tolerances
            if nominal is not None:
                tol = _spec_tolerance(comp) or DEFAULT_TOL.get(ctype, 5.0)
                in_wca = ctype in PASSIVE
                in_mc  = ctype in PASSIVE
                if name in proj_wca or name in proj_mc:
                    entry  = proj_wca.get(name, proj_mc.get(name))
                    tol    = float(entry['tolerance'] if isinstance(entry, dict) else entry)
                    in_wca, in_mc = name in proj_wca, name in proj_mc
                tol, in_wca, in_mc = saved.get('tol', {}).get(name, [tol, in_wca, in_mc])
                r = self.tol_table.rowCount()
                self.tol_table.insertRow(r)
                self.tol_table.setItem(r, 0, _text_item(name))
                self.tol_table.setItem(r, 1, _text_item(ctype))
                self.tol_table.setItem(r, 2, _text_item(value))
                spin = QDoubleSpinBox()
                spin.setRange(0.0, 100.0)
                spin.setDecimals(2)
                spin.setSuffix(' %')
                spin.setValue(float(tol))
                self.tol_table.setCellWidget(r, 3, spin)
                self._tol_spins[name] = spin
                self.tol_table.setItem(r, 4, _check_item(bool(in_wca)))
                self.tol_table.setItem(r, 5, _check_item(bool(in_mc)))
            # ISO 26262
            sr  = name not in (proj_iso.get('not_safety_related') or [])
            dc  = _level(self._project_value(proj_iso.get('diagnostic_coverage'), name, ctype))
            lat = _level(self._project_value(proj_iso.get('latent_coverage'), name, ctype))
            safe = float(self._project_value(proj_iso.get('safe_fraction'), name, ctype) or 0)
            safe = safe * 100 if safe <= 1 else safe
            sr, dc, lat, safe = saved.get('iso', {}).get(name, [sr, dc, lat, safe])
            r = self.iso_table.rowCount()
            self.iso_table.insertRow(r)
            self.iso_table.setItem(r, 0, _text_item(name))
            self.iso_table.setItem(r, 1, _text_item(ctype))
            self.iso_table.setItem(r, 2, _check_item(bool(sr)))
            dc_box, lat_box = combo(DC_LEVELS, dc), combo(DC_LEVELS, lat)
            dc_box.setToolTip(DC_TIPS)
            lat_box.setToolTip('Coverage of latent multiple-point faults (e.g. start-up tests)')
            safe_spin = QDoubleSpinBox()
            safe_spin.setRange(0, 100)
            safe_spin.setDecimals(0)
            safe_spin.setSuffix(' %')
            safe_spin.setValue(float(safe))
            safe_spin.setToolTip('Share of the failure rate that cannot violate the safety goal')
            self.iso_table.setCellWidget(r, 3, dc_box)
            self.iso_table.setCellWidget(r, 4, lat_box)
            self.iso_table.setCellWidget(r, 5, safe_spin)
            self._iso_widgets[name] = (dc_box, lat_box, safe_spin)

        # outputs
        candidates = self._candidates()
        chosen = saved.get('outputs') or [o for o in self.project['wca'].get('output_variables', [])
                                          if o.lower() in {c.lower() for c in candidates}]
        if not chosen:
            chosen = [c for c in candidates if c.lower() == 'v(out)'] or candidates[:1]
        self.outputs.clear()
        for c in candidates:
            it = QListWidgetItem(c)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if c in chosen else Qt.CheckState.Unchecked)
            self.outputs.addItem(it)
        self.mc_output.clear()
        self.mc_output.addItems(candidates)
        mc_out = saved.get('mc_output') or self.project['montecarlo'].get('output_variable') or (chosen[:1] or [''])[0]
        idx = self.mc_output.findText(mc_out, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.mc_output.setCurrentIndex(idx)
        elif mc_out:
            self.mc_output.setEditText(mc_out)
        for t in (self.tol_table, self.iso_table):
            t.setMinimumHeight(min(80 + 40 * max(t.rowCount(), 1), 520))
        self._building = False
        self.run_btn.setEnabled(self.session.is_open and not self.ctx.worker.busy)
        self._update_estimate()

    @staticmethod
    def _project_value(table: dict | None, name: str, ctype: str):
        if not table:
            return None
        for key in (name, ctype, '*'):
            v = table.get(key)
            if v is not None:
                return v.get('*', next(iter(v.values()), None)) if isinstance(v, dict) else v
        return None

    def _candidates(self) -> list[str]:
        if not self.session.is_open:
            return []
        circ  = self.session.circuit
        nets  = sorted({n for n in circ['flags'].values() if n != '0'}, key=str.lower)
        out   = [f'V({n})' for n in nets]
        out  += [f"I({c['name']})" for c in circ['components'] if c['type'] in TWO_PIN]
        return out

    def _circuit_edited(self) -> None:
        """Values changed: keep the setup, refresh the value column."""
        state = self.circuit_state()
        if self.session.is_open:
            settings.save_circuit_state(self.session.path, state)
        self.load_circuit()

    # -- state ---------------------------------------------------------------------------
    def circuit_state(self) -> dict:
        tol = {}
        for r in range(self.tol_table.rowCount()):
            name = self.tol_table.item(r, 0).text()
            tol[name] = [self._tol_spins[name].value(),
                         self.tol_table.item(r, 4).checkState() == Qt.CheckState.Checked,
                         self.tol_table.item(r, 5).checkState() == Qt.CheckState.Checked]
        iso = {}
        for r in range(self.iso_table.rowCount()):
            name = self.iso_table.item(r, 0).text()
            dc, lat, safe = self._iso_widgets[name]
            iso[name] = [self.iso_table.item(r, 2).checkState() == Qt.CheckState.Checked,
                         dc.currentText(), lat.currentText(), safe.value()]
        outputs = [self.outputs.item(i).text() for i in range(self.outputs.count())
                   if self.outputs.item(i).checkState() == Qt.CheckState.Checked]
        return {'tol': tol, 'iso': iso, 'outputs': outputs, 'mc_output': self.mc_output.currentText()}

    def save_state(self) -> None:
        if self.session.is_open:
            settings.save_circuit_state(self.session.path, self.circuit_state())
        settings.put('analysis/globals', json.dumps({
            'sim': self.chk_sim.isChecked(), 'wca': self.chk_wca.isChecked(), 'mc': self.chk_mc.isChecked(),
            'keep': self.chk_keep.isChecked(), 'temperature': self.temperature.value(),
            'environment': self.environment.currentData(), 'mission': self.mission.value(),
            'asil': self.asil.currentText(), 'runs': self.mc_runs.value(), 'dist': self.mc_dist.currentText(),
            'seed': self.mc_seed.value(), 'corners': self.max_corners.value()}))

    def _restore_globals(self) -> None:
        try:
            g = json.loads(settings.get('analysis/globals', '{}') or '{}')
        except (TypeError, ValueError):
            g = {}
        pro = self.project
        self.chk_sim.setChecked(bool(g.get('sim', True)))
        self.chk_wca.setChecked(bool(g.get('wca', pro['wca'].get('enabled', True))))
        self.chk_mc.setChecked(bool(g.get('mc', pro['montecarlo'].get('enabled', True))))
        self.chk_keep.setChecked(bool(g.get('keep', False)))
        self.temperature.setValue(float(g.get('temperature', pro['reliability']['temperature_c'])))
        env = g.get('environment', pro['reliability']['environment'])
        self.environment.setCurrentIndex(max(0, self.environment.findData(str(env).upper())))
        self.mission.setValue(int(g.get('mission', pro['fta']['mission_hours'])))
        self.asil.setCurrentText(str(g.get('asil', pro['iso26262'].get('target_asil', 'B'))))
        self.mc_runs.setValue(int(g.get('runs', pro['montecarlo']['runs'])))
        self.mc_dist.setCurrentText(str(g.get('dist', pro['montecarlo']['distribution'])))
        self.mc_seed.setValue(int(g.get('seed', pro['montecarlo'].get('seed') or 0)))
        self.max_corners.setValue(int(g.get('corners', pro['wca'].get('max_corner_components', 8))))

    # -- bulk actions -------------------------------------------------------------------
    def _bulk_tol(self, mode: str) -> None:
        comps = {c['name']: c for c in self.session.components()}
        for r in range(self.tol_table.rowCount()):
            name  = self.tol_table.item(r, 0).text()
            ctype = self.tol_table.item(r, 1).text()
            if mode == 'reset':
                self._tol_spins[name].setValue(_spec_tolerance(comps[name]) or DEFAULT_TOL.get(ctype, 5.0))
                continue
            on = mode == 'all' or (mode == 'passive' and ctype in PASSIVE)
            for col in (4, 5):
                self.tol_table.item(r, col).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _bulk_iso(self, col: int, level: str) -> None:
        for dc, lat, _ in self._iso_widgets.values():
            (dc if col == 3 else lat).setCurrentText(level)

    # -- estimate / config ----------------------------------------------------------------
    def _selected(self, col: int) -> dict[str, float]:
        out = {}
        for r in range(self.tol_table.rowCount()):
            if self.tol_table.item(r, col) and self.tol_table.item(r, col).checkState() == Qt.CheckState.Checked:
                name = self.tol_table.item(r, 0).text()
                out[name] = self._tol_spins[name].value()
        return out

    def _update_estimate(self, *_) -> None:
        if self._building or not hasattr(self, 'estimate'):
            return
        if not self.session.is_open:
            self.estimate.setText('Open a schematic to start.')
            return
        sims = 0
        parts = []
        if self.chk_sim.isChecked():
            sims += 1
            n = len(self._selected(4))
            if self.chk_wca.isChecked() and n:
                corners = 2 ** n if n <= self.max_corners.value() else 2 * n
                sims += 1 + corners
                parts.append(f'WCA {corners + 1}')
            if self.chk_mc.isChecked() and self._selected(5):
                sims += 1 + self.mc_runs.value()
                parts.append(f'Monte Carlo {self.mc_runs.value() + 1}')
        detail = f" ({', '.join(parts)})" if parts else ''
        comps  = len(self.session.components())
        self.estimate.setText(f'{comps} components  ·  ≈ {sims} LTspice simulation{"s" * (sims != 1)}{detail}')

    def validate(self) -> str | None:
        if self.chk_sim.isChecked() and self.chk_wca.isChecked():
            if not self._selected(4):
                return 'Worst-case analysis: tick at least one component in the Tolerances table (WCA column).'
            if not self.circuit_state()['outputs']:
                return 'Worst-case analysis: tick at least one output signal.'
        if self.chk_sim.isChecked() and self.chk_mc.isChecked():
            if not self._selected(5):
                return 'Monte Carlo: tick at least one component in the Tolerances table (Monte Carlo column).'
            if not self.mc_output.currentText().strip():
                return 'Monte Carlo: choose an output signal.'
        return None

    def build_config(self) -> dict:
        cfg   = copy.deepcopy(self.project)
        state = self.circuit_state()
        cfg['reliability'].update({'temperature_c': self.temperature.value(),
                                   'environment': self.environment.currentData(),
                                   'fit_overrides': self.ctx.fit_overrides()})
        cfg['fta']['mission_hours'] = self.mission.value()
        iso = {'target_asil': self.asil.currentText(), 'not_safety_related': [],
               'safe_fraction': {}, 'diagnostic_coverage': {}, 'latent_coverage': {}}
        for name, (sr, dc, lat, safe) in state['iso'].items():
            if not sr:
                iso['not_safety_related'].append(name)
            iso['diagnostic_coverage'][name] = {'*': dc}
            iso['latent_coverage'][name]     = {'*': lat}
            if safe:
                iso['safe_fraction'][name] = {'*': safe / 100.0}
        cfg['iso26262'] = iso
        cfg['wca'] = {**cfg['wca'], 'enabled': self.chk_wca.isChecked(), 'analysis_type': 'passive',
                      'components': self._selected(4), 'output_variables': state['outputs'],
                      'max_corner_components': self.max_corners.value()}
        cfg['montecarlo'] = {**cfg['montecarlo'], 'enabled': self.chk_mc.isChecked(), 'runs': self.mc_runs.value(),
                             'distribution': self.mc_dist.currentText(), 'seed': self.mc_seed.value() or None,
                             'output_variable': self.mc_output.currentText().strip(),
                             'tolerances': self._selected(5)}
        cfg.update(self.ctx.run_settings())
        return cfg

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self.run_btn.setEnabled(not busy and self.session.is_open)
