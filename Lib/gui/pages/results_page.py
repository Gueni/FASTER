# Purpose:     Results page: KPIs with PASS / FAIL, every result table, output files and the run log.
"""Results of one analysis run (read from its run folder)."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLineEdit, QPlainTextEdit, QStackedLayout, QTabWidget, QVBoxLayout,
                               QWidget)

from ..widgets import BasePage, Card, DataTable, KpiCard, button, flow, label


#? -------------------------------------------------------------------------------
def open_path(path: str | Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


#? -------------------------------------------------------------------------------
def _fmt_pct(v) -> str:
    return 'n/a' if v is None or (isinstance(v, float) and math.isnan(v)) else f'{100 * v:.2f} %'


#? -------------------------------------------------------------------------------
def _num(v, fmt: str = '{:.4g}') -> str:
    return '-' if v is None else fmt.format(v)


#? -------------------------------------------------------------------------------
class TablePane(QWidget):
    """Filter box + table."""

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter rows…')
        self.filter.setClearButtonEnabled(True)
        self.table = DataTable()
        self.filter.textChanged.connect(self.table.set_filter)
        lay.addWidget(self.filter)
        lay.addWidget(self.table, 1)

    def set_frame(self, df: pd.DataFrame | None) -> None:
        self.table.set_frame(df if df is not None else pd.DataFrame({'': ['No data for this run']}))


#? -------------------------------------------------------------------------------
class ResultsPage(BasePage):
    title     = 'Results'
    subtitle  = 'Key figures, result tables and files of the analysis'
    icon_name = 'chart'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        self.run_dir: Path | None = None
        self.summary: dict = {}
        self.stack = QStackedLayout(self)

        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch(1)
        msg = label('No results yet.\nRun an analysis, or open a previous run from History.', 'Empty')
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(msg)
        el.addStretch(1)
        self.stack.addWidget(empty)

        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(16, 14, 16, 16)
        v.setSpacing(12)
        self.head = Card('', '', 'chart')
        self.report_btn = button('Open report', 'report', 'primary', slot=self._open_report)
        self.folder_btn = button('Open folder', 'folder', slot=lambda: self.run_dir and open_path(self.run_dir))
        self.wave_btn   = button('Waveforms', 'activity', slot=lambda: self.ctx.show_page('Waveforms'))
        for b in (self.wave_btn, self.folder_btn, self.report_btn):
            self.head.header_actions.addWidget(b)
        self.kpis = {k: KpiCard(k) for k in ('Verdict', 'SPFM', 'LFM', 'PMHF', 'System FIT', 'MTTF',
                                            'Worst case', 'Monte Carlo')}
        self.head.add(flow(*self.kpis.values(), spacing=10))
        v.addWidget(self.head)

        self.tabs = QTabWidget()
        self.panes: dict[str, TablePane] = {}
        for name in ('ISO 26262', 'Lambda', 'FMEDA', 'FTA', 'Worst case', 'WCA cases', 'Monte Carlo', 'Traces'):
            pane = TablePane()
            self.panes[name] = pane
            self.tabs.addTab(pane, name)
        self.files = TablePane()
        self.files.table.doubleClicked.connect(self._open_file)
        self.tabs.addTab(self.files, 'Files')
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName('Console')
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.tabs.addTab(self.log_view, 'log.log')
        v.addWidget(self.tabs, 1)
        self.stack.addWidget(body)

    # -- loading -------------------------------------------------------------------------
    def load(self, run_dir: str | Path) -> bool:
        run_dir = Path(run_dir)
        if not run_dir.is_dir():
            return False
        self.run_dir = run_dir
        try:
            self.summary = json.loads((run_dir / 'summary.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.summary = {'circuit': run_dir.name, 'outputs': {}}
        s = self.summary
        started = s.get('started', '')
        try:
            started = datetime.fromisoformat(started).strftime('%d %b %Y  %H:%M')
        except (TypeError, ValueError):
            pass
        self.head.title_label.setText(f"{s.get('circuit', run_dir.name)}")
        errs = s.get('errors') or {}
        sub  = f"{started}  ·  {s.get('seconds', '?')} s  ·  {s.get('components', '?')} components  ·  {run_dir}"
        if errs:
            sub += '  ·  ⚠ ' + '; '.join(f'{k}: {v}' for k, v in errs.items())
        self.head.set_subtitle(sub)
        self._fill_kpis()
        self._fill_tables()
        self.stack.setCurrentIndex(1)
        return True

    def _output(self, key: str) -> Path | None:
        name = (self.summary.get('outputs') or {}).get(key)
        if name and (self.run_dir / name).exists():
            return self.run_dir / name
        return None

    def _fill_kpis(self) -> None:
        s   = self.summary
        iso = s.get('iso26262') or {}
        m   = iso.get('metrics') or {}
        res = {r.get('Metric'): r.get('Result') for r in iso.get('table', [])}
        state = lambda key: {'PASS': 'pass', 'FAIL': 'fail'}.get(res.get(key), '')     # noqa: E731
        if iso:
            self.kpis['Verdict'].set('PASS' if iso.get('passed') else 'FAIL', f"Target ASIL {iso.get('asil')}",
                                     'pass' if iso.get('passed') else 'fail')
        else:
            self.kpis['Verdict'].set('-', 'no ISO 26262 data')
        self.kpis['SPFM'].set(_fmt_pct(m.get('SPFM')), 'single-point fault metric', state('SPFM'))
        self.kpis['LFM'].set(_fmt_pct(m.get('LFM')), 'latent fault metric', state('LFM'))
        self.kpis['PMHF'].set(f"{_num(m.get('PMHF'))} FIT", 'probabilistic metric', state('PMHF'))
        fta = s.get('fta') or {}
        self.kpis['System FIT'].set(_num(fta.get('Total FIT')), f"{fta.get('Failure Modes', '-')} failure modes")
        mttf = fta.get('MTTF (h)')
        self.kpis['MTTF'].set(f'{mttf / 8760:.4g} y' if mttf else '-',
                              f"P(fail) {_num(fta.get('Probability'), '{:.2e}')} / {fta.get('Mission (h)', '-')} h")
        wca = (s.get('wca') or {}).get('table') or []
        if wca:
            worst = max(wca, key=lambda r: r.get('Deviation (%)') or 0)
            self.kpis['Worst case'].set(f"{worst.get('Deviation (%)', 0):.2f} %",
                                        f"{worst.get('Output')} · {worst.get('Worst Case Values')}")
        else:
            self.kpis['Worst case'].set('-', 'not run')
        mc = s.get('montecarlo') or {}
        peak = next((r for r in mc.get('table', []) if r.get('Metric') == 'Peak'), None)
        if peak:
            self.kpis['Monte Carlo'].set(f"{_num(peak.get('mean'))} ± {_num(peak.get('std'), '{:.2g}')}",
                                         f"peak {mc.get('output')} · {mc.get('runs')} runs")
        else:
            self.kpis['Monte Carlo'].set('-', 'not run')

    @staticmethod
    def _sheet(path: Path | None, sheet: str) -> pd.DataFrame | None:
        if path is None:
            return None
        try:
            return pd.read_excel(path, sheet_name=sheet)
        except Exception:
            return None

    def _fill_tables(self) -> None:
        s = self.summary
        fmeda, fta, wca = self._output('fmeda'), self._output('fta'), self._output('wca')
        iso = pd.DataFrame((s.get('iso26262') or {}).get('table') or [])
        self.panes['ISO 26262'].set_frame(iso if not iso.empty else self._sheet(fmeda, 'ISO 26262 metrics'))
        self.panes['Lambda'].set_frame(self._sheet(fmeda, 'Lambda per component'))
        self.panes['FMEDA'].set_frame(self._sheet(fmeda, 'FMEDA'))
        self.panes['FTA'].set_frame(self._sheet(fta, 'Failure Modes'))
        self.panes['Worst case'].set_frame(self._sheet(wca, 'Summary'))
        self.panes['WCA cases'].set_frame(self._sheet(wca, 'Cases'))
        samples = self._output('montecarlo_samples')
        self.panes['Monte Carlo'].set_frame(pd.read_csv(samples) if samples else None)
        traces = pd.DataFrame(s.get('traces') or [])
        self.panes['Traces'].set_frame(traces if not traces.empty else None)
        for name, has in (('Worst case', wca), ('WCA cases', wca), ('Monte Carlo', samples)):
            self.tabs.setTabEnabled(self.tabs.indexOf(self.panes[name]), has is not None)
        rows = [{'Output': k, 'File': v, 'Size (kB)': round((self.run_dir / v).stat().st_size / 1024, 1)}
                for k, v in (s.get('outputs') or {}).items() if (self.run_dir / v).exists()]
        if not rows:
            rows = [{'Output': '', 'File': p.name, 'Size (kB)': round(p.stat().st_size / 1024, 1)}
                    for p in sorted(self.run_dir.iterdir()) if p.is_file()]
        self.files.set_frame(pd.DataFrame(rows))
        log = self.run_dir / 'log.log'
        self.log_view.setPlainText(log.read_text(encoding='utf-8', errors='replace') if log.exists() else '')

    # -- actions -------------------------------------------------------------------------
    def _open_report(self) -> None:
        report = self._output('report')
        if report:
            open_path(report)
        else:
            self.ctx.toast('This run has no HTML report.', 'warning')

    def _open_file(self, index) -> None:
        src = self.files.table.proxy.mapToSource(index)
        name = self.files.table.model_.frame().iloc[src.row()]['File']
        open_path(self.run_dir / name)

    def nominal_raw(self) -> Path | None:
        return self._output('nominal_raw') if self.run_dir else None

    def mc_waveforms(self) -> Path | None:
        return self._output('montecarlo_waveforms') if self.run_dir else None
