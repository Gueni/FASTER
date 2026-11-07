#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                         ____              __
#?                        / __ \__  ______  / /   ____  ____ _
#?                       / /_/ / / / / __ \/ /   / __ \/ __ `/
#?                      / _, _/ /_/ / / / / /___/ /_/ / /_/ /
#?                     /_/ |_|\__,_/_/ /_/_____/\____/\__, /
#?                                                   /____/
#?
#? Name:        runlog.py
#? Purpose:     Per-run log file (log.log) with banner, rich tables and all messages.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Run log written to ``<run dir>/log.log``.

Everything goes through one file handle so messages and tables stay in order:

* the figlet banner and run information (versions, LTspice path, config),
* every ``logging`` record of the run (DEBUG and above, including PyLTSpice),
* every result as a rich table (components, FMEDA, FTA, traces, WCA, Monte Carlo ...).

Summary tables can also be echoed to the terminal with ``console=True``.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from ..core.banner import banner

LOG_NAME      = 'log.log'
LOG_WIDTH     = 220
LOG_FORMAT    = '%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-28s %(message)s'
PACKAGES      = ('PyLTSpice', 'spicelib', 'numpy', 'pandas', 'plotly', 'openpyxl', 'pillow', 'pyfiglet', 'rich')
QUIET_LOGGERS = ('PIL', 'matplotlib', 'urllib3', 'asyncio')


#? -------------------------------------------------------------------------------
def _fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    if isinstance(value, float):
        return f'{value:.6g}'
    return str(value)


#? -------------------------------------------------------------------------------
def dataframe_table(df: pd.DataFrame, title: str = '', max_rows: int | None = None) -> Table:
    """Convert a DataFrame into a rich Table (numbers right-aligned, 6 significant digits)."""
    table = Table(title=title or None, box=box.ROUNDED, header_style='bold', title_justify='left',
                  show_lines=False, expand=False)
    numeric = set(df.select_dtypes('number').columns)
    for col in df.columns:
        if col in numeric:
            table.add_column(str(col), justify='right', no_wrap=True, min_width=len(str(col)))
        else:
            table.add_column(str(col), justify='left', overflow='fold')
    rows = df if max_rows is None else df.head(max_rows)
    for row in rows.itertuples(index=False):
        table.add_row(*(_fmt(v) for v in row))
    if max_rows is not None and len(df) > max_rows:
        table.caption = f'{len(df) - max_rows} more rows not shown'
    return table


#? -------------------------------------------------------------------------------
def dict_table(data: dict, title: str = '', key: str = 'Item', value: str = 'Value') -> Table:
    table = Table(title=title or None, box=box.ROUNDED, header_style='bold', title_justify='left')
    table.add_column(key, style='bold')
    table.add_column(value, overflow='fold')
    for k, v in data.items():
        table.add_row(str(k), _fmt(v))
    return table


#? -------------------------------------------------------------------------------
class _TerminalFilter(logging.Filter):
    """Keep the terminal readable: third-party chatter goes to the log file only."""
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith(('PyLTSpice', 'spicelib')):
            return record.levelno >= logging.WARNING
        return True


#? -------------------------------------------------------------------------------
class _NoiseFilter(logging.Filter):
    """Drop spicelib messages repeated for every simulation job (symbol parsing, deprecation notes)."""
    NOISE = ('Parsing ASY file', 'Parsing ASC file', 'Searching for symbol', 'maintained for',
             'Plot read successfully')

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith('spicelib') and record.levelno < logging.WARNING:
            msg = record.getMessage()
            return not any(n in msg for n in self.NOISE)
        return True


