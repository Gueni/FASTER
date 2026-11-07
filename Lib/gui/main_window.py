#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?            __  ___      _          _       ___           __
#?           /  |/  /___ _(_)___     | |     / (_)___  ____/ /___ _      __
#?          / /|_/ / __ `/ / __ \    | | /| / / / __ \/ __  / __ \ | /| / /
#?         / /  / / /_/ / / / / /    | |/ |/ / / / / / /_/ / /_/ / |/ |/ /
#?        /_/  /_/\__,_/_/_/ /_/     |__/|__/_/_/ /_/\__,_/\____/|__/|__/
#?
#? Name:        main_window.py
#? Purpose:     Main window: title bar, sidebar navigation, pages, console, analysis orchestration.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""FASTER main window (layout and behaviour shared with Flash)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QProgressBar, QSizePolicy, QSplitter, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from .. import __version__
from ..core.config import find_ltspice
from ..core.paths import data_dir, examples_dir, results_dir
from . import settings
from .icons import app_icon
from .pages.analysis_page import AnalysisPage
from .pages.circuit_page import CircuitPage
from .pages.history_page import HistoryPage
from .pages.library_page import LibraryPage
from .pages.results_page import ResultsPage, open_path
from .pages.settings_page import SettingsPage
from .pages.waveforms_page import WaveformsPage
from .session import CircuitSession
from .theme import theme
from .titlebar import TitleBar, WindowChrome
from .widgets import Console, StatusPill, Toast, button, icon_button, repolish, set_icon
from .worker import AnalysisRequest, AnalysisWorker

SIDEBAR_EXPANDED    = 212
SIDEBAR_COLLAPSED   = 68
AUTO_COLLAPSE_WIDTH = 1100


