#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                    _       __     __
#?                   | |     / /__  / /________  ____ ___  ___
#?                   | | /| / / _ \/ / ___/ __ \/ __ `__ \/ _ \
#?                   | |/ |/ /  __/ / /__/ /_/ / / / / / /  __/
#?                   |__/|__/\___/_/\___/\____/_/ /_/ /_/\___/
#?
#? Name:        welcome.py
#? Purpose:     First start: let the user choose the data folder.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Data folder dialog.

Shown on the first start (unless the installer already stored a choice) and
from the Settings page. Nothing is ever written to the install folder.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from ..core.paths import APP_DIR, DEFAULT_DATA_DIR, data_dir, is_writable, set_data_dir
from .icons import app_icon
from .theme import _mono_family
from .widgets import PathField, button, label


#? -------------------------------------------------------------------------------
def folder_problem(path: str) -> str:
    """Reason why ``path`` cannot be the data folder, or ``''``."""
    if not path:
        return 'Choose a folder.'
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        return 'Invalid path.'
    try:
        if p == APP_DIR or APP_DIR in p.parents:
            return 'Choose a folder outside the application folder.'
    except ValueError:
        pass
    probe = p
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    if not probe.is_dir() or not is_writable(probe):
        return 'This folder is not writable.'
    return ''


#? -------------------------------------------------------------------------------
class DataFolderDialog(QDialog):
    def __init__(self, parent=None, first_start: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle('Welcome to FASTER' if first_start else 'Data folder')
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(600)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(48, 48))
        head.addWidget(logo)
        head.addSpacing(10)
        head.addWidget(label('Welcome to FASTER' if first_start else 'Data folder', 'PageTitle'), 1)
        lay.addLayout(head)
        lay.addWidget(label('Choose where FASTER keeps your work. It contains:', wrap=True))
        tree = label('results\\       one folder per analysis run\n'
                     'examples\\      example circuits to get started\n'
                     'config.json    default analysis settings')
        tree.setStyleSheet(f'font-family: "{_mono_family()}"; padding: 4px 0 6px 12px;')
        lay.addWidget(tree)
        self.path = PathField(str(DEFAULT_DATA_DIR), directory=True, caption='Data folder', must_exist=False)
        self.path.setText(str(data_dir()))
        self.path.changed.connect(self._check)
        lay.addWidget(self.path)
        self.hint = label('', 'Hint', wrap=True)
        lay.addWidget(self.hint)
        lay.addWidget(label('You can change it later in Settings. Existing results are not moved.', 'Hint',
                            wrap=True))

        buttons = QHBoxLayout()
        buttons.addWidget(button('Use default', 'refresh', slot=lambda: self.path.setText(str(DEFAULT_DATA_DIR))))
        buttons.addStretch(1)
        if not first_start:
            buttons.addWidget(button('Cancel', slot=self.reject))
        self.ok = button('Continue' if first_start else 'Apply', 'check', 'primary', slot=self._accept)
        buttons.addWidget(self.ok)
        lay.addSpacing(6)
        lay.addLayout(buttons)
        self._check()

    def _check(self) -> None:
        problem = folder_problem(self.path.text())
        self.hint.setText(problem or 'The folder is created if it does not exist.')
        self.ok.setEnabled(not problem)

    def _accept(self) -> None:
        if not folder_problem(self.path.text()):
            self.chosen = set_data_dir(self.path.text())
            self.accept()


#? -------------------------------------------------------------------------------
def choose_data_folder(parent=None, first_start: bool = False) -> Path | None:
    dlg = DataFolderDialog(parent, first_start)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.chosen
    return None

#? -------------------------------------------------------------------------------