#? -------------------------------------------------------------------------------
class RunLog:
    """Context manager owning ``<run_dir>/log.log``."""

    def __init__(self, run_dir: str | os.PathLike, terminal: bool = True):
        self.path     = Path(run_dir) / LOG_NAME
        self.terminal = terminal
        self._fh      = None
        self._handler: logging.Handler | None = None
        self._saved: dict[str, Any] = {}
        self._t0 = time.perf_counter()

    #? lifecycle                                                                    
    def __enter__(self) -> 'RunLog':
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, 'w', encoding='utf-8', newline='\n')
        self.file = Console(file=self._fh, width=LOG_WIDTH, force_terminal=False, color_system=None,
                            no_color=True, highlight=False, emoji=False, soft_wrap=False)
        self.term = Console(highlight=False) if self.terminal else None

        root          = logging.getLogger()
        self._handler = logging.StreamHandler(self._fh)
        self._handler.setLevel(logging.DEBUG)
        self._handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt='%H:%M:%S'))
        self._handler.addFilter(_NoiseFilter())
        # the terminal handler(s) keep their own level; the file sees DEBUG
        self._saved['root_level'] = root.level
        for h in root.handlers:
            if h.level == logging.NOTSET:
                h.setLevel(root.level or logging.INFO)
            h.addFilter(_TerminalFilter())
        root.setLevel(logging.DEBUG)
        root.addHandler(self._handler)
        for name in ('PyLTSpice', 'spicelib'):
            lg = logging.getLogger(name)
            self._saved[name] = lg.level
            lg.setLevel(logging.INFO)
        for name in QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            logging.getLogger(__name__).error('Run aborted', exc_info=(exc_type, exc, tb))
        self.rule(f'End of run - {time.perf_counter() - self._t0:.1f} s')
        root = logging.getLogger()
        root.removeHandler(self._handler)
        for h in root.handlers:
            for f in [f for f in h.filters if isinstance(f, _TerminalFilter)]:
                h.removeFilter(f)
        root.setLevel(self._saved.get('root_level', logging.WARNING))
        for name in ('PyLTSpice', 'spicelib'):
            logging.getLogger(name).setLevel(self._saved.get(name, logging.NOTSET))
        self._handler.close()
        self._fh.close()

    #? writing                                                                        
    def _out(self, renderable, console: bool) -> None:
        self.file.print(renderable)
        self._fh.flush()
        if console and self.term is not None:
            self.term.print(renderable)

    def rule(self, title: str, console: bool = False) -> None:
        self.file.print()
        self._out(Rule(f' {title} ', characters='═'), console)

    def text(self, message: str, console: bool = False) -> None:
        self._out(message, console)

    def table(self, df: pd.DataFrame, title: str = '', console: bool = False,
              console_rows: int | None = 30) -> None:
        if df is None or df.empty:
            self._out(f'{title}: (no data)', console)
            return
        self.file.print(dataframe_table(df, title))
        self._fh.flush()
        if console and self.term is not None:
            self.term.print(dataframe_table(df, title, max_rows=console_rows))

    def mapping(self, data: dict, title: str = '', console: bool = False,
                key: str = 'Item', value: str = 'Value') -> None:
        self._out(dict_table(data, title, key, value), console)

    def header(self, schematic: Path, run_dir: Path, config: dict, ltspice: Path | None) -> None:
        self.file.print(banner('FASTER'))
        info = {
            'Started'       : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Schematic'     : str(schematic),
            'Run folder'    : str(run_dir),
            'Command'       : ' '.join(sys.argv),
            'Python'        : f'{platform.python_version()} ({sys.executable})',
            'Platform'      : platform.platform(),
            'LTspice'       : str(ltspice) if ltspice else 'not found (PyLTSpice auto-detect)',
        }
        self.mapping(info, 'Run information')
        versions = {}
        for pkg in PACKAGES:
            try:
                versions[pkg] = metadata.version(pkg)
            except metadata.PackageNotFoundError:
                versions[pkg] = 'not installed'
        self.mapping(versions, 'Package versions', key='Package', value='Version')
        self._out(Panel(json.dumps(config, indent=2, default=str), title='Configuration',
                        title_align='left', box=box.ROUNDED, expand=False), False)

    def outputs(self, outputs: dict[str, Path], errors: dict[str, str]) -> None:
        self.rule('Outputs', console=False)
        rows = [{'Output': k, 'File': Path(v).name,
                 'Size (kB)': round(Path(v).stat().st_size / 1024, 1) if Path(v).is_file() else None}
                for k, v in outputs.items()]
        rows.append({'Output': 'log', 'File': self.path.name, 'Size (kB)': None})
        self.text(f'Run folder: {self.path.parent}')
        self.table(pd.DataFrame(rows), 'Generated files')
        if errors:
            self.table(pd.DataFrame([{'Step': k, 'Error': v} for k, v in errors.items()]), 'Errors')

#? -------------------------------------------------------------------------------
