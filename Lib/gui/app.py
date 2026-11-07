#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                                  ___
#?                                 /   |  ____  ____
#?                                / /| | / __ \/ __ \
#?                               / ___ |/ /_/ / /_/ /
#?                              /_/  |_/ .___/ .___/
#?                                    /_/   /_/
#?
#? Name:        app.py
#? Purpose:     Start the FASTER desktop application.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Application bootstrap: high-DPI, theme, main window."""

from __future__ import annotations

import os
import sys
from pathlib import Path


#? -------------------------------------------------------------------------------
def _enable_high_dpi() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if sys.platform == 'win32':          # own taskbar icon / group instead of python.exe's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Gueni.FASTER')
        except Exception:
            pass


#? -------------------------------------------------------------------------------
def create_app(argv: list[str] | None = None):
    from PySide6.QtWidgets import QApplication

    from . import settings
    from .icons import app_icon
    from .theme import theme

    _enable_high_dpi()
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(settings.APP_NAME)
    app.setApplicationDisplayName(settings.APP_NAME)
    app.setOrganizationName(settings.ORG_NAME)
    app.setWindowIcon(app_icon())
    theme().set_mode((settings.get('ui/theme', 'system') or 'system').lower())
    return app


#? -------------------------------------------------------------------------------
def run_gui(schematic: str | None = None) -> int:
    from PySide6.QtCore import QTimer

    from . import settings
    from .main_window import MainWindow

    from ..core import paths

    app   = create_app()
    first = not paths.data_dir_configured()
    if first and not os.environ.get('FASTER_SMOKE_TEST'):
        from .welcome import choose_data_folder
        if choose_data_folder(first_start=True) is None:       # closed: keep the default
            paths.set_data_dir(paths.DEFAULT_DATA_DIR)
    try:
        paths.ensure_data_dir()
    except OSError as exc:
        print(f'Data folder {paths.data_dir()} is not usable: {exc}', file=sys.stderr)
    window = MainWindow()
    window.show()
    target = schematic or settings.get('files/last', '')
    if not target and first:
        example = paths.examples_dir() / 'Test.asc'
        target  = str(example) if example.is_file() else ''
    if target and Path(target).is_file():
        QTimer.singleShot(0, lambda: window.open_path(target))
    if os.environ.get('FASTER_SMOKE_TEST'):          # build checks: start, render, quit
        QTimer.singleShot(int(os.environ.get('FASTER_SMOKE_TEST_MS', '2500')), app.quit)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(run_gui(sys.argv[1] if len(sys.argv) > 1 else None))

#? -------------------------------------------------------------------------------
