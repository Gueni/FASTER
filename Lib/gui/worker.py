#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                       _       __           __
#?                      | |     / /___  _____/ /_____  _____
#?                      | | /| / / __ \/ ___/ //_/ _ \/ ___/
#?                      | |/ |/ / /_/ / /  / ,< /  __/ /
#?                      |__/|__/\____/_/  /_/|_|\___/_/
#?
#? Name:        worker.py
#? Purpose:     Run the analysis pipeline in a separate process and stream its output to the GUI.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Analysis worker.

The pipeline runs in ``python main.py <asc> --gui-worker`` (installed build:
``FASTER.exe <asc> --gui-worker``) so the interface
never freezes and *Stop* can kill the whole process tree (including every
LTspice instance). The worker prints normal log lines plus markers::

    @@PROGRESS <percent> <step>
    @@RESULT <run folder>
    @@ERROR <message>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from ..core.paths import FROZEN, PROJECT_ROOT_SRC, data_dir


#? -------------------------------------------------------------------------------
@dataclass
class AnalysisRequest:
    schematic   : Path
    config      : dict
    name        : str | None = None
    output_root : str | None = None
    simulate    : bool = True
    run_wca     : bool = True
    run_mc      : bool = True
    keep_sims   : bool = False
    extra_args  : list[str] = field(default_factory=list)


#? -------------------------------------------------------------------------------
def classify(text: str) -> str:
    t = text.upper()
    if ' ERROR ' in t or t.startswith('TRACEBACK') or 'EXCEPTION' in t or ' CRITICAL ' in t:
        return 'error'
    if ' WARNING ' in t:
        return 'warning'
    if 'DONE IN' in t:
        return 'success'
    return 'info'


#? -------------------------------------------------------------------------------
class AnalysisWorker(QObject):
    line         = Signal(str, str)          # text, kind
    progress     = Signal(float, str)        # percent (-1 = indeterminate), step
    started      = Signal(str)               # title
    finished     = Signal(int, str, float)   # exit code (-2 = stopped), run folder, seconds
    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._buffer  = ''
        self._run_dir = ''
        self._t0      = 0.0
        self._stopped = False
        self._config_file: Path | None = None
        self._cleanup: list[Path] = []

    @property
    def busy(self) -> bool:
        return self._proc is not None

    def start(self, req: AnalysisRequest, cleanup: list[Path] | None = None) -> bool:
        if self.busy:
            return False
        fd, cfg_path = tempfile.mkstemp(prefix='faster_cfg_', suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(req.config, fh, indent=2, default=str)
        self._config_file = Path(cfg_path)
        self._cleanup     = list(cleanup or [])

        root = data_dir()
        args = [] if FROZEN else [str(PROJECT_ROOT_SRC / 'main.py')]
        args += [str(req.schematic), '--gui-worker', '-c', cfg_path, '--data-dir', str(root)]
        if req.name:
            args += ['--name', req.name]
        if req.output_root:
            args += ['-o', req.output_root]
        if not req.simulate:
            args.append('--no-sim')
        if not req.run_wca:
            args.append('--no-wca')
        if not req.run_mc:
            args.append('--no-mc')
        if req.keep_sims:
            args.append('--keep-sims')
        args += req.extra_args

        proc = QProcess(self)
        env  = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUNBUFFERED', '1')
        env.insert('PYTHONIOENCODING', 'utf-8')
        proc.setProcessEnvironment(env)
        root.mkdir(parents=True, exist_ok=True)
        proc.setWorkingDirectory(str(root))         # never the (read-only) install folder
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setProgram(sys.executable)
        proc.setArguments(args)
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self._proc, self._buffer, self._run_dir = proc, '', ''
        self._stopped, self._t0 = False, time.monotonic()

        self.busy_changed.emit(True)
        self.progress.emit(0.0, 'Starting')
        self.started.emit(f'Analysis of {req.name or Path(req.schematic).stem}')
        proc.start()
        return True

    def stop(self) -> None:
        """Kill the worker and every child process (LTspice) it started."""
        if self._proc is None:
            return
        self._stopped = True
        pid           = int(self._proc.processId() or 0)
        if sys.platform == 'win32' and pid:
            subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            self._proc.kill()

    #? process I/O                                                                      
    def _on_output(self) -> None:
        if self._proc is None:
            return
        self._buffer += bytes(self._proc.readAllStandardOutput().data()).decode('utf-8', errors='replace')
        *lines, self._buffer = self._buffer.replace('\r\n', '\n').split('\n')
        for text in lines:
            self._handle(text)

    def _handle(self, text: str) -> None:
        if text.startswith('@@PROGRESS '):
            _, pct, *step = text.split(' ', 2)
            try:
                self.progress.emit(float(pct), step[0] if step else '')
            except ValueError:
                pass
        elif text.startswith('@@RESULT '):
            self._run_dir = text[9:].strip()
        elif text.startswith('@@ERROR '):
            self.line.emit(f'Error: {text[8:]}', 'error')
        elif text.strip():
            self.line.emit(text, classify(text))

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.line.emit(f'Could not start the analysis process ({self._proc.errorString()})', 'error')
            self._finish(-1)

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._on_output()
        if self._buffer:
            self._handle(self._buffer)
            self._buffer = ''
        if self._stopped:
            code = -2
        elif status == QProcess.ExitStatus.CrashExit:
            code = -1
        self._finish(code)

    def _finish(self, code: int) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        proc.deleteLater()
        for path in [self._config_file, *self._cleanup]:
            try:
                if path is not None and path.exists():
                    path.unlink()
            except OSError:
                pass
        self.busy_changed.emit(False)
        self.finished.emit(code, self._run_dir, time.monotonic() - self._t0)

#? -------------------------------------------------------------------------------
