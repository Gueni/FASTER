#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                       _____      __  __  _
#?                      / ___/___  / /_/ /_(_)___  ____ ______
#?                      \__ \/ _ \/ __/ __/ / __ \/ __ `/ ___/
#?                     ___/ /  __/ /_/ /_/ / / / / /_/ (__  )
#?                    /____/\___/\__/\__/_/_/ /_/\__, /____/
#?                                              /____/
#?
#? Name:        settings_page.py
#? Purpose:     Settings page: theme, LTspice, output folder, performance and behaviour.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Application settings."""

from __future__ import annotations

import os
import platform
from importlib import metadata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QSpinBox

from ...core.config import find_ltspice
from ...core.paths import APP_DIR, data_dir, ensure_data_dir, results_dir, user_config
from .. import settings
from ..theme import theme
from ..widgets import Card, PathField, ScrollPage, button, combo, field, label, row
from .results_page import open_path


#? -------------------------------------------------------------------------------
class SettingsPage(ScrollPage):
    title     = 'Settings'
    subtitle  = 'Appearance, LTspice, output folder and behaviour'
    icon_name = 'settings'

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(ctx, parent)
        look             = Card('Appearance', '', 'sun')
        self.theme_combo = combo(['system', 'light', 'dark'], settings.get('ui/theme', 'system'))
        self.theme_combo.currentTextChanged.connect(self._theme)
        look.add(field('Theme', self.theme_combo, 'Ctrl+T toggles light / dark'))
        self.grid.add(look)

        lt           = Card('LTspice', 'Leave empty to detect it automatically.', 'cpu')
        self.ltspice = PathField('Auto-detect', 'LTspice (*.exe);;All files (*)', caption='LTspice executable')
        self.ltspice.setText(settings.get('run/ltspice', ''))
        self.ltspice.changed.connect(lambda t: (settings.put('run/ltspice', t), self._detect()))
        self.detected = label('', 'Hint', wrap=True)
        lt.add(field('Executable', self.ltspice))
        lt.add(self.detected)
        self.grid.add(lt)

        out = Card('Data folder', 'Results, examples and config.json. Never inside the application folder.',
                   'folder')
        self.data_label = label('', wrap=True)
        self.data_label.setTextInteractionFlags(self.data_label.textInteractionFlags()
                                                | Qt.TextInteractionFlag.TextSelectableByMouse)
        out.add(self.data_label)
        out.add(row(button('Change…', 'folder', 'primary', slot=self._change_data),
                    button('Open', 'open', slot=lambda: open_path(ensure_data_dir())),
                    button('Edit config.json', 'file', slot=self._edit_config), None,
                    stretch=[0, 0, 0, 1]))
        self.open_report  = QCheckBox('Open the HTML report when an analysis finishes')
        self.show_results = QCheckBox('Show the Results page when an analysis finishes')
        self.open_report.setChecked(settings.get('run/open_report', False))
        self.show_results.setChecked(settings.get('run/show_results', True))
        self.open_report.toggled.connect(lambda v: settings.put('run/open_report', v))
        self.show_results.toggled.connect(lambda v: settings.put('run/show_results', v))
        out.add(self.open_report)
        out.add(self.show_results)
        self.grid.add(out)

        perf          = Card('Performance', 'Simulations run in parallel LTspice processes.', 'zap')
        self.parallel = QSpinBox()
        self.parallel.setRange(1, 64)
        self.parallel.setValue(settings.get('run/parallel', max(2, (os.cpu_count() or 4) // 2)))
        self.parallel.valueChanged.connect(lambda v: settings.put('run/parallel', v))
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 86400)
        self.timeout.setSuffix(' s')
        self.timeout.setValue(settings.get('run/timeout', 600))
        self.timeout.valueChanged.connect(lambda v: settings.put('run/timeout', v))
        perf.add(row(field('Parallel simulations', self.parallel), field('Timeout per simulation', self.timeout)))
        self.grid.add(perf)

        about    = Card('About', '', 'info')
        versions = []
        for pkg in ('PyLTSpice', 'spicelib', 'PySide6-Essentials', 'pyqtgraph', 'pandas', 'plotly'):
            try:
                versions.append(f'{pkg} {metadata.version(pkg)}')
            except metadata.PackageNotFoundError:
                pass
        about.add(label('FASTER - Failure Analysis, Simulation, Testing and Evaluation Report.\n'
                        'FMEDA, ISO 26262 hardware metrics, FTA, worst-case and Monte Carlo analysis of '
                        'LTspice circuits.', wrap=True))
        about.add(label(f'Python {platform.python_version()}  ·  ' + '  ·  '.join(versions), 'Hint', wrap=True))
        about.add(label(f'Installed in {APP_DIR}', 'Hint', wrap=True))
        self.grid.add(about)
        self._detect()
        self._show_data()

    def _theme(self, mode: str) -> None:
        settings.put('ui/theme', mode)
        theme().set_mode(mode)

    def sync_theme_combo(self) -> None:
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(theme().palette.name)
        self.theme_combo.blockSignals(False)
        settings.put('ui/theme', theme().palette.name)

    def _detect(self) -> None:
        exe = find_ltspice(self.ltspice.text() or None)
        self.detected.setText(f'Using: {exe}' if exe else 'LTspice not found - simulations will be unavailable.')

    def _show_data(self) -> None:
        self.data_label.setText(f'<b>{data_dir()}</b><br>Runs are saved in {results_dir()}')

    def _change_data(self) -> None:
        if self.ctx.worker.busy:
            self.ctx.toast('Wait for the running analysis to finish.', 'warning')
            return
        from ..welcome import choose_data_folder
        chosen = choose_data_folder(self.window(), first_start=False)
        if chosen:
            self._show_data()
            self.ctx.history_page.refresh()
            self.ctx.toast(f'Data folder: {chosen}', 'success', 3500)

    def _edit_config(self) -> None:
        ensure_data_dir()
        cfg = user_config()
        if not cfg.exists():
            cfg.write_text('{}' + chr(10), encoding='utf-8')
        open_path(cfg)

#? -------------------------------------------------------------------------------
