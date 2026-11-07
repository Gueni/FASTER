#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                          __  ___      __
#?                         / / / (_)____/ /_____  _______  __
#?                        / /_/ / / ___/ __/ __ \/ ___/ / / /
#?                       / __  / (__  ) /_/ /_/ / /  / /_/ /
#?                      /_/ /_/_/____/\__/\____/_/   \__, /
#?                                                  /____/
#?
#? Name:        history_page.py
#? Purpose:     History page: every previous analysis run with its verdict; reopen, open report or delete.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Run history (scans the output folder for run folders)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import QLineEdit, QVBoxLayout

from ..widgets import BasePage, Card, DataTable, button, row
from .results_page import open_path


#? -------------------------------------------------------------------------------
def scan_runs(root: Path) -> pd.DataFrame:
    rows = []
    if root.is_dir():
        for d in root.iterdir():
            if not d.is_dir() or not (d / 'log.log').exists():
                continue
            s = {}
            try:
                s = json.loads((d / 'summary.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
            iso = s.get('iso26262') or {}
            m   = iso.get('metrics') or {}
            try:
                when = datetime.fromisoformat(s['started'])
            except (KeyError, TypeError, ValueError):
                when = datetime.fromtimestamp((d / 'log.log').stat().st_mtime)
            fta = s.get('fta') or {}
            rows.append({
                'Date': when.strftime('%Y-%m-%d %H:%M'),
                'Circuit': s.get('circuit', d.name.rsplit('_', 2)[0]),
                'Verdict': ('PASS' if iso.get('passed') else 'FAIL') if iso else '',
                'ASIL': iso.get('asil', ''),
                'SPFM (%)': round(100 * m['SPFM'], 2) if m.get('SPFM') is not None else None,
                'LFM (%)': round(100 * m['LFM'], 2) if m.get('LFM') is not None else None,
                'PMHF (FIT)': round(m['PMHF'], 3) if m.get('PMHF') is not None else None,
                'System FIT': round(fta['Total FIT'], 2) if fta.get('Total FIT') is not None else None,
                'WCA': 'yes' if s.get('wca') else '',
                'Monte Carlo': (s.get('montecarlo') or {}).get('runs', ''),
                'Time (s)': s.get('seconds'),
                'Errors': len(s.get('errors') or {}),
                'Folder': d.name,
            })
    df = pd.DataFrame(rows)
    return df.sort_values('Date', ascending=False).reset_index(drop=True) if not df.empty else df


#? -------------------------------------------------------------------------------
class HistoryPage(BasePage):
    title     = 'History'
    subtitle  = 'Previous analyses: double-click to open the results'
    icon_name = 'history'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        card        = Card('Runs', '', 'history', expand=True)
        self.card   = card
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter by circuit, date, verdict…')
        self.filter.setClearButtonEnabled(True)
        self.table = DataTable()
        self.filter.textChanged.connect(self.table.set_filter)
        self.table.doubleClicked.connect(lambda *_: self._open())
        card.add(self.filter)
        card.add(self.table, 1)
        self.delete_btn = button('Delete', 'trash', 'danger', slot=self._delete)
        card.add(row(button('Open results', 'chart', 'primary', slot=self._open),
                     button('Report', 'report', slot=lambda: self._file('report')),
                     button('Folder', 'folder', slot=lambda: self._folder() and open_path(self._folder())),
                     button('Refresh', 'refresh', slot=self.refresh), None, self.delete_btn,
                     stretch=[0, 0, 0, 0, 1, 0]))
        self.busy_actions(self.delete_btn)
        outer.addWidget(card)

    def refresh(self) -> None:
        root = self.ctx.output_root()
        df   = scan_runs(root)
        self.table.set_frame(df)
        self.card.set_subtitle(f'{len(df)} run{"s" * (len(df) != 1)} in {root}')

    def _folder(self) -> Path | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            self.ctx.toast('Select a run first.', 'info', 1800)
            return None
        src = self.table.proxy.mapToSource(idx)
        return self.ctx.output_root() / self.table.model_.frame().iloc[src.row()]['Folder']

    def _open(self) -> None:
        folder = self._folder()
        if folder:
            self.ctx.show_results(folder)

    def _file(self, key: str) -> None:
        folder = self._folder()
        if not folder:
            return
        try:
            name = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))['outputs'][key]
            open_path(folder / name)
        except (OSError, ValueError, KeyError):
            hits = list(folder.glob('report_*.html'))
            if hits:
                open_path(hits[0])
            else:
                self.ctx.toast('No report in this run.', 'warning')

    def _delete(self) -> None:
        folder = self._folder()
        if folder and self.ctx.confirm('Delete run', f'Delete the run folder?\n{folder}', danger=True,
                                       ok_text='Delete'):
            shutil.rmtree(folder, ignore_errors=True)
            self.refresh()
            self.ctx.toast('Run deleted', 'info', 2000)

#? -------------------------------------------------------------------------------
