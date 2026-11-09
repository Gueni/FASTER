#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#? Name:        simulate.py
#? Purpose:     Run LTspice in the background on the edited schematic.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------

"""Background LTspice runs.

LTspice is used as the simulation engine only: ``LTspice -netlist file.asc``
writes the netlist (LTspice resolves symbols, models and hierarchy), then
``LTspice -b file.net`` simulates it and writes ``file.raw`` and ``file.log``.
The netlist also tells which SPICE node every pin landed on, which the
editor needs for probing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


#? -------------------------------------------------------------------------------
@dataclass
class SimResult:
    ok       : bool
    asc      : Path
    net      : Path | None = None
    raw      : Path | None = None
    log      : str = ''
    netlist  : str = ''
    error    : str = ''
    seconds  : float = 0.0
    elements : dict[str, list[str]] = field(default_factory=dict)    # element name (lower) -> tokens

    def nodes_of(self, names: list[str], n: int) -> list[str] | None:
        """Nodes of the first element whose name matches one of ``names`` (case-insensitive)."""
        for name in names:
            tokens = self.elements.get(name.lower())
            if tokens is not None:
                return tokens[1:1 + n]
        return None


#? -------------------------------------------------------------------------------
def read_text(path: Path) -> str:
    """LTspice writes logs/netlists as UTF-16 or 8 bit, depending on the version."""
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16', errors='replace')
    if len(raw) > 1 and raw[1:2] == b'\x00':
        return raw.decode('utf-16-le', errors='replace')
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1', errors='replace')


def parse_netlist(text: str) -> dict[str, list[str]]:
    elements: dict[str, list[str]] = {}
    lines: list[str] = []
    for ln in text.splitlines():
        if ln.startswith('+') and lines:
            lines[-1] += ' ' + ln[1:]
        else:
            lines.append(ln)
    depth = 0
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith('*'):
            continue
        low = s.lower()
        if low.startswith('.subckt'):
            depth += 1
            continue
        if low.startswith('.ends'):
            depth = max(0, depth - 1)
            continue
        if s.startswith('.') or depth:
            continue
        tokens = s.split()
        elements.setdefault(tokens[0].lower(), tokens)
    return elements


#? -------------------------------------------------------------------------------
class SimRunner(QObject):
    """Netlist + batch simulation with QProcess (keeps the UI responsive)."""
    started  = Signal(str)
    finished = Signal(object)        # SimResult
    output   = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.proc: QProcess | None = None
        self.exe: Path | None = None
        self.asc: Path | None = None
        self._stage = ''
        self._t0 = 0.0
        self._stopped = False

    @property
    def busy(self) -> bool:
        return self.proc is not None

    def start(self, exe: Path, asc: Path) -> bool:
        if self.busy:
            return False
        self.exe, self.asc = Path(exe), Path(asc)
        self._stopped = False
        self._t0 = time.monotonic()
        for ext in ('.raw', '.op.raw', '.log'):
            try:
                self.asc.with_suffix(ext).unlink(missing_ok=True)
            except OSError:
                pass
        self.started.emit(self.asc.name)
        self._run('netlist', ['-netlist', str(self.asc)])
        return True

    def stop(self) -> None:
        if self.proc is not None:
            self._stopped = True
            self.proc.kill()

    def _run(self, stage: str, args: list[str]) -> None:
        self._stage = stage
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(self.asc.parent))
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._done)
        self.proc.errorOccurred.connect(self._error)
        self.proc.start(str(self.exe), args)

    def _read(self) -> None:
        if self.proc is not None:
            data = bytes(self.proc.readAllStandardOutput()).decode('utf-8', errors='replace').strip()
            if data:
                self.output.emit(data)

    def _error(self, err) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self._finish(SimResult(False, self.asc, error=f'Cannot start LTspice ({self.exe}).'))

    def _done(self, code: int, _status) -> None:
        if self.proc is None:
            return
        net = self.asc.with_suffix('.net')
        if self._stopped:
            return self._finish(SimResult(False, self.asc, error='Simulation stopped.'))
        if self._stage == 'netlist':
            if not net.is_file():
                return self._finish(SimResult(False, self.asc, error='LTspice could not netlist the schematic.'))
            self.proc.deleteLater()
            self.proc = None
            self._run('sim', ['-b', str(net)])
            return
        netlist = read_text(net) if net.is_file() else ''
        logf    = self.asc.with_suffix('.log')
        log     = read_text(logf) if logf.is_file() else ''
        raw     = next((p for p in (self.asc.with_suffix('.raw'), self.asc.with_suffix('.op.raw')) if p.is_file()), None)
        res = SimResult(raw is not None, self.asc, net, raw, log, netlist, seconds=time.monotonic() - self._t0,
                        elements=parse_netlist(netlist))
        if raw is None:
            res.error = 'The simulation produced no results - see the SPICE error log.'
        self._finish(res)

    def _finish(self, res: SimResult) -> None:
        if self.proc is not None:
            self.proc.deleteLater()
        self.proc = None
        self.finished.emit(res)

#? -------------------------------------------------------------------------------