#? -------------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f'FASTER {__version__}')
        self.setWindowIcon(app_icon())
        self.setMinimumSize(760, 560)
        WindowChrome.make_frameless(self)
        self.session  = CircuitSession(self)
        self.worker   = AnalysisWorker(self)
        self._resizer = None
        self._sidebar_pinned: bool | None = None

        root = QWidget()
        root.setObjectName('Root')
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.titlebar = TitleBar(self, app_icon(), 'FASTER', f'Reliability analysis for LTspice  ·  v{__version__}')
        outer.addWidget(self.titlebar)
        body = QWidget()
        h    = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        outer.addWidget(body, 1)
        self.setCentralWidget(root)
        self._root = root

        self.circuit_page   = CircuitPage(self)
        self.analysis_page  = AnalysisPage(self)
        self.results_page   = ResultsPage(self)
        self.waveforms_page = WaveformsPage(self)
        self.library_page   = LibraryPage(self)
        self.history_page   = HistoryPage(self)
        self.settings_page  = SettingsPage(self)
        self.pages = [self.circuit_page, self.analysis_page, self.results_page, self.waveforms_page,
                      self.library_page, self.history_page, self.settings_page]

        h.addWidget(self._build_sidebar())
        content = QWidget()
        v       = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_topbar())
        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self._build_console())
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        v.addWidget(self.splitter, 1)
        h.addWidget(content, 1)

        self._build_statusbar()
        self.toast_widget = Toast(self)
        self._wire()
        self._shortcuts()
        self._restore_geometry()
        self.history_page.refresh()
        self.select_page(settings.get('ui/page', 0))
        theme().changed.connect(lambda *_: self._apply_theme_icons())
        self._apply_theme_icons()
        self._sync_circuit()
        exe = find_ltspice(settings.get('run/ltspice', '') or None)
        self.log(f'FASTER {__version__} ready. LTspice: {exe or "not found"}', 'muted')

    #? construction                                                                         
    def _build_sidebar(self) -> QWidget:
        self.sidebar = QFrame()
        self.sidebar.setObjectName('Sidebar')
        self.sidebar.setFixedWidth(SIDEBAR_EXPANDED)
        lay = QVBoxLayout(self.sidebar)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(2)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QToolButton] = []
        for i, page in enumerate(self.pages):
            b = QToolButton()
            b.setObjectName('NavButton')
            b.setText(page.title)
            b.setToolTip(f'{page.title}  (Ctrl+{i + 1})')
            b.setCheckable(True)
            b.setIconSize(QSize(20, 20))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.select_page(idx))
            set_icon(b, page.icon_name, 'muted')
            self.nav_group.addButton(b, i)
            self.nav_buttons.append(b)
            lay.addWidget(b)
        lay.addStretch(1)
        self.sidebar_footer = QLabel(f'v{__version__}')
        self.sidebar_footer.setObjectName('SidebarFooter')
        self.sidebar_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.sidebar_footer)
        return self.sidebar

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName('TopBar')
        top = QHBoxLayout(bar)
        top.setContentsMargins(16, 12, 16, 12)
        top.setSpacing(10)
        top.addWidget(icon_button('menu', 'Collapse / expand sidebar (Ctrl+B)', self.toggle_sidebar))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.page_title = QLabel()
        self.page_title.setObjectName('PageTitle')
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName('PageSubtitle')
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        top.addLayout(titles, 1)
        self.circuit_chip = QLabel('No circuit')
        self.circuit_chip.setObjectName('Chip')
        top.addWidget(self.circuit_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self.state_pill = StatusPill('Idle', 'idle')
        top.addWidget(self.state_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self.run_btn = button('Run', 'play', 'primary', tip='Run the analysis (Ctrl+R)', slot=self.run_analysis)
        top.addWidget(self.run_btn)
        self.theme_btn = icon_button('moon', 'Toggle light / dark theme (Ctrl+T)', self._toggle_theme)
        top.addWidget(self.theme_btn)
        self.console_btn = icon_button('panel', 'Show / hide console (Ctrl+J)', self.toggle_console, checkable=True)
        self.console_btn.setChecked(True)
        top.addWidget(self.console_btn)
        return bar

    def _build_console(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('ConsolePanel')
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 10, 16, 12)
        v.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel('Console')
        title.setObjectName('ConsoleTitle')
        head.addWidget(title)
        self.job_label = QLabel('')
        self.job_label.setObjectName('Hint')
        head.addWidget(self.job_label, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFixedHeight(8)
        self.progress.setMinimumWidth(120)
        self.progress.setMaximumWidth(280)
        head.addWidget(self.progress, 1)
        self.pct_label = QLabel('')
        self.pct_label.setObjectName('Hint')
        self.pct_label.setMinimumWidth(44)
        head.addWidget(self.pct_label)
        self.stop_btn = icon_button('stop', 'Stop the analysis (Esc)', self.worker.stop, role='danger')
        self.stop_btn.setEnabled(False)
        head.addWidget(self.stop_btn)
        self.autoscroll_btn = icon_button('chevron-down', 'Auto-scroll', checkable=True)
        self.autoscroll_btn.setChecked(True)
        self.autoscroll_btn.toggled.connect(lambda on: setattr(self.console, 'autoscroll', on))
        head.addWidget(self.autoscroll_btn)
        head.addWidget(icon_button('copy', 'Copy log', self._copy_log))
        head.addWidget(icon_button('trash', 'Clear log (Ctrl+L)', lambda: self.console.clear()))
        v.addLayout(head)
        self.console = Console()
        self.console.setMinimumHeight(80)
        v.addWidget(self.console, 1)
        self.console_panel = panel
        return panel

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(True)
        self.status_right = QLabel('')
        sb.addPermanentWidget(self.status_right)
        sb.showMessage('Ready')

    def _wire(self) -> None:
        w = self.worker
        w.started.connect(self._job_started)
        w.line.connect(self.console.append_line)
        w.progress.connect(self._job_progress)
        w.finished.connect(self._job_finished)
        w.busy_changed.connect(self._busy_changed)
        self.session.loaded.connect(lambda *_: self._sync_circuit())
        self.session.closed.connect(self._sync_circuit)
        self.session.modified_changed.connect(lambda *_: self._sync_circuit())
        ap = self.analysis_page
        ap.temperature.valueChanged.connect(lambda *_: self.library_page.refresh_profile())
        ap.environment.currentIndexChanged.connect(lambda *_: self.library_page.refresh_profile())

    def _shortcuts(self) -> None:
        for i in range(len(self.pages)):
            QShortcut(QKeySequence(f'Ctrl+{i + 1}'), self, lambda idx=i: self.select_page(idx))
        QShortcut(QKeySequence('Ctrl+O'), self, self.open_dialog)
        QShortcut(QKeySequence('Ctrl+S'), self, self.save)
        QShortcut(QKeySequence('Ctrl+R'), self, self.run_analysis)
        QShortcut(QKeySequence('Ctrl+Return'), self, self.run_analysis)
        QShortcut(QKeySequence('Escape'), self, self.worker.stop)
        QShortcut(QKeySequence('Ctrl+L'), self, lambda: self.console.clear())
        QShortcut(QKeySequence('Ctrl+J'), self, lambda: self.console_btn.click())
        QShortcut(QKeySequence('Ctrl+T'), self, self._toggle_theme)
        QShortcut(QKeySequence('Ctrl+B'), self, self.toggle_sidebar)

    #? context API used by the pages                                                          
    def toast(self, text: str, kind: str = 'info', ms: int = 3500) -> None:
        self.toast_widget.show_message(text, kind, ms)

    def log(self, text: str, kind: str = 'info') -> None:
        for line in text.splitlines() or ['']:
            self.console.append_line(line, kind)

    def confirm(self, title: str, text: str, danger: bool = False, ok_text: str = 'Continue') -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(f'<b>{title}</b>')
        box.setInformativeText(text)
        box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
        ok = box.addButton(ok_text, QMessageBox.ButtonRole.AcceptRole)
        ok.setProperty('kind', 'danger' if danger else 'primary')
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return box.clickedButton() is ok

    def output_root(self) -> Path:
        """Run folders live in ``<data folder>/results``."""
        return results_dir()

    def run_settings(self) -> dict:
        return {'parallel_sims': settings.get('run/parallel', max(2, (os.cpu_count() or 4) // 2)),
                'sim_timeout': settings.get('run/timeout', 600),
                'ltspice_path': settings.get('run/ltspice', '') or None}

    def fit_overrides(self) -> dict[str, float]:
        return self.library_page.fit_overrides()

    def show_page(self, title: str) -> None:
        for i, p in enumerate(self.pages):
            if p.title == title:
                self.select_page(i)
                return

    def show_results(self, run_dir: str | Path) -> None:
        if self.results_page.load(run_dir):
            self.waveforms_page.load_run(self.results_page.nominal_raw(), self.results_page.mc_waveforms())
            self.show_page('Results')
        else:
            self.toast(f'Cannot open {run_dir}', 'error')

    #? files                                                                                    
    def _discard_ok(self) -> bool:
        if not self.session.modified:
            return True
        return self.confirm('Unsaved changes', f'{self.session.name} has unsaved edits. Discard them?',
                            danger=True, ok_text='Discard')

    def open_dialog(self) -> None:
        start = str(self.session.path.parent) if self.session.path else str(examples_dir())
        path, _ = QFileDialog.getOpenFileName(self, 'Open LTspice schematic', start,
                                              'LTspice schematic (*.asc);;All files (*)')
        if path:
            self.open_path(path)

    def open_path(self, path: str | Path) -> None:
        path = Path(path)
        if not path.is_file():
            self.toast(f'File not found: {path}', 'error')
            return
        if not self._discard_ok():
            return
        if self.session.is_open:
            self.analysis_page.save_state()
        try:
            self.session.open(path)
        except Exception as exc:
            self.toast(f'Cannot open {path.name}: {exc}', 'error', 6000)
            return
        settings.add_recent(path)
        settings.put('files/last', str(path))
        n = len(self.session.components())
        self.log(f'Opened {path}  ({n} components)', 'muted')
        self.toast(f'{path.name} loaded · {n} components', 'success', 2200)
        self.show_page('Circuit')

    def save(self) -> None:
        if self.session.is_open and self.session.modified:
            target = self.session.save()
            self.toast(f'Saved {target.name}', 'success', 2000)
            self.log(f'Saved {target}', 'muted')

    def save_as(self) -> None:
        if not self.session.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save schematic as', str(self.session.path),
                                              'LTspice schematic (*.asc)')
        if path:
            target = self.session.save(path)
            settings.add_recent(target)
            self.toast(f'Saved {Path(target).name}', 'success', 2000)

    def revert(self) -> None:
        if self.session.modified and self.confirm('Revert', 'Discard all unsaved edits?', danger=True,
                                                  ok_text='Revert'):
            self.session.revert()

    def open_in_ltspice(self) -> None:
        if not self.session.is_open:
            return
        exe = find_ltspice(settings.get('run/ltspice', '') or None)
        if exe is None:
            self.toast('LTspice not found - set it in Settings.', 'warning')
            return
        if self.session.modified:
            self.toast('LTspice shows the saved file; save first to see your edits there.', 'info', 4000)
        subprocess.Popen([str(exe), str(self.session.path)], close_fds=True)

    def _sync_circuit(self) -> None:
        s = self.session
        if s.is_open:
            self.circuit_chip.setText(f"{s.name}{'  ●  modified' if s.modified else ''}")
            self.circuit_chip.setToolTip(str(s.path))
            self.status_right.setText(f'{s.path}  ')
        else:
            self.circuit_chip.setText('No circuit')
            self.status_right.setText('')
        self.circuit_chip.setProperty('modified', bool(s.modified))
        repolish(self.circuit_chip)
        self.run_btn.setEnabled(s.is_open and not self.worker.busy)

    #? analysis                                                                                   
    def run_analysis(self) -> None:
        if self.worker.busy:
            self.toast('An analysis is already running.', 'warning')
            return
        if not self.session.is_open:
            self.toast('Open a schematic first.', 'info')
            self.show_page('Circuit')
            return
        problem = self.analysis_page.validate()
        if problem:
            self.toast(problem, 'warning', 6000)
            self.show_page('Analysis')
            return
        ap = self.analysis_page
        ap.save_state()
        schematic, name, cleanup = self.session.analysis_input()
        req = AnalysisRequest(schematic=schematic, config=ap.build_config(), name=name,
                              output_root=str(self.output_root()), simulate=ap.chk_sim.isChecked(),
                              run_wca=ap.chk_wca.isChecked(), run_mc=ap.chk_mc.isChecked(),
                              keep_sims=ap.chk_keep.isChecked())
        if self.session.modified:
            self.log('Analysing the edited (unsaved) circuit.', 'muted')
        self.worker.start(req, cleanup)

    def _job_started(self, title: str) -> None:
        self.console.append_line('')
        self.console.append_line(f'▶ {title}', 'command')
        self.job_label.setText(title)
        self.statusBar().showMessage(f'{title}…')
        if not self.console_btn.isChecked():
            self.console_btn.click()

    def _job_progress(self, pct: float, step: str) -> None:
        if pct < 0:
            self.progress.setRange(0, 0)
            self.pct_label.setText('')
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(pct * 10))
            self.pct_label.setText(f'{pct:.0f}%')
        if step:
            self.job_label.setText(step)
            self.state_pill.set_state(step if len(step) < 28 else 'Working…', 'busy')

    def _job_finished(self, code: int, run_dir: str, seconds: float) -> None:
        took = f'{seconds:.1f} s'
        if code in (0, 2) and run_dir:
            self.show_results(run_dir) if settings.get('run/show_results', True) else self.results_page.load(run_dir)
            if not settings.get('run/show_results', True):
                self.waveforms_page.load_run(self.results_page.nominal_raw(), self.results_page.mc_waveforms())
            self.history_page.refresh()
            verdict = (self.results_page.summary.get('iso26262') or {}).get('passed')
            if code == 0:
                self.console.append_line(f'✓ Analysis finished in {took}  ->  {run_dir}', 'success')
                self.toast(f'Analysis completed in {took}', 'success')
            else:
                self.console.append_line(f'⚠ Analysis finished with errors in {took} - see the log', 'warning')
                self.toast('Analysis finished with errors - see the console', 'warning', 5000)
            self.state_pill.set_state('PASS' if verdict else 'FAIL' if verdict is not None else 'Done',
                                      'pass' if verdict else 'fail' if verdict is not None else 'ok')
            if settings.get('run/open_report', False):
                report = self.results_page._output('report')
                if report:
                    open_path(report)
            self.statusBar().showMessage(f'Analysis completed in {took}', 8000)
        elif code == -2:
            self.console.append_line('■ Analysis stopped', 'warning')
            self.toast('Analysis stopped', 'warning')
            self.state_pill.set_state('Stopped', 'idle')
            self.statusBar().showMessage('Analysis stopped', 8000)
        else:
            self.console.append_line(f'✗ Analysis failed (exit code {code})', 'error')
            self.toast('Analysis failed - see the console', 'error', 6000)
            self.state_pill.set_state('Failed', 'error')
            self.statusBar().showMessage('Analysis failed', 8000)
        self.job_label.setText(f'{self.job_label.text()}  ·  {took}')

    def _busy_changed(self, busy: bool) -> None:
        self.stop_btn.setEnabled(busy)
        for p in self.pages:
            p.set_busy(busy)
        self.run_btn.setEnabled(not busy and self.session.is_open)
        if busy:
            self.state_pill.set_state('Working…', 'busy')
            self.progress.setValue(0)

    #? layout                                                                                     
    def select_page(self, index: int) -> None:
        index = max(0, min(int(index), len(self.pages) - 1))
        self.stack.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        page = self.pages[index]
        self.page_title.setText(page.title)
        self.page_subtitle.setText(page.subtitle)
        settings.put('ui/page', index)
        if page is self.history_page:
            page.refresh()

    def toggle_sidebar(self) -> None:
        expand               = self.sidebar.width() < SIDEBAR_EXPANDED
        self._sidebar_pinned = expand
        self._set_sidebar(expand, animate=True)

    def _set_sidebar(self, expanded: bool, animate: bool = False) -> None:
        target = SIDEBAR_EXPANDED if expanded else SIDEBAR_COLLAPSED
        style  = Qt.ToolButtonStyle.ToolButtonTextBesideIcon if expanded else Qt.ToolButtonStyle.ToolButtonIconOnly
        for b in self.nav_buttons:
            b.setToolButtonStyle(style)
        self.sidebar_footer.setVisible(expanded)
        if self.sidebar.width() == target:
            return
        if not animate:
            self.sidebar.setFixedWidth(target)
            return
        group = QParallelAnimationGroup(self)
        for prop in (b'minimumWidth', b'maximumWidth'):
            a = QPropertyAnimation(self.sidebar, prop, group)
            a.setDuration(180)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.setStartValue(self.sidebar.width())
            a.setEndValue(target)
            group.addAnimation(a)
        group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    def toggle_console(self) -> None:
        self.console_panel.setVisible(self.console_btn.isChecked())

    def showEvent(self, event) -> None:      # noqa: N802
        super().showEvent(event)
        if self._resizer is None:
            self._resizer = WindowChrome.polish(self)
            self._sync_frame()

    def changeEvent(self, event) -> None:      # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_frame()

    def _sync_frame(self) -> None:
        framed = sys.platform != 'win32' and not (self.isMaximized() or self.isFullScreen())
        if self._root.property('framed') != framed:
            self._root.setProperty('framed', framed)
            self._root.style().unpolish(self._root)
            self._root.style().polish(self._root)

    def resizeEvent(self, event) -> None:      # noqa: N802
        super().resizeEvent(event)
        if self._sidebar_pinned is None:
            self._set_sidebar(self.width() >= AUTO_COLLAPSE_WIDTH)
        if self.toast_widget.isVisible():
            self.toast_widget.place()

    def _toggle_theme(self) -> None:
        theme().toggle()
        self.settings_page.sync_theme_combo()

    def _apply_theme_icons(self) -> None:
        set_icon(self.theme_btn, 'sun' if theme().palette.name == 'dark' else 'moon')

    def _copy_log(self) -> None:
        QApplication.clipboard().setText(self.console.toPlainText())
        self.toast('Log copied to clipboard', 'info', 1800)

    #? persistence                                                                                
    def _restore_geometry(self) -> None:
        geo = settings.app_settings().value('ui/geometry')
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.resize(int(screen.width() * 0.82), int(screen.height() * 0.86))
            self.move(screen.center() - self.rect().center())
        sizes = settings.app_settings().value('ui/splitter')
        if sizes:
            try:
                self.splitter.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):
                pass

    def closeEvent(self, event) -> None:      # noqa: N802
        if self.worker.busy:
            if not self.confirm('Analysis running', 'An analysis is still running. Stop it and quit?',
                                danger=True, ok_text='Stop and quit'):
                event.ignore()
                return
            self.worker.stop()
        if not self._discard_ok():
            event.ignore()
            return
        self.analysis_page.save_state()
        s = settings.app_settings()
        s.setValue('ui/geometry', self.saveGeometry())
        s.setValue('ui/splitter', self.splitter.sizes())
        s.sync()
        super().closeEvent(event)

#? -------------------------------------------------------------------------------
